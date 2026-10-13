"""
Result tables for the Results / Roster pages.

Every function takes a ParsedDataset and an optimisation result (IP or GP - both expose
``assignments`` and ``coverage_by_day_shift``) and returns a DataFrame computed directly from the
roster, so the figures are identical for live solves and for saved reference runs.
"""

from typing import Any, Dict

import pandas as pd

from src.data_model import ParsedDataset
from src.integer_program import get_employee_contract_constraints
from src.stat_charts import OFF_COLOUR, shift_colours
from src.tables import day_labels, weekday_labels


def _cover_map(dataset: ParsedDataset):
    return {(c.day, c.shift): c for c in dataset.cover_requirements}


def coverage_summary(dataset: ParsedDataset, result: Any) -> Dict[str, float]:
    """Headline staffing figures for one roster."""
    cov = result.coverage_by_day_shift
    req = _cover_map(dataset)
    required = sum(c.min_nurses for c in req.values())
    met = sum(min(cov.get(k, 0), c.min_nurses) for k, c in req.items())
    under = sum(max(0, c.min_nurses - cov.get(k, 0)) for k, c in req.items())
    over = sum(max(0, cov.get(k, 0) - c.max_nurses) for k, c in req.items())
    short_slots = sum(1 for k, c in req.items() if cov.get(k, 0) < c.min_nurses)
    return {
        "Required nurse-shifts": required,
        "Assigned nurse-shifts": len(result.assignments),
        "Understaffed nurse-shifts": under,
        "Understaffed day-shifts": short_slots,
        "Overstaffed nurse-shifts (above Max)": over,
        "Coverage (%)": round(100 * met / required, 2) if required else 0.0,
    }


def shiftwise_staffing(dataset: ParsedDataset, result: Any) -> pd.DataFrame:
    """Required vs assigned nurse-shifts, summed over the horizon, for each shift type."""
    cov = result.coverage_by_day_shift
    rows = []
    for s in sorted(dataset.shift_types):
        crs = [c for c in dataset.cover_requirements if c.shift == s]
        required = sum(c.min_nurses for c in crs)
        assigned = sum(cov.get((c.day, s), 0) for c in crs)
        short = sum(max(0, c.min_nurses - cov.get((c.day, s), 0)) for c in crs)
        surplus = sum(max(0, cov.get((c.day, s), 0) - c.max_nurses) for c in crs)
        rows.append({"Shift": s, "Required": required, "Assigned": assigned, "Shortfall": short,
                     "Surplus (above Max)": surplus,
                     "Coverage (%)": round(100 * (required - short) / required, 1) if required else 100.0})
    return pd.DataFrame(rows)


def daywise_assignments(dataset: ParsedDataset, result: Any) -> pd.DataFrame:
    """One row per day: assigned/required for every shift, nurses working, nurses off."""
    cov = result.coverage_by_day_shift
    req = _cover_map(dataset)
    wd = weekday_labels(dataset)
    n_nurses = len(dataset.employees)
    shifts = sorted(dataset.shift_types)
    rows = []
    for d in range(dataset.planning_period.days):
        row = {"Day": d, "Weekday": wd[d]}
        working = 0
        short = 0
        for s in shifts:
            a = cov.get((d, s), 0)
            working += a
            c = req.get((d, s))
            row[f"{s} (assigned/required)"] = f"{a}/{c.min_nurses}" if c else str(a)
            if c:
                short += max(0, c.min_nurses - a)
        row["Nurses working"] = working
        row["Nurses off"] = n_nurses - working
        row["Understaffed by"] = short
        rows.append(row)
    return pd.DataFrame(rows)


def understaffed_slots(dataset: ParsedDataset, result: Any) -> pd.DataFrame:
    """Every day-shift that is below its minimum requirement, with the penalty it carries."""
    cov = result.coverage_by_day_shift
    wd = weekday_labels(dataset)
    rows = []
    for c in sorted(dataset.cover_requirements, key=lambda c: (c.day, c.shift)):
        a = cov.get((c.day, c.shift), 0)
        if a < c.min_nurses:
            rows.append({"Day": c.day, "Weekday": wd[c.day], "Shift": c.shift, "Required": c.min_nurses,
                         "Assigned": a, "Short by": c.min_nurses - a,
                         "Penalty (XML weight x shortfall)": c.min_weight * (c.min_nurses - a)})
    return pd.DataFrame(rows, columns=["Day", "Weekday", "Shift", "Required", "Assigned", "Short by",
                                       "Penalty (XML weight x shortfall)"])


def violations_table(dataset: ParsedDataset, result: Any) -> pd.DataFrame:
    """Violated ShiftOn / ShiftOff requests with their penalty weights."""
    wd = weekday_labels(dataset)
    rows = []
    for r in dataset.shift_requests:
        worked = result.assignments.get((r.employee_id, r.day))
        hit = (worked == r.shift) if r.shift not in ("$", "-") else ((worked is not None) if r.shift == "$" else worked is None)
        violated = (not hit) if r.is_on_request else hit
        if violated:
            rows.append({"Nurse": r.employee_id, "Day": r.day, "Weekday": wd[r.day], "Shift": r.shift,
                         "Request": "ShiftOn (wanted to work)" if r.is_on_request else "ShiftOff (wanted to avoid)",
                         "Roster has": worked or "day off", "Penalty weight": r.weight})
    return pd.DataFrame(rows, columns=["Nurse", "Day", "Weekday", "Shift", "Request", "Roster has", "Penalty weight"])


def workload_table(dataset: ParsedDataset, result: Any) -> pd.DataFrame:
    """Per nurse: shifts worked by type, workload, contract limits, weekends worked."""
    wd = weekday_labels(dataset)
    shifts = sorted(dataset.shift_types)
    dur = min(s.duration for s in dataset.shift_types.values())
    targets = getattr(result, "workload_target_per_employee", None)
    rows = []
    for n in sorted(dataset.employees):
        c = get_employee_contract_constraints(dataset, n)
        mine = {d: s for (e, d), s in result.assignments.items() if e == n}
        weeks = dataset.planning_period.days // 7
        weekends = sum(
            1 for w in range(weeks)
            if any(d in mine for d in range(7 * w, 7 * w + 7) if d < len(wd) and wd[d] in ("Sat", "Sun"))
        )
        row = {"Nurse": n, "Shifts worked": len(mine)}
        for s in shifts:
            row[f"{s} shifts"] = sum(1 for v in mine.values() if v == s)
        row.update({
            "Workload (min)": result.workload_per_employee.get(n, 0),
            "Contract min (min)": c["min_workload"],
            "Contract max (min)": c["max_workload"],
            "Contract min shifts": -(-c["min_workload"] // dur) if c["min_workload"] is not None else None,
            "Contract max shifts": c["max_workload"] // dur if c["max_workload"] is not None else None,
            "Weekends worked": weekends,
        })
        if targets:
            row["GP target (min)"] = targets.get(n)
            row["Deviation from target (min)"] = round(result.workload_per_employee.get(n, 0) - targets.get(n, 0), 1)
        rows.append(row)
    return pd.DataFrame(rows)


def roster_table(dataset: ParsedDataset, result: Any, off_label: str = "-") -> pd.DataFrame:
    """Nurse x Day roster (shift letter or ``off_label``)."""
    labels = day_labels(dataset)
    rows = []
    for n in sorted(dataset.employees):
        row = {"Nurse": n}
        for d, lab in enumerate(labels):
            row[lab] = result.assignments.get((n, d), off_label)
        rows.append(row)
    return pd.DataFrame(rows).set_index("Nurse")


def style_roster(df: pd.DataFrame, dataset: ParsedDataset, off_label: str = "-"):
    """pandas Styler colouring each cell with its shift's XML colour."""
    colours = shift_colours(dataset)

    def _cell(v):
        if v in colours:
            return f"background-color: {colours[v]}; color: white; font-weight: 600; text-align: center"
        return f"background-color: {OFF_COLOUR}; color: #9aa0a6; text-align: center"

    return df.style.map(_cell)


def roster_long_csv(dataset: ParsedDataset, result: Any) -> bytes:
    wd = weekday_labels(dataset)
    rows = [{"Nurse": n, "Day": d, "Weekday": wd[d], "Shift": result.assignments.get((n, d), "Off")}
            for n in sorted(dataset.employees) for d in range(dataset.planning_period.days)]
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
