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

SEGMENT_COLORS = {"Gold": "#F59E0B", "Silver": "#94A3B8", "Bronze": "#EA580C", "Unknown": "#64748B"}
STATUS_COLORS = {"Open": "#EF4444", "Reviewed": "#F59E0B", "Fixed": "#10B981"}
CHART_SEQ = ["#3B82F6", "#8B5CF6", "#06B6D4", "#10B981", "#F59E0B", "#EF4444", "#EC4899"]
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(15,23,42,0.15)",
    font=dict(color="#E2E8F0"),
    legend=dict(bgcolor="rgba(15,23,42,0.35)"),
    margin=dict(t=48, b=36, l=36, r=24),
)

st.set_page_config(page_title="Customer 360 Pipeline", page_icon="🧭", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {font-family: 'Inter', sans-serif;}
    .stApp {
      background:
        radial-gradient(1200px 500px at 10% -10%, rgba(59,130,246,.22), transparent 60%),
        radial-gradient(900px 420px at 90% 0%, rgba(139,92,246,.18), transparent 55%),
        radial-gradient(700px 380px at 50% 100%, rgba(6,182,212,.10), transparent 60%),
        linear-gradient(180deg, #020617 0%, #0F172A 45%, #111827 100%);
      color: #E5E7EB;
    }
    .block-container {padding-top: .85rem; padding-bottom: 2rem; max-width: 1400px;}
    section[data-testid="stSidebar"] {
      background: linear-gradient(180deg, rgba(15,23,42,.96), rgba(2,6,23,.98));
      border-right: 1px solid rgba(148,163,184,.18);
    }
    section[data-testid="stSidebar"] .block-container {padding-top: 1rem;}
    div[data-testid="stMetric"] {
      background: linear-gradient(135deg, rgba(30,41,59,.92), rgba(15,23,42,.92));
      border: 1px solid rgba(148,163,184,.22);
      box-shadow: 0 10px 30px rgba(2,6,23,.28);
      padding: .85rem 1rem; border-radius: 16px;
      transition: transform .15s ease, border-color .15s ease;
    }
    div[data-testid="stMetric"]:hover {transform: translateY(-2px); border-color: rgba(96,165,250,.45);}
    div[data-testid="stMetric"] label {color:#CBD5E1 !important; font-weight:600;}
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {color:#F8FAFC !important; font-weight:800;}
    .hero {
      position: relative; overflow: hidden;
      background: linear-gradient(135deg, rgba(37,99,235,.95), rgba(79,70,229,.88) 45%, rgba(15,23,42,.96));
      border: 1px solid rgba(191,219,254,.25);
      box-shadow: 0 18px 50px rgba(30,64,175,.25);
      color:white; padding:1.2rem 1.35rem; border-radius:22px; margin-bottom:.9rem;
    }
    .hero:before {
      content:""; position:absolute; inset:-40% auto auto 55%; width:420px; height:420px;
      background: radial-gradient(circle, rgba(255,255,255,.18), transparent 65%);
      pointer-events:none;
    }
    .chip {display:inline-block; padding:.22rem .62rem; border-radius:999px; font-size:.76rem; font-weight:700; margin-right:.35rem; margin-top:.3rem; border:1px solid rgba(255,255,255,.18);}
    .gold {background:rgba(245,158,11,.22); color:#FDE68A;} .silver {background:rgba(148,163,184,.22); color:#E2E8F0;} .bronze {background:rgba(234,88,12,.22); color:#FED7AA;}
    .note {background:linear-gradient(135deg, rgba(59,130,246,.14), rgba(15,23,42,.55)); border:1px solid rgba(96,165,250,.28); padding:.75rem .9rem; border-radius:14px; color:#DBEAFE;}
    .panel {background:linear-gradient(180deg, rgba(30,41,59,.55), rgba(15,23,42,.45)); border:1px solid rgba(148,163,184,.16); border-radius:18px; padding:.2rem .2rem 0;}
    .stTabs [data-baseweb="tab-list"] {gap:.4rem; background: rgba(15,23,42,.45); padding:.35rem; border-radius:14px; border:1px solid rgba(148,163,184,.14);}
    .stTabs [data-baseweb="tab"] {height:auto; border-radius:10px; color:#CBD5E1; padding:.45rem .8rem; font-weight:600;}
    .stTabs [aria-selected="true"] {background: linear-gradient(135deg, rgba(59,130,246,.35), rgba(139,92,246,.25)) !important; color:#FFFFFF !important;}
    .stButton > button, .stDownloadButton > button {
      border-radius: 12px; border:1px solid rgba(148,163,184,.22);
      background: linear-gradient(135deg, rgba(30,41,59,.95), rgba(15,23,42,.95));
      color:#E5E7EB; font-weight:600; transition: all .15s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {border-color: rgba(96,165,250,.5); transform: translateY(-1px);}
    .stButton > button[kind="primary"] {background: linear-gradient(135deg, #2563EB, #4F46E5) !important; border:none !important;}
    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {border:1px solid rgba(148,163,184,.14); border-radius:14px; overflow:hidden;}
    .stPlotlyChart {background: linear-gradient(180deg, rgba(30,41,59,.30), rgba(15,23,42,.18)); border:1px solid rgba(148,163,184,.12); border-radius:16px; padding:.25rem;}
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
    st.session_state.pop("working_c360", None)
    st.session_state.pop("working_c360_stamp", None)
    st.session_state.pop("dq_workflow", None)
    st.session_state.pop("dq_workflow_stamp", None)
    st.cache_data.clear()
    return result


def fmt_money(v):
    try:
        if pd.isna(v):
            return "—"
        return f"₹{float(v):,.0f}"
    except Exception:
        return "—"


def issue_key(row):
    parts = [str(row.get(c, "")) for c in ["issue_source", "issue_reason", "customer_id", "email", "name", "support_tickets", "lifetime_value"]]
    return "|".join(parts)


def prepare_dq_workflow(issues_df):
    if issues_df.empty:
        return pd.DataFrame(columns=["issue_key", "issue_source", "issue_reason", "customer_id", "status", "reviewer_comment"])
    wf = issues_df.copy()
    wf["issue_key"] = wf.apply(issue_key, axis=1)
    wf["status"] = "Open"
    wf["reviewer_comment"] = ""
    return wf


def style_fig(fig, title=None, height=360):
    fig.update_layout(**PLOTLY_LAYOUT, height=height, title=dict(text=title or fig.layout.title.text, x=0.01, xanchor="left", font=dict(size=16)))
    fig.update_xaxes(gridcolor="rgba(148,163,184,.12)", zerolinecolor="rgba(148,163,184,.12)")
    fig.update_yaxes(gridcolor="rgba(148,163,184,.12)", zerolinecolor="rgba(148,163,184,.12)")
    return fig


def show_chart(fig):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})


output_dir = BASE / CONFIG.get("output_dir", "data/output")
summary_path = output_dir / "run_summary.json"
stamp = summary_path.stat().st_mtime if summary_path.exists() else 0
data = load_outputs(stamp)

report = data["report"] or {}
df = data["customer360"].copy()
seg_counts_preview = {}
if not df.empty and "lifetime_value" in df.columns and "segment" not in df.columns:
    seg_cfg = CONFIG.get("segmentation", {})
    def _seg(v):
        if pd.isna(v): return "Unknown"
        if v >= seg_cfg.get("gold_min", 100001): return "Gold"
        if v >= seg_cfg.get("silver_min", 50000): return "Silver"
        return "Bronze"
    df["segment"] = df["lifetime_value"].apply(_seg)
if not df.empty and "segment" in df.columns:
    seg_counts_preview = df["segment"].value_counts().to_dict()

st.markdown(
    f"""
    <div class="hero">
      <h1 style="margin:0;font-size:2rem;letter-spacing:-.02em;">Customer 360 Pipeline Studio</h1>
      <p style="margin:.35rem 0 0;color:#DBEAFE;max-width:980px;">Interactive analytics over JSON (CRM) + CSV (Orders) + XML (Support): ingestion, schema standardization, DQ checks, unified profile merge, and business insights.</p>
      <div style="margin-top:.6rem">
        <span class="chip gold">Gold {seg_counts_preview.get('Gold', 0)}</span>
        <span class="chip silver">Silver {seg_counts_preview.get('Silver', 0)}</span>
        <span class="chip bronze">Bronze {seg_counts_preview.get('Bronze', 0)}</span>
        <span class="chip" style="background:rgba(255,255,255,.12);color:#EFF6FF;">Unified {len(df) if not df.empty else '—'}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Mission Controls")
    st.caption("Config-driven sources")
    st.json(CONFIG.get("input_sources", {}), expanded=False)
    run_col, _ = st.columns([1, 0.01])
    with run_col:
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
    st.markdown('<div class="note">Deployed demo note: edits/resolutions are session-safe; download exports to keep changes on Streamlit Cloud.</div>', unsafe_allow_html=True)

tabs = st.tabs(["📊 Overview", "🛡️ Data Quality", "✅ DQ Resolution", "👤 Customer 360", "🧰 Data Operations", "💡 Insights Lab", "🧬 Lineage & Exports"])
report = data["report"] or {}
df = data["customer360"].copy()

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
        dq_total = sum(int(report.get(k, 0) or 0) for k in ["duplicates", "invalid_emails", "missing_fields", "negative_revenue", "invalid_customer_ids"])
        k3.metric("DQ Issues", dq_total)
        k4.metric("Gold", seg_counts.get("Gold", 0))
        k5.metric("Silver", seg_counts.get("Silver", 0))
        k6.metric("Bronze", seg_counts.get("Bronze", 0))

        left, right = st.columns([1.15, 1])
        with left:
            st.subheader("Segment Mix")
            if not segments_df.empty:
                view_mode = st.radio("View", ["Donut", "Bar"], horizontal=True, key="seg_view")
                plot_df = segments_df.sort_values("customer_count", ascending=False)
                if view_mode == "Donut":
                    fig = px.pie(plot_df, names="segment", values="customer_count", hole=.58, color="segment", color_discrete_map=SEGMENT_COLORS)
                    fig.update_traces(textposition="inside", textinfo="percent+label+value", marker=dict(line=dict(color='rgba(15,23,42,.8)', width=2)))
                else:
                    fig = px.bar(plot_df, x="segment", y="customer_count", color="segment", text="customer_count", color_discrete_map=SEGMENT_COLORS)
                    fig.update_traces(marker_line_width=0, textposition="outside")
                show_chart(style_fig(fig, "Customer Segments", 360))
                st.dataframe(plot_df, use_container_width=True, hide_index=True)
        with right:
            st.subheader("Pipeline Timeline")
            last = st.session_state.get("last_run") or (json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None)
            steps = last.get("steps") if last else []
            if steps:
                step_df = pd.DataFrame(steps)
                fig = px.bar(step_df, x="seconds", y="step", orientation="h", color="status", color_discrete_map={"success": "#10B981", "error": "#EF4444"}, text="detail")
                fig.update_layout(yaxis={"categoryorder": "array", "categoryarray": list(reversed(step_df["step"].tolist()))})
                fig.update_traces(textposition="inside", insidetextanchor="middle")
                show_chart(style_fig(fig, "Execution Time by Stage", 360))
            else:
                st.caption("Run pipeline to capture step timing.")

        if not df.empty and "lifetime_value" in df.columns:
            st.subheader("Lifetime Value Distribution")
            h1, h2 = st.columns([1, 3])
            bins = h1.slider("Bins", 10, 60, 30, key="ltv_bins")
            color_by = h2.radio("Color by", ["segment", "city"] if "city" in df.columns else ["segment"], horizontal=True, key="ltv_color")
            fig = px.histogram(df, x="lifetime_value", nbins=bins, color=color_by, marginal="box",
                               color_discrete_map=SEGMENT_COLORS if color_by == "segment" else None,
                               color_discrete_sequence=CHART_SEQ, opacity=.88)
            fig.update_traces(marker_line_width=0)
            show_chart(style_fig(fig, "Revenue distribution across the unified customer base", 380))

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
        left, right = st.columns([1, 1.15])
        with left:
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=score,
                delta={"reference": 95, "increasing": {"color": "#10B981"}, "decreasing": {"color": "#EF4444"}},
                title={"text": "Data Quality Score", "font": {"color": "#E2E8F0"}},
                number={"font": {"color": "#F8FAFC", "size": 44}},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": "#94A3B8"},
                    "bar": {"color": "#3B82F6", "thickness": .75},
                    "bgcolor": "rgba(15,23,42,.35)",
                    "borderwidth": 1,
                    "bordercolor": "rgba(148,163,184,.2)",
                    "steps": [
                        {"range": [0, 70], "color": "rgba(239,68,68,.22)"},
                        {"range": [70, 90], "color": "rgba(245,158,11,.20)"},
                        {"range": [90, 100], "color": "rgba(16,185,129,.20)"},
                    ],
                    "threshold": {"line": {"color": "#A78BFA", "width": 3}, "thickness": .8, "value": score},
                },
            ))
            show_chart(style_fig(fig, "Overall DQ Health", 340))
        with right:
            fig = px.bar(issue_df, x="count", y="check", orientation="h", text="count", color="count", color_continuous_scale=["#60A5FA", "#F59E0B", "#EF4444"])
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
            fig.update_traces(textposition="outside")
            show_chart(style_fig(fig, "Issue Breakdown", 340))
        st.dataframe(issue_df, use_container_width=True, hide_index=True)
        st.subheader("Drill-down: problematic records")
        issues_df = data["issues"]
        if issues_df.empty:
            st.success("No issue samples recorded.")
        else:
            f1, f2 = st.columns(2)
            reason = f1.selectbox("Issue reason", ["All"] + sorted(issues_df["issue_reason"].dropna().unique().tolist()) if "issue_reason" in issues_df.columns else ["All"], key="dq_reason")
            source = f2.selectbox("Source", ["All"] + sorted(issues_df["issue_source"].dropna().unique().tolist()) if "issue_source" in issues_df.columns else ["All"], key="dq_source")
            view = issues_df.copy()
            if reason != "All": view = view[view["issue_reason"] == reason]
            if source != "All": view = view[view["issue_source"] == source]
            st.dataframe(view, use_container_width=True, hide_index=True)
        with st.expander("Raw quality report JSON"):
            st.json(report)

with tabs[2]:
    st.subheader("DQ Issue Resolution Workflow")
    st.markdown('<div class="note">Governance workflow: triage detected DQ issues as <b>Open / Reviewed / Fixed</b>, add reviewer comments, and export a resolution report. On Streamlit Cloud, export the report to keep workflow state.</div>', unsafe_allow_html=True)
    issues_df = data["issues"]
    if issues_df.empty:
        st.success("No detected quality issues to resolve.")
    else:
        if st.session_state.get("dq_workflow_stamp") != stamp or st.session_state.get("dq_workflow") is None:
            st.session_state["dq_workflow"] = prepare_dq_workflow(issues_df)
            st.session_state["dq_workflow_stamp"] = stamp
        wf = st.session_state["dq_workflow"].copy()
        c1, c2, c3 = st.columns(3)
        status_filter = c1.multiselect("Status filter", ["Open", "Reviewed", "Fixed"], default=["Open", "Reviewed", "Fixed"])
        reason_filter = c2.multiselect("Reason filter", sorted(wf["issue_reason"].dropna().unique().tolist()) if "issue_reason" in wf.columns else [])
        q = c3.text_input("Search issue/customer", "")
        view = wf.copy()
        if status_filter:
            view = view[view["status"].isin(status_filter)]
        if reason_filter:
            view = view[view["issue_reason"].isin(reason_filter)]
        if q:
            mask = pd.Series(False, index=view.index)
            for col in [c for c in ["customer_id", "name", "email", "issue_reason", "reviewer_comment"] if c in view.columns]:
                mask |= view[col].astype(str).str.contains(q, case=False, na=False)
            view = view[mask]
        st.caption(f"Showing {len(view)} of {len(wf)} issues")
        edited = st.data_editor(
            view,
            use_container_width=True,
            hide_index=True,
            key="dq_editor",
            column_config={
                "status": st.column_config.SelectboxColumn("status", options=["Open", "Reviewed", "Fixed"], required=True),
                "reviewer_comment": st.column_config.TextColumn("reviewer_comment"),
                "issue_key": st.column_config.TextColumn("issue_key", disabled=True),
                "issue_source": st.column_config.TextColumn("issue_source", disabled=True),
                "issue_reason": st.column_config.TextColumn("issue_reason", disabled=True),
            },
        )
        if st.button("Apply resolution updates", use_container_width=True):
            updated = wf.set_index("issue_key")
            for _, row in edited.iterrows():
                key = row.get("issue_key")
                if key in updated.index:
                    updated.loc[key, "status"] = row.get("status", "Open")
                    updated.loc[key, "reviewer_comment"] = row.get("reviewer_comment", "")
            st.session_state["dq_workflow"] = updated.reset_index()
            st.success("Resolution workflow updated.")
            st.rerun()
        wf = st.session_state["dq_workflow"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Open", int((wf["status"] == "Open").sum()))
        m2.metric("Reviewed", int((wf["status"] == "Reviewed").sum()))
        m3.metric("Fixed", int((wf["status"] == "Fixed").sum()))
        m4.metric("Commented", int(wf["reviewer_comment"].fillna("").astype(str).str.strip().ne("").sum()))
        status_counts = wf["status"].value_counts().rename_axis("status").reset_index(name="count")
        fig = px.bar(status_counts, x="status", y="count", color="status", color_discrete_map=STATUS_COLORS, text="count")
        fig.update_traces(textposition="outside")
        show_chart(style_fig(fig, "Resolution Status", 320))
        e1, e2 = st.columns(2)
        e1.download_button("Download resolution report (CSV)", wf.to_csv(index=False).encode("utf-8"), "dq_resolution_report.csv", "text/csv", use_container_width=True)
        e2.download_button("Download resolution report (JSON)", wf.to_json(orient="records", indent=2).encode("utf-8"), "dq_resolution_report.json", "application/json", use_container_width=True)

with tabs[3]:
    st.subheader("Customer 360 Explorer")
    if df.empty:
        st.info("Run the pipeline to build the unified dataset.")
    else:
        f1, f2, f3, f4 = st.columns([1.5, 1, 1, 1])
        q = f1.text_input("Search ID / name / email / city", "", key="explorer_q")
        seg_filter = f2.multiselect("Segment", options=sorted(df["segment"].dropna().unique().tolist()) if "segment" in df.columns else [], default=[], key="explorer_seg")
        city_filter = f3.multiselect("City", options=sorted(df["city"].dropna().astype(str).unique().tolist()) if "city" in df.columns else [], default=[], key="explorer_city")
        risk_only = f4.checkbox("Support > 5 tickets", value=False, key="explorer_risk")
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
            selected = st.selectbox("Open profile", ids[:500], key="profile_select")
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
            tl = pd.DataFrame([{"event": "Registered", "date": row.get("registration_date")}, {"event": "Last Order", "date": row.get("last_order_date")}, {"event": "Last Ticket", "date": row.get("last_ticket_date")}]).dropna()
            tl["date"] = pd.to_datetime(tl["date"], errors="coerce")
            tl = tl.dropna().sort_values("date")
            if not tl.empty:
                fig = px.scatter(tl, x="date", y="event", color="event", size=[14] * len(tl), color_discrete_sequence=CHART_SEQ)
                fig.update_traces(marker=dict(line=dict(width=1, color='rgba(255,255,255,.35)')))
                show_chart(style_fig(fig, "Customer activity timeline", 300))

with tabs[4]:
    st.subheader("Data Operations")
    st.markdown('<div class="note">Operate on a working copy of the unified Customer 360 dataset: filter, edit fields, flag rows for deletion, add notes, and export the updated dataset. Source files are not modified.</div>', unsafe_allow_html=True)
    if df.empty:
        st.info("Run the pipeline before using data operations.")
    else:
        if st.session_state.get("working_c360_stamp") != stamp or st.session_state.get("working_c360") is None:
            work = df.copy()
            for col in ["ops_note", "ops_action"]:
                if col not in work.columns:
                    work[col] = "" if col == "ops_note" else "Keep"
            st.session_state["working_c360"] = work
            st.session_state["working_c360_stamp"] = stamp
        work = st.session_state["working_c360"].copy()
        f1, f2, f3 = st.columns([1.4, 1, 1])
        q = f1.text_input("Search working dataset", "", key="ops_q")
        seg_filter = f2.multiselect("Segment", options=sorted(work["segment"].dropna().astype(str).unique().tolist()) if "segment" in work.columns else [], key="ops_seg")
        action_filter = f3.multiselect("Action", options=["Keep", "Review", "Delete"], default=["Keep", "Review", "Delete"], key="ops_action")
        view = work.copy()
        if q:
            mask = pd.Series(False, index=view.index)
            for col in [c for c in ["customer_id", "name", "email", "city", "ops_note"] if c in view.columns]:
                mask |= view[col].astype(str).str.contains(q, case=False, na=False)
            view = view[mask]
        if seg_filter and "segment" in view.columns:
            view = view[view["segment"].astype(str).isin(seg_filter)]
        if action_filter and "ops_action" in view.columns:
            view = view[view["ops_action"].astype(str).isin(action_filter)]
        st.caption(f"Showing {len(view)} of {len(work)} working records")
        editable_cols = [c for c in ["customer_id", "name", "email", "city", "total_orders", "lifetime_value", "last_order_date", "support_tickets", "last_ticket_date", "segment", "ops_action", "ops_note"] if c in view.columns]
        edited = st.data_editor(
            view[editable_cols],
            use_container_width=True,
            hide_index=True,
            key="ops_editor",
            column_config={
                "customer_id": st.column_config.TextColumn("customer_id", disabled=True),
                "ops_action": st.column_config.SelectboxColumn("ops_action", options=["Keep", "Review", "Delete"], required=True),
                "ops_note": st.column_config.TextColumn("ops_note"),
            },
        )
        b1, b2, b3 = st.columns(3)
        if b1.button("Apply edits", use_container_width=True):
            base = work.set_index("customer_id") if "customer_id" in work.columns else work.copy()
            for _, row in edited.iterrows():
                cid = row.get("customer_id")
                if "customer_id" in work.columns and cid in base.index:
                    for col in editable_cols:
                        base.loc[cid, col] = row.get(col)
            st.session_state["working_c360"] = base.reset_index() if "customer_id" in work.columns else base
            st.success("Working dataset updated.")
            st.rerun()
        if b2.button("Remove rows marked Delete", use_container_width=True):
            current = st.session_state["working_c360"]
            kept = current[current["ops_action"].astype(str) != "Delete"].copy() if "ops_action" in current.columns else current
            st.session_state["working_c360"] = kept
            st.success(f"Removed {len(current) - len(kept)} rows from working dataset.")
            st.rerun()
        if b3.button("Reset working dataset", use_container_width=True):
            st.session_state.pop("working_c360", None)
            st.session_state.pop("working_c360_stamp", None)
            st.rerun()

        current = st.session_state["working_c360"]
        active = current[current["ops_action"].astype(str) != "Delete"].copy() if "ops_action" in current.columns else current
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Working Records", len(current))
        m2.metric("Active Records", len(active))
        m3.metric("Marked Review", int((current.get("ops_action", pd.Series(dtype=str)) == "Review").sum()) if "ops_action" in current.columns else 0)
        m4.metric("Marked Delete", int((current.get("ops_action", pd.Series(dtype=str)) == "Delete").sum()) if "ops_action" in current.columns else 0)
        st.dataframe(active, use_container_width=True, hide_index=True)
        e1, e2, e3 = st.columns(3)
        e1.download_button("Download working dataset (CSV)", current.to_csv(index=False).encode("utf-8"), "customer360_working.csv", "text/csv", use_container_width=True)
        e2.download_button("Download active dataset (JSON)", active.to_json(orient="records", indent=2).encode("utf-8"), "customer360_active.json", "application/json", use_container_width=True)
        audit = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_last_run": summary_path.read_text(encoding="utf-8") if summary_path.exists() else None,
            "working_records": len(current),
            "active_records": len(active),
            "marked_review": int((current.get("ops_action", pd.Series(dtype=str)) == "Review").sum()) if "ops_action" in current.columns else 0,
            "marked_delete": int((current.get("ops_action", pd.Series(dtype=str)) == "Delete").sum()) if "ops_action" in current.columns else 0,
        }
        e3.download_button("Download operations audit (JSON)", json.dumps(audit, indent=2).encode("utf-8"), "data_operations_audit.json", "application/json", use_container_width=True)

with tabs[5]:
    st.subheader("Insights Lab")
    if df.empty:
        st.info("Run the pipeline to generate insights.")
    else:
        top10 = data["top10"].copy() if not data["top10"].empty else df.nlargest(10, "lifetime_value")[[c for c in ["customer_id","name","city","lifetime_value","total_orders","segment"] if c in df.columns]]
        l, r = st.columns([1.2, 1])
        with l:
            st.markdown("#### Top 10 Customers by Revenue")
            if not top10.empty:
                top10p = top10.sort_values("lifetime_value", ascending=True)
                fig = px.bar(top10p, x="lifetime_value", y="customer_id", orientation="h", color="segment" if "segment" in top10p.columns else None, color_discrete_map=SEGMENT_COLORS, text_auto=".2s", hover_data=[c for c in ["name","city","total_orders","lifetime_value"] if c in top10p.columns])
                fig.update_traces(textposition="outside")
                show_chart(style_fig(fig, "Highest lifetime value customers", 420))
                st.dataframe(top10.sort_values("lifetime_value", ascending=False), use_container_width=True, hide_index=True)
        with r:
            st.markdown("#### Segment Contribution")
            if not segments_df.empty:
                seg_rev = df.groupby("segment", dropna=False)["lifetime_value"].sum(min_count=1).reset_index(name="revenue") if "lifetime_value" in df.columns else segments_df.assign(revenue=0)
                seg_count = df.groupby("segment", dropna=False)["customer_id"].nunique().reset_index(name="customers") if "customer_id" in df.columns else segments_df.rename(columns={"customer_count": "customers"})[["segment","customers"]]
                seg_rev = seg_rev.merge(seg_count, on="segment", how="left")
                chart_type = st.radio("Chart", ["Revenue", "Customers", "Bubble"], horizontal=True, key="seg_chart")
                if chart_type == "Revenue":
                    fig = px.bar(seg_rev, x="segment", y="revenue", color="segment", color_discrete_map=SEGMENT_COLORS, text_auto=".3s")
                    fig.update_traces(textposition="outside")
                elif chart_type == "Customers":
                    fig = px.bar(seg_rev, x="segment", y="customers", color="segment", color_discrete_map=SEGMENT_COLORS, text="customers")
                    fig.update_traces(textposition="outside")
                else:
                    fig = px.scatter(seg_rev, x="customers", y="revenue", size="revenue", color="segment", color_discrete_map=SEGMENT_COLORS, text="segment", size_max=55)
                    fig.update_traces(textposition="top center")
                show_chart(style_fig(fig, "Segment performance", 420))
                st.dataframe(seg_rev, use_container_width=True, hide_index=True)
        st.markdown("#### Regional Analytics")
        regional = data["regional"].copy() if not data["regional"].empty else pd.DataFrame()
        if not regional.empty:
            a, b = st.columns(2)
            reg_rev = regional.sort_values("revenue", ascending=False)
            fig = px.bar(reg_rev, x="city", y="revenue", color="revenue", color_continuous_scale=["#1D4ED8", "#22D3EE", "#A78BFA"], text_auto=".3s")
            fig.update_layout(coloraxis_showscale=False)
            fig.update_traces(textposition="outside")
            show_chart(style_fig(fig, "Revenue by City", 360))
            reg_cnt = regional.sort_values("customer_count", ascending=False)
            fig = px.bar(reg_cnt, x="city", y="customer_count", color="customer_count", color_continuous_scale=["#0F766E", "#34D399", "#FDE68A"], text="customer_count")
            fig.update_layout(coloraxis_showscale=False)
            fig.update_traces(textposition="outside")
            show_chart(style_fig(fig, "Customer Count by City", 360))
            st.dataframe(regional, use_container_width=True, hide_index=True)
        s1, s2 = st.columns(2)
        with s1:
            st.markdown("#### Support vs Revenue")
            if {"support_tickets","lifetime_value"}.issubset(df.columns):
                fig = px.scatter(df, x="support_tickets", y="lifetime_value", color="segment" if "segment" in df.columns else None, color_discrete_map=SEGMENT_COLORS, hover_data=[c for c in ["customer_id","name","city"] if c in df.columns], opacity=.8)
                fig.update_traces(marker=dict(size=9, line=dict(width=.5, color='rgba(255,255,255,.25)')))
                show_chart(style_fig(fig, "Value vs. support load", 380))
        with s2:
            st.markdown("#### Customers with > 5 Tickets")
            risk = data["support_risk"].copy() if not data["support_risk"].empty else df[df["support_tickets"].fillna(0) > 5]
            if risk.empty:
                st.success("No customers above the support threshold.")
            else:
                st.metric("At-risk/high-touch customers", len(risk))
                risk_plot = risk.sort_values("support_tickets", ascending=False).head(15)
                if {"customer_id", "support_tickets"}.issubset(risk_plot.columns):
                    fig = px.bar(risk_plot.sort_values("support_tickets"), x="support_tickets", y="customer_id", orientation="h", color="support_tickets", color_continuous_scale=["#F59E0B", "#EF4444"], text="support_tickets")
                    fig.update_layout(coloraxis_showscale=False)
                    show_chart(style_fig(fig, "Top support load customers", 300))
                st.dataframe(risk.sort_values("support_tickets", ascending=False), use_container_width=True, hide_index=True)

with tabs[6]:
    st.subheader("Source Lineage & Schema Map")
    st.dataframe(get_lineage(), use_container_width=True, hide_index=True)
    st.markdown('<div class="note">Canonical merge key: <code>customer_id</code> ← <code>customer_id</code> (CRM), <code>cust_id</code> (Orders), <code>customerId</code> (Support).</div>', unsafe_allow_html=True)
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
                st.download_button(label, data=path.read_bytes(), file_name=path.name, mime=mime, use_container_width=True, key=f"export_{i}")
            else:
                st.caption(f"{label}: not generated yet")
    st.caption("Data Operations and DQ Resolution exports are available in their respective tabs.")
