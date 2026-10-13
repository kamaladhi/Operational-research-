"""
Goal Programming weight-sensitivity experiment (documentation aid - the model itself is unchanged).

Re-solves the unchanged GP model on one instance for several values of the workload-fairness weight
w4 (all other weights keep their documented defaults) and records how the three goals trade off.
Results: results/gp_weight_sensitivity.json and .csv, summarised in docs/GOAL_PROGRAMMING.md.

Usage (from the project root):
    python scripts/gp_weight_sensitivity.py                         # Instance3, default grid
    python scripts/gp_weight_sensitivity.py --instance Instance2 --time-limit 300
"""

import argparse
import concurrent.futures as cf
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEFAULT_GRID = [0.0, 0.1, 0.2, 0.21, 0.25, 0.3, 0.5, 1.0]


def solve_w4(args):
    instance, w4, time_limit = args
    from src.parser import parse_xml
    from src.goal_program import solve_goal_program
    from src.evaluation import evaluate_gp

    ds = parse_xml(os.path.join(ROOT, "data", "raw", f"{instance}.xml"))
    t0 = time.time()
    r = solve_goal_program(ds, time_limit=time_limit, w4=w4)
    wall = time.time() - t0
    vals = list(r.workload_per_employee.values())
    recomputed = evaluate_gp(ds, r.assignments, {"w4": w4}).objective if r.assignments else None
    return {
        "instance": instance,
        "w4": w4,
        "status": r.status,
        "proven_optimal": r.proven_optimal,
        "gp_objective": r.gp_objective_value,
        "objective_check": None if recomputed is None else abs(recomputed - r.gp_objective_value) < 1e-3,
        "understaffed_nurse_slots": sum(r.understaffing.values()),
        "understaffing_penalty": r.total_understaffing_penalty,
        "request_violations": len(r.shift_request_violations),
        "request_penalty": r.total_request_penalty,
        "fairness_penalty": r.workload_fairness_penalty,
        "workload_range_min": (max(vals) - min(vals)) if vals else None,
        "assignments": len(r.assignments),
        "hard_constraints_ok": r.hard_constraint_valid,
        "seconds": round(wall, 1),
        "time_limit": time_limit,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", default="Instance3")
    ap.add_argument("--w4", nargs="+", type=float, default=DEFAULT_GRID)
    ap.add_argument("--time-limit", type=int, default=900)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()

    tasks = [(a.instance, w, a.time_limit) for w in a.w4]
    rows = []
    with cf.ProcessPoolExecutor(max_workers=min(a.jobs, len(tasks))) as ex:
        for row in ex.map(solve_w4, tasks):
            print(json.dumps(row), flush=True)
            rows.append(row)

    out_dir = os.path.join(ROOT, "results")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "gp_weight_sensitivity.json"), "w", encoding="utf-8") as f:
        json.dump({"note": "Only w4 varies; w1=w2=w3=1. Rows with proven_optimal=false are time-limited "
                           "incumbents, not proven optima.", "rows": rows}, f, indent=1)
    import pandas as pd
    pd.DataFrame(rows).to_csv(os.path.join(out_dir, "gp_weight_sensitivity.csv"), index=False)
    print("saved results/gp_weight_sensitivity.json/.csv")


if __name__ == "__main__":
    main()
