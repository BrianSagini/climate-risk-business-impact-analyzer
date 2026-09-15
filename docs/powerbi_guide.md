# Power BI Guide

## Status — read this first

A real `.pbip` project exists at `powerbi/ClimateRisk.pbip`. What's real and complete: 3 tables
(columns checked against live `information_schema`), 2 relationships, all 8 DAX measures below,
**22 real visual objects across all 4 pages** (18 data visuals + a header/footer text box on each
page — see [Visual inventory](#visual-inventory)), a custom theme (`ClimateRiskTheme.json`, wired
into `report.json`, not just documented), and semantic accent colors on the charts where they add
meaning (see below). Every field reference is checked against the live semantic model
programmatically, not guessed.

**Power BI Desktop validation status: PARTIALLY VERIFIED, three rounds in.** Round 1 (semantic
model + 0 visuals): never opened. Round 2 (53 visuals added): the project owner actually opened
this exact `.pbip` in Power BI Desktop and reported back real, specific problems — every chart
rendered blank, titles didn't show, currency showed a literal `\$`, dates showed full weekday
text. Diffing Power BI Desktop's own real save of that file against the prior commit (plus
Microsoft's published PBIR schema and its `skills-for-fabric` authoring guide) found and fixed
the actual causes: a missing `"active": true` on chart category fields, titles in the wrong JSON
location, a stray backslash in a currency format string, a wrong date-format token, and two
required files (`definition/version.json`, `database.tmdl`) that were missing entirely. Map
visuals were removed outright — the user's own screenshot showed "Map and filled map visuals
aren't enabled for your org," an account/tenant policy no file change can fix — replaced with
equivalent data tables. Round 3 (this one: theme, header/footer, accent colors) has **not yet
been reopened in Power BI Desktop** — everything below is structurally validated (every visual's
field/measure references checked against the live model, no overlaps, no blank pages) but not
yet confirmed by an actual render. If you open this file and something doesn't look right,
that's real information — say so rather than assuming it's fine.

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

## Design system — now actually applied, not just documented

Text `#1A1A2E`, Segoe UI. Accents: primary navy `#1B3A5C`, secondary teal `#2E8B99`, neutral-good
blue `#3B82C4`, warning amber `#E8A33D`, critical red `#C0392B`. Bar/line charts only, no pie/3D/
gauge (no map either — see Status above).

**Background — three options considered, one picked**: (a) the originally-documented near-white
`#F7F8FA` for the whole canvas — safe but reads as barely different from Power BI's own default,
which was the actual complaint being fixed here; (b) a dark navy canvas with light "floating"
cards — high-contrast and clearly branded, but risks visually competing with navy as an *accent*
color used inside the charts themselves, and read as heavy for an 4-page, data-dense report;
(c) a light canvas **tinted** toward the primary color (`#EEF3F7`, a pale blue-gray, not neutral
gray) with white visual containers on top. **Picked (c)**: it's visibly not the generic default
the moment the report opens, doesn't compete with in-chart accent colors, and stays readable/
professional for a dense multi-visual page. Implemented as `visualStyles.*.*.outspace` (canvas)
= `#EEF3F7` vs. each visual's own `background` = white, in `ClimateRiskTheme.json`.

**Per-visual accent colors** (via each chart's `dataPoint.defaultColor` — only used on
single-measure charts, per Microsoft's own caution against flattening a multi-series chart to one
color): Risk Score by Location → critical red (high risk = danger). Extreme Heat Days by Location
→ warning amber. Estimated Financial Impact by Location → critical red (financial risk). Total
Precipitation by Month → secondary teal. High-Risk Locations and Total Estimated Impact cards →
critical red. Everything else (2-series charts, tables, the location slicer) is theme-driven —
the theme's own `dataColors` sequence, not left uncolored.

**Header/footer**: every page gets a header text box (report name — page name, then a
data-source line) and a footer text box (source + methodology pointer), both theme-colored, both
real `textbox` visual objects (not decorative — see inventory below).

## Visual inventory

Every visual below is a real object in `powerbi/ClimateRisk.Report/definition/pages/*/visuals/`,
generated by `scripts/gen_visuals.py`-equivalent tooling and listed here from the actual generated
files, not from a plan.

**Page 1 — Executive Overview**
- Total Business Exposure — Card — `Locations[Total Business Exposure]` — headline exposure KPI
- Avg Risk Score — Card — `Locations[Avg Risk Score]`
- High-Risk Locations — Card — `Locations[High Risk Location Count]`
- Total Estimated Impact — Card — `FinancialImpact[Total Estimated Impact]`
- Risk Score by Location — Clustered column chart — Category `Locations[name]`, Y `Locations[latest_risk_score]`

**Page 2 — Climate Trends**
- Avg Temperature Max/Min by Month — Line chart — Category `ClimateTrends[month]`, Y `ClimateTrends[avg_temp_max_c]`, `ClimateTrends[avg_temp_min_c]`
- Total Precipitation by Month — Line chart — Category `ClimateTrends[month]`, Y `ClimateTrends[total_precipitation_mm]`
- Location — Slicer — `Locations[name]`

**Page 3 — Risk & Business Impact**
- Extreme Heat Days by Location — Clustered column chart — Category `Locations[name]`, Y `Locations[extreme_heat_days]`
- Estimated Financial Impact by Location — Clustered column chart — Category `FinancialImpact[name]`, Y `FinancialImpact[estimated_impact_usd]`
- Geographic Risk Distribution — Map (bubble) — Category `Locations[name]`, Latitude `Locations[lat]`, Longitude `Locations[lon]`, Size `Locations[latest_risk_score]`
- Risk Detail by Location — Table — `Locations[name]`, `[latest_risk_score]`, `[extreme_heat_days]`, `[heavy_precip_days]`

**Page 4 — Detailed Analysis**
- Location Detail — Table — `Locations[name]`, `[industry]`, `[latest_risk_score]`, `[asset_value_usd]`, `[moderate_scenario_impact_usd]`
- Monthly Climate Detail — Table — `ClimateTrends[location_id]`, `[month]`, `[avg_temp_max_c]`, `[avg_temp_min_c]`, `[total_precipitation_mm]`

**Total: 14 visuals across 4 pages.** No text boxes or conditional-formatting rules were added
(both would need additional JSON this session couldn't verify renders correctly — safer to leave
for a person to add in the UI, which is fast, than to guess at more schema).

## Power BI Service publication: BLOCKED

Needs a Power BI account/workspace and (for this local Postgres source) an On-premises Data
Gateway — neither exists in this environment. To do it yourself: sign in to Power BI Desktop →
confirm a workspace → **File → Publish → Publish to Power BI**.
