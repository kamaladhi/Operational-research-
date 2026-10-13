"""Saved reference solutions: verified on load, tamper-evident, and equal to the published optima."""

import json
import os
import shutil
import tempfile
import unittest

from src.reference_solutions import (REFERENCE_DIR, ReferenceSolutionError, has_reference, load_reference,
                                     reference_path, reference_provenance)
from tests.common import PUBLISHED_OPTIMUM, dataset


class TestReferenceSolutions(unittest.TestCase):
    def test_every_bundled_ip_reference_is_proven_optimal_and_equals_the_published_value(self):
        for name, optimum in PUBLISHED_OPTIMUM.items():
            r = load_reference(dataset(name), "ip")
            self.assertTrue(r.proven_optimal, name)
            self.assertEqual(r.status, "Optimal")
            self.assertEqual(r.objective_value, optimum, name)
            self.assertEqual(r.benchmark_gap_percent, 0.0)
            self.assertEqual(r.source, "saved reference run")

    def test_instance3_gp_reference(self):
        r = load_reference(dataset("Instance3"), "gp")
        self.assertTrue(r.proven_optimal)
        self.assertEqual(r.gp_objective_value, 2000.0)
        self.assertTrue(r.hard_constraint_valid)
        self.assertFalse(r.gp_benchmark_comparable)

    def test_provenance_and_availability(self):
        self.assertTrue(has_reference(dataset("Instance3"), "ip"))
        prov = reference_provenance(dataset("Instance3"), "ip")
        self.assertEqual(prov["instance"], "Instance3")
        self.assertTrue(prov["proven_optimal"])
        self.assertIn("CBC", prov["solver"]["solver"])

    def test_missing_reference_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(has_reference(dataset("Instance3"), "ip", tmp))
            with self.assertRaises(ReferenceSolutionError):
                load_reference(dataset("Instance3"), "ip", tmp)

    def _tampered_copy(self, mutate):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        src = reference_path("Instance3", "ip", REFERENCE_DIR)
        with open(src, encoding="utf-8") as f:
            data = json.load(f)
        mutate(data)
        with open(reference_path("Instance3", "ip", tmp), "w", encoding="utf-8") as f:
            json.dump(data, f)
        return tmp

    def test_tampered_objective_is_rejected(self):
        tmp = self._tampered_copy(lambda d: d.__setitem__("objective", 900.0))
        with self.assertRaises(ReferenceSolutionError) as cm:
            load_reference(dataset("Instance3"), "ip", tmp)
        self.assertIn("recomputed", str(cm.exception))

    def test_tampered_roster_that_breaks_hard_constraints_is_rejected(self):
        def mutate(d):
            d["assignments"] = [a for a in d["assignments"] if a[0] != "B"] + [["B", day, "E"] for day in range(14)]
        tmp = self._tampered_copy(mutate)
        with self.assertRaises(ReferenceSolutionError) as cm:
            load_reference(dataset("Instance3"), "ip", tmp)
        self.assertIn("hard constraints", str(cm.exception))

    def test_reference_for_wrong_instance_is_rejected(self):
        tmp = self._tampered_copy(lambda d: d.__setitem__("instance", "Instance1"))
        with self.assertRaises(ReferenceSolutionError):
            load_reference(dataset("Instance3"), "ip", tmp)

    def test_files_exist_for_all_bundled_instances(self):
        for name in PUBLISHED_OPTIMUM:
            self.assertTrue(os.path.exists(reference_path(name, "ip")), name)


if __name__ == "__main__":
    unittest.main()
