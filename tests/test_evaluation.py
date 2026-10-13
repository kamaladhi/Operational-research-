"""The independent evaluator must reproduce the solvers' objectives exactly."""

import unittest

from src.evaluation import build_gp_result, build_ip_result, evaluate_gp, evaluate_ip, gp_workload_targets
from src.goal_program import solve_goal_program
from src.integer_program import solve_integer_program
from src.validation import validate_solution
from tests.common import PUBLISHED_OPTIMUM, dataset, reference


class TestEvaluateIP(unittest.TestCase):
    def test_empty_roster_penalty_is_computed_from_the_data(self):
        ds = dataset("Instance3")
        ev = evaluate_ip(ds, {})
        under = sum(c.min_weight * c.min_nurses for c in ds.cover_requirements)
        on_weights = sum(r.weight for r in ds.shift_requests if r.is_on_request)
        self.assertEqual(ev.understaffing_penalty, under)
        self.assertEqual(ev.overstaffing_penalty, 0)
        self.assertEqual(ev.request_penalty, on_weights)          # nobody works -> all ShiftOn violated, no ShiftOff
        self.assertEqual(ev.objective, under + on_weights)

    def test_reference_rosters_reproduce_published_optima(self):
        for name, optimum in PUBLISHED_OPTIMUM.items():
            r = reference(name, "ip")
            self.assertEqual(evaluate_ip(dataset(name), r.assignments).objective, optimum, name)

    def test_solver_objective_equals_recomputed_objective(self):
        for name in ("Instance1", "Instance2"):
            ds = dataset(name)
            r = solve_integer_program(ds, time_limit=60)
            self.assertAlmostEqual(r.objective_value, evaluate_ip(ds, r.assignments).objective, places=6, msg=name)

    def test_build_ip_result_matches_a_live_solve(self):
        ds = dataset("Instance2")
        live = solve_integer_program(ds, time_limit=60)
        rebuilt = build_ip_result(ds, live.assignments, status="Optimal", proven_optimal=True, solve_time=0.0)
        self.assertEqual(rebuilt.objective_value, live.objective_value)
        self.assertEqual(rebuilt.understaffing, live.understaffing)
        self.assertEqual(rebuilt.overstaffing, live.overstaffing)
        self.assertEqual(sorted(rebuilt.shift_request_violations), sorted(live.shift_request_violations))
        self.assertEqual(rebuilt.workload_per_employee, live.workload_per_employee)
        self.assertEqual(rebuilt.benchmark_reference, live.benchmark_reference)


class TestEvaluateGP(unittest.TestCase):
    def test_targets_are_contract_midpoints(self):
        t = gp_workload_targets(dataset("Instance3"))
        self.assertEqual(t["A"], 3840.0)      # (3360 + 4320) / 2  - full-time
        self.assertEqual(t["P"], 1680.0)      # (1200 + 2160) / 2  - part-time

    def test_reference_gp_objective_decomposes(self):
        ds = dataset("Instance3")
        r = reference("Instance3", "gp")
        ev = evaluate_gp(ds, r.assignments)
        self.assertEqual(ev.objective, 2000.0)
        self.assertEqual(ev.understaffing_penalty, 1400.0)
        self.assertEqual(ev.request_penalty, 0.0)
        self.assertEqual(ev.fairness_penalty, 600.0)
        self.assertEqual(ev.understaffing_penalty + ev.overstaffing_penalty + ev.request_penalty + ev.fairness_penalty,
                         ev.objective)

    def test_solver_objective_equals_recomputed_objective_for_several_weights(self):
        ds = dataset("Instance1")
        for w4 in (0.0, 0.2, 0.5, 1.0):
            r = solve_goal_program(ds, time_limit=60, w4=w4)
            ev = evaluate_gp(ds, r.assignments, {"w4": w4})
            self.assertAlmostEqual(r.gp_objective_value, ev.objective, places=4, msg=f"w4={w4}")
            self.assertTrue(r.hard_constraint_valid)

    def test_build_gp_result_matches_a_live_solve(self):
        ds = dataset("Instance2")
        live = solve_goal_program(ds, time_limit=60)
        rebuilt = build_gp_result(ds, live.assignments, status="Optimal", proven_optimal=True, solve_time=0.0)
        self.assertAlmostEqual(rebuilt.gp_objective_value, live.gp_objective_value, places=4)
        self.assertEqual(rebuilt.total_understaffing_penalty, live.total_understaffing_penalty)
        self.assertEqual(rebuilt.total_request_penalty, live.total_request_penalty)
        self.assertAlmostEqual(rebuilt.workload_fairness_penalty, live.workload_fairness_penalty, places=2)
        self.assertEqual(rebuilt.workload_per_employee, live.workload_per_employee)
        self.assertTrue(rebuilt.hard_constraint_valid)

    def test_gp_with_zero_fairness_weight_equals_ip_objective_on_instance3(self):
        """Documented property: with w4 = 0 the GP objective reduces to the IP/benchmark objective (Min = Max)."""
        ds = dataset("Instance3")
        r = reference("Instance3", "ip")
        self.assertEqual(evaluate_gp(ds, r.assignments, {"w4": 0.0}).objective, evaluate_ip(ds, r.assignments).objective)


class TestValidator(unittest.TestCase):
    def test_reference_rosters_are_feasible(self):
        for name in PUBLISHED_OPTIMUM:
            for model in ("ip", "gp"):
                try:
                    r = reference(name, model)
                except Exception:
                    continue
                self.assertTrue(validate_solution(dataset(name), r.assignments).is_feasible, (name, model))

    def test_validator_detects_a_broken_roster(self):
        ds = dataset("Instance3")
        roster = dict(reference("Instance3", "ip").assignments)
        # make nurse A work 14 days in a row on shift E: breaks max-consecutive, rest/fixed-off and workload rules
        for d in range(14):
            roster[("A", d)] = "E"
        report = validate_solution(ds, roster)
        self.assertFalse(report.is_feasible)
        self.assertGreater(len(report.errors), 0)


if __name__ == "__main__":
    unittest.main()
