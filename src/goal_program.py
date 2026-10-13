"""
Goal Programming model for Nurse Rostering (Instance 3).

GP Formulation:
--------------
The same hard constraints as the IP model are enforced.
Three goal categories are expressed via deviation variables:

  Goal 1 — Staffing Coverage
    Minimize under-staffing deviation weighted by XML penalty weights.
    Understaffing (d_under[d,s]) is always undesirable.
    Overstaffing (d_over[d,s]) is undesirable at a much lower XML weight.

  Goal 2 — Request Satisfaction
    Minimize weighted violations of ShiftOn and ShiftOff requests,
    using the actual weight attributes from the XML.

  Goal 3 — Workload Fairness
    Minimize the sum of positive and negative deviations from a
    fair workload target W_target[n].

    W_target[n] is the midpoint of the nurse's contractual workload bounds:
        W_target[n] = (MinWorkload[n] + MaxWorkload[n]) / 2
    so it always lies inside the hard workload bounds enforced as constraints.

    deviation_pos[n] = max(0, actual_workload[n] - W_target[n])
    deviation_neg[n] = max(0, W_target[n] - actual_workload[n])

Weighted-sum objective (NOT lexicographic):
    min Z = w1 * sum_{d,s} WeightMin[d,s] * d_under[d,s]
          + w2 * sum_i   OnWeight[i]  * v_on[i]
          + w2 * sum_i   OffWeight[i] * v_off[i]
          + w3 * sum_{d,s} WeightMax[d,s] * d_over[d,s]
          + w4 * sum_n   (wp_pos[n] + wp_neg[n])

Weight selection rationale:
    w1 = 1.0  — Understaffing is critical; weights are already large (100) in XML.
    w2 = 1.0  — Request weights are encoded in the XML (1–10 range).
    w3 = 1.0  — Overstaffing weights are small (1) in XML, naturally lower priority.
    w4 = 0.5  — Workload fairness is measured in minutes, so w4 converts minutes to
                 penalty units.  At w4 = 0.5 one 480-minute shift of deviation from
                 the target costs 240 units, which is MORE than one unfilled
                 nurse-slot (100).  Fairness is therefore deliberately weighted above
                 a single unit of coverage in this formulation, and the GP will leave
                 extra slots unfilled to stay close to the workload targets.  See
                 docs/GOAL_PROGRAMMING.md (weight-sensitivity table): at w4 = 0 the GP
                 reduces to the IP objective, and the coverage/fairness trade-off
                 appears as w4 increases.

NOTE: The GP objective is NOT directly comparable to the benchmark objective of 1001.
The benchmark objective is computed by the IP model using exact XML penalty weights
with a specific weighting structure. The GP objective includes an additional workload
fairness term (Goal 3) that has no direct benchmark equivalent. Comparison must be
done component by component, not as a single number.
"""

import pulp
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from src.data_model import ParsedDataset
from src.integer_program import get_employee_contract_constraints, time_to_mins
from src.solver_utils import make_cbc_solver, interpret_cbc_status
from src.benchmarks import benchmark_for
import time


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class GoalProgrammingResult:
    status: str
    gp_objective_value: Optional[float]
    solve_time: float

    # Roster
    assignments: Dict[Tuple[str, int], str]          # (employee, day) -> shift
    coverage_by_day_shift: Dict[Tuple[int, str], int]

    # Goal 1 — Coverage deviations
    understaffing: Dict[Tuple[int, str], int]         # d_under[d,s]
    overstaffing: Dict[Tuple[int, str], int]          # d_over[d,s]
    total_understaffing_penalty: float
    total_overstaffing_penalty: float

    # Goal 2 — Request deviations
    shift_request_violations: List[str]
    total_request_penalty: float

    # Goal 3 — Workload fairness
    workload_per_employee: Dict[str, int]             # actual minutes worked
    workload_target_per_employee: Dict[str, float]    # W_target[n]
    workload_pos_dev: Dict[str, float]                # positive deviation
    workload_neg_dev: Dict[str, float]                # negative deviation
    workload_fairness_penalty: float

    # Validation
    hard_constraint_valid: bool
    hard_constraint_errors: List[str]

    # Formulation metadata
    weights: Dict[str, float]                         # w1, w2, w3, w4
    benchmark_reference: Optional[float]              # IP benchmark value (not GP comparable); None if unknown
    gp_benchmark_comparable: bool                     # always False (GP has extra fairness term)
    note: str

    # Solver provenance
    proven_optimal: bool = False                      # True only if CBC proved optimality
    time_limit: Optional[float] = None                # seconds given to the solver (None for saved runs)
    source: str = "live solve"                        # "live solve" or "saved reference run"


# ---------------------------------------------------------------------------
# Helper: build all hard constraints into a PuLP problem
# (mirrors integer_program.py exactly so hard constraints are identical)
# ---------------------------------------------------------------------------

def _add_hard_constraints(
    prob: pulp.LpProblem,
    dataset: ParsedDataset,
    x: dict,
    y: dict,
    z: dict,
    employees: list,
    days: list,
    shifts: list,
    num_weekends: int,
    prefix: str = "GP"
):
    """Add all hard constraints to the problem (identical to IP model)."""

    # 1. Single shift per day & y relation
    for n in employees:
        for d in days:
            prob += pulp.lpSum([x[n, d, s] for s in shifts]) == y[n, d], \
                   f"{prefix}_YRel_{n}_{d}"
            prob += y[n, d] <= 1, f"{prefix}_Single_{n}_{d}"

    # 2. Valid shifts
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        if c['valid_shifts']:
            for d in days:
                for s in shifts:
                    if s not in c['valid_shifts']:
                        prob += x[n, d, s] == 0, f"{prefix}_ValidShift_{n}_{d}_{s}"

    # 3. Fixed assignments
    for fa in dataset.fixed_assignments:
        n, d, s = fa.employee_id, fa.day, fa.shift
        if s == '-':
            prob += y[n, d] == 0, f"{prefix}_FixedOff_{n}_{d}"
        elif s in shifts:
            prob += x[n, d, s] == 1, f"{prefix}_FixedOn_{n}_{d}_{s}"

    # 4. Workload bounds (hard)
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        wl = pulp.lpSum([dataset.shift_types[s].duration * x[n, d, s]
                         for d in days for s in shifts])
        if c['max_workload'] is not None:
            prob += wl <= c['max_workload'], f"{prefix}_MaxWL_{n}"
        if c['min_workload'] is not None:
            prob += wl >= c['min_workload'], f"{prefix}_MinWL_{n}"

    # 5. Max total shifts by type
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        for s, mx in c['max_tot'].items():
            prob += pulp.lpSum([x[n, d, s] for d in days]) <= mx, \
                   f"{prefix}_MaxTot_{n}_{s}"

    # 6. Prohibited rest transitions
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        if c['min_rest'] is not None:
            mr = c['min_rest']
            for d in range(len(days) - 1):
                for s1 in shifts:
                    for s2 in shifts:
                        end1 = time_to_mins(dataset.shift_types[s1].start_time) + \
                               dataset.shift_types[s1].duration
                        start2 = time_to_mins(dataset.shift_types[s2].start_time) + 1440
                        if start2 - end1 < mr:
                            prob += x[n, d, s1] + x[n, d+1, s2] <= 1, \
                                   f"{prefix}_Rest_{n}_{d}_{s1}_{s2}"

    # 7. Max consecutive shifts
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        if c['max_seq'] is not None:
            ms = c['max_seq']
            for d in range(len(days) - ms):
                prob += pulp.lpSum([y[n, d+k] for k in range(ms + 1)]) <= ms, \
                       f"{prefix}_MaxSeq_{n}_{d}"

    # 8. Min consecutive shifts (boundary-exempt)
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        if c['min_seq'] is not None and c['min_seq'] > 1:
            ms = c['min_seq']
            for d in range(1, len(days)):
                for k in range(1, ms):
                    if d + k < len(days):
                        prob += y[n, d] - y[n, d-1] <= y[n, d+k], \
                               f"{prefix}_MinSeq_{n}_{d}_k{k}"

    # 9. Min consecutive days off (boundary-exempt)
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        if c['min_days_off'] is not None and c['min_days_off'] > 1:
            md = c['min_days_off']
            for d in range(1, len(days)):
                for k in range(1, md):
                    if d + k < len(days):
                        prob += y[n, d-1] - y[n, d] + y[n, d+k] <= 1, \
                               f"{prefix}_MinDO_{n}_{d}_k{k}"

    # 10. Working weekends
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        for w in range(num_weekends):
            sat = 5 + 7 * w
            sun = 6 + 7 * w
            prob += z[n, w] >= y[n, sat], f"{prefix}_WkndSat_{n}_{w}"
            prob += z[n, w] >= y[n, sun], f"{prefix}_WkndSun_{n}_{w}"
            prob += z[n, w] <= y[n, sat] + y[n, sun], f"{prefix}_WkndSum_{n}_{w}"
        if c['max_weekends'] is not None:
            prob += pulp.lpSum([z[n, w] for w in range(num_weekends)]) <= c['max_weekends'], \
                   f"{prefix}_MaxWknd_{n}"


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------

def solve_goal_program(
    dataset: ParsedDataset,
    time_limit: int = 120,
    w1: float = 1.0,
    w2: float = 1.0,
    w3: float = 1.0,
    w4: float = 0.5,
) -> GoalProgrammingResult:
    """
    Solve the nurse rostering problem using weighted-sum Goal Programming.

    Parameters
    ----------
    dataset     : ParsedDataset from the XML parser.
    time_limit  : CBC solver time limit in seconds (default 120).
    w1          : Weight for Goal 1 (understaffing).  Default 1.0.
    w2          : Weight for Goal 2 (request violations). Default 1.0.
    w3          : Weight for Goal 3a (overstaffing). Default 1.0.
    w4          : Weight for Goal 3b (workload fairness). Default 0.5.
    """
    t0 = time.time()

    employees = list(dataset.employees.keys())
    days      = list(range(dataset.planning_period.days))
    shifts    = list(dataset.shift_types.keys())
    num_weekends = dataset.planning_period.days // 7

    prob = pulp.LpProblem("Nurse_Rostering_GP", pulp.LpMinimize)

    # -----------------------------------------------------------------------
    # Decision variables (same as IP)
    # -----------------------------------------------------------------------
    x = pulp.LpVariable.dicts(
        "gx", [(n, d, s) for n in employees for d in days for s in shifts],
        0, 1, pulp.LpBinary)
    y = pulp.LpVariable.dicts(
        "gy", [(n, d) for n in employees for d in days],
        0, 1, pulp.LpBinary)
    z = pulp.LpVariable.dicts(
        "gz", [(n, w) for n in employees for w in range(num_weekends)],
        0, 1, pulp.LpBinary)

    # -----------------------------------------------------------------------
    # Hard constraints (identical to IP)
    # -----------------------------------------------------------------------
    _add_hard_constraints(prob, dataset, x, y, z, employees, days, shifts, num_weekends)

    # -----------------------------------------------------------------------
    # Goal 1: Staffing coverage deviation variables
    # Goal equation: sum_n x[n,d,s] + d_under[d,s] - d_over[d,s] = ReqMin[d,s]
    # Undesirable: d_under[d,s] > 0 (priority 1)
    # Also undesirable: d_over beyond ReqMax[d,s] (priority 3 via w3)
    # -----------------------------------------------------------------------
    d_under = pulp.LpVariable.dicts(
        "d_under", [(d, s) for d in days for s in shifts], 0, None, pulp.LpInteger)
    d_over = pulp.LpVariable.dicts(
        "d_over",  [(d, s) for d in days for s in shifts], 0, None, pulp.LpInteger)

    for cr in dataset.cover_requirements:
        d, s = cr.day, cr.shift
        assigned = pulp.lpSum([x[n, d, s] for n in employees])
        # Goal equation anchored to ReqMin — d_under captures shortfall, d_over surplus
        prob += assigned + d_under[d, s] - d_over[d, s] == cr.min_nurses, \
               f"GP_CoverGoal_{d}_{s}"
        # Hard upper bound (overstaffing beyond ReqMax still penalised separately)
        # We do NOT add a hard cover-min constraint here; it becomes a soft goal.
        # But we must still respect ReqMax as soft via d_over.

    # -----------------------------------------------------------------------
    # Goal 2: Request deviation variables
    # v_on[i] = 1 if ShiftOn request i is NOT satisfied (undesirable)
    # v_off[i] = 1 if ShiftOff request i IS violated (undesirable)
    # -----------------------------------------------------------------------
    on_requests  = [r for r in dataset.shift_requests if r.is_on_request]
    off_requests = [r for r in dataset.shift_requests if not r.is_on_request]

    v_on  = pulp.LpVariable.dicts("gv_on",  range(len(on_requests)),  0, 1, pulp.LpBinary)
    v_off = pulp.LpVariable.dicts("gv_off", range(len(off_requests)), 0, 1, pulp.LpBinary)

    for i, req in enumerate(on_requests):
        prob += x[req.employee_id, req.day, req.shift] + v_on[i] >= 1, \
               f"GP_ReqOn_{i}"
    for i, req in enumerate(off_requests):
        prob += x[req.employee_id, req.day, req.shift] - v_off[i] <= 0, \
               f"GP_ReqOff_{i}"

    # -----------------------------------------------------------------------
    # Goal 3: Workload fairness deviation variables
    #
    # W_target[n] = clip(total_available_minutes / num_nurses,
    #                    MinWorkload[n], MaxWorkload[n])
    #
    # total_available_minutes = num_days_worked_possible * shift_duration
    # Since all shifts are 480 min and we have 14 days, a reasonable target
    # is derived from the midpoint of each nurse's workload bounds.
    #
    # We use the midpoint of [MinWorkload[n], MaxWorkload[n]] as the target
    # because it is the most balanced achievable point within each nurse's
    # hard bounds, and avoids the global-average target violating per-nurse
    # contract constraints.
    #
    # wp_pos[n] = positive deviation from target (working too much)
    # wp_neg[n] = negative deviation from target (working too little)
    # -----------------------------------------------------------------------
    workload_targets = {}
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        lo = c['min_workload'] if c['min_workload'] is not None else 0
        hi = c['max_workload'] if c['max_workload'] is not None else sum(
            dataset.shift_types[s].duration * len(days) for s in shifts)
        workload_targets[n] = (lo + hi) / 2.0

    wp_pos = pulp.LpVariable.dicts("gw_pos", employees, 0, None)
    wp_neg = pulp.LpVariable.dicts("gw_neg", employees, 0, None)

    for n in employees:
        actual_wl = pulp.lpSum([
            dataset.shift_types[s].duration * x[n, d, s]
            for d in days for s in shifts])
        target = workload_targets[n]
        # Goal equation: actual_wl + wp_neg[n] - wp_pos[n] = target
        prob += actual_wl + wp_neg[n] - wp_pos[n] == target, \
               f"GP_WLGoal_{n}"

    # -----------------------------------------------------------------------
    # Weighted-sum objective
    # -----------------------------------------------------------------------
    obj_terms = []

    # Goal 1a: understaffing (weighted by XML penalty, scaled by w1)
    for cr in dataset.cover_requirements:
        d, s = cr.day, cr.shift
        obj_terms.append(w1 * cr.min_weight * d_under[d, s])

    # Goal 1b: overstaffing (weighted by XML penalty, scaled by w3)
    for cr in dataset.cover_requirements:
        d, s = cr.day, cr.shift
        obj_terms.append(w3 * cr.max_weight * d_over[d, s])

    # Goal 2: request violations (weighted by XML request weight, scaled by w2)
    for i, req in enumerate(on_requests):
        obj_terms.append(w2 * req.weight * v_on[i])
    for i, req in enumerate(off_requests):
        obj_terms.append(w2 * req.weight * v_off[i])

    # Goal 3: workload fairness (scaled by w4)
    for n in employees:
        obj_terms.append(w4 * wp_pos[n])
        obj_terms.append(w4 * wp_neg[n])

    prob += pulp.lpSum(obj_terms)

    # -----------------------------------------------------------------------
    # Solve
    # -----------------------------------------------------------------------
    solver = make_cbc_solver(time_limit)
    prob.solve(solver)

    elapsed = time.time() - t0
    # PuLP reports "Optimal" even when CBC stopped on the time limit; use the real solution status.
    status, proven_optimal = interpret_cbc_status(prob)
    obj_val = pulp.value(prob.objective) if status in ['Optimal', 'Feasible'] else None

    # -----------------------------------------------------------------------
    # Extract results
    # -----------------------------------------------------------------------
    assignments   = {}
    coverage      = {}
    under_vals    = {}
    over_vals     = {}
    workload_vals = {n: 0 for n in employees}
    req_violations = []
    wp_pos_vals   = {n: 0.0 for n in employees}
    wp_neg_vals   = {n: 0.0 for n in employees}

    total_under_pen  = 0.0
    total_over_pen   = 0.0
    total_req_pen    = 0.0
    total_fair_pen   = 0.0

    if obj_val is not None:
        # Assignments & workloads
        for n in employees:
            for d in days:
                for s in shifts:
                    val = pulp.value(x[n, d, s])
                    if val is not None and val > 0.5:
                        assignments[(n, d)] = s
                        coverage[(d, s)] = coverage.get((d, s), 0) + 1
                        workload_vals[n] += dataset.shift_types[s].duration

        # Fill zero coverage
        for d in days:
            for s in shifts:
                if (d, s) not in coverage:
                    coverage[(d, s)] = 0

        # Coverage deviations
        for cr in dataset.cover_requirements:
            d, s = cr.day, cr.shift
            u_val = pulp.value(d_under[d, s])
            o_val = pulp.value(d_over[d, s])
            if u_val and u_val > 1e-6:
                under_vals[(d, s)] = round(u_val)
                total_under_pen += w1 * cr.min_weight * u_val
            if o_val and o_val > 1e-6:
                over_vals[(d, s)] = round(o_val)
                total_over_pen += w3 * cr.max_weight * o_val

        # Request violations
        for i, req in enumerate(on_requests):
            val = pulp.value(v_on[i])
            if val is not None and val > 0.5:
                req_violations.append(
                    f"On-request violated: {req.employee_id} shift {req.shift} day {req.day} (w={req.weight})")
                total_req_pen += w2 * req.weight
        for i, req in enumerate(off_requests):
            val = pulp.value(v_off[i])
            if val is not None and val > 0.5:
                req_violations.append(
                    f"Off-request violated: {req.employee_id} shift {req.shift} day {req.day} (w={req.weight})")
                total_req_pen += w2 * req.weight

        # Workload fairness
        for n in employees:
            pp = pulp.value(wp_pos[n])
            pn = pulp.value(wp_neg[n])
            if pp and pp > 1e-6:
                wp_pos_vals[n] = round(pp, 2)
                total_fair_pen += w4 * pp
            if pn and pn > 1e-6:
                wp_neg_vals[n] = round(pn, 2)
                total_fair_pen += w4 * pn

    # -----------------------------------------------------------------------
    # Independent hard-constraint validation
    # -----------------------------------------------------------------------
    from src.validation import validate_solution
    val_report = validate_solution(dataset, assignments)

    return GoalProgrammingResult(
        status=status,
        gp_objective_value=obj_val,
        solve_time=elapsed,
        assignments=assignments,
        coverage_by_day_shift=coverage,
        understaffing=under_vals,
        overstaffing=over_vals,
        total_understaffing_penalty=round(total_under_pen, 2),
        total_overstaffing_penalty=round(total_over_pen, 2),
        shift_request_violations=req_violations,
        total_request_penalty=round(total_req_pen, 2),
        workload_per_employee=workload_vals,
        workload_target_per_employee={n: round(workload_targets[n], 1) for n in employees},
        workload_pos_dev=wp_pos_vals,
        workload_neg_dev=wp_neg_vals,
        workload_fairness_penalty=round(total_fair_pen, 2),
        hard_constraint_valid=val_report.is_feasible,
        hard_constraint_errors=val_report.errors,
        weights={'w1_understaffing': w1, 'w2_requests': w2,
                 'w3_overstaffing': w3, 'w4_fairness': w4},
        benchmark_reference=benchmark_for(dataset),
        gp_benchmark_comparable=False,
        note=(
            "GP objective is NOT directly comparable to the benchmark objective. "
            "The GP includes a workload-fairness term absent from the benchmark objective. "
            "Component-level comparison (understaffing penalty, request penalty) is valid."
        ),
        proven_optimal=proven_optimal,
        time_limit=time_limit,
    )
