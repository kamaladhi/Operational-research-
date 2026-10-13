"""
Visualization module for Nurse Rostering optimization results.

Generates Plotly figures for Streamlit based on OptimizationResult,
GoalProgrammingResult, and ComparisonResult objects.  (Pre-optimisation charts of the raw
dataset live in ``src/stat_charts.py``.)
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Any, Optional

from src.data_model import ParsedDataset
from src.comparison import ComparisonResult
from src.stat_charts import OFF_COLOUR, shift_colours
from src.tables import day_labels


def create_coverage_chart(dataset: ParsedDataset, result: Any) -> go.Figure:
    """
    1. Staffing Coverage
    Chart showing required vs actual staffing for every day/shift.
    Works for both OptimizationResult (IP) and GoalProgrammingResult (GP).
    """
    records = []

    assigned_cov = result.coverage_by_day_shift
    reqs = sorted(dataset.cover_requirements, key=lambda cr: (cr.day, cr.shift))

    for cr in reqs:
        actual = assigned_cov.get((cr.day, cr.shift), 0)
        label = f"Day {cr.day} ({cr.shift})"
        records.append({"DayShift": label, "Type": "Required (Min)", "Nurses": cr.min_nurses})
        records.append({"DayShift": label, "Type": "Actual Assigned", "Nurses": actual})

    df = pd.DataFrame(records)

    fig = px.bar(
        df,
        x="DayShift",
        y="Nurses",
        color="Type",
        barmode="group",
        title="Staffing Coverage per Day/Shift",
        labels={"DayShift": "Day and Shift", "Nurses": "Number of Nurses"},
        color_discrete_sequence=["#EF553B", "#636EFA"]
    )
    fig.update_layout(xaxis_tickangle=-45)
    return fig


def create_shortfall_heatmap(dataset: ParsedDataset, result: Any) -> go.Figure:
    """Day x Shift map of (assigned - required): red = understaffed, white = exact, blue = surplus."""
    labels = day_labels(dataset)
    shifts = sorted(dataset.shift_types)
    z = [[0] * len(labels) for _ in shifts]
    req = {(c.day, c.shift): c.min_nurses for c in dataset.cover_requirements}
    for i, s in enumerate(shifts):
        for d in range(len(labels)):
            z[i][d] = result.coverage_by_day_shift.get((d, s), 0) - req.get((d, s), 0)
    bound = max(1, max(abs(v) for row in z for v in row))
    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=shifts, zmin=-bound, zmax=bound, colorscale="RdBu", showscale=False,
        text=[[("" if v == 0 else f"{v:+d}") for v in row] for row in z], texttemplate="%{text}",
        xgap=2, ygap=2, hovertemplate="%{x}<br>Shift %{y}<br>assigned - required = %{z}<extra></extra>"))
    fig.update_layout(title="Coverage shortfall map (assigned - required; red = understaffed)",
                      xaxis_tickangle=-45, margin=dict(t=50))
    return fig


def create_gp_breakdown_chart(result: Any) -> go.Figure:
    """Bar chart of the weighted components that make up the Goal Programming objective."""
    comps = {
        "Understaffing (w1)": result.total_understaffing_penalty,
        "Overstaffing (w3)": result.total_overstaffing_penalty,
        "Request violations (w2)": result.total_request_penalty,
        "Workload fairness (w4)": result.workload_fairness_penalty,
    }
    fig = go.Figure(go.Bar(x=list(comps), y=list(comps.values()), text=[f"{v:g}" for v in comps.values()],
                           textposition="outside", marker_color=["#e45756", "#f58518", "#54a24b", "#4c78a8"]))
    fig.update_layout(title="Goal Programming objective by component (weighted)", yaxis_title="Penalty units",
                      margin=dict(t=50), yaxis_range=[0, max(comps.values() or [1]) * 1.2 + 1])
    return fig


def create_ip_breakdown_chart(dataset: ParsedDataset, ip_result: Any) -> go.Figure:
    """Components of the IP (benchmark) objective, recomputed from the roster."""
    from src.evaluation import evaluate_ip
    ev = evaluate_ip(dataset, ip_result.assignments)
    comps = {
        "Understaffing": ev.understaffing_penalty,
        "Overstaffing": ev.overstaffing_penalty,
        "Request violations": ev.request_penalty,
    }
    fig = go.Figure(go.Bar(x=list(comps), y=list(comps.values()), text=[f"{v:g}" for v in comps.values()],
                           textposition="outside", marker_color=["#e45756", "#f58518", "#54a24b"]))
    fig.update_layout(title="Integer Programming objective by component", yaxis_title="Penalty units",
                      margin=dict(t=50), yaxis_range=[0, max(comps.values()) * 1.2 + 1])
    return fig


def create_ip_gp_coverage_chart(comp: ComparisonResult) -> go.Figure:
    """
    2. IP vs GP Coverage Comparison
    Compare aggregate understaffing and overstaffing.
    """
    records = [
        {"Model": "Integer Programming", "Metric": "Understaffing", "Value": comp.ip_coverage.total_understaffing_magnitude},
        {"Model": "Goal Programming", "Metric": "Understaffing", "Value": comp.gp_coverage.total_understaffing_magnitude},
        {"Model": "Integer Programming", "Metric": "Overstaffing", "Value": comp.ip_coverage.total_overstaffing_magnitude},
        {"Model": "Goal Programming", "Metric": "Overstaffing", "Value": comp.gp_coverage.total_overstaffing_magnitude},
    ]
    df = pd.DataFrame(records)

    fig = px.bar(
        df,
        x="Metric",
        y="Value",
        color="Model",
        barmode="group",
        title="IP vs GP Coverage Comparison",
        text_auto=True,
        labels={"Value": "Magnitude (Nurses)"}
    )
    return fig


def create_workload_chart(comp: ComparisonResult) -> go.Figure:
    """
    3. Nurse Workload Distribution
    Visualization of workload (minutes) per nurse.
    """
    records = []

    for emp, mins in comp.ip_workload.workload_per_nurse.items():
        records.append({"Nurse": emp, "Model": "IP", "Workload (mins)": mins})

    for emp, mins in comp.gp_workload.workload_per_nurse.items():
        records.append({"Nurse": emp, "Model": "GP", "Workload (mins)": mins})

    df = pd.DataFrame(records)
    df = df.sort_values(by="Nurse")

    fig = px.bar(
        df,
        x="Nurse",
        y="Workload (mins)",
        color="Model",
        barmode="group",
        title="Nurse Workload Distribution (IP vs GP)"
    )
    fig.update_layout(xaxis_tickangle=-45)
    return fig


def create_fairness_chart(comp: ComparisonResult) -> go.Figure:
    """
    4. Workload Fairness
    Visualize workload range, std dev, and Jain's index.
    """
    models = ["Integer Programming", "Goal Programming"]
    ranges = [comp.ip_workload.workload_range, comp.gp_workload.workload_range]
    std_devs = [comp.ip_workload.std_dev, comp.gp_workload.std_dev]
    jain = [comp.ip_workload.fairness_index, comp.gp_workload.fairness_index]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(name="Workload Range (mins)", x=models, y=ranges, marker_color='rgb(55, 83, 109)'),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(name="Standard Deviation", x=models, y=std_devs, marker_color='rgb(26, 118, 255)'),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(name="Jain's Fairness Index", x=models, y=jain, mode='lines+markers', marker_color='red'),
        secondary_y=True,
    )

    fig.update_layout(title_text="Workload Fairness Comparison", barmode='group')
    fig.update_yaxes(title_text="Minutes", secondary_y=False)
    fig.update_yaxes(title_text="Jain Index (1 = perfect)", secondary_y=True, range=[0.8, 1.05])

    return fig


def create_request_chart(comp: ComparisonResult) -> go.Figure:
    """
    5. Request Satisfaction
    IP vs GP request violations.
    """
    records = [
        {"Model": "IP", "Violation Type": "Shift On", "Violations": comp.ip_requests.on_violations},
        {"Model": "GP", "Violation Type": "Shift On", "Violations": comp.gp_requests.on_violations},
        {"Model": "IP", "Violation Type": "Shift Off", "Violations": comp.ip_requests.off_violations},
        {"Model": "GP", "Violation Type": "Shift Off", "Violations": comp.gp_requests.off_violations},
    ]
    df = pd.DataFrame(records)

    fig = px.bar(
        df,
        x="Model",
        y="Violations",
        color="Violation Type",
        title="Request Violations (IP vs GP)",
        text_auto=True,
    )
    return fig


def create_shift_distribution_chart(ip_result: Any, gp_result: Any,
                                    dataset: Optional[ParsedDataset] = None) -> go.Figure:
    """
    6. Shift Distribution
    Chart showing how many shifts of each type each model assigns.  Shift types are read from the
    rosters themselves (nothing hard-coded); colours follow the XML when a dataset is supplied.
    """
    def _count(result):
        counts = {}
        for shift in result.assignments.values():
            counts[shift] = counts.get(shift, 0) + 1
        return counts

    ip_shifts, gp_shifts = _count(ip_result), _count(gp_result)

    records = []
    for s, count in sorted(ip_shifts.items()):
        records.append({"Model": "IP", "Shift": s, "Count": count})
    for s, count in sorted(gp_shifts.items()):
        records.append({"Model": "GP", "Shift": s, "Count": count})

    df = pd.DataFrame(records)
    if df.empty:
        return go.Figure()

    fig = px.bar(
        df,
        x="Shift",
        y="Count",
        color="Model",
        barmode="group",
        title="Total Shift Type Assignments (IP vs GP)",
        text_auto=True
    )
    return fig


def create_roster_heatmap(result: Any, dataset: ParsedDataset) -> go.Figure:
    """
    7. Roster Heatmap
    Nurse x Day roster. Each shift type has its own (XML) colour, days off are light grey, and the
    cell text is the shift letter, so the picture can be read without a legend.
    """
    employees = sorted(dataset.employees.keys())
    labels = day_labels(dataset)
    shifts = sorted(dataset.shift_types)
    colours = shift_colours(dataset)
    code = {"Off": 0, **{s: i + 1 for i, s in enumerate(shifts)}}

    z, text = [], []
    for emp in employees:
        row_z, row_t = [], []
        for d in range(dataset.planning_period.days):
            shift = result.assignments.get((emp, d))
            row_z.append(code[shift] if shift in code else 0)
            row_t.append(shift if shift else "")
        z.append(row_z)
        text.append(row_t)

    # discrete colour scale: n+1 equal bands (Off + one per shift)
    n = len(code)
    palette = [OFF_COLOUR] + [colours[s] for s in shifts]
    scale = []
    for i, c in enumerate(palette):
        scale += [[i / n, c], [(i + 1) / n, c]]

    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=employees, zmin=0, zmax=n - 1 if n > 1 else 1,
        colorscale=scale, showscale=False, xgap=2, ygap=2,
        text=text, texttemplate="%{text}",
        hovertemplate="Nurse %{y}<br>%{x}<br>Shift: %{text}<extra></extra>"))
    fig.update_layout(title="Roster heat map (blank = day off)", yaxis=dict(autorange="reversed"),
                      xaxis_tickangle=-45, height=max(420, 24 * len(employees) + 140), margin=dict(t=50))
    return fig


def create_benchmark_chart(comp: ComparisonResult) -> go.Figure:
    """
    8. Benchmark Visualization
    Benchmark-oriented visualization for the IP solution ONLY.
    GP is explicitly excluded because it is not comparable.
    """
    if comp.ip_objective is None:
        return go.Figure()

    fig = go.Figure()
    note = "GP objective is mathematically incomparable and not shown."
    if comp.benchmark_reference is None:
        title = f"IP Objective (no published benchmark for this dataset)<br><span style='font-size:0.8em;color:gray'>{note}</span>"
        fig.add_trace(go.Indicator(mode="number", value=comp.ip_objective, title={"text": title},
                                   domain={'x': [0, 1], 'y': [0, 1]}))
        return fig

    proof = "proven optimal" if comp.ip_proven_optimal else "NOT proven optimal"
    exact = abs(comp.ip_objective - comp.benchmark_reference) < 1e-9
    title = (f"IP Objective vs Benchmark ({comp.benchmark_reference:g}) - IP solution {proof}"
             f"{' - matches the benchmark exactly' if exact else ''}"
             f"<br><span style='font-size:0.8em;color:gray'>{note}</span>")
    fig.add_trace(go.Indicator(
        mode="number+delta",
        value=comp.ip_objective,
        delta={"reference": comp.benchmark_reference, "position": "top", "valueformat": ".2f",
               "increasing": {"color": "#27ae60" if exact else "#c0392b"}, "decreasing": {"color": "#27ae60"}},
        title={"text": title},
        domain={'x': [0, 1], 'y': [0, 1]}
    ))
    return fig
