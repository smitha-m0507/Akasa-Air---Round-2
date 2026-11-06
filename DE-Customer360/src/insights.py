import pandas as pd


def segment_customer(value, config):
    if pd.isna(value):
        return "Unknown"
    seg = config.get("segmentation", {})
    gold_min = seg.get("gold_min", 100001)
    silver_min = seg.get("silver_min", 50000)
    if value >= gold_min:
        return "Gold"
    if value >= silver_min:
        return "Silver"
    return "Bronze"


def build_insights(customer360, config):
    df = customer360.copy()
    df["segment"] = df["lifetime_value"].apply(lambda v: segment_customer(v, config)) if "lifetime_value" in df.columns else "Unknown"
    top10 = df.sort_values("lifetime_value", ascending=False, na_position="last").head(10)[
        [c for c in ["customer_id", "name", "city", "lifetime_value", "total_orders", "segment"] if c in df.columns]
    ].copy()
    segments = df["segment"].value_counts(dropna=False).rename_axis("segment").reset_index(name="customer_count")
    high_support_threshold = config.get("quality", {}).get("high_support_tickets", 5)
    support_risk = df[df["support_tickets"].fillna(0) > high_support_threshold][
        [c for c in ["customer_id", "name", "city", "support_tickets", "last_ticket_date", "segment"] if c in df.columns]
    ].sort_values("support_tickets", ascending=False)
    revenue_by_city = df.groupby("city", dropna=False)["lifetime_value"].sum(min_count=1).reset_index(name="revenue")
    customers_by_city = df.groupby("city", dropna=False)["customer_id"].nunique().reset_index(name="customer_count")
    regional = revenue_by_city.merge(customers_by_city, on="city", how="outer")
    regional["city"] = regional["city"].fillna("Unknown")
    return {
        "customer360_segmented": df,
        "top10_revenue": top10,
        "segments": segments,
        "support_risk": support_risk,
        "regional": regional.sort_values("revenue", ascending=False, na_position="last"),
    }
