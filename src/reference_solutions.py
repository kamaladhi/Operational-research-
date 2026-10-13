"""
Saved reference solutions.

Solving Instance 3 to proven optimality takes a couple of minutes, which is slow for a live
demonstration.  ``scripts/generate_reference_solutions.py`` runs the two models once, with a
long time limit, and stores the resulting rosters in ``results/reference_solutions``.

The UI can load such a file instantly.  Loading never trusts the stored numbers:

* the roster is re-validated against every hard constraint (``validate_solution``),
* the objective is recomputed by ``src.evaluation`` and must equal the stored value,
* the result is labelled ``source = "saved reference run"`` everywhere it is shown.

The stored status/solve time are provenance of the original run (solver, status, seconds).
"""

import json
import os
from typing import Dict, Optional, Tuple, Union

from src.benchmarks import identify_instance
from src.data_model import ParsedDataset
from src.evaluation import build_gp_result, build_ip_result, evaluate_gp, evaluate_ip
from src.goal_program import GoalProgrammingResult
from src.integer_program import OptimizationResult
from src.validation import validate_solution

REFERENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "results", "reference_solutions")


class ReferenceSolutionError(Exception):
    """A saved solution failed verification."""


def reference_path(instance: str, model: str, directory: str = REFERENCE_DIR) -> str:
    return os.path.join(directory, f"{instance}_{model.lower()}.json")


def has_reference(dataset: ParsedDataset, model: str, directory: str = REFERENCE_DIR) -> bool:
    inst = identify_instance(dataset)
    return inst is not None and os.path.exists(reference_path(inst, model, directory))


def save_reference(
    dataset: ParsedDataset,
    model: str,
    result: Union[OptimizationResult, GoalProgrammingResult],
    solver_info: Dict,
    directory: str = REFERENCE_DIR,
) -> str:
    """Store a solved roster plus the provenance of the run that produced it."""
    inst = identify_instance(dataset)
    if inst is None:
        raise ReferenceSolutionError("Only known benchmark instances can be saved as references.")
    objective = result.objective_value if model.lower() == "ip" else result.gp_objective_value
    payload = {
        "instance": inst,
        "model": model.upper(),
        "status": result.status,
        "proven_optimal": bool(result.proven_optimal),
        "objective": objective,
        "solve_time_s": round(result.solve_time, 2),
        "time_limit_s": result.time_limit,
        "solver": solver_info,
        "weights": getattr(result, "weights", None),
        "assignments": sorted([n, d, s] for (n, d), s in result.assignments.items()),
    }
    os.makedirs(directory, exist_ok=True)
    path = reference_path(inst, model, directory)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    return path


def load_reference(
    dataset: ParsedDataset, model: str, directory: str = REFERENCE_DIR
) -> Union[OptimizationResult, GoalProgrammingResult]:
    """Load, verify and rebuild a saved reference result for the dataset's instance."""
    inst = identify_instance(dataset)
    if inst is None:
        raise ReferenceSolutionError("This dataset is not a known benchmark instance.")
    path = reference_path(inst, model, directory)
    if not os.path.exists(path):
        raise ReferenceSolutionError(f"No saved {model.upper()} reference for {inst}.")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("instance") != inst or data.get("model") != model.upper():
        raise ReferenceSolutionError("Reference file does not match the dataset/model.")

    assignments = {(n, int(d)): s for n, d, s in data["assignments"]}
    report = validate_solution(dataset, assignments)
    if not report.is_feasible:
        raise ReferenceSolutionError("Saved roster violates hard constraints: " + "; ".join(report.errors[:3]))

    stored = float(data["objective"])
    if model.lower() == "ip":
        recomputed = evaluate_ip(dataset, assignments).objective
        result = build_ip_result(
            dataset, assignments, status=data["status"], proven_optimal=bool(data["proven_optimal"]),
            solve_time=float(data["solve_time_s"]), time_limit=data.get("time_limit_s"))
    else:
        w = data.get("weights") or {}
        weights = {"w1": w.get("w1_understaffing", 1.0), "w2": w.get("w2_requests", 1.0),
                   "w3": w.get("w3_overstaffing", 1.0), "w4": w.get("w4_fairness", 0.5)}
        recomputed = evaluate_gp(dataset, assignments, weights).objective
        result = build_gp_result(
            dataset, assignments, status=data["status"], proven_optimal=bool(data["proven_optimal"]),
            solve_time=float(data["solve_time_s"]), weights=weights, time_limit=data.get("time_limit_s"))
    if abs(recomputed - stored) > 1e-3:
        raise ReferenceSolutionError(
            f"Stored objective {stored} does not match the recomputed objective {recomputed:.4f}.")
    return result


def reference_provenance(dataset: ParsedDataset, model: str, directory: str = REFERENCE_DIR) -> Optional[dict]:
    """Metadata of the stored run (solver, status, seconds) without rebuilding the result."""
    inst = identify_instance(dataset)
    if inst is None:
        return None
    path = reference_path(inst, model, directory)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return {k: d.get(k) for k in ("instance", "model", "status", "proven_optimal", "objective",
                                  "solve_time_s", "time_limit_s", "solver")}
