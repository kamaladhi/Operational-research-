"""
Comparison module: IP vs GP solution analysis.

Compares OptimizationResult (from integer_program.py) and
GoalProgrammingResult (from goal_program.py) at the component level.

IMPORTANT mathematical note
----------------------------
The IP objective and the GP objective are computed from DIFFERENT
objective functions and must NOT be compared as raw numbers. The GP
includes a workload-fairness term with different units/scale that has
no equivalent in the IP objective.

All comparison metrics in this module are either:
  (a) component-level (coverage, requests, workload) — valid to compare, or
  (b) objective-specific (IP gap vs benchmark) — only stated for IP.

Both rosters are re-validated against the hard constraints here (nothing is assumed).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import json
import os

from src.data_model import ParsedDataset
from src.integer_program import OptimizationResult
from src.goal_program import GoalProgrammingResult
from src.benchmarks import gap_percent
from src.validation import validate_solution


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class CoverageMetrics:
    """Per-model coverage statistics."""
    total_required_nurse_slots: int          # sum of ReqMin across all (d,s)
    total_assigned_nurse_slots: int          # total assignments made
    total_understaffed_slots: int            # number of (d,s) pairs with understaffing
    total_overstaffed_slots: int             # number of (d,s) pairs with overstaffing
    total_understaffing_magnitude: int       # sum of d_under values
    total_overstaffing_magnitude: int        # sum of d_over values
    weighted_understaffing_penalty: float    # sum(WeightMin * d_under)
    weighted_overstaffing_penalty: float     # sum(WeightMax * d_over)
    coverage_rate_pct: float                 # sum(min(assigned, required)) / sum(required) * 100


@dataclass
class WorkloadMetrics:
    """Per-model workload statistics."""
    workload_per_nurse: Dict[str, int]       # minutes per nurse
    mean_workload: float
    min_workload: int
    max_workload: int
    workload_range: int                      # max - min
    std_dev: float                           # standard deviation
    fairness_index: float                    # Jain's fairness index (0–1, higher = fairer)


@dataclass
class RequestMetrics:
    """Per-model request satisfaction statistics."""
    total_on_requests: int
    total_off_requests: int
    on_violations: int
    off_violations: int
    total_violations: int
    violation_rate_pct: float                # total_violations / (on+off) * 100
    weighted_penalty: float                  # sum(weight * violation)


@dataclass
class ComparisonResult:
    # ------- Per-model results -------
    ip_status: str
    ip_objective: Optional[float]
    ip_solve_time: float
    ip_validation_passed: bool
    ip_validation_errors: List[str]

    gp_status: str
    gp_objective: Optional[float]
    gp_solve_time: float
    gp_validation_passed: bool
    gp_validation_errors: List[str]

    # ------- Benchmark (IP only) -------
    benchmark_reference: Optional[float]     # published best-known value (None if instance unknown)
    ip_benchmark_gap: Optional[float]        # IP objective − benchmark
    ip_benchmark_gap_pct: Optional[float]    # gap / benchmark * 100
    gp_benchmark_comparable: bool            # always False

    # ------- Component-level metrics -------
    ip_coverage: CoverageMetrics
    gp_coverage: CoverageMetrics
    ip_workload: WorkloadMetrics
    gp_workload: WorkloadMetrics
    ip_requests: RequestMetrics
    gp_requests: RequestMetrics

    # ------- Trade-off summary -------
    trade_off_summary: List[str]

    # ------- Notes -------
    comparison_note: str

    # ------- Solver provenance -------
    ip_proven_optimal: bool = False
    gp_proven_optimal: bool = False
    ip_source: str = "live solve"
    gp_source: str = "live solve"
    gp_weights: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helper calculations
# ---------------------------------------------------------------------------

def _compute_jain_fairness(values: List[float]) -> float:
    """
    Jain's Fairness Index = (sum x_i)^2 / (n * sum x_i^2).
    Returns value in [0, 1]. 1 = perfectly fair (all equal).
    Returns 1.0 if all values are 0 or there is only 1 nurse.
    """
    n = len(values)
    if n == 0:
        return 1.0
    s = sum(values)
    sq = sum(v**2 for v in values)
    if sq == 0:
        return 1.0
    return (s ** 2) / (n * sq)


def _compute_std_dev(values: List[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5


def _coverage_metrics(
    result_understaffing: Dict[Tuple[int, str], int],
    result_overstaffing: Dict[Tuple[int, str], int],
    assignments: Dict[Tuple[str, int], str],
    dataset: ParsedDataset,
) -> CoverageMetrics:
    """Compute coverage metrics from a result's deviation dicts."""

    # Required slots from XML
    total_required = sum(cr.min_nurses for cr in dataset.cover_requirements)

    # Assigned slots (total assignments)
    total_assigned = len(assignments)

    # Understaffing
    under_slots = len(result_understaffing)
    under_mag = sum(result_understaffing.values())

    # Overstaffing
    over_slots = len(result_overstaffing)
    over_mag = sum(result_overstaffing.values())

    # Weighted penalties (match what the models use)
    under_pen = 0.0
    over_pen = 0.0
    cr_map = {(cr.day, cr.shift): cr for cr in dataset.cover_requirements}
    for (d, s), v in result_understaffing.items():
        cr = cr_map.get((d, s))
        if cr:
            under_pen += cr.min_weight * v
    for (d, s), v in result_overstaffing.items():
        cr = cr_map.get((d, s))
        if cr:
            over_pen += cr.max_weight * v

    # Coverage rate = demand actually met / demand. Capped per day-shift so that overstaffing one
    # shift cannot hide understaffing of another.
    counts: Dict[Tuple[int, str], int] = {}
    for (_, d), s in assignments.items():
        counts[(d, s)] = counts.get((d, s), 0) + 1
    met = sum(min(counts.get((cr.day, cr.shift), 0), cr.min_nurses) for cr in dataset.cover_requirements)
    rate = (met / total_required * 100) if total_required > 0 else 0.0

    return CoverageMetrics(
        total_required_nurse_slots=total_required,
        total_assigned_nurse_slots=total_assigned,
        total_understaffed_slots=under_slots,
        total_overstaffed_slots=over_slots,
        total_understaffing_magnitude=under_mag,
        total_overstaffing_magnitude=over_mag,
        weighted_understaffing_penalty=round(under_pen, 2),
        weighted_overstaffing_penalty=round(over_pen, 2),
        coverage_rate_pct=round(rate, 2),
    )


def _workload_metrics(workload_per_nurse: Dict[str, int]) -> WorkloadMetrics:
    vals = list(workload_per_nurse.values())
    if not vals:
        return WorkloadMetrics({}, 0, 0, 0, 0, 0.0, 1.0)
    mean = sum(vals) / len(vals)
    mn   = min(vals)
    mx   = max(vals)
    std  = _compute_std_dev(vals)
    fair = _compute_jain_fairness(vals)
    return WorkloadMetrics(
        workload_per_nurse=workload_per_nurse,
        mean_workload=round(mean, 1),
        min_workload=mn,
        max_workload=mx,
        workload_range=mx - mn,
        std_dev=round(std, 1),
        fairness_index=round(fair, 4),
    )


def _request_metrics(
    violations: List[str],
    dataset: ParsedDataset,
    is_gp: bool = False,
    gp_result: Optional[GoalProgrammingResult] = None,
    ip_result: Optional[OptimizationResult] = None,
) -> RequestMetrics:
    on_reqs  = [r for r in dataset.shift_requests if r.is_on_request]
    off_reqs = [r for r in dataset.shift_requests if not r.is_on_request]

    on_viol  = sum(1 for v in violations if v.startswith("On-request"))
    off_viol = sum(1 for v in violations if v.startswith("Off-request"))
    total    = on_viol + off_viol
    total_reqs = len(on_reqs) + len(off_reqs)
    rate     = (total / total_reqs * 100) if total_reqs > 0 else 0.0

    # Weighted penalty
    if is_gp and gp_result is not None:
        weighted_pen = gp_result.total_request_penalty
    elif not is_gp and ip_result is not None:
        # Reconstruct from violation strings: not directly stored, estimate from violations
        # IP stores violations as strings without weights; use 0 for unknown weights here
        weighted_pen = 0.0
        viol_set = set(violations)
        for i, req in enumerate(on_reqs):
            label = f"On-request violated: {req.employee_id} {req.shift} on day {req.day}"
            if label in viol_set:
                weighted_pen += req.weight
        for i, req in enumerate(off_reqs):
            label = f"Off-request violated: {req.employee_id} {req.shift} on day {req.day}"
            if label in viol_set:
                weighted_pen += req.weight
    else:
        weighted_pen = 0.0

    return RequestMetrics(
        total_on_requests=len(on_reqs),
        total_off_requests=len(off_reqs),
        on_violations=on_viol,
        off_violations=off_viol,
        total_violations=total,
        violation_rate_pct=round(rate, 2),
        weighted_penalty=round(weighted_pen, 2),
    )


def _build_trade_off_summary(
    ip_cov: CoverageMetrics,
    gp_cov: CoverageMetrics,
    ip_wl: WorkloadMetrics,
    gp_wl: WorkloadMetrics,
    ip_req: RequestMetrics,
    gp_req: RequestMetrics,
    ip_obj: Optional[float],
    ip_gap_pct: Optional[float],
    benchmark: Optional[float] = None,
    ip_proven: bool = False,
) -> List[str]:
    summary = []

    # Benchmark
    if ip_obj is None:
        summary.append("The IP model returned no solution, so no benchmark comparison is possible.")
    elif benchmark is None or ip_gap_pct is None:
        summary.append(
            f"IP objective is {ip_obj:g}. This dataset is not a published benchmark instance, so no "
            f"best-known value is available. GP objective is NOT benchmark-comparable "
            f"(includes workload-fairness term)."
        )
    else:
        proof = "proven optimal by CBC" if ip_proven else "NOT proven optimal (time limit)"
        if abs(ip_gap_pct) < 1e-9:
            rel = f"equals the best-known benchmark value {benchmark:g}"
        elif ip_gap_pct > 0:
            rel = f"is {ip_gap_pct:.2f}% above the best-known benchmark value {benchmark:g}"
        else:
            rel = f"is {abs(ip_gap_pct):.2f}% BELOW the best-known benchmark value {benchmark:g}"
        summary.append(
            f"IP objective ({ip_obj:g}) {rel}; the IP solution is {proof}. "
            f"GP objective is NOT benchmark-comparable (includes workload-fairness term)."
        )

    # Coverage
    if gp_cov.weighted_understaffing_penalty > ip_cov.weighted_understaffing_penalty:
        diff = gp_cov.weighted_understaffing_penalty - ip_cov.weighted_understaffing_penalty
        summary.append(
            f"IP achieves lower understaffing penalty ({ip_cov.weighted_understaffing_penalty}) "
            f"vs GP ({gp_cov.weighted_understaffing_penalty}) — difference: {diff:.0f}."
        )
    else:
        summary.append(
            f"GP achieves lower or equal understaffing penalty ({gp_cov.weighted_understaffing_penalty}) "
            f"vs IP ({ip_cov.weighted_understaffing_penalty})."
        )

    # Requests
    n_requests = gp_req.total_on_requests + gp_req.total_off_requests
    if gp_req.total_violations < ip_req.total_violations:
        if gp_req.total_violations == 0:
            summary.append(
                f"GP satisfies all {n_requests} shift requests (0 violations). "
                f"IP has {ip_req.total_violations} violation(s)."
            )
        else:
            summary.append(
                f"GP has fewer request violations ({gp_req.total_violations} of {n_requests}) "
                f"than IP ({ip_req.total_violations})."
            )
    elif ip_req.total_violations == gp_req.total_violations:
        summary.append(f"Both models have the same number of request violations ({ip_req.total_violations}).")
    else:
        summary.append(
            f"IP has fewer request violations ({ip_req.total_violations}) than GP ({gp_req.total_violations})."
        )

    # Workload fairness (Jain's Index)
    if gp_wl.fairness_index >= ip_wl.fairness_index:
        summary.append(
            f"GP achieves higher workload fairness (Jain index {gp_wl.fairness_index:.4f}) "
            f"vs IP ({ip_wl.fairness_index:.4f}). "
            f"GP workload range: {gp_wl.workload_range} min; IP: {ip_wl.workload_range} min."
        )
    else:
        summary.append(
            f"IP achieves higher workload fairness (Jain index {ip_wl.fairness_index:.4f}) "
            f"vs GP ({gp_wl.fairness_index:.4f})."
        )

    # Solve time
    summary.append(
        "These are inherent model trade-offs. No single model dominates on all metrics. "
        "The choice between IP and GP depends on which objectives the hospital prioritises."
    )

    return summary


# ---------------------------------------------------------------------------
# Main comparison function
# ---------------------------------------------------------------------------

def compare_optimization_results(
    ip_result: OptimizationResult,
    gp_result: GoalProgrammingResult,
    dataset: ParsedDataset,
) -> ComparisonResult:
    """
    Compare IP and GP results at the component level.

    Parameters
    ----------
    ip_result : OptimizationResult from solve_integer_program()
    gp_result : GoalProgrammingResult from solve_goal_program()
    dataset   : ParsedDataset used by both solvers

    Returns
    -------
    ComparisonResult containing per-model and cross-model metrics.
    """

    # Coverage
    ip_cov = _coverage_metrics(ip_result.understaffing, ip_result.overstaffing,
                                ip_result.assignments, dataset)
    gp_cov = _coverage_metrics(gp_result.understaffing, gp_result.overstaffing,
                                gp_result.assignments, dataset)

    # Workload
    ip_wl = _workload_metrics(ip_result.workload_per_employee)
    gp_wl = _workload_metrics(gp_result.workload_per_employee)

    # Requests
    ip_req = _request_metrics(ip_result.shift_request_violations, dataset,
                               is_gp=False, ip_result=ip_result)
    gp_req = _request_metrics(gp_result.shift_request_violations, dataset,
                               is_gp=True, gp_result=gp_result)

    # Benchmark gap (IP only) - against the published value of THIS instance, if it is a known one
    bm = ip_result.benchmark_reference
    ip_gap = None
    ip_gap_pct = None
    if ip_result.objective_value is not None and bm:
        ip_gap = ip_result.objective_value - bm
        ip_gap_pct = gap_percent(ip_result.objective_value, bm)

    # Hard-constraint validation of the IP roster (computed here, never assumed)
    ip_report = validate_solution(dataset, ip_result.assignments)

    # Trade-off summary
    trades = _build_trade_off_summary(
        ip_cov, gp_cov, ip_wl, gp_wl, ip_req, gp_req,
        ip_result.objective_value, ip_gap_pct, bm, ip_result.proven_optimal
    )

    ip_obj_txt = f"{ip_result.objective_value:g}" if ip_result.objective_value is not None else "n/a"
    gp_obj_txt = f"{gp_result.gp_objective_value:g}" if gp_result.gp_objective_value is not None else "n/a"

    return ComparisonResult(
        ip_status=ip_result.status,
        ip_objective=ip_result.objective_value,
        ip_solve_time=ip_result.solve_time,
        ip_validation_passed=ip_report.is_feasible,
        ip_validation_errors=ip_report.errors,

        gp_status=gp_result.status,
        gp_objective=gp_result.gp_objective_value,
        gp_solve_time=gp_result.solve_time,
        gp_validation_passed=gp_result.hard_constraint_valid,
        gp_validation_errors=gp_result.hard_constraint_errors,

        benchmark_reference=bm,
        ip_benchmark_gap=round(ip_gap, 4) if ip_gap is not None else None,
        ip_benchmark_gap_pct=round(ip_gap_pct, 4) if ip_gap_pct is not None else None,
        gp_benchmark_comparable=gp_result.gp_benchmark_comparable,

        ip_coverage=ip_cov,
        gp_coverage=gp_cov,
        ip_workload=ip_wl,
        gp_workload=gp_wl,
        ip_requests=ip_req,
        gp_requests=gp_req,

        trade_off_summary=trades,
        comparison_note=(
            f"GP objective ({gp_obj_txt}) and IP objective ({ip_obj_txt}) use different objective "
            "functions and must NOT be compared as raw numbers. IP is benchmark-oriented; "
            "GP adds a workload-fairness component. Compare using the component-level "
            "metrics: coverage, requests, and workload fairness."
        ),
        ip_proven_optimal=ip_result.proven_optimal,
        gp_proven_optimal=gp_result.proven_optimal,
        ip_source=ip_result.source,
        gp_source=gp_result.source,
        gp_weights=dict(gp_result.weights),
    )


# ---------------------------------------------------------------------------
# Serialise to JSON for reproducibility
# ---------------------------------------------------------------------------

def comparison_to_dict(comparison: ComparisonResult) -> dict:
    """JSON-serialisable view of a ComparisonResult (used for the saved file and the UI download)."""

    def _ser(obj):
        if isinstance(obj, dict):
            return {str(k): _ser(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_ser(v) for v in obj]
        if isinstance(obj, (CoverageMetrics, WorkloadMetrics, RequestMetrics)):
            return {k: _ser(v) for k, v in obj.__dict__.items()}
        return obj

    data = {
        "ip": {
            "status": comparison.ip_status,
            "proven_optimal": comparison.ip_proven_optimal,
            "source": comparison.ip_source,
            "objective": comparison.ip_objective,
            "solve_time": comparison.ip_solve_time,
            "validation_passed": comparison.ip_validation_passed,
        },
        "gp": {
            "status": comparison.gp_status,
            "proven_optimal": comparison.gp_proven_optimal,
            "source": comparison.gp_source,
            "objective": comparison.gp_objective,
            "solve_time": comparison.gp_solve_time,
            "validation_passed": comparison.gp_validation_passed,
            "weights": comparison.gp_weights,
        },
        "benchmark": {
            "reference": comparison.benchmark_reference,
            "ip_gap": comparison.ip_benchmark_gap,
            "ip_gap_pct": comparison.ip_benchmark_gap_pct,
            "gp_benchmark_comparable": comparison.gp_benchmark_comparable,
        },
        "ip_coverage": _ser(comparison.ip_coverage),
        "gp_coverage": _ser(comparison.gp_coverage),
        "ip_workload": {
            "mean": comparison.ip_workload.mean_workload,
            "min": comparison.ip_workload.min_workload,
            "max": comparison.ip_workload.max_workload,
            "range": comparison.ip_workload.workload_range,
            "std_dev": comparison.ip_workload.std_dev,
            "jain_fairness_index": comparison.ip_workload.fairness_index,
        },
        "gp_workload": {
            "mean": comparison.gp_workload.mean_workload,
            "min": comparison.gp_workload.min_workload,
            "max": comparison.gp_workload.max_workload,
            "range": comparison.gp_workload.workload_range,
            "std_dev": comparison.gp_workload.std_dev,
            "jain_fairness_index": comparison.gp_workload.fairness_index,
        },
        "ip_requests": _ser(comparison.ip_requests),
        "gp_requests": _ser(comparison.gp_requests),
        "trade_off_summary": comparison.trade_off_summary,
        "note": comparison.comparison_note,
    }
    return data


def save_comparison(comparison: ComparisonResult, output_dir: str = "results",
                    filename: str = "ip_vs_gp_comparison.json") -> str:
    """Save comparison to a JSON file under output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(comparison_to_dict(comparison), f, indent=2)
    return path
