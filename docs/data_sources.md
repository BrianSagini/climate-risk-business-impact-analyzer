# Data Sources

## Climate history — real, keyless

**Open-Meteo Historical Weather API** (`https://archive-api.open-meteo.com/v1/archive`) — daily
`temperature_2m_max`, `temperature_2m_min`, `precipitation_sum`, `windspeed_10m_max` for 10 US
cities, ~3 years of history. No API key or account required (verified live). License: CC-BY-4.0,
attribution: "Weather data by Open-Meteo.com". Rate limits: generous free tier (10,000
requests/day); this pipeline issues 10 requests per run.

## Business exposure — synthetic

Each location's `industry`, `annual_revenue_usd`, and `asset_value_usd` are illustrative
placeholders sized to plausible single-facility ranges — not sourced from any real company's
financials. Flagged `is_synthetic_business_data = true` in `climate_risk.locations`. This exists
to make the real climate signal analyzable in business terms.

## No API key required

Nothing in this pipeline needs a credential of any kind.
