"""The solver-status fix: 'Optimal' may only be reported when CBC actually proved optimality."""

import unittest
from types import SimpleNamespace

import pulp

from src.integer_program import solve_integer_program
from src.solver_utils import describe_status, interpret_cbc_status
from tests.common import PUBLISHED_OPTIMUM, dataset


def _prob(sol_status, status=1):
    return SimpleNamespace(sol_status=sol_status, status=status)


class TestInterpretStatus(unittest.TestCase):
    def test_optimal_solution_found(self):
        self.assertEqual(interpret_cbc_status(_prob(pulp.LpSolutionOptimal)), ("Optimal", True))

    def test_time_limited_incumbent_is_feasible_not_optimal(self):
        # PuLP gives status == 1 ("Optimal") here; the project must NOT repeat that claim.
        self.assertEqual(interpret_cbc_status(_prob(pulp.LpSolutionIntegerFeasible, status=1)), ("Feasible", False))

    def test_infeasible_unbounded_and_not_solved(self):
        self.assertEqual(interpret_cbc_status(_prob(pulp.LpSolutionInfeasible, status=-1)), ("Infeasible", False))
        self.assertEqual(interpret_cbc_status(_prob(pulp.LpSolutionUnbounded, status=-2)), ("Unbounded", False))
        self.assertEqual(interpret_cbc_status(_prob(pulp.LpSolutionNoSolutionFound, status=0)), ("Not Solved", False))
        # status 1 but no solution value at all must not be reported as solved
        self.assertEqual(interpret_cbc_status(_prob(pulp.LpSolutionNoSolutionFound, status=1)), ("Not Solved", False))

    def test_describe_status_never_claims_optimality_for_feasible(self):
        self.assertIn("NOT proven", describe_status("Feasible", False, 60))
        self.assertIn("Proven optimal", describe_status("Optimal", True))
        self.assertIn("No feasible", describe_status("Infeasible", False))


class TestRealSolverStatus(unittest.TestCase):
    def test_easy_instance_is_proven_optimal(self):
        r = solve_integer_program(dataset("Instance1"), time_limit=60)
        self.assertEqual(r.status, "Optimal")
        self.assertTrue(r.proven_optimal)
        self.assertEqual(r.objective_value, PUBLISHED_OPTIMUM["Instance1"])

    def test_time_limited_run_is_reported_as_feasible(self):
        """Instance 3 needs minutes to prove optimality, so a 5 s run must come back as Feasible."""
        r = solve_integer_program(dataset("Instance3"), time_limit=5)
        self.assertEqual(r.status, "Feasible")
        self.assertFalse(r.proven_optimal)
        self.assertIsNotNone(r.objective_value)
        self.assertGreaterEqual(r.objective_value, PUBLISHED_OPTIMUM["Instance3"])
        self.assertEqual(r.time_limit, 5)


if __name__ == "__main__":
    unittest.main()
