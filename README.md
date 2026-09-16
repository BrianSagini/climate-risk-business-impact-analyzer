# Climate Risk & Business Impact Analyzer

Ten US business locations, three years of real daily weather history, and a risk score I built
from scratch to turn temperature and precipitation extremes into something a business reader can
act on: a 0–100 score per location, and a dollar-figure financial impact estimate under three
severity scenarios. It's the first of four projects in a portfolio built around the same idea —
take a real orchestration/storage/BI stack and put a genuinely different analytical problem
through it each time (see [the rest of the portfolio](#the-rest-of-the-portfolio)).

The weather data is real, pulled from Open-Meteo's historical archive API. The business side —
each location's industry, revenue, asset value — is synthetic, sized to plausible ranges and
flagged explicitly in the schema (`is_synthetic_business_data = true`) so nobody mistakes it for
real company financials. Full sourcing and the exact risk-score and financial-impact formulas are
in `docs/methodology.md`.

**Stack**: Airflow 3.3.1 → PostgreSQL 16 → Python/SQL → Streamlit + Plotly → Power BI.

## Getting it running

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # -> AIRFLOW_FERNET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"                                 # -> AIRFLOW_JWT_SECRET
# paste both into .env

docker compose up -d --build
docker compose ps   # airflow-init should exit 0, everything else healthy/starting
```

Airflow's at http://localhost:8081. Once it's up:

```bash
docker compose exec airflow-scheduler airflow dags unpause climate_risk_pipeline
docker compose exec airflow-scheduler airflow dags trigger climate_risk_pipeline
```

Give it a few minutes, then the dashboard's live at http://localhost:8501.
`docker compose down` shuts it down without touching the data.

## Architecture

One DAG, `climate_risk_pipeline`: check the weather source is reachable → ensure the schema
exists → pull climate history from Open-Meteo and load the business-location metadata → validate
and load → compute risk scores in SQL → compute scenario financial impact in SQL → build the
Power BI views → a data-quality gate at the end. Every table keys on something natural, so
re-running the DAG upserts instead of duplicating rows — I wanted it safe to trigger twice by
accident.

## The risk score, honestly

```
risk_score = LEAST(100, extreme_heat_days*1.5 + heavy_precip_days*2.0 + GREATEST(temp_anomaly_c,0)*10.0)
```

I built this as a transparent heuristic, not a certified climate model, and I'd rather the formula
be sitting right here in the open than dressed up as something more authoritative. Financial
impact multiplies that score against asset value under mild/moderate/severe scenario multipliers
I chose to produce a believable spread — not an actuarial or insurance-grade loss model. The full
writeup, including where this would need real climatological data and real damage functions to be
production-grade, is in `docs/methodology.md`.

## Power BI

I hand-built the semantic model — 3 tables, 2 relationships, 8 DAX measures, checked field-by-field
against the SQL above — and the full 4-page, 22-visual report on top of it: cards, charts, tables,
a slicer, and a themed header/footer on every page. The palette is navy and teal for the neutral
data, amber and red held back specifically for warning and critical-risk signals, on a tinted
canvas behind white visual panels rather than Power BI's flat default white.

I opened every page in Desktop myself and confirmed each one renders with real data and the right
colors before I called this done — that's not a given with hand-authored `.pbip` files, and I ran
into real quirks doing it (a couple of visual properties that silently do nothing if they're in
the wrong spot in the JSON, a chart aggregation Power BI needs stated explicitly or it just renders
empty). Screenshots are in `docs/evidence/`; the full design reasoning and page layout are in
`docs/powerbi_guide.md`.

## Docs

`docs/methodology.md`, `docs/powerbi_guide.md`, `docs/database_schema.md`, `docs/data_sources.md`.

## The rest of the portfolio

Dark Store Intelligence, AI Hiring Bias Detector, Fraud Pattern Evolution Tracker — each its own
self-contained repo, same stack, different domain.
