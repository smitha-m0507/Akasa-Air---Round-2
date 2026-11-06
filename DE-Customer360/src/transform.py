import re
import pandas as pd

SCHEMA_MAP = {
    "cust_id": "customer_id",
    "customerId": "customer_id",
    "customerid": "customer_id",
    "customer_id": "customer_id",
    "lastTicketDate": "last_ticket_date",
    "lastticketdate": "last_ticket_date",
    "tickets": "support_tickets",
}


def _snake(name):
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name).strip())
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    return name.strip("_").lower()


def standardize_df(df, source):
    out = df.copy()
    rename = {}
    for col in out.columns:
        if col == "__source":
            continue
        key = SCHEMA_MAP.get(col) or SCHEMA_MAP.get(_snake(col)) or _snake(col)
        rename[col] = key
    out = out.rename(columns=rename)
    if "customer_id" in out.columns:
        out["customer_id"] = out["customer_id"].astype(str).str.strip()
        out.loc[out["customer_id"].isin(["nan", "None", ""]), "customer_id"] = pd.NA
    if "email" in out.columns:
        out["email"] = out["email"].astype(str).str.strip().str.lower()
        out.loc[out["email"].isin(["nan", "none", ""]), "email"] = pd.NA
    for col in ["total_orders", "lifetime_value", "support_tickets"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ["registration_date", "last_order_date", "last_ticket_date"]:
        if col in out.columns:
            parsed = pd.to_datetime(out[col], errors="coerce")
            out[col] = parsed.dt.strftime("%Y-%m-%d")
            out.loc[out[col].isin(["NaT", "nan"]), col] = pd.NA
    out["__source"] = source
    return out


LINEAGE = [
    {"unified_field": "customer_id", "source": "CRM/Orders/Support", "raw_fields": "customer_id, cust_id, customerId", "transform": "trim, canonical rename"},
    {"unified_field": "name", "source": "CRM", "raw_fields": "name", "transform": "passthrough"},
    {"unified_field": "email", "source": "CRM", "raw_fields": "email", "transform": "trim, lowercase"},
    {"unified_field": "city", "source": "CRM", "raw_fields": "city", "transform": "passthrough"},
    {"unified_field": "registration_date", "source": "CRM", "raw_fields": "registration_date", "transform": "ISO date parse"},
    {"unified_field": "total_orders", "source": "Orders", "raw_fields": "total_orders", "transform": "numeric cast"},
    {"unified_field": "lifetime_value", "source": "Orders", "raw_fields": "lifetime_value", "transform": "numeric cast"},
    {"unified_field": "last_order_date", "source": "Orders", "raw_fields": "last_order_date", "transform": "ISO date parse"},
    {"unified_field": "support_tickets", "source": "Support", "raw_fields": "tickets", "transform": "rename, numeric cast"},
    {"unified_field": "last_ticket_date", "source": "Support", "raw_fields": "lastTicketDate", "transform": "rename, ISO date parse"},
]


def get_lineage():
    return pd.DataFrame(LINEAGE)
