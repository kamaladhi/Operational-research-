"""
Plotly charts for the pre-optimisation Statistics page.

All charts are built from ``src.data_statistics`` (which in turn only uses fields from the XML).
Shift colours come from the XML's own ``<Color>`` elements so every chart in the app uses the same
colour for the same shift.
"""

from typing import Dict

import plotly.express as px
import plotly.graph_objects as go

from src import data_statistics as ds
from src.data_model import ParsedDataset

_FALLBACK = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b"]
OFF_COLOUR = "#e9ecef"


def shift_colours(dataset: ParsedDataset) -> Dict[str, str]:
    """Shift ID -> colour, using the XML <Color> (a CSS colour name) where present."""
    out = {}
    for i, sid in enumerate(sorted(dataset.shift_types)):
        label = (dataset.shift_types[sid].label or "").strip()
        out[sid] = label if label else _FALLBACK[i % len(_FALLBACK)]
    return out


def demand_heatmap(dataset: ParsedDataset) -> go.Figure:
    """Required nurses for every day (columns) and shift (rows)."""
    mat = ds.staffing_matrix(dataset)
    fig = px.imshow(
        mat.T.values, x=list(mat.index), y=list(mat.columns), text_auto=True, aspect="auto",
        color_continuous_scale="Blues", labels=dict(x="Day", y="Shift", color="Required"),
    )
    fig.update_layout(title="Required nurses per day and shift", coloraxis_showscale=False,
                      xaxis_tickangle=-45, margin=dict(t=50))
    return fig


def demand_by_day_chart(dataset: ParsedDataset) -> go.Figure:
    """Stacked bars: total required nurses per day, split by shift."""
    mat = ds.staffing_matrix(dataset)
    colours = shift_colours(dataset)
    fig = go.Figure()
    for s in mat.columns:
        fig.add_trace(go.Bar(name=f"Shift {s}", x=list(mat.index), y=mat[s].tolist(), marker_color=colours[s]))
    fig.update_layout(barmode="stack", title="Required nurses per day (stacked by shift)",
                      xaxis_title="Day", yaxis_title="Nurses required", xaxis_tickangle=-45,
                      legend_title_text="", margin=dict(t=50))
    return fig


def demand_by_shift_chart(dataset: ParsedDataset) -> go.Figure:
    """Distribution of the daily requirement for each shift type (box plot with every day shown)."""
    mat = ds.staffing_matrix(dataset)
    colours = shift_colours(dataset)
    fig = go.Figure()
    for s in mat.columns:
        fig.add_trace(go.Box(y=mat[s].tolist(), name=f"Shift {s}", boxpoints="all", jitter=0.4,
                             pointpos=0, marker_color=colours[s], boxmean=True))
    fig.update_layout(title="Distribution of the daily requirement per shift (diamond = mean)",
                      yaxis_title="Nurses required per day", showlegend=False, margin=dict(t=50))
    return fig


def weekday_profile_chart(dataset: ParsedDataset) -> go.Figure:
    prof = ds.weekday_profile(dataset)
    fig = px.bar(prof, x="Weekday", y="Average required nurses", text_auto=".1f",
                 title="Average total requirement by weekday")
    fig.update_traces(marker_color="#4c78a8")
    fig.update_layout(margin=dict(t=50))
    return fig


def demand_vs_capacity_chart(dataset: ParsedDataset) -> go.Figure:
    """Total demand against the nurses' contractual minimum and maximum number of shifts."""
    emp = ds.nurse_table(dataset)
    demand = sum(c.min_nurses for c in dataset.cover_requirements)
    lo = emp["Min shifts"].sum()
    hi = emp["Max shifts"].sum()
    fig = go.Figure(go.Bar(
        x=["Sum of contractual MIN shifts", "Required nurse-shifts (demand)", "Sum of contractual MAX shifts"],
        y=[lo, demand, hi], text=[lo, demand, hi], textposition="outside",
        marker_color=["#9ecae9", "#e45756", "#4c78a8"]))
    fig.update_layout(title="Demand vs contractual capacity (nurse-shifts)", yaxis_title="Nurse-shifts",
                      margin=dict(t=50), yaxis_range=[0, max(hi, demand) * 1.15])
    return fig


def nurse_shift_limits_chart(dataset: ParsedDataset) -> go.Figure:
    """Floating bars: each nurse's contractual [min, max] number of shifts over the horizon."""
    emp = ds.nurse_table(dataset).sort_values(["Max shifts", "Nurse"], ascending=[False, True])
    span = (emp["Max shifts"] - emp["Min shifts"]).tolist()
    fig = go.Figure(go.Bar(
        y=emp["Nurse"].tolist(), x=span, base=emp["Min shifts"].tolist(), orientation="h",
        marker_color="#4c78a8",
        customdata=list(zip(emp["Min shifts"], emp["Max shifts"], emp["Valid shifts"])),
        hovertemplate="Nurse %{y}<br>Shifts: %{customdata[0]} to %{customdata[1]}"
                      "<br>Allowed shifts: %{customdata[2]}<extra></extra>"))
    fig.update_layout(title="Contractual workload range per nurse (number of shifts)",
                      xaxis_title="Shifts in the planning period", yaxis=dict(autorange="reversed"),
                      margin=dict(t=50), height=max(380, 22 * len(emp) + 120))
    return fig


def eligibility_chart(dataset: ParsedDataset) -> go.Figure:
    el = ds.eligibility_vs_demand(dataset)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Nurses allowed to work the shift", x=el["Shift"], y=el["Nurses allowed to work it"],
                         marker_color="#4c78a8", text=el["Nurses allowed to work it"], textposition="outside"))
    fig.add_trace(go.Bar(name="Peak daily demand", x=el["Shift"], y=el["Peak daily demand"],
                         marker_color="#e45756", text=el["Peak daily demand"], textposition="outside"))
    fig.update_layout(barmode="group", title="Shift eligibility vs peak demand", xaxis_title="Shift",
                      yaxis_title="Nurses", margin=dict(t=50), legend_title_text="")
    return fig


def requests_per_nurse_chart(dataset: ParsedDataset) -> go.Figure:
    r = ds.requests_per_nurse(dataset)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="ShiftOn (wants to work)", x=r["Nurse"], y=r["ShiftOn requests"], marker_color="#54a24b"))
    fig.add_trace(go.Bar(name="ShiftOff (wants to avoid)", x=r["Nurse"], y=r["ShiftOff requests"], marker_color="#e45756"))
    fig.add_trace(go.Bar(name="Fixed day off", x=r["Nurse"], y=r["Fixed days off"], marker_color="#9d9da1"))
    fig.update_layout(barmode="stack", title="Requests and fixed days off per nurse", xaxis_title="Nurse",
                      yaxis_title="Count", margin=dict(t=50), legend_title_text="")
    return fig


def request_heatmap(dataset: ParsedDataset) -> go.Figure:
    """Nurse x Day map of requests: green = wants to work, red = wants to avoid, grey = fixed day off."""
    codes, text = ds.request_matrix(dataset)
    # discrete colour scale for the codes -1, 0, 1, 2
    scale = [[0.00, "#e45756"], [0.25, "#e45756"],
             [0.25, "#f5f6f7"], [0.50, "#f5f6f7"],
             [0.50, "#54a24b"], [0.75, "#54a24b"],
             [0.75, "#9d9da1"], [1.00, "#9d9da1"]]
    fig = go.Figure(go.Heatmap(
        z=codes.values, x=list(codes.columns), y=list(codes.index), zmin=-1, zmax=2,
        colorscale=scale, showscale=False, xgap=2, ygap=2,
        text=text.values, texttemplate="%{text}", hoverinfo="x+y+text"))
    fig.update_layout(title="Requests map  (green = ShiftOn, red = ShiftOff, grey X = fixed day off)",
                      yaxis=dict(autorange="reversed"), xaxis_tickangle=-45, margin=dict(t=50),
                      height=max(420, 24 * len(codes) + 140))
    return fig


def request_weight_chart(dataset: ParsedDataset) -> go.Figure:
    d = ds.request_weight_distribution(dataset)
    if d.empty:
        fig = go.Figure()
        fig.update_layout(title="Penalty weights of the requests (no requests in this dataset)")
        return fig
    fig = px.bar(d, x="Weight", y="Count", color="Type", barmode="group", text_auto=True,
                 color_discrete_map={"ShiftOn": "#54a24b", "ShiftOff": "#e45756"},
                 title="Penalty weights of the requests")
    fig.update_xaxes(type="category")
    fig.update_layout(margin=dict(t=50), legend_title_text="")
    return fig
