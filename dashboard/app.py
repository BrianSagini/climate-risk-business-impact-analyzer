"""Climate Risk & Business Impact Analyzer -- Streamlit dashboard.

Reads only from climate_risk.* via the read-only ANALYTICS_DATABASE_URL
connection (analytics_ro role) -- never recomputes risk scores or
financial impact here; that logic lives in SQL
(projects/01_climate_risk_business_impact/sql/002_risk_scores.sql,
003_financial_impact.sql) so the dashboard's numbers always match what
the pipeline computed.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from shared.database import get_engine

st.set_page_config(page_title="Climate Risk & Business Impact", layout="wide")
st.title("🌎 Climate Risk & Business Impact Analyzer")
st.caption(
    "Real climate history from Open-Meteo (archive-api.open-meteo.com). "
    "Business exposure figures (industry, revenue, asset value) are "
    "**synthetic placeholders** for portfolio-demo purposes, not real "
    "company financials. See docs/methodology_climate_risk.md for the "
    "risk-scoring and financial-impact methodology and its limitations."
)


@st.cache_data(ttl=300)
def load_locations() -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(text("SELECT * FROM climate_risk.locations ORDER BY name"), engine)


@st.cache_data(ttl=300)
def load_risk_scores() -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(
        text(
            """
            SELECT r.*, l.name, l.lat, l.lon, l.industry
            FROM climate_risk.risk_scores r
            JOIN climate_risk.locations l ON l.location_id = r.location_id
            ORDER BY r.location_id, r.year
            """
        ),
        engine,
    )


@st.cache_data(ttl=300)
def load_financial_impact() -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(
        text(
            """
            SELECT f.*, l.name, l.industry
            FROM climate_risk.scenario_financial_impact f
            JOIN climate_risk.locations l ON l.location_id = f.location_id
            ORDER BY f.location_id, f.year, f.scenario
            """
        ),
        engine,
    )


try:
    locations = load_locations()
    risk = load_risk_scores()
    impact = load_financial_impact()
except Exception as exc:  # noqa: BLE001 -- surfaced to the user, not swallowed
    st.error(f"Could not connect to the analytics database: {exc}")
    st.stop()

if locations.empty:
    st.warning(
        "No data yet. Trigger the `climate_risk_pipeline` DAG in Airflow "
        "(http://localhost:8081) and wait for it to complete, then refresh."
    )
    st.stop()

selected_locations = st.multiselect(
    "Locations", options=locations["name"].tolist(), default=locations["name"].tolist()
)
risk_f = risk[risk["name"].isin(selected_locations)]
impact_f = impact[impact["name"].isin(selected_locations)]

if risk_f.empty:
    st.info(
        "Locations are loaded but no yearly risk scores exist yet — the "
        "pipeline's `compute_risk_scores` task needs at least one full "
        "DAG run to populate `climate_risk.risk_scores`."
    )
    st.stop()

col1, col2, col3 = st.columns(3)
latest_year = int(risk_f["year"].max())
latest = risk_f[risk_f["year"] == latest_year]
col1.metric("Highest risk score", f"{latest['risk_score'].max():.0f}/100", latest.loc[latest['risk_score'].idxmax(), 'name'])
col2.metric("Avg risk score (latest year)", f"{latest['risk_score'].mean():.1f}/100")
col3.metric("Locations tracked", len(locations))

st.subheader("Business locations & climate risk")
map_df = latest.copy()
fig_map = px.scatter_geo(
    map_df, lat="lat", lon="lon", size="risk_score", color="risk_score",
    hover_name="name", hover_data={"industry": True, "risk_score": ":.1f", "lat": False, "lon": False},
    color_continuous_scale="OrRd", scope="usa", title=f"Risk score by location ({latest_year})",
)
st.plotly_chart(fig_map, use_container_width=True)

st.subheader("Risk score trend by location")
fig_trend = px.line(risk_f, x="year", y="risk_score", color="name", markers=True)
st.plotly_chart(fig_trend, use_container_width=True)

st.subheader("Estimated financial impact by scenario")
scenario = st.selectbox("Scenario", options=["mild", "moderate", "severe"], index=1)
impact_scenario = impact_f[(impact_f["scenario"] == scenario) & (impact_f["year"] == latest_year)]
impact_scenario = impact_scenario.sort_values("estimated_impact_usd", ascending=False)
fig_impact = px.bar(
    impact_scenario, x="name", y="estimated_impact_usd", color="industry",
    labels={"estimated_impact_usd": "Estimated impact (USD)", "name": "Location"},
    title=f"Estimated {scenario}-scenario financial impact, {latest_year}",
)
st.plotly_chart(fig_impact, use_container_width=True)

st.dataframe(
    impact_scenario[["name", "industry", "estimated_impact_usd", "pct_of_asset_value"]]
    .rename(columns={"name": "Location", "estimated_impact_usd": "Estimated impact (USD)", "pct_of_asset_value": "% of asset value"}),
    use_container_width=True,
    hide_index=True,
)

with st.expander("Methodology & limitations"):
    st.markdown(
        """
        - **Climate data** is real, sourced from Open-Meteo's historical archive (no API key required).
        - **Risk score** (0-100) is an illustrative heuristic: `extreme_heat_days * 1.5 + heavy_precip_days * 2.0 + max(temp_anomaly, 0) * 10`,
          capped at 100. It is **not** a scientifically validated or actuarial climate risk model.
        - **Temperature anomaly** is measured against each location's *own earliest year in this dataset*
          (~3 years of history), not a 30-year climatological normal — treat it as a short-window signal only.
        - **Business exposure** (industry, revenue, asset value) is synthetic and illustrative, not real company data.
        - **Financial impact** = `(risk_score/100) * asset_value * scenario_multiplier`, where multipliers
          (2% / 5% / 12% for mild/moderate/severe) are judgment-call placeholders, not derived from an insurance model.
        """
    )
