-- Power BI-facing views for Project 1. Pure passthrough/join views over
-- tables already populated by 002_risk_scores.sql / 003_financial_impact.sql
-- -- no logic is duplicated here, so Power BI can never disagree with the
-- SQL analytical model or the Streamlit dashboard.

CREATE OR REPLACE VIEW climate_risk.powerbi_summary AS
SELECT
    l.location_id,
    l.name,
    l.lat,
    l.lon,
    l.industry,
    l.annual_revenue_usd,
    l.asset_value_usd,
    l.is_synthetic_business_data,
    r.year AS latest_year,
    r.risk_score AS latest_risk_score,
    r.extreme_heat_days,
    r.heavy_precip_days,
    r.temp_anomaly_c,
    f.estimated_impact_usd AS moderate_scenario_impact_usd
FROM climate_risk.locations l
LEFT JOIN LATERAL (
    SELECT * FROM climate_risk.risk_scores rs
    WHERE rs.location_id = l.location_id
    ORDER BY rs.year DESC LIMIT 1
) r ON true
LEFT JOIN climate_risk.scenario_financial_impact f
    ON f.location_id = l.location_id AND f.year = r.year AND f.scenario = 'moderate';

CREATE OR REPLACE VIEW climate_risk.powerbi_trends AS
SELECT
    location_id,
    date_trunc('month', date)::date AS month,
    AVG(temp_max_c) AS avg_temp_max_c,
    AVG(temp_min_c) AS avg_temp_min_c,
    SUM(precipitation_mm) AS total_precipitation_mm,
    MAX(windspeed_max_kmh) AS max_windspeed_kmh
FROM climate_risk.daily_climate
GROUP BY location_id, date_trunc('month', date);

CREATE OR REPLACE VIEW climate_risk.powerbi_geography AS
SELECT
    l.location_id, l.name, l.lat, l.lon, l.industry,
    r.year, r.risk_score, r.extreme_heat_days, r.heavy_precip_days
FROM climate_risk.locations l
JOIN climate_risk.risk_scores r ON r.location_id = l.location_id;

CREATE OR REPLACE VIEW climate_risk.powerbi_financial_impact AS
SELECT
    f.location_id, l.name, l.industry, f.year, f.scenario,
    f.estimated_impact_usd, f.pct_of_asset_value
FROM climate_risk.scenario_financial_impact f
JOIN climate_risk.locations l ON l.location_id = f.location_id;
