# Optimization comparison: IP vs GP

All figures are produced by `src/comparison.py` from the saved, verified reference solutions
(`python scripts/generate_comparison_reports.py` -> `results/ip_vs_gp_comparison_<Instance>.json`, `results/summary.csv`).
Both rosters are re-validated against the hard constraints inside the comparison - validation is computed, never assumed.

## The caveat that governs everything

The IP objective is the benchmark objective. The GP objective adds a workload-fairness term (and uses different weights).
**Raw objectives are never compared** (1001 vs 2000 says nothing about which roster is "better"). The IP is compared with
the published benchmark; the two models are compared with each other **component by component**.

## Instance 3 (20 nurses, 14 days)

| | Integer Programming | Goal Programming (default weights) |
|---|---|---|
| Solution status | proven optimal | proven optimal |
| Objective | 1001 (published optimum 1001, gap 0 %) | 2000 (not benchmark-comparable) |
| Solve time* | 181.8 s | 24.1 s |
| Hard constraints | all satisfied | all satisfied |
| **Coverage** - unfilled nurse-shifts (of 154) | **10** | 14 |
| Coverage rate | **93.51 %** | 90.91 % |
| Weighted understaffing penalty | **1000** | 1400 |
| Overstaffing | 0 | 0 |
| **Requests** - violations (of 64) | 1 (a ShiftOn, weight 1) | **0** |
| **Workload** - range (min / max shift-minutes) | 2400 (1920 / 4320) | **1920** (1920 / 3840) |
| Std. deviation of workload | 930.8 min | **831.4 min** |
| Jain's fairness index | 0.9324 | **0.9423** |

\*single-threaded CBC, several solves in parallel.

**Reading it:** the IP fills 4 more nurse-shifts (patient cover) - and 10 is the proven minimum possible. The GP accepts
4 more unfilled nurse-shifts in exchange for zero request violations and a workload range 480 minutes narrower. The size
of that exchange is governed by w4 (see the sensitivity table in `GOAL_PROGRAMMING.md`). **Neither model dominates**; the
choice depends on whether the hospital ranks coverage or nurse fairness first.

## The same comparison on the other bundled instances

| Instance | Unfilled IP / GP | Request violations IP / GP | Workload range IP / GP (min) | Jain IP / GP |
|---|---|---|---|---|
| Instance 1 | 6 / 7  | 4 / 8   | 960 / 0     | 0.9900 / 1.0000 |
| Instance 2 | 8 / 12 | 18 / 11 | 2400 / 1920 | 0.9252 / 0.9351 |
| Instance 3 | 10 / 14 | 1 / 0  | 2400 / 1920 | 0.9324 / 0.9423 |
| Instance 4 | 17 / 17 | 7 / 8  | 960 / 0     | 0.9984 / 1.0000 |

Two consistent patterns: the GP never has *better* coverage than the IP (the IP's coverage is optimal for the benchmark
objective) and its workload is at least as balanced. The request result is **instance-dependent** (GP better on 2 and 3,
worse on 1 and 4) - so the statement "the GP satisfies all requests" holds for Instance 3 only.

## Metrics (as implemented)

| Category | Metric | Definition |
|---|---|---|
| Coverage | Understaffing / overstaffing magnitude | sum of shortfalls below Min / excess above Max |
| Coverage | Weighted penalty | sum(XML weight x deviation) |
| Coverage | Coverage rate | sum(min(assigned, required)) / sum(required) - capped per day-shift so surplus cannot hide a shortfall |
| Requests | Violations, rate, weighted penalty | counted from the roster against the XML requests |
| Workload | Range, std. deviation | over all nurses (full-time and part-time mixed) |
| Workload | Jain's index | (sum x)^2 / (n * sum x^2); 1 = perfectly equal |

## Limitations

* Post-hoc comparison of two single solutions, not a Pareto frontier (the weight study in `GOAL_PROGRAMMING.md` is the
  closest thing: it shows the one switch point of the trade-off).
* Range and Jain's index treat all nurses alike although contracts differ (full-time 7-9 shifts, part-time 3-4), so a perfect
  roster still has a non-zero range on instances that mix contract types.
