import json
import sqlite3
import xml.etree.ElementTree as ET

from src.config import load_config
from src.ingest import ingest_all, load_support_xml
from src.pipeline import run_pipeline
from src.quality import run_quality
from src.transform import standardize_df


def test_ingest_all_loads_three_sources(tmp_path):
    (tmp_path / "crm.json").write_text('[{"customer_id":"C0001","name":"A","email":"a@b.com"}]', encoding="utf-8")
    (tmp_path / "orders.csv").write_text("cust_id,lifetime_value\nC0001,100\n", encoding="utf-8")
    root = ET.Element("customers")
    c = ET.SubElement(root, "customer")
    ET.SubElement(c, "customerId").text = "C0001"
    ET.SubElement(c, "tickets").text = "2"
    ET.ElementTree(root).write(tmp_path / "support.xml", encoding="utf-8")
    cfg = {"input_sources": {"crm": "crm.json", "orders": "orders.csv", "support": "support.xml"}}
    raw = ingest_all(tmp_path, cfg)
    assert set(raw) == {"crm", "orders", "support"}
    assert raw["crm"].iloc[0]["customer_id"] == "C0001"
    assert raw["support"].iloc[0]["customerId"] == "C0001"


def test_schema_standardization_maps_ids_and_tickets():
    raw = ingest_all("C:/Users/Admin/OneDrive/Desktop/Akasa Air-Round 2/DE-Customer360", load_config("C:/Users/Admin/OneDrive/Desktop/Akasa Air-Round 2/DE-Customer360"))
    orders = standardize_df(raw["orders"], "orders")
    support = standardize_df(raw["support"], "support")
    assert "customer_id" in orders.columns
    assert "customer_id" in support.columns
    assert "support_tickets" in support.columns
    assert "last_ticket_date" in support.columns


def test_quality_checks_detect_expected_issue_classes():
    base = "C:/Users/Admin/OneDrive/Desktop/Akasa Air-Round 2/DE-Customer360"
    cfg = load_config(base)
    raw = ingest_all(base, cfg)
    std = {k: standardize_df(v, k) for k, v in raw.items()}
    report, samples = run_quality(raw, std, cfg)
    for key in ["total_records", "duplicates", "invalid_emails", "missing_fields", "negative_revenue", "invalid_customer_ids"]:
        assert key in report
    assert report["duplicates"] >= 1
    assert report["invalid_emails"] >= 1
    assert report["negative_revenue"] >= 1
    assert report["invalid_customer_ids"] >= 1
    assert not samples.empty
    assert "issue_reason" in samples.columns


def test_pipeline_creates_outputs_and_sqlite(tmp_path):
    base = "C:/Users/Admin/OneDrive/Desktop/Akasa Air-Round 2/DE-Customer360"
    cfg = load_config(base)
    cfg = json.loads(json.dumps(cfg))
    cfg["output_dir"] = str(tmp_path / "out")
    cfg["db_path"] = str(tmp_path / "out" / "customer360.db")
    cfg["log_path"] = str(tmp_path / "logs" / "pipeline.log")
    result = run_pipeline(base, cfg)
    assert (tmp_path / "out" / "customer_360.json").exists()
    assert (tmp_path / "out" / "data_quality_report.json").exists()
    assert result["report"]["successful_records"] > 0
    with sqlite3.connect(tmp_path / "out" / "customer360.db") as con:
        count = con.execute("select count(*) from customer_360").fetchone()[0]
    assert count == len(result["customer360"])
