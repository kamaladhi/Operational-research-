"""
Structural fingerprint of the two optimisation models.

``build_models(dataset)`` runs the project's own ``solve_integer_program`` / ``solve_goal_program`` with
PuLP's ``solve`` intercepted, so the *real* model-building code executes but no solver is called.
``signature(prob)`` hashes every variable (name, bounds, category) and every constraint (name, sense,
right-hand side, sorted coefficients) plus the objective, independent of PuLP's LP-file formatting.

tests/test_model_unchanged.py pins the fingerprints that the ORIGINAL project code produced for
Instance 3, so any accidental change to a formulation is caught.
"""

import hashlib
from typing import Dict, Tuple

import pulp


class _Stop(Exception):
    pass


def build_models(dataset) -> Dict[str, pulp.LpProblem]:
    """Return {'IP': problem, 'GP': problem} as built by the project code (nothing is solved)."""
    from src.integer_program import solve_integer_program
    from src.goal_program import solve_goal_program

    captured = {}
    original = pulp.LpProblem.solve

    def fake_solve(self, solver=None, **kwargs):
        captured["prob"] = self
        raise _Stop()

    pulp.LpProblem.solve = fake_solve
    try:
        out = {}
        for key, fn in (("IP", solve_integer_program), ("GP", solve_goal_program)):
            try:
                fn(dataset, 10)
            except _Stop:
                pass
            out[key] = captured["prob"]
        return out
    finally:
        pulp.LpProblem.solve = original


def signature(prob: pulp.LpProblem) -> Tuple[int, int, str]:
    """(#variables, #constraints, sha256) of the model."""
    h = hashlib.sha256()
    for v in sorted(prob.variables(), key=lambda v: v.name):
        h.update(f"V|{v.name}|{v.lowBound}|{v.upBound}|{v.cat}\n".encode())
    for name in sorted(prob.constraints):
        c = prob.constraints[name]
        coeffs = sorted((v.name, float(a)) for v, a in c.items())
        h.update(f"C|{name}|{c.sense}|{c.constant}|{coeffs}\n".encode())
    obj = sorted((v.name, float(a)) for v, a in prob.objective.items())
    h.update(f"O|{prob.sense}|{obj}\n".encode())
    return len(prob.variables()), len(prob.constraints), h.hexdigest()
