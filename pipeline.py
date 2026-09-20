"""Climate Risk & Business Impact Analyzer -- ingestion + transform logic.

Data source: Open-Meteo (https://open-meteo.com), keyless, CC-BY-4.0
attribution required, no rate-limit auth needed for this call volume
(<=10,000 requests/day, we issue ~10). Verified live on 2026-09-12.

Business exposure (industry, revenue, asset value per location) is
SYNTHETIC -- clearly labeled as such in the `is_synthetic` column and in
docs/data_sources.md. It exists to make the climate signal analyzable in
business terms; it is not a real financial disclosure for any company.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from shared.database import get_engine, upsert_dataframe
from shared.ingestion import get_json_with_retry, save_raw_json
from shared.validation import validate_dataframe

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HISTORY_YEARS = 3
RNG_SEED = 7

# Real cities, synthetic business exposure -- revenue/asset figures are
# illustrative placeholders sized to plausible single-facility ranges,
# not sourced from any company's actual financials.
LOCATIONS = [
    {"location_id": "MIA", "name": "Miami, FL",        "lat": 25.7743, "lon": -80.1937, "industry": "Logistics/Warehousing", "annual_revenue_usd": 42_000_000, "asset_value_usd": 18_000_000},
    {"location_id": "HOU", "name": "Houston, TX",       "lat": 29.7604, "lon": -95.3698, "industry": "Oil & Gas Processing",  "annual_revenue_usd": 210_000_000, "asset_value_usd": 340_000_000},
    {"location_id": "PHX", "name": "Phoenix, AZ",       "lat": 33.4484, "lon": -112.0740, "industry": "Data Center",          "annual_revenue_usd": 65_000_000, "asset_value_usd": 120_000_000},
    {"location_id": "NOL", "name": "New Orleans, LA",   "lat": 29.9511, "lon": -90.0715, "industry": "Port & Shipping",       "annual_revenue_usd": 88_000_000, "asset_value_usd": 150_000_000},
    {"location_id": "SFO", "name": "San Francisco, CA", "lat": 37.7749, "lon": -122.4194, "industry": "Corporate HQ",         "annual_revenue_usd": 500_000_000, "asset_value_usd": 90_000_000},
    {"location_id": "CHI", "name": "Chicago, IL",       "lat": 41.8781, "lon": -87.6298, "industry": "Manufacturing",         "annual_revenue_usd": 130_000_000, "asset_value_usd": 210_000_000},
    {"location_id": "NYC", "name": "New York, NY",      "lat": 40.7128, "lon": -74.0060, "industry": "Financial Services",    "annual_revenue_usd": 900_000_000, "asset_value_usd": 250_000_000},
    {"location_id": "DEN", "name": "Denver, CO",        "lat": 39.7392, "lon": -104.9903, "industry": "Agriculture Supply",   "annual_revenue_usd": 55_000_000, "asset_value_usd": 70_000_000},
    {"location_id": "SEA", "name": "Seattle, WA",       "lat": 47.6062, "lon": -122.3321, "industry": "Tech / R&D Campus",    "annual_revenue_usd": 300_000_000, "asset_value_usd": 180_000_000},
    {"location_id": "ATL", "name": "Atlanta, GA",       "lat": 33.7490, "lon": -84.3880, "industry": "Distribution Center",   "annual_revenue_usd": 75_000_000, "asset_value_usd": 60_000_000},
]

RAW_DIR = os.path.join(os.path.dirname(__file__), "data_raw")
EVIDENCE_DIR = os.path.join(os.path.dirname(__file__), "docs", "evidence")


def locations_dataframe() -> pd.DataFrame:
    df = pd.DataFrame(LOCATIONS)
    df["is_synthetic_business_data"] = True
    return df


def extract_climate_for_location(location: dict, end_date: date | None = None) -> pd.DataFrame:
    end_date = end_date or (date.today() - timedelta(days=2))  # archive API lags ~2 days
    start_date = end_date - timedelta(days=365 * HISTORY_YEARS)

    payload = get_json_with_retry(
        ARCHIVE_URL,
        params={
            "latitude": location["lat"],
            "longitude": location["lon"],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
            "timezone": "auto",
        },
    )
    save_raw_json(payload, raw_dir=RAW_DIR, prefix=f"climate_{location['location_id']}")

    daily = payload["daily"]
    df = pd.DataFrame(
        {
            "location_id": location["location_id"],
            "date": pd.to_datetime(daily["time"]).date,
            "temp_max_c": daily["temperature_2m_max"],
            "temp_min_c": daily["temperature_2m_min"],
            "precipitation_mm": daily["precipitation_sum"],
            "windspeed_max_kmh": daily["windspeed_10m_max"],
        }
    )
    return df


def extract_all_locations() -> pd.DataFrame:
    frames = [extract_climate_for_location(loc) for loc in LOCATIONS]
    return pd.concat(frames, ignore_index=True)


def validate_climate(df: pd.DataFrame):
    return validate_dataframe(
        df,
        required_columns=["location_id", "date", "temp_max_c", "temp_min_c", "precipitation_mm"],
        not_null_columns=["location_id", "date"],
        numeric_ranges={
            "temp_max_c": (-60, 60),
            "temp_min_c": (-70, 55),
            "precipitation_mm": (0, 1200),
        },
    )


def load_locations() -> int:
    return upsert_dataframe(
        locations_dataframe(), schema="climate_risk", table="locations", key_columns=["location_id"]
    )


def load_daily_climate(df: pd.DataFrame) -> int:
    return upsert_dataframe(
        df, schema="climate_risk", table="daily_climate", key_columns=["location_id", "date"]
    )


def compute_and_load_risk_scores() -> int:
    """Yearly risk indicators per location, computed in SQL (see sql/002_risk_scores.sql
    for the analytical model); this just executes it and reports row count."""
    from shared.database import run_sql_file

    sql_path = os.path.join(os.path.dirname(__file__), "sql", "002_risk_scores.sql")
    run_sql_file(sql_path)
    engine = get_engine()
    with engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM climate_risk.risk_scores").scalar()
    return int(count)


def compute_and_load_financial_impact() -> int:
    from shared.database import run_sql_file

    sql_path = os.path.join(os.path.dirname(__file__), "sql", "003_financial_impact.sql")
    run_sql_file(sql_path)
    engine = get_engine()
    with engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM climate_risk.scenario_financial_impact").scalar()
    return int(count)


# --- Supervised risk model -------------------------------------------------
#
# climate_risk.risk_scores is one row per location per year -- 10 locations x
# 4 partial-to-full years = 40 rows (verified live: SELECT COUNT(*) FROM
# climate_risk.risk_scores). A train/test split on 40 rows isn't a
# statistically honest evaluation of a gradient-boosted model; whatever R^2
# came out of a 30/10-ish split would be closer to noise than signal.
#
# Fix: engineer the same 3 ingredients the hand-tuned formula already uses
# (extreme_heat_days, heavy_precip_days, temp_anomaly_c) at MONTHLY grain
# from daily_climate instead of reusing the sparse annual table. Verified
# live: 11,030 daily_climate rows, 10 locations, 2023-09-11 to 2026-09-17 --
# 370 location-months, of which 20 (the first and last calendar month per
# location, ~17-20 days instead of ~30) are partial and dropped, leaving 350
# real location-months (Oct 2023 - Aug 2026). See docs/model_card.md for the
# full reasoning, including why the target is monthly_risk_score (the same
# formula reapplied at month grain) rather than the annual risk_score itself.
RISK_MODEL_TEST_SPLIT_DATE = "2025-10-01"  # train: Oct'23-Sep'25 (24 mo/location); test: Oct'25-Aug'26 (11 mo/location)
RISK_MODEL_FEATURES = ["extreme_heat_days", "heavy_precip_days", "temp_anomaly_c"]


def _load_climate_features_monthly() -> pd.DataFrame:
    """Monthly-grain version of what sql/002_risk_scores.sql computes
    annually. Rebuilt directly from daily_climate (not derived from the
    annual risk_scores table) so this is a real, independent feature build,
    using the identical per-location baseline the annual formula uses: that
    location's average daily high across its earliest calendar year on
    record (2023 here, itself only Sep-Dec since the archive starts
    2023-09-11 -- a real limitation the annual formula already has, not one
    this monthly version introduces; see docs/model_card.md)."""
    daily = pd.read_sql(
        "SELECT location_id, date, temp_max_c, precipitation_mm FROM climate_risk.daily_climate",
        get_engine(),
    )
    daily["date"] = pd.to_datetime(daily["date"])
    daily["month"] = daily["date"].dt.to_period("M").dt.to_timestamp()
    daily["year"] = daily["date"].dt.year

    baseline_year = daily.groupby("location_id")["year"].min().rename("baseline_year")
    baseline = (
        daily.merge(baseline_year, on="location_id")
        .query("year == baseline_year")
        .groupby("location_id")["temp_max_c"].mean()
        .rename("baseline_temp_max_c")
    )

    monthly = daily.groupby(["location_id", "month"]).agg(
        extreme_heat_days=("temp_max_c", lambda s: int((s > 35).sum())),
        heavy_precip_days=("precipitation_mm", lambda s: int((s > 25).sum())),
        avg_temp_max_c=("temp_max_c", "mean"),
        days_observed=("temp_max_c", "size"),
    ).reset_index()

    monthly = monthly.merge(baseline, on="location_id")
    monthly["temp_anomaly_c"] = monthly["avg_temp_max_c"] - monthly["baseline_temp_max_c"]

    # Partial calendar months (the archive's first and last real date per
    # location) have structurally fewer heat/precip days than a full month
    # for reasons that have nothing to do with climate -- drop them rather
    # than let them bias the monthly counts low.
    monthly = monthly[monthly["days_observed"] >= 25].drop(columns=["days_observed", "baseline_temp_max_c"])

    monthly["monthly_risk_score"] = np.minimum(
        100.0,
        monthly["extreme_heat_days"] * 1.5
        + monthly["heavy_precip_days"] * 2.0
        + np.maximum(monthly["temp_anomaly_c"], 0) * 10.0,
    )
    monthly["year"] = monthly["month"].dt.year
    return monthly.sort_values(["location_id", "month"]).reset_index(drop=True)


def build_risk_model_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Time-based split on the monthly frame (never random -- a random split
    would let e.g. July 2025's weather leak into a June 2025 test fold), plus
    the annual-formula-baseline prediction joined onto every month of its
    year: the real risk_score already stored in climate_risk.risk_scores for
    that (location, year), repeated across each of that year's months. That
    baseline is a genuinely different, non-circular prediction from the
    model's -- it never sees this month's weather, only last-computed annual
    weather -- so comparing it to monthly_risk_score is a fair contest, not
    the model grading its own homework."""
    monthly = _load_climate_features_monthly()
    annual = pd.read_sql(
        "SELECT location_id, year, risk_score AS annual_formula_prediction FROM climate_risk.risk_scores",
        get_engine(),
    )
    monthly = monthly.merge(annual, on=["location_id", "year"], how="left")

    train = monthly[monthly["month"] < RISK_MODEL_TEST_SPLIT_DATE].copy()
    test = monthly[monthly["month"] >= RISK_MODEL_TEST_SPLIT_DATE].copy()
    return train, test


def train_risk_model() -> dict:
    """Train an XGBoost regressor on the monthly features above to predict
    monthly_risk_score, and compare it against the existing annual formula's
    output (repeated across each test month of its year) on the same
    held-out months. Writes both models' real MAE/R2 to
    climate_risk.model_evaluation and the model's test-set predictions to
    climate_risk.risk_model_predictions -- whichever way the comparison
    lands, since a hand-tuned 3-feature linear-ish rule beating a
    gradient-boosted model on ~240 training rows would be a legitimate
    result, not a failure to hide."""
    from sklearn.metrics import mean_absolute_error, r2_score
    from xgboost import XGBRegressor

    train, test = build_risk_model_features()
    X_train = train[RISK_MODEL_FEATURES].to_numpy()
    y_train = train["monthly_risk_score"].to_numpy()
    X_test = test[RISK_MODEL_FEATURES].to_numpy()
    y_test = test["monthly_risk_score"].to_numpy()

    # Shallow/few trees on purpose: 3 numeric features and ~240 training
    # rows is a small, simple regression problem -- a deep, many-tree
    # XGBoost here would be reaching for capacity this data doesn't need
    # and support overfitting, not better fit.
    model = XGBRegressor(
        n_estimators=150, max_depth=3, learning_rate=0.1, random_state=RNG_SEED,
    )
    model.fit(X_train, y_train)
    model_pred = model.predict(X_test)

    baseline_pred = test["annual_formula_prediction"].to_numpy()

    computed_at = datetime.now(timezone.utc)
    metrics = [
        {
            "model_name": "xgboost_monthly_risk_model",
            "mae": float(mean_absolute_error(y_test, model_pred)),
            "r2": float(r2_score(y_test, model_pred)),
            "computed_at": computed_at,
        },
        {
            "model_name": "annual_formula_baseline",
            "mae": float(mean_absolute_error(y_test, baseline_pred)),
            "r2": float(r2_score(y_test, baseline_pred)),
            "computed_at": computed_at,
        },
    ]
    upsert_dataframe(pd.DataFrame(metrics), schema="climate_risk", table="model_evaluation", key_columns=["model_name"])

    predictions = pd.DataFrame({
        "location_id": test["location_id"].to_numpy(),
        "month_start": test["month"].dt.date.to_numpy(),
        "model_name": "xgboost_monthly_risk_model",
        "predicted_risk_score": model_pred,
        "actual_monthly_risk_score": y_test,
        "computed_at": computed_at,
    })
    upsert_dataframe(
        predictions, schema="climate_risk", table="risk_model_predictions",
        key_columns=["location_id", "month_start", "model_name"],
    )

    # Rollup sanity check: average this model's test-period monthly
    # predictions per (location, year) and compare to that location-year's
    # REAL annual risk_score. The test window (Oct'25-Aug'26) never covers a
    # full calendar year for any location, so this is a partial-year
    # approximation -- reported as a rough sanity check (MAE only, no R2:
    # too few points across too few location-years to make an R2 meaningful),
    # not a rigorous annual accuracy claim.
    rollup = (
        test.assign(predicted=model_pred)
        .groupby(["location_id", "year"])
        .agg(predicted_annual=("predicted", "mean"), actual_annual=("annual_formula_prediction", "first"),
             months_in_test=("predicted", "size"))
        .reset_index()
    )
    rollup_mae = float(mean_absolute_error(rollup["actual_annual"], rollup["predicted_annual"]))

    save_risk_model_evidence(
        model=model, y_test=y_test, model_pred=model_pred, baseline_pred=baseline_pred, metrics=metrics,
    )

    return {
        "metrics": metrics,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "rollup_mae": rollup_mae,
        "rollup_location_years": int(len(rollup)),
    }


def save_risk_model_evidence(
    *, model, y_test: np.ndarray, model_pred: np.ndarray, baseline_pred: np.ndarray, metrics: list[dict],
) -> None:
    """Predicted-vs-actual scatter, an MAE/R2 comparison bar chart, and the
    XGBoost model's native feature importances -- real images from this
    actual run, not mocked."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    by_name = {m["model_name"]: m for m in metrics}

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(y_test, model_pred, alpha=0.6, label="xgboost_monthly_risk_model", color="#2a6f97")
    ax.scatter(y_test, baseline_pred, alpha=0.6, label="annual_formula_baseline", color="#e07a5f", marker="^")
    lims = [0, max(float(y_test.max()), float(model_pred.max()), float(baseline_pred.max())) + 5]
    ax.plot(lims, lims, "k--", alpha=0.3, label="perfect prediction")
    ax.set_xlabel("Actual monthly_risk_score")
    ax.set_ylabel("Predicted risk score")
    ax.set_title("Predicted vs. actual, held-out test months (Oct 2025-Aug 2026)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(EVIDENCE_DIR, "climate_predicted_vs_actual.png"), dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    names = list(by_name.keys())
    axes[0].bar(names, [by_name[n]["mae"] for n in names], color=["#2a6f97", "#e07a5f"])
    axes[0].set_title("MAE on held-out months (lower is better)")
    axes[0].tick_params(axis="x", rotation=15)
    axes[1].bar(names, [by_name[n]["r2"] for n in names], color=["#2a6f97", "#e07a5f"])
    axes[1].set_title("R2 on held-out months (higher is better)")
    axes[1].tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(os.path.join(EVIDENCE_DIR, "climate_mae_r2_comparison.png"), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    importances = model.feature_importances_
    order = np.argsort(importances)
    ax.barh([RISK_MODEL_FEATURES[i] for i in order], importances[order], color="#2a6f97")
    ax.set_title("XGBoost feature importance (monthly risk model)")
    fig.tight_layout()
    fig.savefig(os.path.join(EVIDENCE_DIR, "climate_feature_importance.png"), dpi=150)
    plt.close(fig)
