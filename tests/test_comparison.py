"""
Tests for the comparison module (src/comparison.py).

They use the saved, verified reference solutions (fast); no solver runs here.  The comparison must
* never compare the raw IP and GP objectives,
* compute (not assume) hard-constraint validation,
* only quote a benchmark gap for a known instance.
"""

import copy
import json
import os
import tempfile
import unittest

from src.comparison import (ComparisonResult, _compute_jain_fairness, _compute_std_dev, comparison_to_dict,
                            compare_optimization_results, save_comparison)
from tests.common import dataset, reference


class TestComparisonHelpers(unittest.TestCase):
    def test_jain_fairness_uniform(self):
        self.assertAlmostEqual(_compute_jain_fairness([3840, 3840, 3840, 3840]), 1.0, places=5)

    def test_jain_fairness_unequal(self):
        idx = _compute_jain_fairness([4320, 3360, 4320, 3360])
        self.assertLess(idx, 1.0)
        self.assertGreater(idx, 0.0)

    def test_jain_fairness_all_zeros(self):
        self.assertAlmostEqual(_compute_jain_fairness([0, 0, 0]), 1.0)

    def test_std_dev(self):
        self.assertAlmostEqual(_compute_std_dev([5, 5, 5, 5]), 0.0)
        self.assertAlmostEqual(_compute_std_dev([2, 4, 4, 4, 5, 5, 7, 9]), 2.0, places=5)


class TestComparisonInstance3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = dataset("Instance3")
        cls.ip = reference("Instance3", "ip")
        cls.gp = reference("Instance3", "gp")
        cls.comp = compare_optimization_results(cls.ip, cls.gp, cls.ds)

    def test_object_and_statuses(self):
        self.assertIsInstance(self.comp, ComparisonResult)
        self.assertTrue(self.comp.ip_proven_optimal)
        self.assertTrue(self.comp.gp_proven_optimal)
        self.assertEqual(self.comp.ip_source, "saved reference run")

    def test_ip_matches_the_benchmark_exactly(self):
        c = self.comp
        self.assertEqual(c.ip_objective, 1001.0)
        self.assertEqual(c.benchmark_reference, 1001.0)
        self.assertEqual(c.ip_benchmark_gap, 0.0)
        self.assertEqual(c.ip_benchmark_gap_pct, 0.0)
        self.assertIn("equals the best-known benchmark value 1001", c.trade_off_summary[0])
        self.assertIn("proven optimal", c.trade_off_summary[0])

    def test_gp_is_flagged_not_comparable_and_note_has_the_real_numbers(self):
        self.assertFalse(self.comp.gp_benchmark_comparable)
        note = self.comp.comparison_note
        self.assertIn("2000", note)
        self.assertIn("1001", note)
        self.assertIn("NOT", note)

    def test_component_figures(self):
        c = self.comp
        self.assertEqual(c.ip_coverage.total_understaffing_magnitude, 10)
        self.assertEqual(c.gp_coverage.total_understaffing_magnitude, 14)
        self.assertEqual(c.ip_coverage.total_required_nurse_slots, 154)
        self.assertEqual(c.ip_requests.total_on_requests + c.ip_requests.total_off_requests, 64)
        self.assertEqual(c.gp_requests.total_violations, 0)
        self.assertLessEqual(c.ip_coverage.coverage_rate_pct, 100.0)
        self.assertEqual(c.ip_workload.workload_range, c.ip_workload.max_workload - c.ip_workload.min_workload)
        self.assertLessEqual(c.gp_workload.workload_range, c.ip_workload.workload_range)

    def test_validation_is_computed_and_passes(self):
        self.assertTrue(self.comp.ip_validation_passed)
        self.assertEqual(self.comp.ip_validation_errors, [])
        self.assertTrue(self.comp.gp_validation_passed)

    def test_validation_is_not_hard_coded(self):
        """A roster that breaks the hard constraints must make the IP validation flag False."""
        bad = copy.copy(self.ip)
        bad.assignments = dict(self.ip.assignments)
        for d in range(14):
            bad.assignments[("E", d)] = "E"          # nurse E works every day, ignoring days off / sequence limits
        comp = compare_optimization_results(bad, self.gp, self.ds)
        self.assertFalse(comp.ip_validation_passed)
        self.assertGreater(len(comp.ip_validation_errors), 0)

    def test_no_winner_is_declared(self):
        self.assertNotIn("winner", " ".join(self.comp.trade_off_summary).lower())

    def test_gap_reflects_a_worse_ip_objective(self):
        worse = copy.copy(self.ip)
        worse.objective_value = 1004.0
        comp = compare_optimization_results(worse, self.gp, self.ds)
        self.assertAlmostEqual(comp.ip_benchmark_gap_pct, 0.2997, places=4)
        self.assertIn("above the best-known", comp.trade_off_summary[0])

    def test_unknown_instance_has_no_benchmark(self):
        no_ref = copy.copy(self.ip)
        no_ref.benchmark_reference = None
        comp = compare_optimization_results(no_ref, self.gp, self.ds)
        self.assertIsNone(comp.benchmark_reference)
        self.assertIsNone(comp.ip_benchmark_gap_pct)
        self.assertIn("not a published benchmark", comp.trade_off_summary[0])

    def test_json_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = save_comparison(self.comp, tmp)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(data, json.loads(json.dumps(comparison_to_dict(self.comp))))
        self.assertTrue(data["ip"]["proven_optimal"])
        self.assertFalse(data["benchmark"]["gp_benchmark_comparable"])
        self.assertEqual(data["gp"]["weights"]["w4_fairness"], 0.5)


class TestComparisonOtherInstances(unittest.TestCase):
    def test_instance1_and_2(self):
        for name, opt in (("Instance1", 607.0), ("Instance2", 828.0)):
            comp = compare_optimization_results(reference(name, "ip"), reference(name, "gp"), dataset(name))
            self.assertEqual(comp.ip_objective, opt)
            self.assertEqual(comp.ip_benchmark_gap_pct, 0.0)
            self.assertTrue(comp.ip_validation_passed and comp.gp_validation_passed)


if __name__ == "__main__":
    unittest.main()
