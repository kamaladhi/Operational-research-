"""
Structured tables (Pandas DataFrames) built from a ParsedDataset.

The project specification requires the XML to be converted into "structured tables suitable for
analysis".  ``dataset_to_tables`` does that, and ``export_tables`` writes them as CSV files
(``data/processed``).  Nothing here is invented: every column comes from the XML or is a direct
arithmetic consequence of it (e.g. workload minutes -> shifts).
"""

import datetime as _dt
import os
from typing import Dict, List

import pandas as pd

from src.data_model import ParsedDataset
from src.integer_program import get_employee_contract_constraints

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def weekday_labels(dataset: ParsedDataset) -> List[str]:
    """Calendar weekday label for each day index of the planning period."""
    start = _dt.datetime.strptime(dataset.planning_period.start_date, "%Y-%m-%d")
    return [WEEKDAYS[(start + _dt.timedelta(days=d)).weekday()] for d in range(dataset.planning_period.days)]


def day_labels(dataset: ParsedDataset) -> List[str]:
    """'D0 Mon', 'D1 Tue', ... for chart axes."""
    return [f"D{d} {w}" for d, w in enumerate(weekday_labels(dataset))]


def _min_duration(dataset: ParsedDataset) -> int:
    return min((s.duration for s in dataset.shift_types.values() if s.duration > 0), default=1)


def dataset_to_tables(dataset: ParsedDataset) -> Dict[str, pd.DataFrame]:
    """Return the dataset as a dict of DataFrames keyed by table name."""
    wd = weekday_labels(dataset)
    dur = _min_duration(dataset)

    shifts = pd.DataFrame(
        [{"Shift": s.id, "Start": s.start_time, "Duration (min)": s.duration, "Colour": s.label}
         for s in dataset.shift_types.values()]
    )

    contracts = pd.DataFrame(
        [{
            "Contract": c.id,
            "Valid shifts": ", ".join(c.valid_shifts) if c.valid_shifts else "all",
            "Min rest (min)": c.min_rest_time,
            "Max consecutive": next((q.value for q in c.max_seq if q.shift == "$"), None),
            "Min consecutive": next((q.value for q in c.min_seq if q.shift == "$"), None),
            "Min days off": next((q.value for q in c.min_seq if q.shift == "-"), None),
            "Max total by shift": ", ".join(f"{q.shift}<={q.value}" for q in c.max_tot) or "-",
            "Min workload (min)": c.workload.min_count if c.workload else None,
            "Max workload (min)": c.workload.max_count if c.workload else None,
            "Max working weekends": c.weekend_patterns_max,
        } for c in dataset.contracts.values()]
    )

    emp_rows = []
    fixed_off: Dict[str, List[int]] = {}
    for fa in dataset.fixed_assignments:
        fixed_off.setdefault(fa.employee_id, []).append(fa.day)
    for n, emp in dataset.employees.items():
        c = get_employee_contract_constraints(dataset, n)
        reqs = [r for r in dataset.shift_requests if r.employee_id == n]
        emp_rows.append({
            "Nurse": n,
            "Contracts": ", ".join(emp.contract_ids),
            "Valid shifts": ", ".join(sorted(c["valid_shifts"])) if c["valid_shifts"] else "all",
            "Min workload (min)": c["min_workload"],
            "Max workload (min)": c["max_workload"],
            "Min shifts": -(-c["min_workload"] // dur) if c["min_workload"] is not None else None,
            "Max shifts": c["max_workload"] // dur if c["max_workload"] is not None else None,
            "Max consecutive": c["max_seq"],
            "Min consecutive": c["min_seq"],
            "Min days off": c["min_days_off"],
            "Max total by shift": ", ".join(f"{s}<={v}" for s, v in sorted(c["max_tot"].items())) or "-",
            "Max working weekends": c["max_weekends"],
            "Fixed days off": len(fixed_off.get(n, [])),
            "ShiftOn requests": sum(1 for r in reqs if r.is_on_request),
            "ShiftOff requests": sum(1 for r in reqs if not r.is_on_request),
            "Request weight total": sum(r.weight for r in reqs),
        })
    employees = pd.DataFrame(emp_rows)

    cover = pd.DataFrame(
        [{"Day": cr.day, "Weekday": wd[cr.day], "Shift": cr.shift,
          "Min nurses": cr.min_nurses, "Min weight (understaffing)": cr.min_weight,
          "Max nurses": cr.max_nurses, "Max weight (overstaffing)": cr.max_weight}
         for cr in sorted(dataset.cover_requirements, key=lambda c: (c.day, c.shift))]
    )

    requests = pd.DataFrame(
        [{"Nurse": r.employee_id, "Day": r.day, "Weekday": wd[r.day], "Shift": r.shift,
          "Type": "ShiftOn (wants to work)" if r.is_on_request else "ShiftOff (wants off)",
          "Weight": r.weight}
         for r in sorted(dataset.shift_requests, key=lambda r: (r.employee_id, r.day))]
    )

    fixed = pd.DataFrame(
        [{"Nurse": fa.employee_id, "Day": fa.day, "Weekday": wd[fa.day],
          "Assignment": "Day off" if fa.shift == "-" else fa.shift}
         for fa in sorted(dataset.fixed_assignments, key=lambda f: (f.employee_id, f.day))]
    )

    return {"shifts": shifts, "contracts": contracts, "employees": employees,
            "cover": cover, "requests": requests, "fixed_assignments": fixed}


def export_tables(dataset: ParsedDataset, out_dir: str, prefix: str = "") -> List[str]:
    """Write every table as CSV into ``out_dir``; returns the file paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name, df in dataset_to_tables(dataset).items():
        path = os.path.join(out_dir, f"{prefix}{name}.csv")
        df.to_csv(path, index=False, encoding="utf-8")
        paths.append(path)
    return paths
