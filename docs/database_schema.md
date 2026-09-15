# Database Schema

Postgres 16, database `analytics`, schema `climate_risk`. A read-only role `analytics_ro` (used
by the Streamlit dashboard and Power BI) has `SELECT` on everything here.

| Table | Grain | Notes |
|---|---|---|
| `locations` | 1 row/location | real lat/lon; synthetic industry/revenue/asset_value (`is_synthetic_business_data`) |
| `daily_climate` | 1 row/location/day | real, from Open-Meteo |
| `risk_scores` | 1 row/location/year | SQL-computed heuristic (see `docs/methodology.md`) |
| `scenario_financial_impact` | 1 row/location/year/scenario | SQL-computed, 3 scenarios |
| `powerbi_summary`, `powerbi_trends`, `powerbi_financial_impact` | views | pure passthrough/join views for Power BI — same data as above, never recomputed |

Every fact table has a natural-key primary key (never a surrogate autoincrement id), so
`ON CONFLICT DO UPDATE` upserts make pipeline reruns idempotent by construction. SQL analytical
models live as plain `.sql` files in `sql/`, executed by dedicated Airflow tasks — never embedded
as Python strings.
