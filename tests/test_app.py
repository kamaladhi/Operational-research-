"""
UI tests: every page of app.py is driven headlessly with Streamlit's own test harness (AppTest).

Solvers are not run for the page-rendering tests - they use the saved, verified reference results
(loaded through the same buttons a user would click) - except for one end-to-end test that clicks the
real "Run" buttons on the fast Instance 1.
"""

import copy
import os
import unittest

from streamlit.testing.v1 import AppTest

from src.evaluation import build_ip_result
from src.integer_program import OptimizationResult
from src.validation import validate_solution
from tests.common import ROOT, dataset, reference

APP = os.path.join(ROOT, "app.py")
PAGES = ["📁 Dataset", "📊 Statistics", "📘 Model", "⚙️ Optimization", "📈 Results",
         "🖼️ Visualizations", "⚖️ Comparison", "📅 Roster"]
STAT_CHOICES = ["Overview", "Staffing demand", "Nurses & contracts", "Requests & fixed days off", "Data tables"]


def fresh():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    return at


def go(at, page):
    at.sidebar.radio(key="nav").set_value(page).run()
    return at


def loaded(name="Instance3", with_results=False):
    """App with a dataset in session state (and, optionally, both reference results loaded via the UI)."""
    at = fresh()
    at.session_state["dataset"] = dataset(name)
    at.session_state["dataset_label"] = name + ".xml"
    at.run()
    if with_results:
        go(at, "⚙️ Optimization")
        at.button(key="load_ip").click().run()
        at.button(key="load_gp").click().run()
    return at


def texts(elements):
    return " ".join(str(e.value) for e in elements)


class TestAppStatic(unittest.TestCase):
    def test_no_hardcoded_solver_results_in_app_source(self):
        with open(APP, encoding="utf-8") as f:
            src = f.read()
        for needle in ("= 1004", "= 2000", "= 1104", "- 1001) / 1001"):
            self.assertNotIn(needle, src)

    def test_app_passes_time_limit_to_the_ip_solver(self):
        with open(APP, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("solve_integer_program(dataset, time_limit=", src)

    def test_deprecated_container_width_only_used_in_the_compat_helper(self):
        with open(APP, encoding="utf-8") as f:
            src = f.read()
        self.assertEqual(src.count("use_container_width"), 2)       # the STRETCH helper (check + fallback) only


class TestColdStart(unittest.TestCase):
    def test_every_page_renders_without_a_dataset(self):
        at = fresh()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("No dataset loaded", texts(at.info))
        for page in PAGES[1:]:
            go(at, page)
            self.assertEqual(len(at.exception), 0, page)
        # the model page needs no data; the rest ask for it / for a run
        go(at, "📘 Model")
        self.assertGreater(len(at.latex), 0)


class TestDatasetPage(unittest.TestCase):
    def test_load_bundled_sample_through_the_ui(self):
        at = fresh()
        at.selectbox(key="sample_pick").select("Instance1")
        at.button(key="load_sample").click().run()
        self.assertEqual(len(at.exception), 0)
        ds = at.session_state["dataset"]
        self.assertEqual(len(ds.employees), 8)
        self.assertIn("607", texts(at.success))                      # recognised + published optimum shown
        self.assertEqual([m.label for m in at.metric][:2], ["Nurses", "Days"])

    def test_unknown_dataset_gets_no_benchmark_message(self):
        ds = copy.deepcopy(dataset("Instance3"))
        ds.shift_requests = ds.shift_requests[:-1]
        at = fresh()
        at.session_state["dataset"] = ds
        at.session_state["dataset_label"] = "custom.xml"
        at.run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("does not match a published benchmark", texts(at.info))

    def test_parser_warnings_are_shown(self):
        ds = copy.deepcopy(dataset("Instance3"))
        ds.warnings = ["Unsupported top-level section(s) ignored by the models: SkillTypes"]
        at = fresh()
        at.session_state["dataset"] = ds
        at.run()
        self.assertIn("SkillTypes", texts(at.warning))


class TestStatisticsPage(unittest.TestCase):
    def test_every_statistics_choice_renders_with_charts(self):
        at = loaded("Instance3")
        go(at, "📊 Statistics")
        for choice in STAT_CHOICES:
            at.radio(key="stats_choice").set_value(choice).run()
            self.assertEqual(len(at.exception), 0, choice)
        # chart-bearing choices
        expected_charts = {"Overview": 1, "Staffing demand": 4, "Nurses & contracts": 2, "Requests & fixed days off": 3}
        for choice, n in expected_charts.items():
            at.radio(key="stats_choice").set_value(choice).run()
            self.assertGreaterEqual(len(at.get("plotly_chart")), n, choice)

    def test_overview_shows_the_real_numbers(self):
        at = loaded("Instance3")
        go(at, "📊 Statistics")
        labels = {m.label: m.value for m in at.metric}
        self.assertEqual(labels["Nurses"], "20")
        self.assertEqual(labels["Required nurse-shifts (sum of Min)"], "154")
        self.assertEqual(labels["Total maximum shifts (all nurses)"], "155")

    def test_statistics_work_for_other_instances(self):
        for name in ("Instance1", "Instance2", "Instance4"):
            at = loaded(name)
            go(at, "📊 Statistics")
            for choice in STAT_CHOICES:
                at.radio(key="stats_choice").set_value(choice).run()
                self.assertEqual(len(at.exception), 0, f"{name}/{choice}")


class TestOptimizationAndResults(unittest.TestCase):
    def test_load_reference_solutions_then_every_page(self):
        at = loaded("Instance3", with_results=True)
        self.assertEqual(len(at.exception), 0)
        ip, gp = at.session_state["ip_result"], at.session_state["gp_result"]
        self.assertEqual((ip.objective_value, ip.proven_optimal), (1001.0, True))
        self.assertEqual((gp.gp_objective_value, gp.proven_optimal), (2000.0, True))
        for page in PAGES:
            go(at, page)
            self.assertEqual(len(at.exception), 0, page)

    def test_results_page_states_proof_of_optimality_and_zero_gap(self):
        at = loaded("Instance3", with_results=True)
        go(at, "📈 Results")
        self.assertIn("Proven optimal", texts(at.success))
        md = texts(at.markdown)
        self.assertIn("1001", md)
        self.assertIn("0.0000%", md)
        self.assertIn("proven by CBC", md)

    def test_comparison_page_contents(self):
        at = loaded("Instance3", with_results=True)
        go(at, "⚖️ Comparison")
        self.assertEqual(len(at.table), 4)                           # overview, coverage, requests, workload
        overview = at.table[0].value
        self.assertIn("✅ proven optimal", overview.loc[overview["Metric"] == "Solution status", "IP"].iloc[0])
        self.assertEqual(overview.loc[overview["Metric"] == "Hard-constraint validation", "IP"].iloc[0], "✅ Pass")
        self.assertIn("equals the best-known", texts(at.markdown))

    def test_visualization_page_has_all_chart_groups(self):
        at = loaded("Instance3", with_results=True)
        go(at, "🖼️ Visualizations")
        self.assertGreaterEqual(len(at.get("plotly_chart")), 3)
        at.radio(key="viz_model").set_value("GP").run()
        self.assertEqual(len(at.exception), 0)

    def test_roster_page_for_both_models(self):
        at = loaded("Instance3", with_results=True)
        go(at, "📅 Roster")
        self.assertIn("All hard constraints satisfied", texts(at.success))
        at.radio(key="roster_model").set_value("GP").run()
        self.assertEqual(len(at.exception), 0)

    def test_feasible_not_proven_is_flagged_with_a_warning(self):
        ds = dataset("Instance3")
        ref = reference("Instance3", "ip")
        r = build_ip_result(ds, ref.assignments, status="Feasible", proven_optimal=False, solve_time=60.0,
                            time_limit=60, source="live solve")
        at = fresh()
        at.session_state["dataset"] = ds
        at.session_state["ip_result"] = r
        at.session_state["val_ip"] = validate_solution(ds, r.assignments)
        at.run()
        go(at, "📈 Results")
        self.assertEqual(len(at.exception), 0)
        self.assertIn("NOT proven optimal", texts(at.warning))
        self.assertIn("NOT proven", texts(at.markdown))

    def test_custom_gp_weights_show_a_warning(self):
        at = loaded("Instance3")
        go(at, "⚙️ Optimization")
        at.number_input(key="w4").set_value(0.3).run()
        self.assertIn("Non-default weights", texts(at.warning))

    def test_end_to_end_live_run_on_instance1(self):
        at = loaded("Instance1")
        go(at, "⚙️ Optimization")
        at.button(key="run_ip").click().run()
        at.button(key="run_gp").click().run()
        self.assertEqual(len(at.exception), 0)
        ip, gp = at.session_state["ip_result"], at.session_state["gp_result"]
        self.assertEqual((ip.status, ip.objective_value, ip.source), ("Optimal", 607.0, "live solve"))
        self.assertEqual((gp.status, gp.gp_objective_value), ("Optimal", 716.0))
        self.assertTrue(at.session_state["val_ip"].is_feasible and at.session_state["val_gp"].is_feasible)
        for page in PAGES[4:]:
            go(at, page)
            self.assertEqual(len(at.exception), 0, page)

    def test_instance_without_reference_files_has_no_load_buttons(self):
        ds = copy.deepcopy(dataset("Instance3"))
        ds.shift_requests = ds.shift_requests[:-1]               # not a known instance -> no saved solutions
        at = fresh()
        at.session_state["dataset"] = ds
        at.run()
        go(at, "⚙️ Optimization")
        keys = [b.key for b in at.button]
        self.assertNotIn("load_ip", keys)
        self.assertIn("run_ip", keys)


class TestFailurePaths(unittest.TestCase):
    """A solve that returns no solution must never crash the UI (it used to raise a TypeError)."""

    def test_no_solution_result_renders_everywhere(self):
        ds = dataset("Instance3")
        bad = OptimizationResult(status="Not Solved", objective_value=None, solve_time=1.0, assignments={},
                                 coverage_by_day_shift={}, understaffing={}, overstaffing={},
                                 shift_request_violations=[], workload_per_employee={n: 0 for n in ds.employees},
                                 benchmark_reference=1001.0, benchmark_gap_percent=None)
        at = fresh()
        at.session_state["dataset"] = ds
        at.session_state["ip_result"] = bad
        at.session_state["val_ip"] = validate_solution(ds, {})
        at.run()
        for page in ["⚙️ Optimization", "📈 Results", "🖼️ Visualizations", "⚖️ Comparison", "📅 Roster"]:
            go(at, page)
            self.assertEqual(len(at.exception), 0, page)
        go(at, "📈 Results")
        self.assertIn("No solution was found", texts(at.error))

    def test_reset_session_clears_everything(self):
        at = loaded("Instance3", with_results=True)
        at.sidebar.button[0].click().run()
        self.assertIsNone(at.session_state["dataset"])
        self.assertIsNone(at.session_state["ip_result"])


if __name__ == "__main__":
    unittest.main()
