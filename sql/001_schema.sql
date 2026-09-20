-- Climate Risk & Business Impact Analyzer -- schema
-- locations.is_synthetic_business_data flags the columns that are NOT
-- real climate data: industry/revenue/asset_value are illustrative.

CREATE TABLE IF NOT EXISTS climate_risk.locations (
    location_id                 TEXT PRIMARY KEY,
    name                        TEXT NOT NULL,
    lat                         DOUBLE PRECISION NOT NULL,
    lon                         DOUBLE PRECISION NOT NULL,
    industry                    TEXT,
    annual_revenue_usd          NUMERIC,
    asset_value_usd             NUMERIC,
    is_synthetic_business_data  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS climate_risk.daily_climate (
    location_id         TEXT NOT NULL REFERENCES climate_risk.locations(location_id),
    date                DATE NOT NULL,
    temp_max_c          DOUBLE PRECISION,
    temp_min_c          DOUBLE PRECISION,
    precipitation_mm    DOUBLE PRECISION,
    windspeed_max_kmh   DOUBLE PRECISION,
    PRIMARY KEY (location_id, date)
);

CREATE TABLE IF NOT EXISTS climate_risk.risk_scores (
    location_id           TEXT NOT NULL REFERENCES climate_risk.locations(location_id),
    year                  INT NOT NULL,
    extreme_heat_days     INT NOT NULL,
    heavy_precip_days     INT NOT NULL,
    avg_temp_max_c        DOUBLE PRECISION,
    temp_anomaly_c        DOUBLE PRECISION,
    risk_score            DOUBLE PRECISION,
    computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (location_id, year)
);

CREATE TABLE IF NOT EXISTS climate_risk.scenario_financial_impact (
    location_id           TEXT NOT NULL REFERENCES climate_risk.locations(location_id),
    year                  INT NOT NULL,
    scenario              TEXT NOT NULL CHECK (scenario IN ('mild', 'moderate', 'severe')),
    estimated_impact_usd  NUMERIC,
    pct_of_asset_value    DOUBLE PRECISION,
    computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (location_id, year, scenario)
);

CREATE INDEX IF NOT EXISTS idx_daily_climate_date ON climate_risk.daily_climate(date);

-- Monthly risk-model evaluation. Same shape as fraud_pattern.model_evaluation
-- (model_name, real metrics, computed_at) for consistency across the
-- portfolio's ML tables -- MAE/R2 here rather than precision/recall/F1/ROC-AUC
-- because this is a regression problem, not classification.
CREATE TABLE IF NOT EXISTS climate_risk.model_evaluation (
    model_name    TEXT NOT NULL,
    mae           DOUBLE PRECISION NOT NULL,
    r2            DOUBLE PRECISION NOT NULL,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (model_name)
);

-- Test-set-only monthly predictions (mirrors fraud_pattern.anomaly_scores'
-- pattern of only ever writing held-out-set predictions, never train-set
-- ones). See docs/model_card.md for what "monthly_risk_score" means and why
-- it's a distinct quantity from the annual risk_scores.risk_score.
CREATE TABLE IF NOT EXISTS climate_risk.risk_model_predictions (
    location_id                 TEXT NOT NULL REFERENCES climate_risk.locations(location_id),
    month_start                 DATE NOT NULL,
    model_name                  TEXT NOT NULL,
    predicted_risk_score        DOUBLE PRECISION NOT NULL,
    actual_monthly_risk_score   DOUBLE PRECISION NOT NULL,
    computed_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (location_id, month_start, model_name)
);
