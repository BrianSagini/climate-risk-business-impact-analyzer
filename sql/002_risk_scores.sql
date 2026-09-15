-- Yearly climate risk indicators per location.
--
-- Methodology (documented in full in docs/methodology_climate_risk.md):
--   extreme_heat_days := days/year with temp_max_c > 35C (95F)
--   heavy_precip_days := days/year with precipitation_mm > 25mm (~1 inch, a
--                         commonly used "heavy rain day" threshold)
--   temp_anomaly_c     := that year's avg daily max temp minus the location's
--                         baseline (its earliest available year in this
--                         dataset -- with only ~3 years of history this is a
--                         short-window anomaly, NOT a 30-year climatological
--                         normal; see limitations doc)
--   risk_score         := a simple illustrative 0-100 heuristic combining the
--                         three signals above. It is NOT a scientifically
--                         validated or actuarial climate risk model.
--
-- Idempotent: re-running replaces each (location_id, year) row via ON CONFLICT.

WITH yearly AS (
    SELECT
        location_id,
        EXTRACT(YEAR FROM date)::INT AS year,
        COUNT(*) FILTER (WHERE temp_max_c > 35) AS extreme_heat_days,
        COUNT(*) FILTER (WHERE precipitation_mm > 25) AS heavy_precip_days,
        AVG(temp_max_c) AS avg_temp_max_c
    FROM climate_risk.daily_climate
    GROUP BY location_id, EXTRACT(YEAR FROM date)
),
baseline AS (
    SELECT location_id, MIN(year) AS baseline_year
    FROM yearly
    GROUP BY location_id
),
with_anomaly AS (
    SELECT
        y.location_id,
        y.year,
        y.extreme_heat_days,
        y.heavy_precip_days,
        y.avg_temp_max_c,
        y.avg_temp_max_c - b_year.avg_temp_max_c AS temp_anomaly_c
    FROM yearly y
    JOIN baseline b ON b.location_id = y.location_id
    JOIN yearly b_year ON b_year.location_id = b.location_id AND b_year.year = b.baseline_year
)
INSERT INTO climate_risk.risk_scores
    (location_id, year, extreme_heat_days, heavy_precip_days, avg_temp_max_c, temp_anomaly_c, risk_score, computed_at)
SELECT
    location_id,
    year,
    extreme_heat_days,
    heavy_precip_days,
    avg_temp_max_c,
    temp_anomaly_c,
    LEAST(100, extreme_heat_days * 1.5 + heavy_precip_days * 2.0 + GREATEST(temp_anomaly_c, 0) * 10.0) AS risk_score,
    now()
FROM with_anomaly
ON CONFLICT (location_id, year) DO UPDATE SET
    extreme_heat_days = EXCLUDED.extreme_heat_days,
    heavy_precip_days = EXCLUDED.heavy_precip_days,
    avg_temp_max_c = EXCLUDED.avg_temp_max_c,
    temp_anomaly_c = EXCLUDED.temp_anomaly_c,
    risk_score = EXCLUDED.risk_score,
    computed_at = EXCLUDED.computed_at;
