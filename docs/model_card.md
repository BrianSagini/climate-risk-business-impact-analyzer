# Model card — monthly risk model

## The sample-size problem, and how it was resolved

`climate_risk.risk_scores` is one row per location per year — verified live against Postgres:
`SELECT COUNT(*) FROM climate_risk.risk_scores` returns **40** (10 locations × 4 partial-to-full
years, 2023–2026). A train/test split on 40 rows (something like 30 train / 10 test) isn't a
statistically honest evaluation of a gradient-boosted model — whatever R² came out of it would be
closer to noise than signal, and reporting it as a real result would misrepresent what a sample
that size can actually support.

**Fix**: engineer both the features and the target at monthly grain from `daily_climate` instead.
Verified live: `daily_climate` has **11,030** rows, 10 locations, real dates from **2023-09-11** to
**2026-09-17**. Grouped by `(location_id, month)` that's **370** location-months. The first and
last calendar month per location are partial — 20 days for September 2023, 17 days for September
2026 (the archive's actual start/end dates), against a full month of ~30 — and a partial month
structurally has fewer extreme-heat/heavy-precip days than a full one for reasons that have
nothing to do with climate, so those 20 partial location-months (2 per location × 10 locations)
are dropped. That leaves **350 real, full-month rows** (Oct 2023 – Aug 2026) — an honestly-sized
sample for a 3-feature regression, roughly 9x the annual table's row count.

## Data

Real daily weather (`temp_max_c`, `precipitation_mm`) from Open-Meteo, same source as the rest of
this project — see `docs/data_sources.md`. Business fields (`asset_value_usd` etc.) are not used by
this model at all; it predicts `risk_score`, not `estimated_impact_usd`, for the reason below.

**Target**: `risk_score`, not `estimated_impact_usd`. `estimated_impact_usd` is a deterministic
transform of `risk_score` (`(risk_score/100) * asset_value_usd * scenario_multiplier`, all three
right-hand terms already known exactly) — modeling it directly would just be re-deriving
multiplication a model already has perfect information to do, not a real prediction problem.
`risk_score` is the actual quantity with a non-trivial relationship to weather.

**Split**: time-based, not random. Train = the monthly frame's first 24 months per location
(Oct 2023 – Sep 2025, **240 rows**). Test = the last 11 months per location (Oct 2025 – Aug 2026,
**110 rows**), held out completely. A random split would let e.g. July 2025's weather leak into a
June 2025 test fold; no model that predicts risk from weather gets evaluated on months adjacent to
ones it trained on, so this project doesn't either.

## Features and target — what "monthly" actually means here

The existing formula (`docs/methodology.md`) computes 3 ingredients once a year:
`extreme_heat_days`, `heavy_precip_days`, `temp_anomaly_c` — then combines them into `risk_score`.
This model uses the **same 3 ingredients, recomputed at monthly grain** directly from
`daily_climate` (not derived from the annual table): `extreme_heat_days`/`heavy_precip_days` counted
within each calendar month, and `temp_anomaly_c` as that month's average daily high minus the
location's baseline (its earliest calendar year on record — the identical baseline definition
`sql/002_risk_scores.sql` uses, just compared against a month instead of a year).

The **target**, `monthly_risk_score`, reapplies the exact same formula shape to these monthly
ingredients: `LEAST(100, heat*1.5 + precip*2.0 + GREATEST(anomaly,0)*10)`. That's a real, useful
quantity in its own right — "what would this location's risk look like scored every month instead
of once a year" — not an arbitrary invented label.

**Why the model's R² against this target is expected to be very high, and why that's not the
interesting result**: the target is a near-linear, deterministic function of the exact 3 features
the model is given. A flexible model reproducing a formula it was handed the exact inputs to is not
a meaningful win — it's expected, and reported as such below, not spun as a triumph. The genuinely
informative comparison is against a baseline that **doesn't** get monthly information (next
section).

## The baseline: the real annual formula, applied where it wasn't designed to be

The comparison point is the **actual annual `risk_score`** already stored in
`climate_risk.risk_scores` for each `(location, year)` — the real, already-computed formula output
— repeated across every test month that falls in that year. This is a fair, non-circular
comparison: the baseline never sees a single day of the test month's actual weather, only last
year's already-computed number; the model sees that month's real heat/precip/anomaly. It is exactly
"the existing formula's actual output" the task asked to compare against, evaluated at the
resolution a user would actually want a risk read at (this month), not the resolution it was built
for (this year).

## Results — real, from this run

Both evaluated against `monthly_risk_score` on the same 110 held-out test rows:

| Model | MAE | R² |
|---|---|---|
| `xgboost_monthly_risk_model` | **0.83** | **0.999** |
| `annual_formula_baseline` (real annual `risk_score`, repeated per month) | 37.48 | −0.44 |

The baseline's negative R² means it does worse than just predicting the test set's mean every
time — worth stating plainly rather than softening. The reason isn't that the annual number is
wrong; it's that a single yearly figure is a poor predictor of any *individual* month once you look
at the actual distribution: the test months' `monthly_risk_score` has a median of 22.5 and a 25th
percentile of 0.5 (most winter months score near 0), while the same test period's annual formula
values average 61.7 with a much narrower spread (std 30.9 vs. 39.6) — an annual average sits in the
middle of a distribution that's actually bimodal month to month (near 0 in winter, near 100 in
summer for the hottest locations), so it's systematically wrong in both directions rather than
occasionally close. `docs/evidence/climate_predicted_vs_actual.png` shows this directly: the
model's points hug the diagonal; the baseline's are scattered across the full vertical range
regardless of the actual value.

**Rollup sanity check**: averaging the model's test-period monthly predictions back up to
`(location, year)` and comparing to that location-year's real annual `risk_score` gives a rollup
MAE of **29.84** across 20 location-years touched by the test window. This number is a much
rougher check than the headline comparison above — the test window (Oct 2025–Aug 2026) never
covers a *full* calendar year for any location, so some location-years in this rollup are averaged
over as few as 3 or 8 test-period months, not 12. Treat it as a sanity check that the model's
predictions are in a plausible annual range, not a rigorous annual-accuracy claim.

## What drives the model's predictions

XGBoost feature importance on the monthly model: `temp_anomaly_c` **0.986**, `extreme_heat_days`
0.008, `heavy_precip_days` 0.006. This lopsided split isn't a modeling artifact — it's a direct
consequence of the formula's own coefficients. At monthly grain, `temp_anomaly_c`'s `×10`
multiplier applied to a range up to ~19.4°C can contribute as much as **194** points to the
pre-clip score, while `extreme_heat_days×1.5` tops out at 46.5 and `heavy_precip_days×2.0` at 14 —
anomaly simply has far more room to move the score than the other two ingredients do, so a model
fit to reproduce the formula correctly learns to lean on it almost exclusively. 17.7% of the 350
monthly rows hit the `LEAST(100, ...)` cap outright. See
`docs/evidence/climate_feature_importance.png`.

## Intended use

A methodology demonstration — an honestly-sized time-based split, and a real, non-circular
comparison against the production formula at a resolution it wasn't built for — not a fielded
climate-risk model. The target it was trained on (`monthly_risk_score`) is itself a synthetic
heuristic, not a scientifically validated risk quantity (see `docs/methodology.md`'s existing
limitations on the annual formula, which all still apply here).

## Comparison against automated model search

As a sanity check on the single hand-configured XGBoost model above, `climate_risk_model.ipynb`
also runs H2O AutoML (community edition, local-only, not part of the Airflow pipeline) over the
exact same `train`/`test` frames and the same 3 features, `max_models=20`. Its leader — a
grid-searched GBM — reaches **MAE 0.9215, R2 0.9967** on this project's real held-out test set,
computed the same way as every other number in this card. The hand-picked model is slightly
*better* on both (MAE 0.825, R2 0.9986): the automated search didn't find anything that beats the
model already used. Two real caveats on the search itself: H2O's own XGBoost backend wasn't
available on this machine and was skipped automatically, and one GBM configuration in H2O's grid
failed outright with `the dataset size is too small to split for min_rows=100.0: must have at
least 200.0 (weighted) rows, but have only 192.0` — an independent, automated confirmation of this
card's own small-sample caveat below: 240 training rows works for the specific 3-feature model
used here, but leaves no headroom for every default hyperparameter grid H2O tries.

**Seeing real predictions**: the notebook also exports the exact test frame every model above was
scored against to `h2o_saved_models/test_frame.csv` (target column included), and
`view_all_ml_in_h2o.py` (outside this repo, local-only) loads it into Flow as `climate_test_frame`
alongside the saved models. In Flow: Models → pick a model (e.g. the leader named in the table
above) → Predict → select `climate_test_frame` → Flow computes and displays a real predictions
table for that model against that data, comparable directly to the `monthly_risk_score` column
already in the frame.

## Known limitations

- **Still a small sample.** 350 rows (240 train) is an honest improvement over the annual table's
  40, but it's still not a large dataset for a 3-feature model — 10 locations contribute strongly
  correlated, overlapping months (each location's weather is autocorrelated month to month), so the
  effective number of independent observations is smaller than 350 suggests.
- **The headline R² is structurally expected, not a discovery.** The model was hard to *not* fit
  well here — its target is a near-linear function of its exact 3 inputs. This is stated plainly
  above rather than presented as an unqualified win.
- **The baseline's poor showing is about resolution mismatch, not the formula being wrong.** The
  annual `risk_score` does what it was designed to do (summarize a year); this model card is not a
  claim that the annual formula is bad at its actual job, only that a single yearly number is a
  poor stand-in for month-specific risk.
- **`temp_anomaly_c`'s baseline-year limitation carries over.** The baseline year (2023) only has
  Sep–Dec data in this archive, the same pre-existing limitation `docs/methodology.md` already
  documents for the annual formula — this monthly version inherits it unchanged, it doesn't fix or
  worsen it.
- **No hyperparameter search.** `n_estimators=150, max_depth=3` was chosen to match the problem's
  small size and few features, not tuned via a validation sweep.
- **The rollup annual comparison is approximate**, for the reasons stated above (partial-year
  coverage in the test window).
