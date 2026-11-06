import json
import sqlite3
from pathlib import Path

import pandas as pd


def _conn(base_dir, db_path):
    path = Path(base_dir) / db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def write_outputs(base_dir, db_path, customer360, report, insights, issue_samples):
    with _conn(base_dir, db_path) as con:
        customer360.to_sql("customer_360", con, if_exists="replace", index=False)
        pd.DataFrame([report]).to_sql("data_quality_report", con, if_exists="replace", index=False)
        insights["top10_revenue"].to_sql("top10_revenue", con, if_exists="replace", index=False)
        insights["segments"].to_sql("segments", con, if_exists="replace", index=False)
        insights["support_risk"].to_sql("support_risk", con, if_exists="replace", index=False)
        insights["regional"].to_sql("regional_analytics", con, if_exists="replace", index=False)
        (issue_samples if not issue_samples.empty else pd.DataFrame(columns=["issue_reason", "issue_source"])).to_sql(
            "quality_issues", con, if_exists="replace", index=False
        )


def read_table(base_dir, db_path, table):
    path = Path(base_dir) / db_path
    if not path.exists():
        return pd.DataFrame()
    with sqlite3.connect(path) as con:
        try:
            return pd.read_sql_query(f"SELECT * FROM {table}", con)
        except Exception:
            return pd.DataFrame()


def read_report(base_dir, db_path):
    df = read_table(base_dir, db_path, "data_quality_report")
    return df.iloc[0].to_dict() if not df.empty else {}
