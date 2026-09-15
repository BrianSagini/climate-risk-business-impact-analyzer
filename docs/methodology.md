# Project 1 — Climate Risk & Business Impact: Methodology & Limitations

## Data

- **Real**: daily `temperature_2m_max`, `temperature_2m_min`, `precipitation_sum`, `windspeed_10m_max`
  for 10 US cities, ~3 years of history, from Open-Meteo's historical archive API (no key required).
- **Synthetic**: each location's `industry`, `annual_revenue_usd`, `asset_value_usd` are illustrative
  placeholders sized to plausible single-facility ranges. They are flagged
  `is_synthetic_business_data = true` in `climate_risk.locations` and must never be read as real
  company financials.

## Risk score (0–100, per location per year)

```
risk_score = LEAST(100,
    extreme_heat_days * 1.5
  + heavy_precip_days * 2.0
  + GREATEST(temp_anomaly_c, 0) * 10.0
)
```

- `extreme_heat_days`: days in that year with `temp_max_c > 35°C` (95°F).
- `heavy_precip_days`: days with `precipitation_mm > 25mm` (~1 inch — a commonly used "heavy rain day" threshold).
- `temp_anomaly_c`: that year's average daily max temp minus the location's **own earliest year in this dataset**.

**Limitations**: this is a simple, transparent heuristic built for this portfolio demo — it is
**not** a scientifically validated or actuarial climate risk model, has not been back-tested against
real loss events, and the temperature "anomaly" is a ~3-year short-window signal, not a 30-year
climatological normal (the archive only goes back 3 years in this build — extending `HISTORY_YEARS`
in `pipeline.py` would improve this but was chosen small here to keep ingestion fast for a demo).

## Financial impact scenarios

```
estimated_impact_usd = (risk_score / 100) * asset_value_usd * scenario_multiplier
```

| Scenario | Multiplier |
|---|---|
| mild | 2% |
| moderate | 5% |
| severe | 12% |

These multipliers are illustrative judgment calls chosen to produce a plausible spread across
scenarios for demonstration purposes — they are **not** derived from an insurance/actuarial loss
model, reinsurance pricing, or peer-reviewed climate-finance research. A production version of this
analysis would replace them with location- and peril-specific damage functions (e.g., FEMA HAZUS,
NOAA billion-dollar-disaster cost data, or a licensed catastrophe model).

## Note on the current (in-progress) year

The most recent `year` in `climate_risk.risk_scores` is a **partial year** (the pipeline runs
daily and the archive API lags ~2 days) — its `extreme_heat_days`/`heavy_precip_days` counts
cover only the months elapsed so far, not a full 365 days, and are not comparable on a like-for-like
basis to prior complete years without annualizing. The dashboard does not currently annualize this;
treat the latest year's risk score as a running year-to-date figure.

## What this project does *not* do

- Does not predict future weather or claim forecasting skill beyond Open-Meteo's own forecast horizon.
- Does not model compound/cascading risk (e.g., supply-chain exposure at *other* companies' facilities).
- Does not account for insurance coverage, mitigation investment, or business continuity planning.
