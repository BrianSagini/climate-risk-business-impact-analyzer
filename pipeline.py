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
from datetime import date, timedelta

import pandas as pd

from shared.database import get_engine, upsert_dataframe
from shared.ingestion import get_json_with_retry, save_raw_json
from shared.validation import validate_dataframe

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HISTORY_YEARS = 3

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
