# Viva guide - questions you may be asked, with answers

All numbers below are verified results of this project (`docs/RESULTS.md`).

## The problem and the data

**What problem does the project solve?** Assigning nurses to shifts over a planning period so that required staffing is met, every
contractual rule holds, and as few requests as possible are broken - for a hospital ward, using a public benchmark instance.

**Why this dataset?** Nurse Rostering Benchmark Instance 3 (schedulingbenchmarks.org): public, widely used in research, with a *known proven
optimum (1001)* - so the model can be checked against the literature. 20 nurses, 14 days, 3 shift types, 21 contracts, 64 requests.

**Is it real hospital data?** No - a research benchmark; no skills, departments or labour-law specifics. That is stated as a limitation.

## Integer programming

**Decision variables?** x[n,d,s] binary - nurse n works shift s on day d (840 for Instance 3), plus helper variables y (works that day), z (works that weekend),
integer shortfall/surplus u, o, and binary request-violation variables.

**Why integer programming?** Assignments are yes/no decisions and the rules (rest time, consecutive days, weekends) are logical constraints - the textbook use of binary variables.

**Hard vs soft constraints?** Contract rules (one shift per day, valid shifts, workload limits, rest time, sequences, weekends, fixed days off) are *hard*. Cover (min/max nurses) and
the nurses' requests are *soft*: violating them costs the XML penalty (100 per missing nurse, 1 per surplus, 1-3 per request).

**How do you know the model is correct?** Three independent proofs: (1) the optimum equals the published optimum - **1001** on Instance 3, and 607, 828, 1716 on Instances 1, 2, 4;
(2) a separate validator re-checks every hard constraint on the output; (3) a separate evaluator recomputes the objective from the roster and it matches the solver's.

**Why is the optimum 1001?** 1000 + 1: ten nurse-shifts cannot be filled (contract capacity is only 155 shifts against a demand of 154, and fixed days off, the weekend rule and the sequence rules
remove more) and one weight-1 request cannot be honoured.

**Which solver?** CBC (branch-and-cut) through PuLP. Solving Instance 3 to *proven* optimality takes about 3 minutes single-threaded.

**What if the time limit is too short?** The result is labelled "Feasible, not proven optimal". (PuLP itself would say "Optimal"; the project reads the real solution status - a common pitfall.)

**What does "proven optimal" mean?** Branch-and-bound closed the gap between the best solution and the best bound: no better solution exists.

## Goal programming

**What is goal programming?** Each wish becomes a *goal equation* with under- and over-achievement (deviation) variables; the objective minimises the weighted deviations. Here: coverage (d-, d+),
requests, and workload fairness (wp-, wp+ around a target).

**What are the goals and weights?** G1 coverage (XML weights), G2 requests (XML weights), G3 workload deviation from each nurse's contract midpoint; w1 = w2 = w3 = 1, w4 = 0.5 per minute.

**Why 0.5?** It is a modelling choice, and the project is explicit about its effect: one shift (480 min) of deviation costs 480 x 0.5 = 240, more than one missing nurse (100). The sensitivity study
shows a single switch point at w4 = 100/480 = 0.208: below it the GP is "coverage first" (10 unfilled, same as the IP), at or above it "fairness first" (14 unfilled, 0 request violations, narrower
workload range) - and the result is the same for every w4 from 0.21 to 1.0, so 0.5 is not a knife-edge.

**Is it pre-emptive goal programming?** No - weighted-sum (Archimedean). Pre-emptive would solve the goals in priority order; that is listed as future work.

**What happens at w4 = 0?** The GP objective becomes the IP objective (Instance 3: 1001), proven in the sensitivity study.

## Comparison

**Why not compare 1001 with 2000?** Different objective functions (the GP has the fairness term and a different scale). The models are compared on *common components*: coverage, request violations,
workload spread.

**Which model is better?** Neither dominates. IP: best coverage (10 unfilled vs 14) - the benchmark's priority. GP (default): 0 request violations and a 480-minute narrower workload range on
Instance 3. On other instances the request result flips (worse on Instances 1 and 4), so conclusions are per instance. Which to use depends on whether the hospital ranks cover or fairness first.

## Statistics and the interface

**What statistics does the UI generate?** On demand: overview (size, demand 154, capacity 155), staffing demand (heat map, per day/shift, weekday profile), nurses (contract ranges, eligibility vs
peak demand), requests (per nurse, nurse x day map, weights), and downloadable tables.

**Can another dataset be loaded?** Yes: any NRP XML/ROS file. Unsupported features are reported as warnings; known published instances are recognised and compared against their own optimum.
Instances 1, 2 and 4 are bundled and also reach their published optima.

**Why "Load saved reference solution"?** Proving optimality for Instance 3 takes minutes; the saved solutions are real solver outputs that are re-validated and re-evaluated on loading, labelled as saved runs.

## Tricky questions

**Did you change the models while polishing the project?** No. A test pins both formulations (a hash of every variable, constraint and the objective) taken from the original code; the LP files of the original
and final versions are byte-identical.

**What did you find while polishing?** The earlier UI reported "Optimal" for time-limited runs, a hard-coded "validation passed", a crash when no solution was returned, and documentation numbers that did not match the
results. All fixed and covered by tests.

**Limitations?** Benchmark not real data; boundary convention for sequence rules; weighted-sum rather than lexicographic GP; weekends assume a Monday start (checked by the parser); single-threaded solver
(multithreaded CBC hung in testing).

**Future scope?** Lexicographic goal programming, skills and multiple wards, robust demand, rolling-horizon with history, a fairness metric between comparable nurses.
