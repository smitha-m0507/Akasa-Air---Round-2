import json
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import load_config
from src.db import read_report, read_table
from src.pipeline import run_pipeline
from src.transform import get_lineage

BASE = Path(__file__).resolve().parent
CONFIG = load_config(BASE)

SEGMENT_COLORS = {"Gold": "#D4A017", "Silver": "#64748B", "Bronze": "#B45309", "Unknown": "#94A3B8"}

st.set_page_config(page_title="Customer 360 Pipeline", page_icon="🧭", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    div[data-testid="stMetric"] {background: linear-gradient(135deg,#0f172a,#111827); border:1px solid #334155; padding: .8rem 1rem; border-radius: 14px;}
    div[data-testid="stMetric"] label {color:#cbd5e1 !important;}
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {color:#f8fafc !important;}
    .hero {background: radial-gradient(circle at 10% 10%, #2563eb, #0f172a 55%, #020617); color:white; padding:1.1rem 1.3rem; border-radius:18px; margin-bottom:.8rem; border:1px solid #1e293b;}
    .chip {display:inline-block; padding:.2rem .55rem; border-radius:999px; font-size:.78rem; font-weight:700; margin-right:.35rem;}
    .gold {background:#FEF3C7;color:#92400E;} .silver {background:#E2E8F0;color:#334155;} .bronze {background:#FFEDD5;color:#9A3412;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_outputs(_stamp):
    db = CONFIG.get("db_path", "data/output/customer360.db")
    return {
        "customer360": read_table(BASE, db, "customer_360"),
        "issues": read_table(BASE, db, "quality_issues"),
        "top10": read_table(BASE, db, "top10_revenue"),
        "segments": read_table(BASE, db, "segments"),
        "support_risk": read_table(BASE, db, "support_risk"),
        "regional": read_table(BASE, db, "regional_analytics"),
        "report": read_report(BASE, db),
    }


def run_and_clear():
    result = run_pipeline(BASE, CONFIG)
    st.session_state["last_run"] = result
    st.cache_data.clear()
    return result


def fmt_money(v):
    try:
        if pd.isna(v):
            return "—"
        return f"₹{float(v):,.0f}"
    except Exception:
        return "—"


output_dir = BASE / CONFIG.get("output_dir", "data/output")
summary_path = output_dir / "run_summary.json"
stamp = summary_path.stat().st_mtime if summary_path.exists() else 0
data = load_outputs(stamp)

st.markdown(
    '<div class="hero"><h1 style="margin:0;font-size:1.9rem;">Customer 360 Pipeline Studio</h1>'
    '<p style="margin:.3rem 0 0;color:#dbeafe;">Interactive analytics over JSON (CRM) + CSV (Orders) + XML (Support): ingestion, schema standardization, DQ checks, unified profile merge, and business insights.</p>'
    '<div style="margin-top:.55rem"><span class="chip gold">Gold &gt; ₹100k</span><span class="chip silver">Silver ₹50k–₹100k</span><span class="chip bronze">Bronze &lt; ₹50k</span></div></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Mission Controls")
    st.caption("Config-driven sources")
    st.json(CONFIG.get("input_sources", {}), expanded=False)
    if st.button("🚀 Run / Refresh Pipeline", type="primary", use_container_width=True):
        with st.status("Running Customer 360 pipeline...", expanded=True) as status:
            result = run_and_clear()
            for step in result["steps"]:
                icon = "✅" if step["status"] == "success" else "❌"
                st.write(f"{icon} **{step['step']}** — {step['detail']} ({step['seconds']}s)")
            status.update(label="Pipeline complete", state="complete")
        stamp = summary_path.stat().st_mtime if summary_path.exists() else time.time()
        data = load_outputs(stamp)
        st.rerun()
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        st.caption(f"Last run: {summary.get('timestamp_utc','')}")
        st.caption(f"Sources: {summary.get('source_counts', {})}")
    with st.expander("Thresholds & config"):
        st.json({k: v for k, v in CONFIG.items() if k in ["required_fields", "segmentation", "quality"]})

tabs = st.tabs(["📊 Overview", "🛡️ Data Quality", "👤 Customer 360", "💡 Insights Lab", "🧬 Lineage & Exports"])
report = data["report"] or {}
df = data["customer360"].copy()

# normalize segment display for existing outputs loaded before UI tweaks
if not df.empty and "segment" not in df.columns and "lifetime_value" in df.columns:
    seg = CONFIG.get("segmentation", {})
    def _seg(v):
        if pd.isna(v): return "Unknown"
        if v >= seg.get("gold_min", 100001): return "Gold"
        if v >= seg.get("silver_min", 50000): return "Silver"
        return "Bronze"
    df["segment"] = df["lifetime_value"].apply(_seg)
if not data["segments"].empty and "segment" in data["segments"].columns:
    segments_df = data["segments"].copy()
elif not df.empty and "segment" in df.columns:
    segments_df = df["segment"].value_counts(dropna=False).rename_axis("segment").reset_index(name="customer_count")
else:
    segments_df = pd.DataFrame()

with tabs[0]:
    if df.empty and not report:
        st.info("No outputs found yet. Click **Run / Refresh Pipeline** in the sidebar.")
    else:
        seg_counts = {r["segment"]: int(r["customer_count"]) for _, r in segments_df.iterrows()} if not segments_df.empty else {}
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Total Source Records", report.get("total_records", "—"))
        k2.metric("Unified Customers", report.get("successful_records", len(df) or "—"))
        k3.metric("DQ Issues", sum(int(report.get(k, 0) or 0) for k in ["duplicates", "invalid_emails", "missing_fields", "negative_revenue", "invalid_customer_ids"]))
        k4.metric("Gold", seg_counts.get("Gold", 0))
        k5.metric("Silver", seg_counts.get("Silver", 0))
        k6.metric("Bronze", seg_counts.get("Bronze", 0))

        left, right = st.columns([1.15, 1])
        with left:
            st.subheader("Segment Mix (actual data)")
            if not segments_df.empty:
                fig = px.pie(segments_df, names="segment", values="customer_count", hole=.5,
                             color="segment", color_discrete_map=SEGMENT_COLORS)
                fig.update_traces(textposition="inside", textinfo="percent+label+value")
                fig.update_layout(height=360, margin=dict(t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(segments_df.sort_values("customer_count", ascending=False), use_container_width=True, hide_index=True)
        with right:
            st.subheader("Pipeline Timeline")
            last = st.session_state.get("last_run") or (json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None)
            steps = last.get("steps") if last else []
            if steps:
                step_df = pd.DataFrame(steps)
                fig = px.bar(step_df, x="seconds", y="step", orientation="h", color="status",
                             color_discrete_map={"success": "#16a34a", "error": "#dc2626"}, text="detail")
                fig.update_layout(height=360, yaxis={"categoryorder": "array", "categoryarray": list(reversed(step_df["step"].tolist()))})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Run pipeline to capture step timing.")

        if not df.empty and "lifetime_value" in df.columns:
            st.subheader("Lifetime Value Distribution")
            fig = px.histogram(df, x="lifetime_value", nbins=30, color="segment", marginal="box",
                               color_discrete_map=SEGMENT_COLORS, title="How revenue is distributed across segments")
            fig.update_layout(height=360)
            st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.subheader("Data Quality Cockpit")
    if not report:
        st.warning("No quality report found. Run the pipeline.")
    else:
        issue_keys = ["duplicates", "invalid_emails", "missing_fields", "negative_revenue", "invalid_customer_ids", "orphan_order_ids", "orphan_support_ids"]
        total = max(int(report.get("total_records", 1) or 1), 1)
        issues = sum(int(report.get(k, 0) or 0) for k in issue_keys)
        score = max(0, round(100 * (1 - issues / total), 1))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("DQ Score", f"{score}/100")
        c2.metric("Issues Found", issues)
        c3.metric("Records Assessed", report.get("total_records", 0))
        c4.metric("Successful Unified", report.get("successful_records", 0))
        issue_df = pd.DataFrame([{"check": k.replace('_', ' ').title(), "count": int(report.get(k, 0) or 0)} for k in issue_keys])
        left, right = st.columns([1, 1])
        with left:
            fig = go.Figure(go.Indicator(mode="gauge+number", value=score, title={"text": "Data Quality Score"},
                                         gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#2563eb"},
                                                "steps": [{"range": [0, 70], "color": "#fee2e2"}, {"range": [70, 90], "color": "#fef3c7"}, {"range": [90, 100], "color": "#dcfce7"}]}))
            fig.update_layout(height=320, margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.plotly_chart(px.bar(issue_df, x="check", y="count", text_auto=True, color="count", color_continuous_scale="Reds", title="Issue Breakdown"), use_container_width=True)
        st.dataframe(issue_df, use_container_width=True, hide_index=True)
        st.subheader("Drill-down: problematic records")
        issues_df = data["issues"]
        if issues_df.empty:
            st.success("No issue samples recorded.")
        else:
            f1, f2 = st.columns(2)
            reason = f1.selectbox("Issue reason", ["All"] + sorted(issues_df["issue_reason"].dropna().unique().tolist()) if "issue_reason" in issues_df.columns else ["All"])
            source = f2.selectbox("Source", ["All"] + sorted(issues_df["issue_source"].dropna().unique().tolist()) if "issue_source" in issues_df.columns else ["All"])
            view = issues_df.copy()
            if reason != "All": view = view[view["issue_reason"] == reason]
            if source != "All": view = view[view["issue_source"] == source]
            st.dataframe(view, use_container_width=True, hide_index=True)
        with st.expander("Raw quality report JSON"):
            st.json(report)

with tabs[2]:
    st.subheader("Customer 360 Explorer")
    if df.empty:
        st.info("Run the pipeline to build the unified dataset.")
    else:
        f1, f2, f3, f4 = st.columns([1.5, 1, 1, 1])
        q = f1.text_input("Search ID / name / email / city", "")
        seg_filter = f2.multiselect("Segment", options=sorted(df["segment"].dropna().unique().tolist()) if "segment" in df.columns else [], default=[])
        city_filter = f3.multiselect("City", options=sorted(df["city"].dropna().astype(str).unique().tolist()) if "city" in df.columns else [], default=[])
        risk_only = f4.checkbox("Support > 5 tickets", value=False)
        view = df.copy()
        if q:
            mask = pd.Series(False, index=view.index)
            for col in [c for c in ["customer_id", "name", "email", "city"] if c in view.columns]:
                mask |= view[col].astype(str).str.contains(q, case=False, na=False)
            view = view[mask]
        if seg_filter and "segment" in view.columns:
            view = view[view["segment"].isin(seg_filter)]
        if city_filter and "city" in view.columns:
            view = view[view["city"].astype(str).isin(city_filter)]
        if risk_only and "support_tickets" in view.columns:
            view = view[view["support_tickets"].fillna(0) > 5]
        st.caption(f"Showing {len(view):,} of {len(df):,} customers")
        st.dataframe(view, use_container_width=True, hide_index=True)
        ids = view["customer_id"].dropna().astype(str).tolist() if "customer_id" in view.columns else []
        if ids:
            selected = st.selectbox("Open profile", ids[:500])
            row = df[df["customer_id"].astype(str) == selected].iloc[0].to_dict()
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Customer", str(row.get("customer_id", "—")))
            p1.caption(f"{row.get('name','—')} · {row.get('city','—')}")
            p2.metric("Lifetime Value", fmt_money(row.get("lifetime_value")))
            p2.caption(f"Orders: {row.get('total_orders','—')} · Last: {row.get('last_order_date','—')}")
            p3.metric("Support Tickets", int(row.get('support_tickets') or 0) if pd.notna(row.get('support_tickets')) else "—")
            p3.caption(f"Last ticket: {row.get('last_ticket_date','—')}")
            seg = row.get("segment", "—")
            p4.metric("Segment", seg)
            p4.caption(row.get("email", "—"))
            tl = pd.DataFrame([
                {"event": "Registered", "date": row.get("registration_date")},
                {"event": "Last Order", "date": row.get("last_order_date")},
                {"event": "Last Ticket", "date": row.get("last_ticket_date")},
            ]).dropna()
            tl["date"] = pd.to_datetime(tl["date"], errors="coerce")
            tl = tl.dropna().sort_values("date")
            if not tl.empty:
                st.plotly_chart(px.scatter(tl, x="date", y="event", color="event", size=[12] * len(tl), title="Customer activity timeline"), use_container_width=True)

with tabs[3]:
    st.subheader("Insights Lab")
    if df.empty:
        st.info("Run the pipeline to generate insights.")
    else:
        top10 = data["top10"].copy() if not data["top10"].empty else df.nlargest(10, "lifetime_value")[[c for c in ["customer_id","name","city","lifetime_value","total_orders","segment"] if c in df.columns]]
        l, r = st.columns([1.2, 1])
        with l:
            st.markdown("#### Top 10 Customers by Revenue")
            if not top10.empty:
                top10 = top10.sort_values("lifetime_value", ascending=True)
                fig = px.bar(top10, x="lifetime_value", y="customer_id", orientation="h", color="segment" if "segment" in top10.columns else None,
                             color_discrete_map=SEGMENT_COLORS, text_auto=".2s",
                             hover_data=[c for c in ["name","city","total_orders","lifetime_value"] if c in top10.columns])
                fig.update_layout(height=420)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(top10.sort_values("lifetime_value", ascending=False), use_container_width=True, hide_index=True)
        with r:
            st.markdown("#### Segment Contribution")
            if not segments_df.empty:
                seg_rev = df.groupby("segment", dropna=False)["lifetime_value"].sum(min_count=1).reset_index(name="revenue") if "lifetime_value" in df.columns else segments_df.assign(revenue=0)
                fig = px.bar(seg_rev, x="segment", y="revenue", color="segment", color_discrete_map=SEGMENT_COLORS, text_auto=".3s")
                fig.update_layout(height=420)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(seg_rev, use_container_width=True, hide_index=True)

        st.markdown("#### Regional Analytics")
        regional = data["regional"].copy() if not data["regional"].empty else pd.DataFrame()
        if not regional.empty:
            a, b = st.columns(2)
            a.plotly_chart(px.bar(regional.sort_values("revenue", ascending=False), x="city", y="revenue", color="city", text_auto=".3s", title="Revenue by City"), use_container_width=True)
            b.plotly_chart(px.bar(regional.sort_values("customer_count", ascending=False), x="city", y="customer_count", color="city", text_auto=True, title="Customer Count by City"), use_container_width=True)
            st.dataframe(regional, use_container_width=True, hide_index=True)

        s1, s2 = st.columns(2)
        with s1:
            st.markdown("#### Support vs Revenue")
            if {"support_tickets","lifetime_value"}.issubset(df.columns):
                fig = px.scatter(df, x="support_tickets", y="lifetime_value", color="segment" if "segment" in df.columns else None,
                                 color_discrete_map=SEGMENT_COLORS, hover_data=[c for c in ["customer_id","name","city"] if c in df.columns],
                                 title="Value vs. support load")
                fig.update_layout(height=380)
                st.plotly_chart(fig, use_container_width=True)
        with s2:
            st.markdown("#### Customers with > 5 Tickets")
            risk = data["support_risk"].copy() if not data["support_risk"].empty else df[df["support_tickets"].fillna(0) > 5]
            if risk.empty:
                st.success("No customers above the support threshold.")
            else:
                st.metric("At-risk/high-touch customers", len(risk))
                st.dataframe(risk.sort_values("support_tickets", ascending=False), use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Source Lineage & Schema Map")
    st.dataframe(get_lineage(), use_container_width=True, hide_index=True)
    st.info("Canonical merge key: `customer_id` ← `customer_id` (CRM), `cust_id` (Orders), `customerId` (Support).")
    st.subheader("Export Center")
    files = [
        ("Unified Customer 360 (JSON)", output_dir / "customer_360.json", "application/json"),
        ("Unified Customer 360 (CSV)", output_dir / "customer_360.csv", "text/csv"),
        ("Data Quality Report", output_dir / "data_quality_report.json", "application/json"),
        ("Quality Issue Samples", output_dir / "quality_issues.csv", "text/csv"),
        ("Top 10 Revenue", output_dir / "top10_revenue.csv", "text/csv"),
        ("Segments", output_dir / "segments.csv", "text/csv"),
        ("Support Risk (>5 tickets)", output_dir / "support_risk.csv", "text/csv"),
        ("Regional Analytics", output_dir / "regional_analytics.csv", "text/csv"),
        ("Run Summary", output_dir / "run_summary.json", "application/json"),
        ("Pipeline Log", BASE / "logs" / "pipeline.log", "text/plain"),
    ]
    cols = st.columns(2)
    for i, (label, path, mime) in enumerate(files):
        with cols[i % 2]:
            if path.exists():
                st.download_button(label, data=path.read_bytes(), file_name=path.name, mime=mime, use_container_width=True)
            else:
                st.caption(f"{label}: not generated yet")
