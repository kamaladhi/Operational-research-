# Verified results and how to reproduce them

Everything below was produced by the code in this repository and re-checked by independent code
(`src/validation.py` for the hard constraints, `src/evaluation.py` for the objectives). Nothing is typed in by hand:
`results/summary.csv` and `results/*.json` are generated files.

## 1. Integer Programming vs the published benchmark optima

| Instance | Published best known = lower bound | IP objective | CBC status | Gap |
|---|---|---|---|---|
| Instance 1 | 607 | 607 | Optimal (proven) | 0 % |
| Instance 2 | 828 | 828 | Optimal (proven) | 0 % |
| Instance 3 | 1001 | 1001 | Optimal (proven) | 0 % |
| Instance 4 | 1716 | 1716 | Optimal (proven) | 0 % |

Source of the published values: <https://www.schedulingbenchmarks.org/nrp/> (saved copy: `data/raw/nrp.html`).
For these instances the best known solution equals the best known lower bound, so the published value is the optimum.
Matching it exactly on four instances of different size (8-20 nurses, 14-28 days, 1-3 shift types) shows the
formulation, the parser and the solver setup are correct.

## 2. Goal Programming (default weights)

| Instance | GP objective | CBC status |
|---|---|---|
| Instance 1 | 716  | Optimal (proven) |
| Instance 2 | 1694 | Optimal (proven) |
| Instance 3 | 2000 | Optimal (proven) |
| Instance 4 | 2021 | Optimal (proven) |

Not comparable with the IP/benchmark objective - see `COMPARISON.md`.

## 3. GP weight sensitivity (Instance 3)

Eight values of w4, all proven optimal; single switch point at w4 = 100/480 = 0.208. Full table and interpretation:
`GOAL_PROGRAMMING.md`; data: `results/gp_weight_sensitivity.csv`.

## 4. Automated tests

117 tests, all passing (`run_tests.bat slow`): parser and diagnostics, benchmark registry, solver-status semantics,
independent evaluator, saved-solution verification (including tamper tests), statistics and charts, comparison, result
tables, the unchanged-model fingerprints, live solves of Instances 1-4, and every page of the UI. See `TESTING.md`.

## 5. Real-browser check

The running application was driven in Microsoft Edge with Playwright: load Instance 3, generate statistics, load the saved
IP and GP solutions, visit every page - no page raised an exception.

## 6. Reproduce

```
python scripts/generate_reference_solutions.py --time-limit 900     # solves + proof of optimality + saves rosters
python scripts/generate_comparison_reports.py                       # results/ip_vs_gp_comparison_*.json, summary.csv/md
python scripts/gp_weight_sensitivity.py                             # results/gp_weight_sensitivity.*
run_tests.bat slow
```

Run times depend on the machine. Reference timings (single-threaded CBC, up to 8 solves in parallel on a 16-core PC):
IP Instance 3 about 3 minutes; GP Instance 3 about 25 seconds; Instances 1-2 about 1 second each.

## 7. Facts worth knowing

* Instance 3's optimum 1001 = 1000 + 1: ten nurse-shifts cannot be filled (contract capacity 155 vs demand 154, minus fixed
  days off, weekend and sequence rules) and one weight-1 request cannot be honoured.
* Multithreaded CBC (`threads > 1`) hung on Instance 3 in testing, so the solver runs single-threaded.
* A 60-second IP limit is **not** enough to prove optimality on Instance 3 (it stops at about 1004); the UI now labels such a
  run "Feasible, not proven optimal" instead of "Optimal".
