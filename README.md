# 🌎 Climate Risk & Business Impact Analyzer

An end-to-end analytics pipeline that scores business-location climate risk from real historical
weather data and estimates financial impact under illustrative scenarios. Part of a 4-project data
analytics portfolio ([siblings](#related-projects) below); this repo is fully self-contained and
runs on its own.

**Stack**: Apache Airflow 3.3.1 (orchestration) → PostgreSQL 16 (storage) → Python/SQL (transforms
& analytics) → Streamlit + Plotly (dashboard) → Power BI (`.pbip` project included, unvalidated —
see [Power BI](#power-bi)).

## Data

- **Real**: daily temperature/precipitation/wind history for 10 US cities (~3 years), from
  [Open-Meteo](https://open-meteo.com)'s historical archive API — keyless, no account needed.
- **Synthetic**: each location's industry, revenue, and asset value are illustrative placeholders
  used to make the climate signal analyzable in business terms — not real company financials.

Full sourcing, licensing, and methodology detail: `docs/methodology.md`.

## Quick start

```bash
cp .env.example .env
# generate real secrets first -- Airflow 3's apiserver refuses to start without them:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # -> AIRFLOW_FERNET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"                                 # -> AIRFLOW_JWT_SECRET
# paste both into .env

docker compose up -d --build
docker compose ps   # confirm airflow-init exited 0, others healthy/starting
```

Airflow UI: http://localhost:8081 (`admin` / whatever `AIRFLOW_ADMIN_PASSWORD` you set).

```bash
docker compose exec airflow-scheduler airflow dags unpause climate_risk_pipeline
docker compose exec airflow-scheduler airflow dags trigger climate_risk_pipeline
```

Dashboard: http://localhost:8501 (works once the DAG completes one run — a few minutes).

Shut down (keeps data): `docker compose down`.

## Pipeline

`climate_risk_pipeline` DAG: check source availability → ensure schema → extract climate history
(Open-Meteo) + load business-location metadata → validate & load → compute risk scores (SQL) →
compute scenario financial impact (SQL) → build Power BI views → data-quality check. Idempotent —
every table has a natural-key primary key, so reruns upsert rather than duplicate.

## What the numbers mean

Risk score (0-100) is a transparent, documented heuristic — not a certified climate risk model.
Financial impact scenarios (mild/moderate/severe) use illustrative multipliers, not an
actuarial/insurance model. Full formulas and explicit limitations: `docs/methodology.md`.

## Power BI

A real `.pbip` project (`powerbi/ClimateRisk.pbip`) exists with the complete data model — 3
tables, 2 relationships, 8 DAX measures, all reconciled against the SQL above — but **it has never
been opened in Power BI Desktop, so it isn't validated.** The 4 report pages exist but have no
visuals yet (hand-authoring visual JSON blind was judged too unreliable to fake). Open the file
yourself to find out if it loads; if so, the model/measures are ready and only layout remains — see
`docs/powerbi_guide.md` for exact page-by-page instructions, DAX, and the color system.

## Documentation

`docs/methodology.md` (formulas, sourcing, limitations) · `docs/powerbi_guide.md` (Power BI build
guide) · `docs/database_schema.md` (table reference) · `docs/data_sources.md`.

## Related projects

Part of a 4-project portfolio, each in its own self-contained repo: Dark Store Intelligence,
AI Hiring Bias Detector, Fraud Pattern Evolution Tracker.
