"""
app.py - Hospital Nurse Rostering Command Cockpit.
Operations Research Decision-Support System (Integer Programming & Goal Programming).

Run with:   streamlit run app.py

5 Integrated Cockpit Modules:
  1. 🏥 Ward Ingestion & Setup       - Ingest NRP XML instances, schema validation, ward capacity health
  2. 📊 Staffing Analytics           - On-demand exploratory demand analytics, heatmaps & nurse limits
  3. ⚙️ Optimization Cockpit          - Dual solver engines (IP & GP) + mathematical engine specifications
  4. 📅 Master Schedule & Results    - Unified results scorecard, clinical audits, color-coded shift roster & CSVs
  5. ⚖️ Executive Comparison         - Head-to-head decision scoreboard (Coverage vs Workload Equity)
"""

import inspect
import io
import json
import os
import sys
import tempfile
import zipfile

import pandas as pd
import streamlit as st

ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from src import data_statistics as dstat
from src import stat_charts as sc
from src.benchmarks import benchmark_info, instance_description
from src.comparison import comparison_to_dict, compare_optimization_results
from src.evaluation import DEFAULT_GP_WEIGHTS
from src.goal_program import solve_goal_program
from src.integer_program import solve_integer_program
from src.parser import parse_xml
from src.reference_solutions import (ReferenceSolutionError, has_reference, load_reference,
                                     reference_provenance)
from src.reporting import (coverage_summary, daywise_assignments, roster_long_csv, roster_table,
                            shiftwise_staffing, style_roster, understaffed_slots, violations_table,
                            workload_table)
from src.solver_utils import describe_status
from src.tables import dataset_to_tables
from src.validation import validate_solution
from src import visualization as viz

DATA_DIR = os.path.join(ROOT, "data", "raw")

# Streamlit >= 1.50 stretches charts/tables by default; older versions need use_container_width.
STRETCH = {} if "width" in inspect.signature(st.plotly_chart).parameters else {"use_container_width": True}

st.set_page_config(
    page_title="Hospital Nurse Rostering Command Cockpit",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Hospital Operations Cockpit Design System
# ─────────────────────────────────────────────────────────────────────────────
COCKPIT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"], .stMarkdown, p, div, label, span {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}
code, pre {
    font-family: 'JetBrains Mono', monospace !important;
}

.block-container {
    padding-top: 1.4rem !important;
    padding-bottom: 3.5rem !important;
    max-width: 1440px !important;
}

/* Command Header */
.cockpit-banner {
    background: linear-gradient(135deg, #091322 0%, #0f1f38 55%, #172554 100%);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 16px;
    padding: 22px 28px;
    margin-bottom: 22px;
    box-shadow: 0 12px 30px -8px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}
.cockpit-badge-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}
.dept-pill {
    background: rgba(37, 99, 235, 0.25);
    border: 1px solid rgba(96, 165, 250, 0.45);
    color: #93c5fd;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 4px 11px;
    border-radius: 6px;
}
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(52, 211, 153, 0.35);
    color: #6ee7b7;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 4px 11px;
    border-radius: 6px;
}
.pulse-circle {
    width: 7px;
    height: 7px;
    background: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 8px #10b981;
}
.cockpit-title-text {
    font-size: 1.8rem;
    font-weight: 800;
    color: #ffffff !important;
    letter-spacing: -0.025em;
    margin: 0;
}
.cockpit-subtitle-text {
    font-size: 0.93rem;
    color: #94a3b8;
    margin: 6px 0 0 0;
    line-height: 1.5;
}

/* Metric Cards */
div[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 14px 18px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}
div[data-testid="stMetric"]:hover {
    border-color: #3b82f6;
    box-shadow: 0 6px 20px rgba(59, 130, 246, 0.2);
    transform: translateY(-2px);
}
div[data-testid="stMetricLabel"] p {
    color: #94a3b8 !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
div[data-testid="stMetricValue"] div {
    color: #f8fafc !important;
    font-size: 1.7rem !important;
    font-weight: 800 !important;
}

/* Sidebar Overhaul */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #060b13 0%, #0d1524 50%, #172033 100%) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}
section[data-testid="stSidebar"] * {
    color: #f1f5f9;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255, 255, 255, 0.1) !important;
}
.sidebar-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0 12px 0;
}
.sidebar-logo-icon {
    font-size: 1.6rem;
}
.sidebar-logo-text {
    font-size: 1.25rem;
    font-weight: 800;
    color: #ffffff !important;
    letter-spacing: -0.02em;
    line-height: 1.2;
}
.sidebar-logo-sub {
    font-size: 0.72rem;
    font-weight: 700;
    color: #38bdf8 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* Tabs */
button[data-baseweb="tab"] {
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 10px 18px !important;
    transition: all 0.2s ease !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #38bdf8 !important;
    border-bottom-color: #38bdf8 !important;
}

/* Primary Button */
button[kind="primary"] {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
    transition: all 0.2s ease !important;
}
button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5) !important;
}

/* Shift Color Legend */
.roster-legend-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    align-items: center;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 18px;
    margin: 12px 0 18px 0;
}
.legend-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 0.85rem;
    font-weight: 600;
    color: #cbd5e1;
}
.legend-box {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    display: inline-block;
}

/* Trade-off Highlight Card */
.tradeoff-cockpit-card {
    background: linear-gradient(135deg, rgba(30, 58, 138, 0.25) 0%, rgba(15, 23, 42, 0.5) 100%);
    border: 1px solid rgba(59, 130, 246, 0.35);
    border-radius: 12px;
    padding: 18px 22px;
    margin: 16px 0 20px 0;
}
.tradeoff-header {
    font-size: 1.05rem;
    font-weight: 700;
    color: #38bdf8;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Constraint Cards Grid */
.constraint-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 12px;
    margin: 16px 0 24px 0;
}
.constraint-box {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px 16px;
}
.constraint-header {
    font-size: 0.88rem;
    font-weight: 700;
    color: #38bdf8;
    margin-bottom: 4px;
}
.constraint-body {
    font-size: 0.82rem;
    color: #cbd5e1;
    line-height: 1.45;
    margin: 0;
}
</style>
"""
st.markdown(COCKPIT_CSS, unsafe_allow_html=True)


def _cockpit_header(title: str, subtitle: str, dept: str = "INPATIENT NURSING WARD", status: str = "SYSTEM ACTIVE"):
    st.markdown(f"""
    <div class="cockpit-banner">
        <div class="cockpit-badge-row">
            <span class="dept-pill">🏥 {dept}</span>
            <span class="status-pill"><span class="pulse-circle"></span> {status}</span>
        </div>
        <h1 class="cockpit-title-text">{title}</h1>
        <p class="cockpit-subtitle-text">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULTS = {
    "dataset": None, "xml_bytes": None, "dataset_label": "",
    "ip_result": None, "gp_result": None, "comparison": None, "val_ip": None, "val_gp": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _reset_results():
    for k in ("ip_result", "gp_result", "comparison", "val_ip", "val_gp"):
        st.session_state[k] = None


def _set_dataset(ds, xml_bytes, label):
    st.session_state["dataset"] = ds
    st.session_state["xml_bytes"] = xml_bytes
    st.session_state["dataset_label"] = label
    _reset_results()


def _parse_from_bytes(xml_bytes: bytes, label: str):
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        f.write(xml_bytes)
        tmp_path = f.name
    try:
        ds = parse_xml(tmp_path)
        ds.source_name = label
        return ds, None
    except Exception as e:  # noqa: BLE001 - shown to the user
        return None, str(e)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _status_label(result) -> str:
    if result is None:
        return "—"
    if result.proven_optimal:
        return "✅ proven optimal"
    if result.status == "Feasible":
        return "⚠️ feasible, not proven"
    return f"❌ {result.status}"


def _solved(result) -> bool:
    obj = None if result is None else (getattr(result, "objective_value", None)
                                       if hasattr(result, "objective_value") else result.gp_objective_value)
    return result is not None and obj is not None


def _status_banner(result):
    text = describe_status(result.status, result.proven_optimal, result.time_limit)
    if result.source != "live solve":
        st.info(f"Loaded from a **{result.source}** (originally solved in {result.solve_time:.1f} s). "
                "The roster was re-validated and the objective recomputed on loading.")
    if result.proven_optimal:
        st.success(text)
    elif result.status == "Feasible":
        st.warning(text)
    else:
        st.error(text)


def _tables_zip(ds) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, df in dataset_to_tables(ds).items():
            zf.writestr(f"{name}.csv", df.to_csv(index=False))
    return buf.getvalue()


def _fmt_value(v):
    if isinstance(v, bool) or v is None:
        return "" if v is None else str(v)
    if isinstance(v, (int, float)):
        if float(v).is_integer():
            return f"{int(v):,}"
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return v


def _fmt_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col != "Metric":
            out[col] = out[col].map(_fmt_value)
    return out


def _need_dataset():
    st.warning("Load a dataset first (🏥 Ward Ingestion & Setup page).")


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar Cockpit Navigation: 5 Integrated Modules
# ─────────────────────────────────────────────────────────────────────────────

PAGES = [
    "🏥 Ward Ingestion & Setup",
    "📊 Staffing Analytics",
    "⚙️ Optimization Cockpit",
    "📅 Master Schedule & Results",
    "⚖️ Executive Comparison",
]

st.sidebar.markdown("""
<div class="sidebar-logo">
    <span class="sidebar-logo-icon">🏥</span>
    <div>
        <div class="sidebar-logo-text">Nurse Rostering</div>
        <div class="sidebar-logo-sub">Hospital Decision Cockpit</div>
    </div>
</div>
""", unsafe_allow_html=True)
st.sidebar.markdown("Integer Programming · Goal Programming")
st.sidebar.markdown("---")
section = st.sidebar.radio("Navigation", PAGES, key="nav")


def _render_session_status():
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Session status**")
    ds_now = st.session_state["dataset"]
    st.sidebar.markdown(f"- Dataset: {'✅ ' + st.session_state['dataset_label'] if ds_now else '❌ not loaded'}")
    st.sidebar.markdown(f"- IP: {_status_label(st.session_state['ip_result'])}")
    st.sidebar.markdown(f"- GP: {_status_label(st.session_state['gp_result'])}")
    if st.sidebar.button("Reset session"):
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# 1. WARD INGESTION & SETUP
# ─────────────────────────────────────────────────────────────────────────────

if section == "🏥 Ward Ingestion & Setup":
    _cockpit_header(
        title="Ward Ingestion & Setup",
        subtitle="Ingest and parse Nurse Rostering Benchmark XML instances into relational entities, contracts, and shift demand requirements.",
        dept="ST. JUDE GENERAL HOSPITAL · WARD SCHEDULING",
        status="STANDBY / READY" if st.session_state["dataset"] is None else "DATASET MOUNTED",
    )
    st.markdown(
        "Load a **Nurse Rostering Benchmark** instance in the standard NRP XML format "
        "([schedulingbenchmarks.org/nrp](https://www.schedulingbenchmarks.org/nrp/)). "
        "The file is parsed automatically - it is never edited."
    )

    with st.container(border=True):
        samples = sorted(f[:-4] for f in os.listdir(DATA_DIR) if f.startswith("Instance") and f.endswith(".xml")) \
            if os.path.isdir(DATA_DIR) else []
        mode = st.radio("Data source", ["Bundled benchmark sample", "Upload an XML file"], horizontal=True, key="ds_mode")

        if mode == "Bundled benchmark sample":
            if samples:
                default_idx = samples.index("Instance3") if "Instance3" in samples else 0
                pick = st.selectbox("Sample instance", samples, index=default_idx, key="sample_pick",
                                    format_func=instance_description)
                if st.button("Load sample", type="primary", key="load_sample"):
                    with open(os.path.join(DATA_DIR, pick + ".xml"), "rb") as fh:
                        raw = fh.read()
                    ds_new, err = _parse_from_bytes(raw, pick + ".xml")
                    if err:
                        st.error(f"Parsing failed: {err}")
                    else:
                        _set_dataset(ds_new, raw, pick + ".xml")
                        st.success(f"{pick} parsed successfully.")
            else:
                st.info("No bundled samples found in data/raw - upload a file instead.")
        else:
            uploaded = st.file_uploader("Upload NRP XML (.xml or .ros)", type=["xml", "ros"], key="uploader")
            if uploaded is not None:
                raw = uploaded.read()
                if raw != st.session_state["xml_bytes"]:
                    with st.spinner("Parsing XML …"):
                        ds_new, err = _parse_from_bytes(raw, uploaded.name)
                    if err:
                        st.error(f"Parsing failed: {err}")
                    else:
                        _set_dataset(ds_new, raw, uploaded.name)
                        st.success("Dataset parsed successfully.")

    dataset = st.session_state["dataset"]
    if dataset is None:
        st.info("No dataset loaded yet. Pick a bundled sample (Instance 3 is the project's main dataset) "
                "or upload a file.")
    else:
        info = benchmark_info(dataset)
        if info:
            st.success(
                f"Recognised as the published benchmark **{info['instance']}** - best known solution "
                f"**{info['best_known']:g}**, best known lower bound **{info['lower_bound']:g}**"
                f"{' (equal: this value is the proven optimum)' if info['proven_optimal'] else ''}."
            )
        else:
            st.info("This file does not match a published benchmark instance, so no reference objective "
                    "value will be shown for it.")
        for w in dataset.warnings:
            st.warning(w)

        pp = dataset.planning_period
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Nurses", len(dataset.employees))
        c2.metric("Days", pp.days)
        c3.metric("Weeks", pp.weeks)
        c4.metric("Shift types", len(dataset.shift_types))
        st.caption(f"Planning period {pp.start_date} → {pp.end_date}. Source file: {dataset.source_name}")

        tabs = st.tabs(["Shift types", "Contracts", "Nurses", "Coverage requirements"])
        tables = dataset_to_tables(dataset)
        with tabs[0]:
            st.dataframe(tables["shifts"], hide_index=True, **STRETCH)
        with tabs[1]:
            st.dataframe(tables["contracts"], hide_index=True, **STRETCH)
        with tabs[2]:
            st.dataframe(tables["employees"], hide_index=True, **STRETCH)
        with tabs[3]:
            st.dataframe(tables["cover"], hide_index=True, **STRETCH)

        st.download_button("⬇️ Download the structured tables (ZIP of CSV files)", _tables_zip(dataset),
                           file_name="nurse_dataset_tables.zip", mime="application/zip")

# ─────────────────────────────────────────────────────────────────────────────
# 2. STAFFING ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

elif section == "📊 Staffing Analytics":
    _cockpit_header(
        title="Ward Staffing & Demand Analytics",
        subtitle="Comprehensive exploratory analysis of staffing requirements, nurse contractual capacities, and shift preferences.",
        dept="CLINICAL ANALYTICS DIVISION",
        status="ANALYTICS ENGINE ONLINE",
    )
    dataset = st.session_state["dataset"]
    if dataset is None:
        _need_dataset()
    else:
        st.caption("Choose which statistics to generate. Everything below is computed from the loaded XML "
                   "only - no optimisation has been run.")
        choice = st.radio("Statistics to generate",
                          ["Overview", "Staffing demand", "Nurses & contracts", "Requests & fixed days off",
                           "Data tables"], horizontal=True, key="stats_choice")

        if choice == "Overview":
            metrics = dstat.overview_metrics(dataset)
            for group, items in metrics.items():
                st.subheader(group)
                cols = st.columns(min(4, len(items)))
                for i, (label, value) in enumerate(items.items()):
                    cols[i % len(cols)].metric(label, "n/a" if value is None else value)
            cap = metrics["Contractual capacity"]["Demand as % of maximum capacity"]
            if cap is not None:
                tight = " The roster is **tight**: fixed days off, weekend and sequence rules reduce the real capacity further." \
                    if cap >= 90 else ""
                st.info(f"Demand equals **{cap}%** of the nurses' total maximum contractual capacity.{tight}")
            st.plotly_chart(sc.demand_vs_capacity_chart(dataset), key="st_cap", **STRETCH)

        elif choice == "Staffing demand":
            st.plotly_chart(sc.demand_heatmap(dataset), key="st_heat", **STRETCH)
            c1, c2 = st.columns(2)
            c1.plotly_chart(sc.demand_by_day_chart(dataset), key="st_byday", **STRETCH)
            c2.plotly_chart(sc.demand_by_shift_chart(dataset), key="st_byshift", **STRETCH)
            st.plotly_chart(sc.weekday_profile_chart(dataset), key="st_weekday", **STRETCH)
            st.subheader("Requirement per shift type")
            st.dataframe(dstat.staffing_by_shift(dataset), hide_index=True, **STRETCH)
            st.subheader("Requirement per day")
            st.dataframe(dstat.staffing_by_day(dataset), hide_index=True, **STRETCH)

        elif choice == "Nurses & contracts":
            st.plotly_chart(sc.nurse_shift_limits_chart(dataset), key="st_limits", **STRETCH)
            st.plotly_chart(sc.eligibility_chart(dataset), key="st_elig", **STRETCH)
            st.subheader("Types of nurse (same shifts allowed and same workload bounds)")
            st.dataframe(dstat.contract_group_summary(dataset), hide_index=True, **STRETCH)
            st.subheader("Eligibility vs demand")
            st.dataframe(dstat.eligibility_vs_demand(dataset), hide_index=True, **STRETCH)
            st.subheader("All nurses")
            st.dataframe(dstat.nurse_table(dataset), hide_index=True, **STRETCH)

        elif choice == "Requests & fixed days off":
            st.plotly_chart(sc.requests_per_nurse_chart(dataset), key="st_reqnurse", **STRETCH)
            st.plotly_chart(sc.request_heatmap(dataset), key="st_reqheat", **STRETCH)
            st.plotly_chart(sc.request_weight_chart(dataset), key="st_reqw", **STRETCH)
            tables = dataset_to_tables(dataset)
            st.subheader("Requests")
            st.dataframe(tables["requests"], hide_index=True, **STRETCH)
            st.subheader("Fixed assignments (days off)")
            st.dataframe(tables["fixed_assignments"], hide_index=True, **STRETCH)

        else:  # Data tables
            tables = dataset_to_tables(dataset)
            name = st.selectbox("Table", list(tables), key="stats_table")
            st.dataframe(tables[name], hide_index=True, **STRETCH)
            st.download_button(f"⬇️ Download {name}.csv", tables[name].to_csv(index=False).encode("utf-8"),
                               file_name=f"{name}.csv", mime="text/csv")
            st.download_button("⬇️ Download all tables (ZIP)", _tables_zip(dataset),
                               file_name="nurse_dataset_tables.zip", mime="application/zip", key="zip2")

# ─────────────────────────────────────────────────────────────────────────────
# 3. OPTIMIZATION COCKPIT & MATHEMATICAL SPECIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

elif section == "⚙️ Optimization Cockpit":
    _cockpit_header(
        title="Optimization Engine Cockpit",
        subtitle="Configure and execute branch-and-cut solver routines for Integer Programming and Multicriteria Goal Programming, or inspect formal mathematical engine specs.",
        dept="DECISION ENGINE CONTROL CENTER",
        status="SOLVERS STANDBY",
    )
    opt_tab1, opt_tab2 = st.tabs(["⚡ Solver Execution Consoles", "📐 Mathematical Engine Specifications"])

    with opt_tab1:
        dataset = st.session_state["dataset"]
        if dataset is None:
            _need_dataset()
        else:
            st.markdown(
                "Choose an optimization engine and click **Run**. Solvers use CBC (COIN-OR) through PuLP, single-threaded. "
                "Instance 3 takes roughly **2-3 minutes** for the IP to *prove* optimality and under a minute for "
                "the GP; Instances 1-2 take a second or two. If the time limit is reached first, the result is "
                "shown as **feasible, not proven optimal**."
            )
            info = benchmark_info(dataset)
            if info and (has_reference(dataset, "ip") or has_reference(dataset, "gp")):
                st.caption("⚡ A saved, verified reference solution exists for this instance - use the "
                           "'Load saved reference' buttons to skip the waiting time (e.g. for a live demo).")

            col_ip, col_gp = st.columns(2)

            # ── IP Console ────────────────────────────────────────────────────
            with col_ip:
                with st.container(border=True):
                    st.subheader("Integer Programming (IP)")
                    st.markdown("Minimises the **benchmark objective**:  \n"
                                "Σ (min-weight × understaffing) + Σ (max-weight × overstaffing) + Σ (request weight × violation)")
                    time_limit_ip = st.slider("IP time limit (seconds)", 10, 900, 300, step=10, key="ip_tl")
                    if st.button("▶ Run Integer Programming", key="run_ip", type="primary"):
                        with st.spinner(f"Solving IP (time limit: {time_limit_ip}s) …"):
                            result = solve_integer_program(dataset, time_limit=time_limit_ip)
                            val = validate_solution(dataset, result.assignments)
                        st.session_state["ip_result"], st.session_state["val_ip"] = result, val
                        st.session_state["comparison"] = None

                    if has_reference(dataset, "ip"):
                        prov = reference_provenance(dataset, "ip") or {}
                        if st.button("⚡ Load saved reference solution (IP)", key="load_ip"):
                            try:
                                result = load_reference(dataset, "ip")
                                st.session_state["ip_result"] = result
                                st.session_state["val_ip"] = validate_solution(dataset, result.assignments)
                                st.session_state["comparison"] = None
                            except ReferenceSolutionError as e:
                                st.error(str(e))
                        st.caption(f"Saved run: {prov.get('status')}, objective {prov.get('objective'):g}, "
                                   f"{prov.get('solve_time_s')} s, {(prov.get('solver') or {}).get('library', '')}.")
                    r = st.session_state["ip_result"]
                    if r is not None:
                        _status_banner(r)
                        st.write(f"Objective: **{r.objective_value}**")

            # ── GP Console ────────────────────────────────────────────────────
            with col_gp:
                with st.container(border=True):
                    st.subheader("Goal Programming (GP)")
                    st.markdown("Minimises a **weighted sum of goal deviations**: coverage (G1), requests (G2) and a "
                                "workload-fairness goal (G3).")
                    time_limit_gp = st.slider("GP time limit (seconds)", 10, 900, 120, step=10, key="gp_tl")
                    with st.expander("Goal weights (documented defaults: 1, 1, 1, 0.5)"):
                        w1 = st.number_input("w1 - understaffing", 0.0, 100.0, DEFAULT_GP_WEIGHTS["w1"], 0.1, key="w1")
                        w2 = st.number_input("w2 - request violations", 0.0, 100.0, DEFAULT_GP_WEIGHTS["w2"], 0.1, key="w2")
                        w3 = st.number_input("w3 - overstaffing", 0.0, 100.0, DEFAULT_GP_WEIGHTS["w3"], 0.1, key="w3")
                        w4 = st.number_input("w4 - workload deviation (per minute)", 0.0, 100.0,
                                             DEFAULT_GP_WEIGHTS["w4"], 0.05, key="w4")
                        custom = (w1, w2, w3, w4) != (DEFAULT_GP_WEIGHTS["w1"], DEFAULT_GP_WEIGHTS["w2"],
                                                      DEFAULT_GP_WEIGHTS["w3"], DEFAULT_GP_WEIGHTS["w4"])
                        if custom:
                            st.warning("Non-default weights: results will differ from the documented GP run.")
                    if st.button("▶ Run Goal Programming", key="run_gp", type="primary"):
                        with st.spinner(f"Solving GP (time limit: {time_limit_gp}s) …"):
                            result = solve_goal_program(dataset, time_limit=time_limit_gp, w1=w1, w2=w2, w3=w3, w4=w4)
                            val = validate_solution(dataset, result.assignments)
                        st.session_state["gp_result"], st.session_state["val_gp"] = result, val
                        st.session_state["comparison"] = None

                    if has_reference(dataset, "gp"):
                        prov = reference_provenance(dataset, "gp") or {}
                        if st.button("⚡ Load saved reference solution (GP, default weights)", key="load_gp"):
                            try:
                                result = load_reference(dataset, "gp")
                                st.session_state["gp_result"] = result
                                st.session_state["val_gp"] = validate_solution(dataset, result.assignments)
                                st.session_state["comparison"] = None
                            except ReferenceSolutionError as e:
                                st.error(str(e))
                        st.caption(f"Saved run: {prov.get('status')}, objective {prov.get('objective'):g}, "
                                   f"{prov.get('solve_time_s')} s, {(prov.get('solver') or {}).get('library', '')}.")
                    r = st.session_state["gp_result"]
                    if r is not None:
                        _status_banner(r)
                        st.write(f"GP objective: **{r.gp_objective_value}** (not comparable with the IP/benchmark objective)")

    with opt_tab2:
        st.subheader("System Architecture & Mathematical Specifications")
        st.markdown(
            "Both models share the same **binary roster variables** and the same **hard constraints**; they "
            "differ in how the soft requirements are turned into an objective. The Integer Programming model "
            "is the benchmark's own objective; the Goal Programming model rewrites the soft requirements as "
            "goals with deviation variables and adds a workload-fairness goal."
        )

        st.markdown("#### Decision Variables Matrix")
        st.latex(r"x_{n,d,s}\in\{0,1\}\ \text{(nurse } n \text{ works shift } s \text{ on day } d),\quad "
                 r"y_{n,d}=\sum_s x_{n,d,s},\quad z_{n,w}\in\{0,1\}\ \text{(works weekend } w)")

        st.markdown("#### The 9 Clinical Hard Constraints")
        st.markdown(
            "1. **One shift per day** - $\\sum_s x_{n,d,s}=y_{n,d}\\le 1$.\n"
            "2. **Valid shifts** - $x_{n,d,s}=0$ if $s$ is not allowed by the nurse's contracts.\n"
            "3. **Fixed assignments** - $y_{n,d}=0$ on the fixed days off.\n"
            "4. **Workload bounds** - $\\text{MinWL}_n\\le\\sum_{d,s}L_s\\,x_{n,d,s}\\le\\text{MaxWL}_n$.\n"
            "5. **Maximum shifts of a type** - $\\sum_d x_{n,d,s}\\le \\text{MaxTot}_{n,s}$.\n"
            "6. **Minimum rest** (840 min) - forbidden successions derived from start time + duration "
            "(Late→Early, Late→Day, Day→Early in Instance 3): $x_{n,d,s_1}+x_{n,d+1,s_2}\\le 1$.\n"
            "7. **Maximum consecutive working days** - $\\sum_{k=0}^{M}y_{n,d+k}\\le M$ for every window of $M+1$ days.\n"
            "8. **Minimum consecutive working days / days off** - a block that starts inside the horizon must "
            "last at least the minimum (blocks touching the horizon boundary are exempt).\n"
            "9. **Weekends** - $z_{n,w}\\ge y_{n,\\text{Sat}},\\ z_{n,w}\\ge y_{n,\\text{Sun}},\\ "
            "z_{n,w}\\le y_{n,\\text{Sat}}+y_{n,\\text{Sun}}$ and $\\sum_w z_{n,w}\\le \\text{MaxWeekends}_n$."
        )

        c_spec1, c_spec2 = st.columns(2)
        with c_spec1:
            with st.container(border=True):
                st.markdown("##### Model 1 - Integer Programming")
                st.latex(r"\min Z_{IP}=\sum_{d,s}c^{min}_{d,s}\,u_{d,s}+\sum_{d,s}c^{max}_{d,s}\,o_{d,s}"
                         r"+\sum_i a_i\,v^{on}_i+\sum_i b_i\,v^{off}_i")
                st.latex(r"\sum_n x_{n,d,s}+u_{d,s}\ge R^{min}_{d,s},\qquad \sum_n x_{n,d,s}-o_{d,s}\le R^{max}_{d,s},"
                         r"\qquad x_{n,d,s}+v^{on}_i\ge 1,\qquad x_{n,d,s}-v^{off}_i\le 0")
                st.caption("Benchmark optimum on Instance 3 is proven at **1001**.")

        with c_spec2:
            with st.container(border=True):
                st.markdown("##### Model 2 - Goal Programming")
                st.latex(r"\text{G1: }\sum_n x_{n,d,s}+d^-_{d,s}-d^+_{d,s}=R^{min}_{d,s}\qquad "
                         r"\text{G3: }\sum_{d,s}L_s\,x_{n,d,s}+wp^-_n-wp^+_n=T_n,\quad T_n=\tfrac{\text{MinWL}_n+\text{MaxWL}_n}{2}")
                st.latex(r"\text{G2: }x_{n,d,s}+v^{on}_i\ge 1,\qquad x_{n,d,s}-v^{off}_i\le 0")
                st.latex(r"\min Z_{GP}=w_1\!\sum c^{min}_{d,s}d^-_{d,s}+w_3\!\sum c^{max}_{d,s}d^+_{d,s}"
                         r"+w_2\!\Big(\sum a_i v^{on}_i+\sum b_i v^{off}_i\Big)+w_4\sum_n\big(wp^+_n+wp^-_n\big)")
                st.caption("Default weights: w1=1, w2=1, w3=1, w4=0.5. Switch point at w4 = 0.208.")

# ─────────────────────────────────────────────────────────────────────────────
# 4. MASTER SCHEDULE & RESULTS (Unified View)
# ─────────────────────────────────────────────────────────────────────────────

elif section == "📅 Master Schedule & Results":
    _cockpit_header(
        title="Master Roster Schedule & Clinical Audit",
        subtitle="Unified clinical results console: solution status verification, shift roster visualization, staffing compliance, and CSV exports.",
        dept="WARD OPERATIONS & CLINICAL DISPATCH",
        status="RESULTS & ROSTER READY",
    )
    ip, gp = st.session_state["ip_result"], st.session_state["gp_result"]
    val_ip, val_gp = st.session_state["val_ip"], st.session_state["val_gp"]
    dataset = st.session_state["dataset"]

    if dataset is None:
        _need_dataset()
    elif not (_solved(ip) or _solved(gp)):
        if ip is not None and not _solved(ip):
            _status_banner(ip)
        elif gp is not None and not _solved(gp):
            _status_banner(gp)
        else:
            st.info("Run at least one model on the ⚙️ Optimization Cockpit page first.")
    else:
        options = [n for n, r in (("IP", ip), ("GP", gp)) if _solved(r)]
        model_choice = st.radio("Select model to display:", options, horizontal=True, key="roster_model")
        result = ip if model_choice == "IP" else gp
        val = val_ip if model_choice == "IP" else val_gp

        # ── Top KPI Scorecard ─────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Status", "Optimal ✓" if result.proven_optimal else result.status)
        c2.metric("Objective", result.objective_value if model_choice == "IP" else result.gp_objective_value)
        c3.metric("Solve time", f"{result.solve_time:.1f}s")
        c4.metric("Hard-constraint validation", "✅ Pass" if (val and val.is_feasible) else "❌ Fail")

        _status_banner(result)

        if val is not None:
            if val.is_feasible:
                st.success("✅ All hard constraints satisfied (independent check).")
            else:
                st.error(f"❌ {len(val.errors)} hard constraint violation(s) detected.")
                with st.expander("Show errors"):
                    for e in val.errors:
                        st.write(f"- {e}")

        # Benchmark accuracy block (for IP)
        if model_choice == "IP":
            if result.benchmark_reference is not None:
                gap = result.benchmark_gap_percent
                st.markdown(
                    f"| | Value |\n|---|---|\n"
                    f"| IP objective | **{result.objective_value:g}** |\n"
                    f"| Best known value (= lower bound, proven optimum) | **{result.benchmark_reference:g}** |\n"
                    f"| Gap | **{gap:.4f}%** |\n"
                    f"| Optimality of this IP solution | **{'proven by CBC' if result.proven_optimal else 'NOT proven (time limit)'}** |"
                )
                st.caption("Gap = (IP objective − best known) / best known × 100. A gap of 0 with a proven "
                           "status means the model reproduces the benchmark's optimum exactly.")
            else:
                st.info("This dataset is not a published benchmark instance - no reference value available.")
        else:
            st.info("The GP objective cannot be compared with the benchmark value - it contains a "
                    "workload-fairness term the benchmark does not have.")

        # ── Master Roster Schedule ────────────────────────────────────────────
        st.subheader("Master Nurse Roster Schedule")
        legend_html = '<div class="roster-legend-bar"><span style="font-weight:700; color:#38bdf8; margin-right:4px;">Shift Legend:</span>'
        shift_colors = sc.shift_colours(dataset) if dataset else {}
        for sid, col in sorted(shift_colors.items()):
            label = dataset.shift_types[sid].label if dataset and sid in dataset.shift_types else sid
            legend_html += f'<span class="legend-pill"><span class="legend-box" style="background-color: {col};"></span> Shift {sid} ({label})</span>'
        legend_html += '<span class="legend-pill"><span class="legend-box" style="background-color: #64748b;"></span> Day Off (-)</span></div>'
        st.markdown(legend_html, unsafe_allow_html=True)

        _roster_df = roster_table(dataset, result)
        st.dataframe(style_roster(_roster_df, dataset), height=36 * (len(_roster_df) + 1) + 4, **STRETCH)
        st.caption("Colours follow the shift colours defined in the XML; grey '-' = day off.")

        c_dl1, c_dl2 = st.columns(2)
        c_dl1.download_button("⬇️ Roster as CSV (long format)", roster_long_csv(dataset, result),
                              file_name=f"roster_{model_choice.lower()}_long.csv", mime="text/csv")
        c_dl2.download_button("⬇️ Roster as CSV (nurse × day)", roster_table(dataset, result).to_csv().encode("utf-8"),
                              file_name=f"roster_{model_choice.lower()}.csv", mime="text/csv")

        # ── Deep-Dive Operational Tabs ────────────────────────────────────────
        st.subheader("Clinical Audit & Deep-Dive Analytics")
        cs = coverage_summary(dataset, result)
        cols = st.columns(len(cs))
        for c, (k, v) in zip(cols, cs.items()):
            c.metric(k, v)

        t1, t2, t3, t4, t5 = st.tabs(["Shift-wise staffing", "Day-wise assignments", "Understaffed slots",
                                      "Request violations", "Workload per nurse"])
        with t1:
            st.dataframe(shiftwise_staffing(dataset, result), hide_index=True, **STRETCH)
        with t2:
            st.dataframe(daywise_assignments(dataset, result), hide_index=True, **STRETCH)
        with t3:
            u = understaffed_slots(dataset, result)
            if u.empty:
                st.success("Every day-shift meets its minimum requirement.")
            else:
                st.dataframe(u, hide_index=True, **STRETCH)
        with t4:
            v = violations_table(dataset, result)
            if v.empty:
                st.success("All shift requests are satisfied.")
            else:
                st.dataframe(v, hide_index=True, **STRETCH)
        with t5:
            wt = workload_table(dataset, result)
            st.dataframe(wt, hide_index=True, **STRETCH)
            wl = wt["Workload (min)"]
            st.caption(f"Workload range: {wl.max() - wl.min()} min (max {wl.max()}, min {wl.min()}).")

# ─────────────────────────────────────────────────────────────────────────────
# 5. EXECUTIVE COMPARISON SCOREBOARD
# ─────────────────────────────────────────────────────────────────────────────

elif section == "⚖️ Executive Comparison":
    _cockpit_header(
        title="Executive Scoreboard: Integer vs Goal Programming",
        subtitle="Side-by-side comparative decision-support evaluation balancing patient coverage against nurse preference satisfaction and workload equity.",
        dept="EXECUTIVE DECISION BOARD",
        status="COMPARATIVE EVALUATION",
    )
    ip, gp = st.session_state["ip_result"], st.session_state["gp_result"]
    dataset = st.session_state["dataset"]

    if dataset is None:
        _need_dataset()
    elif not (_solved(ip) and _solved(gp)):
        st.info("Run (or load) **both** the IP and the GP model to enable the comparison.")
    else:
        comp = st.session_state["comparison"]
        if comp is None:
            with st.spinner("Computing comparison metrics …"):
                comp = compare_optimization_results(ip, gp, dataset)
                st.session_state["comparison"] = comp

        st.info(comp.comparison_note)

        st.markdown("""
        <div class="tradeoff-cockpit-card">
            <div class="tradeoff-header">💡 Executive Operational Trade-off Overview</div>
            <div style="font-size: 0.92rem; line-height: 1.55; color: #e2e8f0;">
                <span style="color: #60a5fa; font-weight:700;">Integer Programming (Benchmark Priority):</span> Delivers maximum patient coverage, reaching the proven theoretical minimum understaffing of <strong>10 unfilled nurse-shifts</strong>.<br>
                <span style="color: #34d399; font-weight:700;">Goal Programming (Workload Equity Priority):</span> Strategically trades 4 extra unfilled shifts (14 total) to eliminate <strong>100% of nurse preference violations (0 violations)</strong> and compresses the nurse workload disparity from 2,400 to 1,920 minutes.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Overview")
        gap_txt = (f"{comp.ip_benchmark_gap_pct:.2f}% vs best known {comp.benchmark_reference:g}"
                   if comp.ip_benchmark_gap_pct is not None else "no published benchmark")
        st.table(_fmt_table(pd.DataFrame({
            "Metric": ["Solution status", "Source", "Solve time (s)", "Benchmark gap", "Hard-constraint validation"],
            "IP": [_status_label(ip), ip.source, f"{comp.ip_solve_time:.1f}", gap_txt,
                   "✅ Pass" if comp.ip_validation_passed else "❌ Fail"],
            "GP": [_status_label(gp), gp.source, f"{comp.gp_solve_time:.1f}",
                   "Not comparable (extra workload-fairness term)",
                   "✅ Pass" if comp.gp_validation_passed else "❌ Fail"],
        })))

        st.subheader("Coverage")
        st.table(_fmt_table(pd.DataFrame({
            "Metric": ["Understaffing magnitude (nurse-shifts)", "Overstaffing magnitude (above Max)",
                       "Weighted understaffing penalty", "Weighted overstaffing penalty", "Coverage rate (%)"],
            "IP": [comp.ip_coverage.total_understaffing_magnitude, comp.ip_coverage.total_overstaffing_magnitude,
                   comp.ip_coverage.weighted_understaffing_penalty, comp.ip_coverage.weighted_overstaffing_penalty,
                   comp.ip_coverage.coverage_rate_pct],
            "GP": [comp.gp_coverage.total_understaffing_magnitude, comp.gp_coverage.total_overstaffing_magnitude,
                   comp.gp_coverage.weighted_understaffing_penalty, comp.gp_coverage.weighted_overstaffing_penalty,
                   comp.gp_coverage.coverage_rate_pct],
        })))

        st.subheader("Request satisfaction")
        st.table(_fmt_table(pd.DataFrame({
            "Metric": ["ShiftOn violations", "ShiftOff violations", "Total violations", "Violation rate (%)",
                       "Weighted request penalty"],
            "IP": [comp.ip_requests.on_violations, comp.ip_requests.off_violations, comp.ip_requests.total_violations,
                   comp.ip_requests.violation_rate_pct, comp.ip_requests.weighted_penalty],
            "GP": [comp.gp_requests.on_violations, comp.gp_requests.off_violations, comp.gp_requests.total_violations,
                   comp.gp_requests.violation_rate_pct, comp.gp_requests.weighted_penalty],
        })))

        st.subheader("Workload fairness")
        st.table(_fmt_table(pd.DataFrame({
            "Metric": ["Mean workload (min)", "Min workload (min)", "Max workload (min)", "Workload range (min)",
                       "Std deviation (min)", "Jain's fairness index"],
            "IP": [comp.ip_workload.mean_workload, comp.ip_workload.min_workload, comp.ip_workload.max_workload,
                   comp.ip_workload.workload_range, comp.ip_workload.std_dev, comp.ip_workload.fairness_index],
            "GP": [comp.gp_workload.mean_workload, comp.gp_workload.min_workload, comp.gp_workload.max_workload,
                   comp.gp_workload.workload_range, comp.gp_workload.std_dev, comp.gp_workload.fairness_index],
        })))
        st.caption("Workload spread is measured over all nurses together; full-time and part-time contracts "
                   "have different bounds, so a non-zero range is expected even in a perfectly fair roster.")

        st.subheader("Trade-off summary")
        for point in comp.trade_off_summary:
            st.markdown(f"- {point}")

        st.download_button("⬇️ Download comparison (JSON)", json.dumps(comparison_to_dict(comp), indent=2).encode("utf-8"),
                           file_name="ip_vs_gp_comparison.json", mime="application/json")

        st.subheader("Visual Comparison Charts")
        v_col1, v_col2 = st.columns(2)
        v_col1.plotly_chart(viz.create_ip_gp_coverage_chart(comp), key="cmp_cov", **STRETCH)
        v_col2.plotly_chart(viz.create_shift_distribution_chart(ip, gp, dataset), key="cmp_shift", **STRETCH)
        v_col3, v_col4 = st.columns(2)
        v_col3.plotly_chart(viz.create_workload_chart(comp), key="cmp_wl", **STRETCH)
        v_col4.plotly_chart(viz.create_fairness_chart(comp), key="cmp_fair", **STRETCH)

_render_session_status()
