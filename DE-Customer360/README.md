# DE-Customer 360 — E-Commerce Data Pipeline

Unified customer pipeline for Akasa Air Round 2 / DE-Customer 360. It ingests CRM (`JSON`), Orders (`CSV`), and Support (`XML`), standardizes schemas, runs data quality checks, merges a Customer 360 dataset, generates business insights, and serves an interactive Streamlit dashboard.

## What it delivers
- **Ingestion**: `crm_customers.json`, `orders.csv`, `support_tickets.xml`
- **Schema standardization**: canonical `customer_id` mapping (`cust_id`, `customerId` → `customer_id`), `tickets`/`lastTicketDate` → `support_tickets`/`last_ticket_date`, type/date normalization
- **Data quality checks**: duplicates, invalid emails, missing mandatory fields, negative revenue, invalid customer IDs; also reports orphan order/support IDs
- **Unified Customer 360**: merged on `customer_id`, saved as JSON/CSV and SQLite
- **Insights**: top 10 customers by revenue, Gold/Silver/Bronze segmentation, customers with >5 tickets, revenue/customer count by city
- **Creative/recruiter-efficient UI**:
  - **Mission Control**: staged pipeline status, timing, source counts
  - **Data Quality Cockpit**: DQ score, issue breakdown, drill-down bad records
  - **Customer 360 Explorer**: searchable table, profile card, activity timeline
  - **Lineage & Exports**: schema/source map and run artifact downloads
- **Config-driven**: `config.json`
- **Logging**: `logs/pipeline.log`
- **Tests**: `pytest` coverage for ingestion, standardization, quality, outputs
- **Database**: SQLite (`data/output/customer360.db`) for curated outputs
- **Deployment**: Docker / Docker Compose

## Project structure
```text
DE-Customer360/
  app.py
  config.json
  requirements.txt
  Dockerfile
  docker-compose.yml
  src/
    config.py ingest.py transform.py quality.py merge.py insights.py pipeline.py db.py
  data/output/
  logs/
  tests/test_pipeline.py
```

## Run locally
```powershell
cd "C:\Users\Admin\OneDrive\Desktop\Akasa Air-Round 2\DE-Customer360"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH='.'
streamlit run app.py
```
Open `http://localhost:8501` and click **Run Pipeline**.

## Run tests
```powershell
cd "C:\Users\Admin\OneDrive\Desktop\Akasa Air-Round 2\DE-Customer360"
$env:PYTHONPATH='.'
python -m pytest -q
```

## Run with Docker
```powershell
cd "C:\Users\Admin\OneDrive\Desktop\Akasa Air-Round 2\DE-Customer360"
docker build -t de-customer360 .
docker run --rm -p 8501:8501 -v "${PWD}/data/output:/app/data/output" -v "${PWD}/logs:/app/logs" de-customer360
```
Or:
```powershell
docker compose up --build
```

## Generated outputs
- `data/output/customer_360.json`, `customer_360.csv`
- `data/output/data_quality_report.json`
- `data/output/quality_issues.csv`
- `data/output/top10_revenue.csv`, `segments.csv`, `support_risk.csv`, `regional_analytics.csv`
- `data/output/run_summary.json`
- `data/output/customer360.db`
- `logs/pipeline.log`

## Quality report shape
```json
{
  "total_records": 1501,
  "duplicates": 1,
  "invalid_emails": 3,
  "missing_fields": 0,
  "negative_revenue": 1,
  "invalid_customer_ids": 1,
  "orphan_order_ids": 0,
  "orphan_support_ids": 0,
  "successful_records": 500
}
```
`successful_records` counts unified CRM-based Customer 360 records whose required fields pass (`customer_id`, `name`, `email` by default).
