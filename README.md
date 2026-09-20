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

The AutoML sanity-check cells at the end of `climate_risk_model.ipynb` are optional and
local-only — they're not part of the Airflow DAG or the container image. Running them needs
`pip install -r requirements-notebooks.txt` in a local virtualenv plus a JVM on your machine (H2O
starts its own local Java process); skip that cell block entirely if you don't have Java installed.

## Architecture

One DAG, `climate_risk_pipeline`: check the weather source is reachable → ensure the schema
exists → pull climate history from Open-Meteo and load the business-location metadata → validate
and load → compute risk scores in SQL → compute scenario financial impact in SQL → train the
monthly risk model → build the Power BI views → a data-quality gate at the end. Every table keys
on something natural, so re-running the DAG upserts instead of duplicating rows — I wanted it safe
to trigger twice by accident.

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

## Machine learning

`climate_risk.risk_scores` is one row per location per year — 40 rows total, verified live. That's
too few to honestly train and evaluate a gradient-boosted model: a 30/10-ish split on 40 rows would
produce an R² closer to noise than signal, and I'd rather say that plainly than report a number
from a split that small. The fix: engineer the same 3 ingredients the annual formula already uses
(`extreme_heat_days`, `heavy_precip_days`, `temp_anomaly_c`) at **monthly** grain straight from
`daily_climate` instead of reusing the sparse annual table — 370 location-months, minus 20 partial
ones at each end of the archive window (a 17-day September has structurally fewer heat/precip days
than a full one, for reasons that have nothing to do with climate), leaves **350 real rows**. Full
reasoning and exact counts: `docs/model_card.md`.

I trained an XGBoost regressor on those 350 rows (240 train / 110 test, time-based split — train on
Oct 2023–Sep 2025, test on Oct 2025–Aug 2026, never random) predicting `risk_score` from the 3
weather ingredients, and compared it against the real, already-computed annual `risk_score` applied
where it wasn't designed to be: repeated across every month of its year, on the same held-out
months.

| Model | MAE | R² |
|---|---|---|
| XGBoost (monthly features) | **0.83** | **0.999** |
| Annual formula, repeated per month | 37.48 | −0.44 |

I want to be upfront about what this comparison does and doesn't show. The model's near-perfect R²
isn't really a discovery — its target is a near-linear function of the exact 3 features it's given,
so a flexible model fitting it well is expected, not a triumph, and I'm saying so rather than
presenting it as one. The actually informative result is *why* the baseline does so badly: the test
months' real risk levels are bimodal — near 0 in winter, near 100 in summer for the hottest
locations, median 22.5 — while the annual figure is a single smoothed number sitting in the middle
(mean 61.7) that's systematically wrong in both directions once you look at any individual month.
`docs/evidence/climate_predicted_vs_actual.png` shows it directly: the model's points hug the
diagonal, the baseline's are scattered top to bottom regardless of the actual value. Feature
importance backs this up for a structural reason, not a surprising one — `temp_anomaly_c` gets
98.6% of the weight, `extreme_heat_days` and `heavy_precip_days` split the rest, because the
formula's own coefficients give anomaly up to 194 points of pre-clip range against 46.5 and 14 for
the other two — the model correctly discovered which lever the formula itself leans on hardest.

This training run is a real Airflow task (`train_risk_model`, wired into `climate_risk_pipeline`
right after `compute_financial_impact` and before the Power BI views), not a notebook run in
isolation — it writes both models' metrics to `climate_risk.model_evaluation` and the XGBoost
model's test-set predictions to `climate_risk.risk_model_predictions`. `climate_risk_model.ipynb`
is the same analysis end to end (EDA, features, training, evaluation) calling the exact same
`pipeline.py` functions the DAG does. Predicted-vs-actual scatter, the MAE/R² comparison, and
feature importance are real images from this exact run, in `docs/evidence/`.

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

`docs/methodology.md`, `docs/model_card.md` (the monthly risk model), `docs/powerbi_guide.md`,
`docs/database_schema.md`, `docs/data_sources.md`.

## The rest of the portfolio

Dark Store Intelligence, AI Hiring Bias Detector, Fraud Pattern Evolution Tracker — each its own
self-contained repo, same stack, different domain.
