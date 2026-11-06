import pandas as pd


def merge_customer360(standardized):
    crm = standardized["crm"].copy()
    orders = standardized["orders"].copy()
    support = standardized["support"].copy()

    if "customer_id" in crm.columns:
        crm = crm.drop_duplicates(subset=["customer_id"], keep="first")
    if "customer_id" in orders.columns:
        orders = orders.drop_duplicates(subset=["customer_id"], keep="last")
    if "customer_id" in support.columns:
        support = support.drop_duplicates(subset=["customer_id"], keep="last")

    keep_crm = [c for c in ["customer_id", "name", "email", "city", "registration_date"] if c in crm.columns]
    keep_orders = [c for c in ["customer_id", "total_orders", "lifetime_value", "last_order_date"] if c in orders.columns]
    keep_support = [c for c in ["customer_id", "support_tickets", "last_ticket_date"] if c in support.columns]

    merged = crm[keep_crm].merge(orders[keep_orders], on="customer_id", how="left")
    merged = merged.merge(support[keep_support], on="customer_id", how="left")

    for col in ["total_orders", "lifetime_value", "support_tickets"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")
    for col in ["name", "email", "city", "registration_date", "last_order_date", "last_ticket_date"]:
        if col in merged.columns:
            merged[col] = merged[col].where(merged[col].notna(), None)
    return merged
