import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd


def load_crm_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = [data]
    df = pd.DataFrame(data)
    df["__source"] = "crm"
    return df


def load_orders_csv(path):
    df = pd.read_csv(path, dtype=str)
    df["__source"] = "orders"
    return df


def load_support_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()
    rows = []
    for node in root.findall(".//customer"):
        row = {}
        for child in list(node):
            row[child.tag] = (child.text or "").strip()
        if row:
            rows.append(row)
    df = pd.DataFrame(rows)
    df["__source"] = "support"
    return df


def ingest_all(base_dir, config):
    base = Path(base_dir)
    sources = config["input_sources"]
    crm = load_crm_json(base / sources["crm"])
    orders = load_orders_csv(base / sources["orders"])
    support = load_support_xml(base / sources["support"])
    return {"crm": crm, "orders": orders, "support": support}
