"""
Independent roster evaluation.

Given only a roster (``assignments``: (employee, day) -> shift), this module recomputes
every objective component of the two models *without* using a solver:

* ``evaluate_ip``  - the benchmark objective minimised by the Integer Programming model
      Z_IP = sum WeightMin*max(0, ReqMin - assigned)
           + sum WeightMax*max(0, assigned - ReqMax)
           + sum request weights of violated ShiftOn / ShiftOff requests
* ``evaluate_gp``  - the weighted-sum Goal Programming objective
      Z_GP = w1*sum WeightMin*d-  + w3*sum WeightMax*d+   (deviations from ReqMin)
           + w2*sum request weights of violated requests
           + w4*sum |workload - target|                    (target = contract midpoint)

For an optimal solver solution the deviation variables take exactly these minimal values,
so the recomputed objective must equal the solver's objective.  That makes this module

1. a cross-check of the solver output (tests assert the two agree),
2. the way saved reference rosters are turned back into full result objects
   (``build_ip_result`` / ``build_gp_result``), and
3. a model-independent source for the figures shown in the UI.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.data_model import ParsedDataset
from src.integer_program import OptimizationResult, get_employee_contract_constraints
from src.goal_program import GoalProgrammingResult
from src.benchmarks import benchmark_for, gap_percent
from src.validation import validate_solution

Assignments = Dict[Tuple[str, int], str]

DEFAULT_GP_WEIGHTS = {"w1": 1.0, "w2": 1.0, "w3": 1.0, "w4": 0.5}


# ---------------------------------------------------------------------------
# Shared pieces
# ---------------------------------------------------------------------------

def _coverage(dataset: ParsedDataset, assignments: Assignments) -> Dict[Tuple[int, str], int]:
    cov = {(d, s): 0 for d in range(dataset.planning_period.days) for s in dataset.shift_types}
    for (_, d), s in assignments.items():
        cov[(d, s)] = cov.get((d, s), 0) + 1
    return cov


def _workload(dataset: ParsedDataset, assignments: Assignments) -> Dict[str, int]:
    wl = {n: 0 for n in dataset.employees}
    for (n, _), s in assignments.items():
        wl[n] += dataset.shift_types[s].duration
    return wl


def _request_violations(dataset: ParsedDataset, assignments: Assignments, with_weight: bool):
    """List of (text, weight, is_on) for each violated request."""
    out = []
    for r in dataset.shift_requests:
        worked = assignments.get((r.employee_id, r.day))
        if r.is_on_request:
            satisfied = worked is not None if r.shift == "$" else (worked == r.shift if r.shift != "-" else worked is None)
            kind, pre = "On-request violated", True
        else:
            satisfied = not (worked is not None if r.shift == "$" else (worked == r.shift if r.shift != "-" else worked is None))
            kind, pre = "Off-request violated", False
        if not satisfied:
            if with_weight:
                text = f"{kind}: {r.employee_id} shift {r.shift} day {r.day} (w={r.weight})"
            else:
                text = f"{kind}: {r.employee_id} {r.shift} on day {r.day}"
            out.append((text, r.weight, pre))
    return out


# ---------------------------------------------------------------------------
# IP objective
# ---------------------------------------------------------------------------

@dataclass
class IPEvaluation:
    objective: float
    coverage: Dict[Tuple[int, str], int]
    understaffing: Dict[Tuple[int, str], int]
    overstaffing: Dict[Tuple[int, str], int]
    understaffing_penalty: float
    overstaffing_penalty: float
    request_penalty: float
    violations: List[str]
    workload: Dict[str, int]


def evaluate_ip(dataset: ParsedDataset, assignments: Assignments) -> IPEvaluation:
    cov = _coverage(dataset, assignments)
    under, over = {}, {}
    u_pen = o_pen = 0.0
    for cr in dataset.cover_requirements:
        a = cov.get((cr.day, cr.shift), 0)
        if a < cr.min_nurses:
            under[(cr.day, cr.shift)] = cr.min_nurses - a
            u_pen += cr.min_weight * (cr.min_nurses - a)
        if a > cr.max_nurses:
            over[(cr.day, cr.shift)] = a - cr.max_nurses
            o_pen += cr.max_weight * (a - cr.max_nurses)
    viol = _request_violations(dataset, assignments, with_weight=False)
    r_pen = float(sum(w for _, w, _ in viol))
    return IPEvaluation(
        objective=u_pen + o_pen + r_pen,
        coverage=cov,
        understaffing=under,
        overstaffing=over,
        understaffing_penalty=u_pen,
        overstaffing_penalty=o_pen,
        request_penalty=r_pen,
        violations=[t for t, _, _ in viol],
        workload=_workload(dataset, assignments),
    )


def build_ip_result(
    dataset: ParsedDataset,
    assignments: Assignments,
    *,
    status: str,
    proven_optimal: bool,
    solve_time: float,
    time_limit: Optional[float] = None,
    source: str = "saved reference run",
) -> OptimizationResult:
    """Rebuild a full OptimizationResult from a roster (objective recomputed, not trusted)."""
    ev = evaluate_ip(dataset, assignments)
    ref = benchmark_for(dataset)
    return OptimizationResult(
        status=status,
        objective_value=ev.objective,
        solve_time=solve_time,
        assignments=dict(assignments),
        coverage_by_day_shift=ev.coverage,
        understaffing=ev.understaffing,
        overstaffing=ev.overstaffing,
        shift_request_violations=ev.violations,
        workload_per_employee=ev.workload,
        benchmark_reference=ref,
        benchmark_gap_percent=gap_percent(ev.objective, ref),
        proven_optimal=proven_optimal,
        time_limit=time_limit,
        source=source,
    )


# ---------------------------------------------------------------------------
# GP objective
# ---------------------------------------------------------------------------

@dataclass
class GPEvaluation:
    objective: float
    understaffing: Dict[Tuple[int, str], int]
    overstaffing: Dict[Tuple[int, str], int]       # relative to ReqMin (the GP goal equation)
    understaffing_penalty: float
    overstaffing_penalty: float
    request_penalty: float
    violations: List[str]
    fairness_penalty: float
    workload: Dict[str, int]
    targets: Dict[str, float]
    pos_dev: Dict[str, float]
    neg_dev: Dict[str, float]


def gp_workload_targets(dataset: ParsedDataset) -> Dict[str, float]:
    """Midpoint of each nurse's contractual workload bounds (same rule as the GP model)."""
    days = dataset.planning_period.days
    targets = {}
    for n in dataset.employees:
        c = get_employee_contract_constraints(dataset, n)
        lo = c["min_workload"] if c["min_workload"] is not None else 0
        hi = c["max_workload"] if c["max_workload"] is not None else sum(
            dataset.shift_types[s].duration * days for s in dataset.shift_types)
        targets[n] = (lo + hi) / 2.0
    return targets


def evaluate_gp(
    dataset: ParsedDataset,
    assignments: Assignments,
    weights: Optional[Dict[str, float]] = None,
) -> GPEvaluation:
    w = {**DEFAULT_GP_WEIGHTS, **(weights or {})}
    cov = _coverage(dataset, assignments)
    under, over = {}, {}
    u_pen = o_pen = 0.0
    for cr in dataset.cover_requirements:
        a = cov.get((cr.day, cr.shift), 0)
        if a < cr.min_nurses:
            under[(cr.day, cr.shift)] = cr.min_nurses - a
            u_pen += w["w1"] * cr.min_weight * (cr.min_nurses - a)
        elif a > cr.min_nurses:
            over[(cr.day, cr.shift)] = a - cr.min_nurses
            o_pen += w["w3"] * cr.max_weight * (a - cr.min_nurses)
    viol = _request_violations(dataset, assignments, with_weight=True)
    r_pen = w["w2"] * sum(wt for _, wt, _ in viol)

    wl = _workload(dataset, assignments)
    targets = gp_workload_targets(dataset)
    pos = {n: max(0.0, wl[n] - targets[n]) for n in wl}
    neg = {n: max(0.0, targets[n] - wl[n]) for n in wl}
    f_pen = w["w4"] * (sum(pos.values()) + sum(neg.values()))

    return GPEvaluation(
        objective=u_pen + o_pen + r_pen + f_pen,
        understaffing=under,
        overstaffing=over,
        understaffing_penalty=round(u_pen, 2),
        overstaffing_penalty=round(o_pen, 2),
        request_penalty=round(r_pen, 2),
        violations=[t for t, _, _ in viol],
        fairness_penalty=round(f_pen, 2),
        workload=wl,
        targets=targets,
        pos_dev={n: round(v, 2) for n, v in pos.items()},
        neg_dev={n: round(v, 2) for n, v in neg.items()},
    )


def build_gp_result(
    dataset: ParsedDataset,
    assignments: Assignments,
    *,
    status: str,
    proven_optimal: bool,
    solve_time: float,
    weights: Optional[Dict[str, float]] = None,
    time_limit: Optional[float] = None,
    source: str = "saved reference run",
) -> GoalProgrammingResult:
    """Rebuild a full GoalProgrammingResult from a roster (objective recomputed, not trusted)."""
    w = {**DEFAULT_GP_WEIGHTS, **(weights or {})}
    ev = evaluate_gp(dataset, assignments, w)
    cov = _coverage(dataset, assignments)
    report = validate_solution(dataset, assignments)
    return GoalProgrammingResult(
        status=status,
        gp_objective_value=round(ev.objective, 4),
        solve_time=solve_time,
        assignments=dict(assignments),
        coverage_by_day_shift=cov,
        understaffing=ev.understaffing,
        overstaffing=ev.overstaffing,
        total_understaffing_penalty=ev.understaffing_penalty,
        total_overstaffing_penalty=ev.overstaffing_penalty,
        shift_request_violations=ev.violations,
        total_request_penalty=ev.request_penalty,
        workload_per_employee=ev.workload,
        workload_target_per_employee={n: round(v, 1) for n, v in ev.targets.items()},
        workload_pos_dev=ev.pos_dev,
        workload_neg_dev=ev.neg_dev,
        workload_fairness_penalty=ev.fairness_penalty,
        hard_constraint_valid=report.is_feasible,
        hard_constraint_errors=report.errors,
        weights={"w1_understaffing": w["w1"], "w2_requests": w["w2"],
                 "w3_overstaffing": w["w3"], "w4_fairness": w["w4"]},
        benchmark_reference=benchmark_for(dataset),
        gp_benchmark_comparable=False,
        note=("GP objective is NOT directly comparable to the benchmark objective. "
              "The GP includes a workload-fairness term absent from the benchmark objective. "
              "Component-level comparison (understaffing penalty, request penalty) is valid."),
        proven_optimal=proven_optimal,
        time_limit=time_limit,
        source=source,
    )
