# Power BI Guide

## Status — read this first

A real `.pbip` project exists at `powerbi/ClimateRisk.pbip`. What's real and complete: 3 tables
(columns checked against live `information_schema`), 2 relationships, all 8 DAX measures below,
**22 real visual objects across all 4 pages** (18 data visuals + a header/footer text box on each
page — see [Visual inventory](#visual-inventory)), a custom theme (`ClimateRiskTheme.json`, wired
into `report.json`, not just documented), and semantic accent colors on the charts where they add
meaning (see below). Every field reference is checked against the live semantic model
programmatically, not guessed.

**Power BI Desktop validation status: FULLY VERIFIED. All 4 pages confirmed rendering correctly
with real data, real colors, in Power BI Desktop**, via window-scoped screenshots (see
`docs/evidence/page1_executive_overview.png` through `page4_detailed_analysis.png`).

Four rounds of real Desktop validation got here. Round 1 (semantic model + 0 visuals): never
opened. Round 2 (53 visuals added): the project owner opened this exact `.pbip` and reported real,
specific problems — every chart rendered blank, titles didn't show, currency showed a literal
`\$`, dates showed full weekday text. Diffing Desktop's own save against the prior commit found
and fixed a missing `"active": true` on chart category fields, titles in the wrong JSON location,
a stray backslash in the currency format, a wrong date-format token, and two missing required
files (`definition/version.json`, `database.tmdl`). Map visuals were removed outright — the
user's own screenshot showed "Map and filled map visuals aren't enabled for your org," an
account/tenant policy no file change can fix — replaced with equivalent data tables. Round 3
(theme, header/footer, accent colors) was generated but not yet reopened.

**Round 4 (this one) actually reopened the file and found two more real, previously-undetected
bugs**, both now fixed and confirmed by re-render:
1. **Chart Y-fields bound as raw, unaggregated `Column` references rendered as completely empty
   plot areas** — no bars, no gridlines, no category ticks, with no error or warning shown
   anywhere in the UI. Confirmed live: switching the broken chart to a different visual type made
   Desktop auto-insert an aggregation wrapper and the chart immediately rendered; explicitly
   setting the aggregation back through Format → Y-axis field → Average on the original
   `clusteredColumnChart` and saving captured Desktop's own correct JSON shape
   (`field.Aggregation.Expression.Column` + `Function`, not a bare `field.Column`). All affected
   charts now use either an existing DAX measure (preferred where one matched the field
   semantically) or that same `Aggregation` wrapper.
2. **Card visuals used `objects.dataPoint.defaultColor` for their accent color** (the same object
   used on charts) — Desktop silently drops `dataPoint` from card visuals as invalid on load, so
   "High-Risk Locations" and "Total Estimated Impact" rendered in plain theme-default text instead
   of red. Confirmed correct via Desktop's own save after setting the color through Format →
   Callout value → Color: cards use `objects.labels[0].properties.color`, not `dataPoint`.

**Round 5 (this one)**: tightened every page's layout to a dense 16px-margin/14px-gutter grid
(visuals resized to fill their row/column instead of stopping short), and fixed the canvas
background — round 3's `visualStyles.*.*.outspace` tint turned out not to be the property that
actually colors the page canvas; Desktop's own theme customizer confirmed the real property is
`visualStyles.page.*.background`, now set to `#D6E4F0`. Both changes reopened and confirmed
rendering correctly across all 4 pages (see [Visual inventory](#visual-inventory) for the density
numbers and [Design system](#design-system--now-actually-applied-not-just-documented) for the
background-property finding).

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

**Background — Desktop-confirmed canvas tint**: a pale blue-gray canvas (`#D6E4F0`) behind white
visual containers, so panels read as distinct cards against a visibly-branded (not default-white)
canvas. The property that actually controls this is `visualStyles.page.*.background` in
`ClimateRiskTheme.json` — **not** `visualStyles.*.*.outspace`, which an earlier round wrongly
assumed controlled the canvas and which Desktop's own theme customizer confirmed does something
else (verified by setting the color live through View → Customize current theme → Page → Canvas
background, saving, and reading back the JSON Desktop wrote). `outspace` is left in place at the
same tint as a harmless no-op; `page.*.background` is the real fix.

**Per-visual accent colors**: charts use each chart's `dataPoint.defaultColor` — only on
single-measure charts, per Microsoft's own caution against flattening a multi-series chart to one
color. Cards use `objects.labels[0].properties.color`, **not** `dataPoint` — Desktop silently
drops `dataPoint` from a card visual as invalid on load (confirmed the same way as the background
fix, above), which is why some cards previously rendered in plain theme-default text despite a
color being "set" in the file. Risk Score by Location → critical red (high risk = danger).
Extreme Heat Days by Location → warning amber. Estimated Financial Impact by Location → critical
red (financial risk). Total Precipitation by Month → secondary teal. High-Risk Locations and
Total Estimated Impact cards → critical red. Everything else (2-series charts, tables, the
location slicer) is theme-driven — the theme's own `dataColors` sequence, not left uncolored.

**Header/footer**: every page gets a header text box (report name — page name, then a
data-source line) and a footer text box (source + methodology pointer), both theme-colored, both
real `textbox` visual objects.

**Layout**: a standard dense grid — 16px canvas margin, 14px gutter between visuals, visuals
resized to fill their row/column exactly rather than stopping short and leaving a dead margin.
Before this pass, pages covered roughly 78–83% of the canvas by visual area, with a highly visible
gap along the right/bottom edges; after, 87–88%, with the header/footer/cards/charts reading as
one continuous grid rather than islands of content in a sea of margin.

## Visual inventory

Every visual below is a real object in `powerbi/ClimateRisk.Report/definition/pages/*/visuals/`.

**Page 1 — Executive Overview**
- Total Business Exposure — Card — `Locations[Total Business Exposure]` — headline exposure KPI
- Avg Risk Score — Card — `Locations[Avg Risk Score]`
- High-Risk Locations — Card — `Locations[High Risk Location Count]`
- Total Estimated Impact — Card — `FinancialImpact[Total Estimated Impact]`
- Risk Score by Location — Clustered column chart — Category `Locations[name]`, Y `Locations[latest_risk_score]` (Average aggregation)

**Page 2 — Climate Trends**
- Avg Temperature Max/Min by Month — Line chart — Category `ClimateTrends[month]`, Y `ClimateTrends[Avg Temp Max (C)]`, `ClimateTrends[Avg Temp Min (C)]`
- Total Precipitation by Month — Line chart — Category `ClimateTrends[month]`, Y `ClimateTrends[Total Precipitation (mm)]`
- Location — Slicer — `Locations[name]`

**Page 3 — Risk & Business Impact**
- Extreme Heat Days by Location — Clustered column chart — Category `Locations[name]`, Y `Locations[extreme_heat_days]` (Sum aggregation)
- Estimated Financial Impact by Location — Clustered column chart — Category `FinancialImpact[name]`, Y `FinancialImpact[Total Estimated Impact]`
- Geographic Risk Detail — Table — `Locations[name]`, `[lat]`, `[lon]`, `[latest_risk_score]` (a table, not a map — see Status above)
- Risk Detail by Location — Table — `Locations[name]`, `[latest_risk_score]`, `[extreme_heat_days]`, `[heavy_precip_days]`

**Page 4 — Detailed Analysis**
- Location Detail — Table — `Locations[name]`, `[industry]`, `[latest_risk_score]`, `[asset_value_usd]`, `[moderate_scenario_impact_usd]`
- Monthly Climate Detail — Table — `ClimateTrends[location_id]`, `[month]`, `[avg_temp_max_c]`, `[avg_temp_min_c]`, `[total_precipitation_mm]`

**Total: 22 visuals across 4 pages** (14 data visuals + a header and footer text box per page).

## Power BI Service publication: BLOCKED

Needs a Power BI account/workspace and (for this local Postgres source) an On-premises Data
Gateway — neither exists in this environment. To do it yourself: sign in to Power BI Desktop →
confirm a workspace → **File → Publish → Publish to Power BI**.
