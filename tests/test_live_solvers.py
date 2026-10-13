"""
Live solver tests: the two UNCHANGED models run end-to-end and must reproduce known optima.

* Instances 1 and 2 solve in about a second - always run.
* Instance 3 needs ~2-3 minutes for the IP to prove optimality; those tests only run when the
  environment variable RUN_SLOW_TESTS=1 is set.

Every solution is validated against the hard constraints and its objective is recomputed by the
independent evaluator.
"""

import unittest

from src.evaluation import evaluate_gp, evaluate_ip
from src.goal_program import solve_goal_program
from src.integer_program import solve_integer_program
from src.validation import validate_solution
from tests.common import PUBLISHED_OPTIMUM, SLOW, dataset

#: Regression values of the GP objective (default weights), proven optimal by CBC.
GP_OPTIMUM = {"Instance1": 716.0, "Instance2": 1694.0, "Instance3": 2000.0}


class TestIntegerProgrammingLive(unittest.TestCase):
    def _check(self, name, limit):
        ds = dataset(name)
        r = solve_integer_program(ds, time_limit=limit)
        self.assertEqual(r.status, "Optimal", f"{name}: {r.status}")
        self.assertTrue(r.proven_optimal)
        self.assertEqual(r.objective_value, PUBLISHED_OPTIMUM[name], f"{name} must reach the published optimum")
        self.assertEqual(r.benchmark_gap_percent, 0.0)
        self.assertTrue(validate_solution(ds, r.assignments).is_feasible)
        self.assertEqual(evaluate_ip(ds, r.assignments).objective, r.objective_value)
        return r

    def test_instance1_reaches_published_optimum_607(self):
        self._check("Instance1", 60)

    def test_instance2_reaches_published_optimum_828(self):
        self._check("Instance2", 60)

    @unittest.skipUnless(SLOW, "set RUN_SLOW_TESTS=1 (takes ~3 minutes)")
    def test_instance3_reaches_published_optimum_1001(self):
        r = self._check("Instance3", 900)
        self.assertEqual(len(r.shift_request_violations), 1)       # one ShiftOn (weight 1) is unavoidable

    @unittest.skipUnless(SLOW, "set RUN_SLOW_TESTS=1 (takes ~2 minutes)")
    def test_instance4_reaches_published_optimum_1716(self):
        self._check("Instance4", 900)


class TestGoalProgrammingLive(unittest.TestCase):
    def _check(self, name, limit):
        ds = dataset(name)
        r = solve_goal_program(ds, time_limit=limit)
        self.assertEqual(r.status, "Optimal", f"{name}: {r.status}")
        self.assertTrue(r.proven_optimal)
        self.assertEqual(r.gp_objective_value, GP_OPTIMUM[name])
        self.assertTrue(r.hard_constraint_valid, r.hard_constraint_errors)
        self.assertFalse(r.gp_benchmark_comparable)
        ev = evaluate_gp(ds, r.assignments)
        self.assertAlmostEqual(ev.objective, r.gp_objective_value, places=4)
        self.assertEqual(sorted(r.weights), ["w1_understaffing", "w2_requests", "w3_overstaffing", "w4_fairness"])
        self.assertEqual(r.weights["w4_fairness"], 0.5)
        return r

    def test_instance1(self):
        self._check("Instance1", 60)

    def test_instance2(self):
        self._check("Instance2", 60)

    def test_workload_targets_respect_hard_bounds(self):
        from src.integer_program import get_employee_contract_constraints
        ds = dataset("Instance1")
        r = solve_goal_program(ds, time_limit=60)
        for n in ds.employees:
            c = get_employee_contract_constraints(ds, n)
            t = r.workload_target_per_employee[n]
            self.assertGreaterEqual(t, c["min_workload"] - 1e-6)
            self.assertLessEqual(t, c["max_workload"] + 1e-6)

    @unittest.skipUnless(SLOW, "set RUN_SLOW_TESTS=1 (takes ~30 seconds)")
    def test_instance3_gp_optimum_2000_with_documented_decomposition(self):
        r = self._check("Instance3", 300)
        self.assertEqual(r.total_understaffing_penalty, 1400.0)
        self.assertEqual(r.workload_fairness_penalty, 600.0)
        self.assertEqual(len(r.shift_request_violations), 0)


if __name__ == "__main__":
    unittest.main()
