-- Scenario financial impact estimation.
--
-- Methodology (see docs/methodology_climate_risk.md): each scenario applies
-- a fixed illustrative multiplier to (risk_score/100) * asset_value_usd,
-- representing a rough "share of asset value exposed to climate-driven
-- disruption per year" under increasingly severe assumptions. These
-- multipliers are illustrative judgment calls for portfolio-demo purposes,
-- not derived from an insurance/actuarial model -- documented as a limitation.
--
--   mild:     2%  of (risk_score-weighted asset value) per year
--   moderate: 5%
--   severe:   12%

INSERT INTO climate_risk.scenario_financial_impact
    (location_id, year, scenario, estimated_impact_usd, pct_of_asset_value, computed_at)
SELECT
    r.location_id,
    r.year,
    s.scenario,
    ROUND(((r.risk_score / 100.0) * l.asset_value_usd * s.multiplier)::numeric, 2) AS estimated_impact_usd,
    ROUND(((r.risk_score / 100.0) * s.multiplier * 100)::numeric, 4) AS pct_of_asset_value,
    now()
FROM climate_risk.risk_scores r
JOIN climate_risk.locations l ON l.location_id = r.location_id
CROSS JOIN (VALUES ('mild', 0.02), ('moderate', 0.05), ('severe', 0.12)) AS s(scenario, multiplier)
ON CONFLICT (location_id, year, scenario) DO UPDATE SET
    estimated_impact_usd = EXCLUDED.estimated_impact_usd,
    pct_of_asset_value = EXCLUDED.pct_of_asset_value,
    computed_at = EXCLUDED.computed_at;
