"""Solution charts (src/visualization.py) built from the saved, verified reference results."""

import unittest

import plotly.graph_objects as go

from src.comparison import compare_optimization_results
from src import visualization as viz
from tests.common import dataset, reference


class TestVisualization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = dataset("Instance3")
        cls.ip = reference("Instance3", "ip")
        cls.gp = reference("Instance3", "gp")
        cls.comp = compare_optimization_results(cls.ip, cls.gp, cls.ds)

    def _ok(self, fig):
        self.assertIsInstance(fig, go.Figure)
        self.assertGreater(len(fig.data), 0)
        return fig

    def test_single_model_charts(self):
        for res in (self.ip, self.gp):
            self._ok(viz.create_coverage_chart(self.ds, res))
            self._ok(viz.create_shortfall_heatmap(self.ds, res))
            self._ok(viz.create_roster_heatmap(res, self.ds))

    def test_comparison_charts(self):
        self._ok(viz.create_ip_gp_coverage_chart(self.comp))
        self._ok(viz.create_workload_chart(self.comp))
        self._ok(viz.create_fairness_chart(self.comp))
        self._ok(viz.create_request_chart(self.comp))
        self._ok(viz.create_shift_distribution_chart(self.ip, self.gp, self.ds))

    def test_breakdown_charts_show_the_model_components(self):
        ip_fig = self._ok(viz.create_ip_breakdown_chart(self.ds, self.ip))
        self.assertEqual(list(ip_fig.data[0].y), [1000.0, 0.0, 1.0])            # under, over, requests (=1001)
        gp_fig = self._ok(viz.create_gp_breakdown_chart(self.gp))
        self.assertEqual(sum(gp_fig.data[0].y), 2000.0)                          # 1400 + 0 + 0 + 600

    def test_roster_heatmap_dimensions_and_content(self):
        fig = viz.create_roster_heatmap(self.ip, self.ds)
        self.assertEqual(len(fig.data[0].z), 20)          # nurses
        self.assertEqual(len(fig.data[0].z[0]), 14)       # days
        worked = sum(1 for row in fig.data[0].z for v in row if v > 0)
        self.assertEqual(worked, len(self.ip.assignments))

    def test_shortfall_heatmap_matches_understaffing(self):
        z = viz.create_shortfall_heatmap(self.ds, self.ip).data[0].z
        short = -sum(v for row in z for v in row if v < 0)
        self.assertEqual(short, 10)

    def test_benchmark_chart_shows_only_the_ip_objective(self):
        fig = viz.create_benchmark_chart(self.comp)
        self.assertEqual(fig.data[0].value, self.comp.ip_objective)
        title = fig.data[0].title.text
        self.assertIn("proven optimal", title)
        self.assertNotIn("2000", title)
        self.assertEqual(fig.data[0].delta.reference, 1001.0)

    def test_benchmark_chart_without_reference_does_not_crash(self):
        import copy
        comp = copy.copy(self.comp)
        comp.benchmark_reference = None
        fig = viz.create_benchmark_chart(comp)
        self.assertEqual(fig.data[0].value, comp.ip_objective)
        self.assertIn("no published benchmark", fig.data[0].title.text)


if __name__ == "__main__":
    unittest.main()
