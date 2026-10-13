import unittest

from src.benchmarks import benchmark_for, benchmark_info, gap_percent, identify_instance, instance_description
from tests.common import PUBLISHED_OPTIMUM, dataset


class TestBenchmarks(unittest.TestCase):
    def test_bundled_instances_are_identified_with_published_values(self):
        for name, value in PUBLISHED_OPTIMUM.items():
            ds = dataset(name)
            self.assertEqual(identify_instance(ds), name)
            self.assertEqual(benchmark_for(ds), value)
            info = benchmark_info(ds)
            self.assertTrue(info["proven_optimal"])
            self.assertEqual(info["best_known"], info["lower_bound"])

    def test_modified_dataset_gets_no_benchmark(self):
        import copy
        ds = copy.deepcopy(dataset("Instance3"))
        ds.shift_requests = ds.shift_requests[:-1]          # no longer the published instance
        self.assertIsNone(identify_instance(ds))
        self.assertIsNone(benchmark_for(ds))
        self.assertIsNone(benchmark_info(ds))

    def test_gap_percent(self):
        self.assertAlmostEqual(gap_percent(1004.0, 1001.0), 0.2997, places=4)
        self.assertEqual(gap_percent(1001.0, 1001.0), 0.0)
        self.assertIsNone(gap_percent(None, 1001.0))
        self.assertIsNone(gap_percent(1001.0, None))

    def test_instance_description(self):
        text = instance_description("Instance3")
        self.assertIn("20 nurses", text)
        self.assertIn("1001", text)


if __name__ == "__main__":
    unittest.main()
