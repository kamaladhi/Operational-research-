# Model 1 - Integer Programming (benchmark objective)

Code: [`src/integer_program.py`](../src/integer_program.py) - function `solve_integer_program(dataset, time_limit)`.
Solver: **CBC** (COIN-OR branch-and-cut) through **PuLP**, single-threaded, silent, wall-clock limit.

The model is the benchmark's own formulation: all contractual rules are **hard constraints**, and the objective
is the sum of the **penalties of the soft requirements** that the XML defines (cover and requests). Because the
objective is exactly the benchmark objective, the optimum can be compared with the published best-known value.

## Sets and data (all read from the XML - nothing hard-coded)

| Symbol | Meaning |
|---|---|
| N, D, S, W | nurses, days, shift types, weekends (Saturday + Sunday of each week) |
| R^min(d,s), R^max(d,s) | minimum / maximum nurses required on day d, shift s |
| c^min(d,s), c^max(d,s) | penalty per missing / surplus nurse (XML `weight`; 100 and 1 in Instance 3) |
| a_i, b_i | penalty weights of ShiftOn request i / ShiftOff request i |
| L_s | shift duration (minutes); start times give the rest-time rule |
| per-nurse limits | valid shifts, min/max workload, max consecutive days, min consecutive days / days off, max shifts of a type, max working weekends - merged over the nurse's contracts |

## Decision variables

| Variable | Type | Meaning |
|---|---|---|
| x[n,d,s] | binary | nurse n works shift s on day d (840 for Instance 3) |
| y[n,d] | binary | nurse n works any shift on day d (= sum_s x) |
| z[n,w] | binary | nurse n works weekend w |
| u[d,s], o[d,s] | integer >= 0 | under- / over-staffing of day d, shift s |
| v_on[i], v_off[i] | binary | ShiftOn / ShiftOff request i is violated |

Instance 3: **1308 variables, 2547 constraints.**

## Hard constraints

1. **One shift per day**: sum_s x[n,d,s] = y[n,d] <= 1
2. **Valid shifts**: x[n,d,s] = 0 if s is not allowed by the nurse's contracts (intersection of all contracts)
3. **Fixed assignments**: y[n,d] = 0 on a fixed day off
4. **Workload bounds**: MinWL[n] <= sum L_s * x[n,d,s] <= MaxWL[n]
5. **Max shifts of a type**: sum_d x[n,d,s] <= MaxTot[n,s]
6. **Minimum rest (840 min)**: if start(s2) + 24h - end(s1) < 840, then x[n,d,s1] + x[n,d+1,s2] <= 1.
   For Instance 3 this forbids Late->Early (480 min), Late->Day (660 min) and Day->Early (780 min).
7. **Max consecutive working days**: sum of y over every window of M+1 days <= M
8. **Min consecutive working days** and **min consecutive days off**: a block that starts inside the horizon
   must last at least the minimum (`y[d] - y[d-1] <= y[d+k]` and `y[d-1] - y[d] + y[d+k] <= 1`); blocks touching the
   horizon boundary are exempt, the benchmark convention for instances without history.
9. **Weekends**: z[n,w] >= y[n,Sat], z[n,w] >= y[n,Sun], z[n,w] <= y[n,Sat] + y[n,Sun]; sum_w z[n,w] <= MaxWeekends[n]

## Soft requirements and objective

```
sum_n x[n,d,s] + u[d,s] >= R^min[d,s]          (missing nurses)
sum_n x[n,d,s] - o[d,s] <= R^max[d,s]          (surplus nurses)
x[n,d,s] + v_on[i]  >= 1                        (ShiftOn request i: nurse n wants shift s on day d)
x[n,d,s] - v_off[i] <= 0                        (ShiftOff request i)

minimise  Z_IP = sum c^min*u + sum c^max*o + sum a_i*v_on[i] + sum b_i*v_off[i]
```

## Results (verified)

| Instance | Published optimum | IP objective | Status | Gap | Unfilled nurse-shifts | Request violations | Solve time* |
|---|---|---|---|---|---|---|---|
| Instance 1 | 607  | 607  | proven optimal | 0 % | 6  | 4 | 1.4 s |
| Instance 2 | 828  | 828  | proven optimal | 0 % | 8  | 18 | 1.6 s |
| **Instance 3** | **1001** | **1001** | **proven optimal** | **0 %** | **10** | **1** | **181.8 s** |
| Instance 4 | 1716 | 1716 | proven optimal | 0 % | 17 | 7 | 126.6 s |

\*single-threaded CBC, measured with several solves running at once; depends on the machine.

**Instance 3 anatomy of the optimum:** 1001 = 1000 (10 unavoidable unfilled nurse-shifts x 100) + 1 (one ShiftOn
request of weight 1 that cannot be honoured). The contractual capacity (155 shifts) barely exceeds the demand (154),
and fixed days off, weekend and sequence rules make 10 slots impossible to fill.

**Scalability evidence (not bundled):** within 240 s the same model reached 1150 on Instance 5 (optimum 1143) and
1955 on Instance 6 (optimum 1950) - valid rosters, 0.6 % and 0.3 % above the proven optima, not proven optimal.

## Solver status - how it is reported

PuLP returns `status = 1` ("Optimal") whenever CBC *returns*, even if the **time limit** stopped the search. The
reliable signal is `sol_status`. The project therefore reports:

| CBC result | Shown as |
|---|---|
| `sol_status = 1` | **Optimal** (proven) |
| `sol_status = 2` | **Feasible - not proven optimal** (typically the time limit) |
| infeasible / unbounded / nothing found | Infeasible / Unbounded / Not Solved |

(An earlier version of the project showed "Optimal" for a 60-second run that had only reached 1004; the same code
proves 1001 given about 3 minutes. See `tests/test_solver_status.py`.)

## Independent checks

* `src/validation.py` re-checks every hard constraint on the produced roster.
* `src/evaluation.py` recomputes Z_IP from the roster alone; tests assert it equals the solver objective.
* `tests/test_model_unchanged.py` pins the model's structure.

## How to run

```python
from src.parser import parse_xml
from src.integer_program import solve_integer_program
ds = parse_xml("data/raw/Instance3.xml")
r = solve_integer_program(ds, time_limit=600)
print(r.status, r.proven_optimal, r.objective_value, r.benchmark_gap_percent)   # Optimal True 1001.0 0.0
```
