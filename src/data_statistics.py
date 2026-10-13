"""
On-demand descriptive statistics of a nurse-rostering dataset (before any optimisation).

Every function returns plain DataFrames / dicts so the same numbers feed the Streamlit page,
the charts (``src/stat_charts.py``), the CSV downloads and the tests.  Only quantities that can be
derived from the XML are reported.

(File name note: ``data_statistics`` rather than ``statistics`` to avoid shadowing the stdlib module.)
"""

from typing import Dict, List, Tuple

import pandas as pd

from src.data_model import ParsedDataset
from src.tables import WEEKDAYS, dataset_to_tables, day_labels, weekday_labels


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def overview_metrics(dataset: ParsedDataset) -> Dict[str, Dict[str, object]]:
    """Grouped headline numbers: dataset size, staffing demand, contractual capacity, requests."""
    pp = dataset.planning_period
    tables = dataset_to_tables(dataset)
    emp = tables["employees"]
    cover = dataset.cover_requirements
    slots = len(cover)

    total_min = sum(c.min_nurses for c in cover)
    total_max = sum(c.max_nurses for c in cover)
    on = sum(1 for r in dataset.shift_requests if r.is_on_request)
    off = len(dataset.shift_requests) - on
    max_capacity = int(emp["Max shifts"].sum()) if "Max shifts" in emp and emp["Max shifts"].notna().all() else None
    min_commit = int(emp["Min shifts"].sum()) if "Min shifts" in emp and emp["Min shifts"].notna().all() else None

    return {
        "Dataset": {
            "Nurses": len(dataset.employees),
            "Planning days": pp.days,
            "Weeks": pp.weeks,
            "Shift types": len(dataset.shift_types),
            "Contracts": len(dataset.contracts),
            "Planning period": f"{pp.start_date} to {pp.end_date}",
            "Possible nurse-day-shift assignments": len(dataset.employees) * pp.days * len(dataset.shift_types),
        },
        "Staffing demand": {
            "Day-shift cover records": slots,
            "Required nurse-shifts (sum of Min)": total_min,
            "Allowed nurse-shifts (sum of Max)": total_max,
            "Average required per day": round(total_min / pp.days, 2) if pp.days else 0,
            "Average required per day-shift": round(total_min / slots, 2) if slots else 0,
            "Smallest requirement in one day-shift": min((c.min_nurses for c in cover), default=0),
            "Largest requirement in one day-shift": max((c.min_nurses for c in cover), default=0),
        },
        "Contractual capacity": {
            "Total maximum shifts (all nurses)": max_capacity,
            "Total minimum shifts (all nurses)": min_commit,
            "Demand as % of maximum capacity": (round(100 * total_min / max_capacity, 1)
                                                if max_capacity else None),
        },
        "Requests and fixed days": {
            "ShiftOn requests (want to work)": on,
            "ShiftOff requests (want to avoid)": off,
            "Total request weight": sum(r.weight for r in dataset.shift_requests),
            "Fixed days off": sum(1 for f in dataset.fixed_assignments if f.shift == "-"),
        },
    }


# ---------------------------------------------------------------------------
# Staffing demand
# ---------------------------------------------------------------------------

def staffing_matrix(dataset: ParsedDataset, column: str = "min") -> pd.DataFrame:
    """Day x Shift matrix of the required (``min``) or maximum (``max``) number of nurses."""
    labels = day_labels(dataset)
    shifts = sorted(dataset.shift_types)
    mat = pd.DataFrame(0, index=labels, columns=shifts)
    for c in dataset.cover_requirements:
        mat.loc[labels[c.day], c.shift] = c.min_nurses if column == "min" else c.max_nurses
    mat.index.name = "Day"
    return mat


def staffing_by_shift(dataset: ParsedDataset) -> pd.DataFrame:
    """Descriptive statistics of the daily requirement for each shift type."""
    mat = staffing_matrix(dataset)
    out = pd.DataFrame({
        "Total required": mat.sum(),
        "Mean per day": mat.mean().round(2),
        "Min per day": mat.min(),
        "Max per day": mat.max(),
        "Std dev": mat.std(ddof=0).round(2),
    })
    out.index.name = "Shift"
    out["Share of demand (%)"] = (100 * out["Total required"] / out["Total required"].sum()).round(1)
    return out.reset_index()


def staffing_by_day(dataset: ParsedDataset) -> pd.DataFrame:
    """Total required nurses per day, with the calendar weekday."""
    mat = staffing_matrix(dataset)
    wd = weekday_labels(dataset)
    out = mat.copy()
    out["Total"] = out.sum(axis=1)
    out.insert(0, "Weekday", wd)
    return out.reset_index()


def weekday_profile(dataset: ParsedDataset) -> pd.DataFrame:
    """Average total demand per weekday (averaged over the weeks in the horizon)."""
    by_day = staffing_by_day(dataset)
    prof = by_day.groupby("Weekday")["Total"].mean().reindex(WEEKDAYS).dropna().round(2)
    return prof.rename("Average required nurses").reset_index()


def eligibility_vs_demand(dataset: ParsedDataset) -> pd.DataFrame:
    """For each shift: how many nurses may work it vs how much of it is demanded."""
    emp = dataset_to_tables(dataset)["employees"]
    mat = staffing_matrix(dataset)
    rows = []
    for s in sorted(dataset.shift_types):
        eligible = int(sum(1 for v in emp["Valid shifts"] if v == "all" or s in [x.strip() for x in v.split(",")]))
        peak = int(mat[s].max())
        rows.append({
            "Shift": s,
            "Nurses allowed to work it": eligible,
            "Total demand (nurse-shifts)": int(mat[s].sum()),
            "Peak daily demand": peak,
            "Peak demand / eligible nurses (%)": round(100 * peak / eligible, 1) if eligible else None,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Nurses
# ---------------------------------------------------------------------------

def nurse_table(dataset: ParsedDataset) -> pd.DataFrame:
    return dataset_to_tables(dataset)["employees"]


def contract_group_summary(dataset: ParsedDataset) -> pd.DataFrame:
    """Nurses grouped by (valid shifts, workload bounds): how many 'types' of nurse exist."""
    emp = nurse_table(dataset)
    g = (emp.groupby(["Valid shifts", "Min shifts", "Max shifts"], dropna=False)
            .agg(Nurses=("Nurse", "count"), Names=("Nurse", lambda x: ", ".join(x)))
            .reset_index().sort_values("Nurses", ascending=False))
    return g


# ---------------------------------------------------------------------------
# Requests and fixed days
# ---------------------------------------------------------------------------

def requests_per_nurse(dataset: ParsedDataset) -> pd.DataFrame:
    emp = nurse_table(dataset)
    return emp[["Nurse", "ShiftOn requests", "ShiftOff requests", "Fixed days off", "Request weight total"]]


def request_weight_distribution(dataset: ParsedDataset) -> pd.DataFrame:
    rows = [{"Weight": r.weight, "Type": "ShiftOn" if r.is_on_request else "ShiftOff"} for r in dataset.shift_requests]
    if not rows:
        return pd.DataFrame(columns=["Weight", "Type", "Count"])
    return (pd.DataFrame(rows).groupby(["Weight", "Type"]).size().rename("Count").reset_index())


def request_matrix(dataset: ParsedDataset) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Nurse x Day matrices for a heat map.

    Returns (codes, text):
        codes: 0 = nothing, 1 = ShiftOn request, -1 = ShiftOff request, 2 = fixed day off
        text:  the shift letter (e.g. 'D'), or 'X' for a fixed day off
    """
    labels = day_labels(dataset)
    nurses = sorted(dataset.employees)
    codes = pd.DataFrame(0, index=nurses, columns=labels)
    text = pd.DataFrame("", index=nurses, columns=labels)
    for f in dataset.fixed_assignments:
        if f.shift == "-":
            codes.loc[f.employee_id, labels[f.day]] = 2
            text.loc[f.employee_id, labels[f.day]] = "X"
    for r in dataset.shift_requests:
        codes.loc[r.employee_id, labels[r.day]] = 1 if r.is_on_request else -1
        text.loc[r.employee_id, labels[r.day]] = r.shift
    codes.index.name = text.index.name = "Nurse"
    return codes, text
