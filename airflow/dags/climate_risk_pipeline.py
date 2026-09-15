"""Climate Risk & Business Impact Analyzer -- Airflow DAG.

extract (Open-Meteo, keyless) -> validate -> load -> SQL risk scoring ->
SQL scenario financial impact -> data-quality check.

Business exposure data (industry/revenue/asset value) is synthetic --
see projects/01_climate_risk_business_impact/pipeline.py and
docs/data_sources.md.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import pandas as pd
import pendulum
import requests
from airflow.sdk import DAG, task

import pipeline
from shared.database import get_engine


with DAG(
    dag_id="climate_risk_pipeline",
    description="Ingest Open-Meteo climate history, score business climate risk, estimate financial impact",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=15),
        "execution_timeout": timedelta(minutes=20),
    },
    tags=["climate", "project-01"],
) as dag:

    @task
    def check_source_available() -> bool:
        resp = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": 0, "longitude": 0,
                "start_date": "2024-01-01", "end_date": "2024-01-01",
                "daily": "temperature_2m_max",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True

    @task
    def ensure_schema() -> None:
        from shared.database import run_sql_file
        run_sql_file(os.path.join(os.path.dirname(pipeline.__file__), "sql", "001_schema.sql"))

    @task
    def load_locations() -> int:
        return pipeline.load_locations()

    @task
    def extract_climate() -> str:
        df = pipeline.extract_all_locations()
        tmp_path = os.path.join(tempfile.gettempdir(), "climate_risk_extract.parquet")
        df.to_parquet(tmp_path)
        return tmp_path

    @task
    def validate_and_load(raw_path: str) -> int:
        df = pd.read_parquet(raw_path)
        report = pipeline.validate_climate(df)
        report.raise_if_invalid(max_invalid_ratio=0.02)
        clean_df = df.drop(index=list(report.invalid_row_indices))
        return pipeline.load_daily_climate(clean_df)

    @task
    def compute_risk_scores(_rows_loaded: int) -> int:
        return pipeline.compute_and_load_risk_scores()

    @task
    def compute_financial_impact(_risk_rows: int) -> int:
        return pipeline.compute_and_load_financial_impact()

    @task
    def create_powerbi_views(_impact_rows: int) -> None:
        from shared.database import run_sql_file
        run_sql_file(os.path.join(os.path.dirname(pipeline.__file__), "sql", "004_powerbi_views.sql"))

    @task
    def data_quality_check(_views_done: None) -> None:
        engine = get_engine()
        with engine.connect() as conn:
            null_scores = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM climate_risk.risk_scores WHERE risk_score IS NULL"
            ).scalar()
            latest_date = conn.exec_driver_sql(
                "SELECT MAX(date) FROM climate_risk.daily_climate"
            ).scalar()
        if null_scores:
            raise ValueError(f"{null_scores} risk_scores rows have NULL risk_score")
        if latest_date is None:
            raise ValueError("daily_climate is empty after load")
        staleness = (datetime.now().date() - latest_date).days
        if staleness > 10:
            raise ValueError(f"daily_climate is stale: latest date is {latest_date} ({staleness} days old)")

    src_ok = check_source_available()
    schema = ensure_schema()
    locs = load_locations()
    raw_path = extract_climate()
    loaded = validate_and_load(raw_path)
    risk = compute_risk_scores(loaded)
    impact = compute_financial_impact(risk)
    views = create_powerbi_views(impact)
    dq = data_quality_check(views)

    src_ok >> schema
    schema >> locs
    schema >> raw_path
    locs >> loaded
    raw_path >> loaded
    loaded >> risk >> impact >> dq
