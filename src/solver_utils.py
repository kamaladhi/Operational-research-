"""
Solver helpers shared by the Integer Programming and Goal Programming modules.

Why this module exists
----------------------
PuLP's ``prob.status`` is 1 ("Optimal") whenever CBC *returns*, including when it
was stopped by the time limit with only a feasible incumbent.  The reliable
signal is ``prob.sol_status``:

    1  "Optimal Solution Found"   -> CBC proved optimality
    2  "Solution Found"           -> integer-feasible incumbent, NOT proven optimal
                                     (typically: time limit reached)
    0 / -1 / -2                   -> not solved / infeasible / unbounded

``interpret_cbc_status`` converts that into the status string used everywhere in
the project, so the UI and the reports never claim optimality that was not proven.
"""

from typing import Optional, Tuple

import pulp


def make_cbc_solver(time_limit: int) -> pulp.PULP_CBC_CMD:
    """
    Build the CBC command used by both models (silent, with a wall-clock limit).

    CBC runs single-threaded on purpose: with ``threads > 1`` the bundled Windows CBC build was
    observed to hang on Instance 3 (14 minutes, 3 CPU-seconds), so multithreading is not offered.
    """
    return pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit)


def interpret_cbc_status(prob: pulp.LpProblem) -> Tuple[str, bool]:
    """
    Translate PuLP/CBC state into ``(status, proven_optimal)``.

    status is one of:
        "Optimal"     - optimality proven
        "Feasible"    - a feasible solution exists but optimality is NOT proven
        "Infeasible"  - the model has no feasible solution
        "Unbounded"
        "Not Solved"  - no usable solution (e.g. time limit hit before the first one)
    """
    sol = getattr(prob, "sol_status", None)
    if sol == pulp.LpSolutionOptimal:
        return "Optimal", True
    if sol == pulp.LpSolutionIntegerFeasible:
        return "Feasible", False
    if prob.status == pulp.LpStatusInfeasible or sol == pulp.LpSolutionInfeasible:
        return "Infeasible", False
    if prob.status == pulp.LpStatusUnbounded or sol == pulp.LpSolutionUnbounded:
        return "Unbounded", False
    return "Not Solved", False


def describe_status(status: str, proven_optimal: bool, time_limit: Optional[float] = None) -> str:
    """One-line, user-facing explanation of a solver status."""
    if status == "Optimal" and proven_optimal:
        return "Proven optimal - CBC finished the search."
    if status == "Feasible":
        limit = f" ({time_limit:.0f} s)" if time_limit else ""
        return ("Feasible, NOT proven optimal - the time limit" + limit +
                " stopped the search. Increase the limit to try to prove optimality.")
    if status == "Infeasible":
        return "No feasible roster exists for this model."
    if status == "Unbounded":
        return "The model is unbounded (check the data)."
    return "No solution was found - increase the time limit."
