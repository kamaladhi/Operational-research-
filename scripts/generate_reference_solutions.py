"""
Generate the saved reference solutions (results/reference_solutions/*.json).

Runs the Integer Programming and Goal Programming models (unchanged) with a long time limit on the
bundled benchmark instances, checks that CBC *proved* optimality, cross-checks the objective with the
independent evaluator, validates every hard constraint, and stores the rosters.

Usage (from the project root):
    python scripts/generate_reference_solutions.py                      # Instances 1-3, both models
    python scripts/generate_reference_solutions.py --instances Instance3 --models ip --time-limit 900
    python scripts/generate_reference_solutions.py --allow-unproven     # also keep time-limited incumbents

Each (instance, model) pair runs in its own process, so they solve in parallel.
"""

import argparse
import concurrent.futures as cf
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DATA_DIR = os.path.join(ROOT, "data", "raw")


def solve_one(args):
    instance, model, time_limit, allow_unproven = args
    import pulp
    from src.parser import parse_xml
    from src.integer_program import solve_integer_program
    from src.goal_program import solve_goal_program
    from src.evaluation import evaluate_ip, evaluate_gp
    from src.validation import validate_solution
    from src.reference_solutions import save_reference

    ds = parse_xml(os.path.join(DATA_DIR, f"{instance}.xml"))
    t0 = time.time()
    if model == "ip":
        res = solve_integer_program(ds, time_limit=time_limit)
        objective, recomputed = res.objective_value, (evaluate_ip(ds, res.assignments).objective if res.assignments else None)
    else:
        res = solve_goal_program(ds, time_limit=time_limit)
        objective = res.gp_objective_value
        recomputed = evaluate_gp(ds, res.assignments).objective if res.assignments else None
    wall = time.time() - t0

    report = validate_solution(ds, res.assignments)
    line = {"instance": instance, "model": model.upper(), "status": res.status, "proven_optimal": res.proven_optimal,
            "objective": objective, "recomputed": recomputed, "valid": report.is_feasible, "seconds": round(wall, 1)}
    if objective is None or not report.is_feasible:
        line["saved"] = False
        line["reason"] = "no solution or hard-constraint violation"
        return line
    if abs(objective - recomputed) > 1e-3:
        line["saved"] = False
        line["reason"] = "solver objective differs from the independent recomputation"
        return line
    if not res.proven_optimal and not allow_unproven:
        line["saved"] = False
        line["reason"] = "optimality not proven within the time limit (use a longer limit or --allow-unproven)"
        return line

    solver_info = {"library": f"PuLP {pulp.__version__}", "solver": "CBC (PULP_CBC_CMD, single thread)",
                   "generated": time.strftime("%Y-%m-%d")}
    path = save_reference(ds, model, res, solver_info)
    line["saved"] = True
    line["file"] = os.path.relpath(path, ROOT)
    return line


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", nargs="+", default=["Instance1", "Instance2", "Instance3"])
    ap.add_argument("--models", nargs="+", choices=["ip", "gp"], default=["ip", "gp"])
    ap.add_argument("--time-limit", type=int, default=900, help="seconds per solve (default 900)")
    ap.add_argument("--allow-unproven", action="store_true")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()

    tasks = [(i, m, a.time_limit, a.allow_unproven) for i in a.instances for m in a.models]
    results = []
    with cf.ProcessPoolExecutor(max_workers=min(a.jobs, len(tasks))) as ex:
        for line in ex.map(solve_one, tasks):
            print(json.dumps(line), flush=True)
            results.append(line)
    bad = [r for r in results if not r.get("saved")]
    print(f"\n{len(results) - len(bad)}/{len(results)} reference solutions saved.")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
