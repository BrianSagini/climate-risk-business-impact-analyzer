# Power BI Guide

## Status — read this first

A real `.pbip` project exists at `powerbi/ClimateRisk.pbip`, generated programmatically (not
clicked through Desktop) — **but it has never been opened in Power BI Desktop, so it is not
validated.** What's real and complete in it: 3 tables (matching the views below, columns checked
against live `information_schema`), 2 relationships, and all 8 DAX measures below, reconciled
against already-verified SQL. What's a placeholder: the report's 4 pages exist, correctly named,
with **zero visuals** — hand-authoring visual JSON blind was judged the highest-risk part to fake,
so it's left for a person to populate interactively (fast — the whole data model already exists).
Whether the file actually opens without error in Power BI Desktop is genuinely unknown.

## Data connectivity

- Get Data → Database → PostgreSQL database
- Server: `localhost:5433` · Database: `analytics` · User: `analytics_ro` (password: your `.env`'s
  `ANALYTICS_RO_PASSWORD`, never pasted into the report file — Power BI keeps it in its own
  credential manager)
- Mode: **Import** (these views are small — at most a few thousand rows)

## Tables, relationships, measures

Tables: `climate_risk.powerbi_summary` (1 row/location), `climate_risk.powerbi_trends` (1
row/location/month), `climate_risk.powerbi_financial_impact` (1 row/location/year/scenario).

Relationships: `powerbi_summary[location_id]` (1) → `powerbi_trends[location_id]` (*) ·
`powerbi_summary[location_id]` (1) → `powerbi_financial_impact[location_id]` (*).

```dax
Total Business Exposure = SUM(powerbi_summary[asset_value_usd])
Avg Risk Score = AVERAGE(powerbi_summary[latest_risk_score])
High Risk Location Count = COUNTROWS(FILTER(powerbi_summary, powerbi_summary[latest_risk_score] >= 60))
Total Estimated Impact = SUM(powerbi_financial_impact[estimated_impact_usd])
Avg Temp Max (C) = AVERAGE(powerbi_trends[avg_temp_max_c])
Avg Temp Min (C) = AVERAGE(powerbi_trends[avg_temp_min_c])
Total Precipitation (mm) = SUM(powerbi_trends[total_precipitation_mm])
Avg Wind Speed (km/h) = AVERAGE(powerbi_trends[max_windspeed_kmh])
```

## Design system

Base: near-white `#F7F8FA` background, navy `#1A1A2E` text, Segoe UI typography. This project's
accents: primary navy `#1B3A5C`, secondary teal `#2E8B99`, neutral-good blue `#3B82C4` (environmental
measures), warning amber `#E8A33D`, critical red `#C0392B`. Bar/line/map charts only — no pie, 3D,
or gauges (nothing here needs them).

## Pages

1. **Executive Overview** — cards: Total Business Exposure, Avg Risk Score, High Risk Location
   Count, Total Estimated Impact; bar chart of risk score by location (blue→amber→red).
2. **Climate Trends** — line charts of avg temp max/min and total precipitation over month; date
   and location slicers.
3. **Risk & Business Impact** — risk score by location with conditional formatting (amber ≥40,
   red ≥60); estimated impact by location sliced by scenario; a text box explaining the risk-score
   formula (copy from `docs/methodology.md`).
4. **Detailed Analysis** — a table of all locations with industry/asset-value columns and, via
   tooltip or a secondary view, that location's monthly trend.

## Power BI Service publication: BLOCKED

Needs a Power BI account/workspace and (for this local Postgres source) an On-premises Data
Gateway — neither exists in this environment. To do it yourself: sign in to Power BI Desktop →
confirm a workspace → **File → Publish → Publish to Power BI**.
