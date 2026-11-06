# DE-Customer 360 — Work Summary

## Goal
Build the **Data Engineering Assignment: E-Commerce Data Pipeline** as instructed: ingest JSON/CSV/XML, standardize schemas, merge a unified Customer 360 profile, run data quality checks, generate business insights/reports, and deliver an interactive Streamlit dashboard (Python, simple stack, deployable; Docker chosen).

## Inputs used (provided)
Located in `DE-Customer360/`:
- `crm_customers.json` — CRM source (501 records in provided data). Fields include `customer_id, name, email, city, registration_date`.
- `orders.csv` — Order Management source (500 records). Fields `cust_id, total_orders, lifetime_value, last_order_date`.
- `support_tickets.xml` — Support source (500 records). Fields `customerId, tickets, lastTicketDate`.

## What was built

### 1. Configuration-driven pipeline
- `config.json` defines `input_sources` (CRM/Orders/Support), output/DB/log paths, required fields, segmentation thresholds, and support-risk threshold.

### 2. Ingestion (`src/ingest.py`)
- Loads CRM JSON arrays, Orders CSV, and Support XML `<customer>` nodes into DataFrames.

### 3. Schema standardization (`src/transform.py`)
- Canonical merge key: `cust_id` / `customerId` / variants → `customer_id`.
- Support fields: `tickets` → `support_tickets`, `lastTicketDate` → `last_ticket_date`.
- Normalization: trims IDs, lowercases/trims emails, casts numeric fields, parses dates to ISO format.
- Includes a **lineage map** (`get_lineage`) showing unified field, source, raw field names, and transform.

### 4. Data quality checks (`src/quality.py`)
Identifies and reports:
- Duplicate CRM `customer_id` records
- Invalid email formats
- Missing mandatory fields (configurable; default `customer_id,name,email`)
- Negative revenue/lifetime values
- Invalid `customer_id` values
- Orphan order/support IDs not found in CRM (reported for traceability)

Produces:
- Summary report JSON with `total_records, duplicates, invalid_emails, missing_fields, negative_revenue, invalid_customer_ids, orphan_order_ids, orphan_support_ids, successful_records`.
- Drill-down issue samples (`quality_issues.csv`) with reasons/sources.

`successful_records` = unified CRM-based Customer 360 records whose required fields pass.

### 5. Customer 360 merge (`src/merge.py`)
- Merges standardized sources on `customer_id` (CRM master; orders/support joined).
- Unified dataset fields: `customer_id, name, email, city, registration_date, total_orders, lifetime_value, last_order_date, support_tickets, last_ticket_date`.

### 6. Insights (`src/insights.py`)
- **Revenue analytics:** Top 10 customers by `lifetime_value`.
- **Segmentation:** Gold `> 100000`, Silver `50000–100000`, Bronze `< 50000` (configurable; boundary handled intentionally).
- **Support insights:** customers with `support_tickets > 5`.
- **Regional analytics:** revenue by city, customer count by city.

### 7. Orchestration, logging, storage (`src/pipeline.py`, `src/config.py`, `src/db.py`)
- `run_pipeline()` executes staged flow: ingest → standardize → quality → merge → insights → persist outputs.
- Python logging to console and `logs/pipeline.log`.
- Outputs written to `data/output/`: `customer_360.json/csv`, `data_quality_report.json`, `quality_issues.csv`, `top10_revenue.csv`, `segments.csv`, `support_risk.csv`, `regional_analytics.csv`, `run_summary.json`.
- Curated outputs also stored in SQLite `data/output/customer360.db`.

### 8. Streamlit dashboard (`app.py`) — interactive/creative UI
Tabs:
- **Overview:** KPI cards, segment mix donut (Gold/Silver/Bronze actual counts), pipeline stage timing, lifetime value distribution histogram.
- **Data Quality Cockpit:** DQ score gauge, issue breakdown, filterable drill-down of bad records, raw report.
- **DQ Resolution Workflow (add-on):** triage detected issues as `Open/Reviewed/Fixed`, add reviewer comments, filter/search issues, view resolution status chart, and export `dq_resolution_report.csv/json`. On Streamlit Cloud, export preserves workflow state for the demo.
- **Customer 360 Explorer:** search, segment/city filters, `>5 tickets` filter, profile metrics, activity timeline.
- **Data Operations (add-on):** operate on a session working copy of unified data — search/filter, edit fields, mark rows `Keep/Review/Delete`, remove deleted rows, reset to pipeline output, and export working/active datasets plus `data_operations_audit.json`. Source files are never modified; on Streamlit Cloud, downloads are the persistence mechanism.
- **Insights Lab:** Top 10 revenue chart/table, segment revenue contribution, revenue/customer count by city, support-vs-revenue scatter, `>5 tickets` risk table.
- **Lineage & Exports:** schema/source lineage and download buttons for all run artifacts/log.

Includes **Run / Refresh Pipeline** control and cache/session refresh to avoid stale analytics.

### 9. Tests + CI (`tests/test_pipeline.py`, `.github/workflows/tests.yml`)
Pytest coverage for:
- Multi-source ingestion
- Schema standardization (`cust_id/customerId` mapping, support field rename)
- Quality-check detection on provided data
- End-to-end pipeline output + SQLite persistence

GitHub Actions workflow (`.github/workflows/tests.yml`) runs `pytest` on pushes/PRs affecting `DE-Customer360/**` using Python 3.11 with `PYTHONPATH=.`.

### 10. Deployment/packaging
- `requirements.txt` — `streamlit`, `pandas`, `plotly`, `pytest`.
- `Dockerfile` — Python 3.11 slim, installs deps, runs Streamlit on port `8501`.
- `docker-compose.yml` — builds service, maps `8501:8501`, mounts `data/output` and `logs`.
- `.dockerignore` / `.gitignore` — excludes venv, caches, local DB/log artifacts as appropriate.
- `README.md` — setup, run, test, Docker, outputs.

## Verified results (on provided dataset)
Pipeline smoke run/test results:
- Source records: CRM 501, Orders 500, Support 500 (`total_records 1501`)
- Unified customers: 500
- DQ findings: `duplicates 1, invalid_emails 3, missing_fields 0, negative_revenue 1, invalid_customer_ids 1, orphan_order_ids 0, orphan_support_ids 0, successful_records 500`
- Segments (actual data): **Gold 318, Silver 101, Bronze 81**
- Support tickets range 0–12; **269 customers with >5 tickets**
- `pytest -q` → **4 passed**
- Core modules compile successfully

## How to run
Local:
```powershell
cd DE-Customer360
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH='.'
streamlit run app.py
```
Open `http://localhost:8501` and click **Run / Refresh Pipeline**.

Docker:
```powershell
cd DE-Customer360
docker compose up --build
```

## Notes
- I could not view user-attached screenshot images in this environment; dashboard/data issues reported were addressed by validating actual source/output data and fixing stale-cache/visualization behavior.
- **Data Operations** and **DQ Resolution** are demo-grade interactive workflows: they work in-session and provide exports. Durable persistence on Streamlit Cloud would require an external database (e.g., Supabase/Postgres).
- Docker build was not executed in this environment, but Docker packaging files were created and the Python/Streamlit app was verified locally via compile/tests/smoke run.
- For public recruiter sharing, deploy via Streamlit Community Cloud from the GitHub repo; GitHub Actions will run pytest on pushes/PRs.
