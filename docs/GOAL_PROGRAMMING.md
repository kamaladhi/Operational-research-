# Model 2 - Goal Programming

Code: [`src/goal_program.py`](../src/goal_program.py) - function `solve_goal_program(dataset, time_limit, w1, w2, w3, w4)`.
Solver: CBC through PuLP (same as Model 1).

## Idea

The IP minimises one penalty sum that the benchmark fixes. The Goal Programming model treats the planner's wishes as
**goals**: each goal is an equation with a negative and a positive **deviation variable**, and the objective minimises
the weighted deviations. It adds a goal the benchmark does not have - **fairness of workload** - and lets the user
change the goal weights on the **Optimization** page.

## Variables and hard constraints

Same binary roster variables x, y, z and **exactly the same hard constraints** as Model 1 (one shift per day, valid
shifts, fixed days off, workload bounds, maximum shifts per type, rest time, consecutive-days rules, weekends).
Soft requirements move out of the constraints and into goals.

## Goals

**G1 - staffing coverage** (per day d and shift s)

    sum_n x[n,d,s] + d-[d,s] - d+[d,s] = R^min[d,s]

d- = missing nurses (penalised with the XML weight c^min, ~100), d+ = surplus nurses (penalised with c^max, ~1).

**G2 - requests**

    x[n,d,s] + v_on[i] >= 1          (ShiftOn request i)
    x[n,d,s] - v_off[i] <= 0         (ShiftOff request i)

penalised with the XML request weights.

**G3 - workload fairness** (per nurse)

    sum_{d,s} L_s * x[n,d,s] + wp-[n] - wp+[n] = T[n],     T[n] = (MinWL[n] + MaxWL[n]) / 2

The target T[n] is the midpoint of the nurse's contractual workload bounds, so it can always be met without breaking
the hard workload constraints. (Full-time nurses: 3840 min = 8 shifts; part-time: 1680 min = 3.5 shifts.)

## Objective

    min Z_GP = w1 * sum c^min * d-  +  w3 * sum c^max * d+  +  w2 * (sum a_i v_on + sum b_i v_off)  +  w4 * sum (wp+ + wp-)

| Weight | Goal | Default |
|---|---|---|
| w1 | understaffing | 1 |
| w2 | request violations | 1 |
| w3 | overstaffing | 1 |
| w4 | workload deviation, **per minute** | 0.5 |

This is a **weighted-sum** goal program (priorities are expressed through the weights), not a pre-emptive/lexicographic one.

## What the weights really mean (and the sensitivity study)

w4 converts minutes into penalty units. One 8-hour shift of deviation from the target costs **480 x w4**; one unfilled
nurse-slot costs **100**. So the GP prefers to leave a slot unfilled rather than push a nurse 480 minutes away from the
target exactly when 480 x w4 > 100, i.e. **w4 > 0.208**. At the default w4 = 0.5 one shift of imbalance costs 240 units -
*more* than a missing nurse (an earlier version of the documentation claimed the opposite; that was wrong).

`scripts/gp_weight_sensitivity.py` re-solves the unchanged GP on Instance 3 for several w4 (w1 = w2 = w3 = 1). Every row
below is **proven optimal** (`results/gp_weight_sensitivity.csv`):

| w4 | GP objective | Unfilled nurse-shifts | Request violations | Fairness penalty | Workload range (min) | Regime |
|---|---|---|---|---|---|---|
| 0    | 1001 | 10 | 1 | 0    | 2400 | **= IP objective** (coverage first) |
| 0.1  | 1315 | 10 | 2 | 312  | 2400 | coverage first, some fairness |
| 0.2  | 1627 | 10 | 3 | 624  | 2400 | coverage first, some fairness |
| 0.21 | 1652 | 14 | 0 | 252  | 1920 | **fairness first** (switch point 0.208) |
| 0.25 | 1700 | 14 | 0 | 300  | 1920 | fairness first |
| 0.3  | 1760 | 14 | 0 | 360  | 1920 | fairness first |
| **0.5 (default)** | **2000** | **14** | **0** | **600** | **1920** | fairness first |
| 1.0  | 2600 | 14 | 0 | 1200 | 1920 | fairness first |

Reading the table:

* **w4 = 0 reproduces the IP result exactly** (objective 1001): the GP is the IP plus one extra goal.
* There is a **single switch point at w4 = 100/480 = 0.208**, exactly as the arithmetic predicts (0.2 -> coverage first,
  0.21 -> fairness first).
* For every w4 in **[0.21, 1.0]** the roster's characteristics are identical (14 unfilled, 0 request violations, range
  1920 min); only the objective scales. The documented default is therefore **not a knife-edge**: any weight above the
  switch point gives the same trade-off.
* The trade-off, stated plainly: moving from the IP to the default GP **costs 4 more unfilled nurse-shifts** (10 -> 14) and
  **buys** 0 request violations (1 -> 0) and a workload range 480 minutes narrower. Whether that is desirable is a
  management priority (patient cover vs. nurse fairness) - the model exposes the trade-off, it does not decide it.

## Results with the default weights

| Instance | GP objective | Status | Unfilled nurse-shifts (IP) | Request violations (IP) | Workload range min (IP) |
|---|---|---|---|---|---|
| Instance 1 | 716  | proven optimal | 7 (6)   | 8 (4)  | 0 (960) |
| Instance 2 | 1694 | proven optimal | 12 (8)  | 11 (18) | 1920 (2400) |
| **Instance 3** | **2000** | **proven optimal** | **14 (10)** | **0 (1)** | **1920 (2400)** |
| Instance 4 | 2021 | proven optimal | 17 (17) | 8 (7)  | 0 (960) |

Instance 3 decomposition: 1400 (14 unfilled x 100) + 0 (overstaffing) + 0 (requests) + 600 (fairness: 0.5 x 1200 minutes of
total deviation from the targets) = **2000**.

The pattern on Instance 3 ("GP satisfies every request") is **not general**: on Instances 1 and 4 the GP breaks *more*
requests than the IP, because the fairness goal competes with them. Conclusions must be drawn per instance.

## Comparing with the IP

The GP objective (2000) and the IP/benchmark objective (1001) measure different things and are **never compared as raw
numbers** - not in the UI, the tests or the reports. They are compared on common components (coverage, requests,
workload): [`COMPARISON.md`](COMPARISON.md).

## Independent checks

* `src/validation.py` verifies the hard constraints of every GP roster.
* `src/evaluation.py` recomputes Z_GP from the roster (any weights); tests assert it equals the solver objective for
  w4 in {0, 0.2, 0.5, 1}.

## Limitations

1. Weighted-sum GP: the priority order is approximate; a lexicographic GP would solve the goals in sequence.
2. The workload target is the contract midpoint, i.e. the goal measures closeness to each nurse's contract, not equality
   between nurses (full-time and part-time nurses have different targets by design).
3. The default w4 = 0.5 is a modelling choice; its consequences are quantified above.
