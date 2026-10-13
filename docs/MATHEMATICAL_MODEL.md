# Mathematical model (final formulation)

Both models use the same sets, binary roster variables and hard constraints; they differ only in how the soft requirements
enter the objective. Implementation: `src/integer_program.py` and `src/goal_program.py`. Details and results:
`docs/INTEGER_PROGRAMMING.md`, `docs/GOAL_PROGRAMMING.md`.

## Sets, data, variables

* Sets: nurses N, days D, shift types S, weekends W (Saturday + Sunday of each week).
* Data from the XML: R^min(d,s), R^max(d,s) (cover) with penalty weights c^min, c^max; request weights a_i (ShiftOn), b_i
  (ShiftOff); shift durations L_s and start times; per-nurse contract limits (valid shifts, workload bounds, MaxTot, MaxSeq,
  MinSeq, MinRestTime, maximum working weekends) merged over all of the nurse's contracts.
* Variables: x[n,d,s] in {0,1} (nurse n works shift s on day d); y[n,d] = sum_s x[n,d,s]; z[n,w] in {0,1} (works weekend w).

## Hard constraints (both models)

1. sum_s x[n,d,s] = y[n,d] <= 1
2. x[n,d,s] = 0 for shifts not valid for n
3. y[n,d] = 0 on fixed days off
4. MinWL[n] <= sum L_s x[n,d,s] <= MaxWL[n]
5. sum_d x[n,d,s] <= MaxTot[n,s]
6. x[n,d,s1] + x[n,d+1,s2] <= 1 whenever start(s2)+24h - end(s1) < MinRestTime (840 min)
7. sum_{k=0..M} y[n,d+k] <= M  for every window of M+1 days (M = max consecutive working days)
8. y[n,d] - y[n,d-1] <= y[n,d+k]  (k = 1..minSeq-1) and  y[n,d-1] - y[n,d] + y[n,d+k] <= 1  (k = 1..minDaysOff-1)
   - blocks touching the horizon boundary are exempt
9. z[n,w] >= y[n,Sat_w], z[n,w] >= y[n,Sun_w], z[n,w] <= y[n,Sat_w] + y[n,Sun_w];  sum_w z[n,w] <= MaxWeekends[n]

## Model 1 - Integer Programming

    min  sum_{d,s} c^min u[d,s] + sum_{d,s} c^max o[d,s] + sum_i a_i v_on[i] + sum_i b_i v_off[i]
    s.t. sum_n x[n,d,s] + u[d,s] >= R^min[d,s]
         sum_n x[n,d,s] - o[d,s] <= R^max[d,s]
         x[n,d,s] + v_on[i] >= 1            (ShiftOn i)
         x[n,d,s] - v_off[i] <= 0           (ShiftOff i)
         u, o >= 0 integer;  v binary

The optimum equals the published benchmark value on Instances 1-4 (607, 828, 1001, 1716).

## Model 2 - Goal Programming

    G1:  sum_n x[n,d,s] + d-[d,s] - d+[d,s] = R^min[d,s]
    G2:  x[n,d,s] + v_on[i] >= 1 ;  x[n,d,s] - v_off[i] <= 0
    G3:  sum_{d,s} L_s x[n,d,s] + wp-[n] - wp+[n] = T[n],   T[n] = (MinWL[n] + MaxWL[n]) / 2

    min  w1 sum c^min d-  +  w3 sum c^max d+  +  w2 (sum a_i v_on + sum b_i v_off)  +  w4 sum (wp+ + wp-)

Default weights w1 = w2 = w3 = 1, w4 = 0.5 (per minute). One shift of workload deviation costs 480 x w4 = 240, one unfilled
nurse-slot 100; the GP switches from "coverage first" to "fairness first" at w4 = 100/480 = 0.208 (proven in the
sensitivity study). With w4 = 0 the GP objective equals the IP objective (Instance 3).

## Why two models

The IP answers "what is the best roster under the benchmark's objective?" (and can be checked against the literature). The GP
answers "what if the planner also wants closeness to each nurse's contractual workload, and wants to weigh the goals?" -
the multicriteria view from the course syllabus. The two are compared on common components, never on raw objective values.
