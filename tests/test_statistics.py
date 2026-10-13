"""Descriptive statistics, structured tables and the pre-optimisation charts."""

import os
import tempfile
import unittest

import plotly.graph_objects as go

from src import data_statistics as ds_
from src import stat_charts as sc
from src.tables import dataset_to_tables, day_labels, export_tables, weekday_labels
from tests.common import dataset


class TestTables(unittest.TestCase):
    def test_all_tables_present_with_expected_sizes(self):
        t = dataset_to_tables(dataset("Instance3"))
        self.assertEqual(set(t), {"shifts", "contracts", "employees", "cover", "requests", "fixed_assignments"})
        self.assertEqual(len(t["shifts"]), 3)
        self.assertEqual(len(t["contracts"]), 21)
        self.assertEqual(len(t["employees"]), 20)
        self.assertEqual(len(t["cover"]), 42)
        self.assertEqual(len(t["requests"]), 64)
        self.assertEqual(len(t["fixed_assignments"]), 20)

    def test_employee_table_values_follow_the_xml(self):
        emp = dataset_to_tables(dataset("Instance3"))["employees"].set_index("Nurse")
        self.assertEqual(emp.loc["A", "Max shifts"], 9)          # 4320 / 480
        self.assertEqual(emp.loc["A", "Min shifts"], 7)          # 3360 / 480
        self.assertEqual(emp.loc["P", "Max shifts"], 4)          # 2160 / 480 rounded down
        self.assertEqual(emp.loc["P", "Min shifts"], 3)          # 1200 / 480 rounded up
        self.assertEqual(emp.loc["B", "Valid shifts"], "D, E, L")
        self.assertEqual(emp.loc["E", "Valid shifts"], "E")
        self.assertEqual(emp.loc["B", "Max total by shift"], "L<=5")

    def test_weekday_labels_start_on_monday_and_saturday_is_day_5(self):
        wd = weekday_labels(dataset("Instance3"))
        self.assertEqual(wd[0], "Mon")
        self.assertEqual((wd[5], wd[6], wd[12], wd[13]), ("Sat", "Sun", "Sat", "Sun"))
        self.assertEqual(day_labels(dataset("Instance3"))[5], "D5 Sat")

    def test_export_writes_one_csv_per_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_tables(dataset("Instance3"), tmp, prefix="I3_")
            self.assertEqual(len(paths), 6)
            self.assertTrue(all(os.path.getsize(p) > 0 for p in paths))


class TestStatistics(unittest.TestCase):
    def test_overview_numbers(self):
        m = ds_.overview_metrics(dataset("Instance3"))
        self.assertEqual(m["Dataset"]["Nurses"], 20)
        self.assertEqual(m["Dataset"]["Possible nurse-day-shift assignments"], 840)
        self.assertEqual(m["Staffing demand"]["Required nurse-shifts (sum of Min)"], 154)
        self.assertEqual(m["Staffing demand"]["Day-shift cover records"], 42)
        self.assertEqual(m["Contractual capacity"]["Total maximum shifts (all nurses)"], 155)   # 15 x 9 + 5 x 4
        self.assertEqual(m["Requests and fixed days"]["ShiftOn requests (want to work)"], 39)
        self.assertEqual(m["Requests and fixed days"]["ShiftOff requests (want to avoid)"], 25)
        self.assertEqual(m["Requests and fixed days"]["Fixed days off"], 20)

    def test_staffing_matrix_and_aggregates_are_consistent(self):
        ds = dataset("Instance3")
        mat = ds_.staffing_matrix(ds)
        self.assertEqual(mat.shape, (14, 3))
        self.assertEqual(int(mat.values.sum()), 154)
        self.assertEqual(mat.loc["D0 Mon", "E"], 2)
        by_shift = ds_.staffing_by_shift(ds)
        self.assertEqual(int(by_shift["Total required"].sum()), 154)
        by_day = ds_.staffing_by_day(ds)
        self.assertEqual(int(by_day["Total"].sum()), 154)
        self.assertAlmostEqual(by_shift["Share of demand (%)"].sum(), 100.0, delta=0.2)

    def test_eligibility_and_groups(self):
        ds = dataset("Instance3")
        el = ds_.eligibility_vs_demand(ds).set_index("Shift")
        self.assertEqual(el.loc["E", "Nurses allowed to work it"], 16)      # everyone except L, N, O, Q (valid shifts)
        self.assertEqual(int(ds_.contract_group_summary(ds)["Nurses"].sum()), 20)

    def test_request_matrix_codes(self):
        codes, text = ds_.request_matrix(dataset("Instance3"))
        self.assertEqual(codes.shape, (20, 14))
        self.assertEqual(int((codes == 1).sum().sum()), 39)
        self.assertEqual(int((codes == -1).sum().sum()), 25)
        self.assertEqual(int((codes == 2).sum().sum()), 20)
        self.assertEqual(text.loc["A", "D0 Mon"], "X")         # fixed day off
        self.assertEqual(text.loc["B", "D0 Mon"], "D")         # ShiftOn D

    def test_requests_per_nurse_totals(self):
        r = ds_.requests_per_nurse(dataset("Instance3"))
        self.assertEqual(int(r["ShiftOn requests"].sum()), 39)
        self.assertEqual(int(r["ShiftOff requests"].sum()), 25)

    def test_statistics_work_on_other_instances(self):
        for name in ("Instance1", "Instance2", "Instance4"):
            ds = dataset(name)
            self.assertEqual(int(ds_.staffing_matrix(ds).values.sum()),
                             sum(c.min_nurses for c in ds.cover_requirements))


class TestStatCharts(unittest.TestCase):
    def test_every_chart_builds_for_every_bundled_instance(self):
        charts = [sc.demand_heatmap, sc.demand_by_day_chart, sc.demand_by_shift_chart, sc.weekday_profile_chart,
                  sc.demand_vs_capacity_chart, sc.nurse_shift_limits_chart, sc.eligibility_chart,
                  sc.requests_per_nurse_chart, sc.request_heatmap, sc.request_weight_chart]
        for name in ("Instance1", "Instance2", "Instance3", "Instance4"):
            for fn in charts:
                fig = fn(dataset(name))
                self.assertIsInstance(fig, go.Figure, f"{fn.__name__}/{name}")
                self.assertGreater(len(fig.data), 0, f"{fn.__name__}/{name}")

    def test_shift_colours_come_from_the_xml(self):
        c = sc.shift_colours(dataset("Instance3"))
        self.assertEqual(c, {"D": "DeepSkyBlue", "E": "FireBrick", "L": "DarkCyan"})

    def test_heatmap_values_match_data(self):
        fig = sc.demand_heatmap(dataset("Instance3"))
        self.assertEqual(int(fig.data[0].z.sum()), 154)


if __name__ == "__main__":
    unittest.main()
