#!/usr/bin/env python3
"""Run a SQL file from sql/ on BigQuery, filling in {{BQ_PROJECT}} and {{BQ_DATASET}}, and optionally write the result to a CSV.

Project and dataset come from --project/--dataset or the BQ_PROJECT / BQ_DATASET environment variables (nothing is hard-coded).
The query reads the public ORCID table `ds-open-datasets.orcid.summaries_2026` (override with {{ORCID_TABLE}} via --orcid-table or ORCID_TABLE).

Usage: BQ_PROJECT=my-project BQ_DATASET=my_dataset python3 scripts/run_bq.py sql/fr_coauthor_edges.sql --out output_2005/fr_coauthor_edges_orcid.csv
Needs `gcloud auth application-default login` and `pip install google-cloud-bigquery pandas db-dtypes`.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def render(sql: str, values: dict[str, str]) -> str:
    for k, v in values.items():
        sql = sql.replace("{{" + k + "}}", v)
    if "{{" in sql:
        sys.exit("Unfilled placeholder in SQL: " + sql[sql.index("{{"):][:40])
    return sql


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sql", type=Path)
    ap.add_argument("--project", default=os.environ.get("BQ_PROJECT"))
    ap.add_argument("--dataset", default=os.environ.get("BQ_DATASET"))
    ap.add_argument("--orcid-table", default=os.environ.get("ORCID_TABLE", "ds-open-datasets.orcid.summaries_2026"))
    ap.add_argument("--out", type=Path, help="write the result to this CSV")
    ap.add_argument("--dry-run", action="store_true", help="print the rendered SQL and exit")
    a = ap.parse_args()
    if not a.project or not a.dataset:
        sys.exit("Set --project/--dataset or BQ_PROJECT/BQ_DATASET")
    sql = render(a.sql.read_text(), {"BQ_PROJECT": a.project, "BQ_DATASET": a.dataset, "ORCID_TABLE": a.orcid_table})
    if a.dry_run:
        print(sql)
        return
    from google.api_core.exceptions import GoogleAPICallError
    from google.cloud import bigquery

    try:
        df = bigquery.Client(project=a.project).query(sql).to_dataframe()
    except GoogleAPICallError as e:
        sys.exit(f"BigQuery error: {e}")
    print(f"{len(df):,} rows")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(a.out, index=False)
        print("wrote", a.out)


if __name__ == "__main__":
    main()
