import re
import pandas as pd

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ID_RE = re.compile(r"^C\d+$")


def _issue(df, mask, reason, source):
    if mask is None or not mask.any():
        return pd.DataFrame()
    out = df.loc[mask].copy()
    out["issue_reason"] = reason
    out["issue_source"] = source
    keep = [c for c in ["customer_id", "name", "email", "city", "total_orders", "lifetime_value", "support_tickets", "issue_reason", "issue_source"] if c in out.columns]
    return out[keep]


def run_quality(raw, standardized, config):
    crm = standardized["crm"].copy()
    orders = standardized["orders"].copy()
    support = standardized["support"].copy()
    required = config.get("required_fields", ["customer_id", "name", "email"])

    samples = []
    duplicate_mask = crm["customer_id"].notna() & crm["customer_id"].duplicated(keep="first") if "customer_id" in crm.columns else pd.Series(False, index=crm.index)
    duplicates = int(duplicate_mask.sum())
    samples.append(_issue(crm, duplicate_mask, "Duplicate CRM customer_id", "crm"))

    invalid_email_mask = pd.Series(False, index=crm.index)
    if "email" in crm.columns:
        email = crm["email"].fillna("").astype(str)
        invalid_email_mask = crm["customer_id"].notna() & ~email.str.match(EMAIL_RE)
    invalid_emails = int(invalid_email_mask.sum())
    samples.append(_issue(crm, invalid_email_mask, "Invalid email format", "crm"))

    missing_mask = pd.Series(False, index=crm.index)
    for field in required:
        if field in crm.columns:
            series = crm[field]
            missing_mask |= series.isna() | (series.astype(str).str.strip() == "")
        else:
            missing_mask |= True
    missing_fields = int(missing_mask.sum())
    samples.append(_issue(crm, missing_mask, "Missing mandatory field", "crm"))

    negative_mask = pd.Series(False, index=orders.index)
    if "lifetime_value" in orders.columns:
        negative_mask = orders["lifetime_value"].notna() & (orders["lifetime_value"] < 0)
    negative_revenue = int(negative_mask.sum())
    samples.append(_issue(orders, negative_mask, "Negative revenue/lifetime_value", "orders"))

    def invalid_id_mask(df):
        if "customer_id" not in df.columns:
            return pd.Series(True, index=df.index)
        cid = df["customer_id"].fillna("").astype(str).str.strip()
        return (cid == "") | ~cid.str.match(ID_RE)

    invalid_crm = invalid_id_mask(crm)
    invalid_orders = invalid_id_mask(orders)
    invalid_support = invalid_id_mask(support)
    samples.append(_issue(crm, invalid_crm, "Invalid customer_id", "crm"))
    samples.append(_issue(orders, invalid_orders, "Invalid customer_id", "orders"))
    samples.append(_issue(support, invalid_support, "Invalid customer_id", "support"))
    invalid_customer_ids = int(invalid_crm.sum() + invalid_orders.sum() + invalid_support.sum())

    orphan_orders = pd.Series(False, index=orders.index)
    orphan_support = pd.Series(False, index=support.index)
    if "customer_id" in crm.columns:
        known = set(crm.loc[~invalid_crm, "customer_id"].dropna().astype(str))
        if "customer_id" in orders.columns:
            orphan_orders = orders["customer_id"].notna() & ~orders["customer_id"].astype(str).isin(known)
        if "customer_id" in support.columns:
            orphan_support = support["customer_id"].notna() & ~support["customer_id"].astype(str).isin(known)
    samples.append(_issue(orders, orphan_orders, "Order customer_id not found in CRM", "orders"))
    samples.append(_issue(support, orphan_support, "Support customer_id not found in CRM", "support"))

    issue_samples = pd.concat([s for s in samples if not s.empty], ignore_index=True) if any(not s.empty for s in samples) else pd.DataFrame()
    total_records = sum(len(v) for v in raw.values())
    report = {
        "total_records": int(total_records),
        "duplicates": duplicates,
        "invalid_emails": invalid_emails,
        "missing_fields": missing_fields,
        "negative_revenue": negative_revenue,
        "invalid_customer_ids": invalid_customer_ids,
        "orphan_order_ids": int(orphan_orders.sum()),
        "orphan_support_ids": int(orphan_support.sum()),
    }
    return report, issue_samples
