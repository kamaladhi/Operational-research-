"""Result tables (src/reporting.py) are consistent with the roster and with each other."""

import unittest

from src.reporting import (coverage_summary, daywise_assignments, roster_long_csv, roster_table, shiftwise_staffing,
                           style_roster, understaffed_slots, violations_table, workload_table)
from tests.common import dataset, reference


class TestReporting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = dataset("Instance3")
        cls.ip = reference("Instance3", "ip")
        cls.gp = reference("Instance3", "gp")

    def test_coverage_summary(self):
        s = coverage_summary(self.ds, self.ip)
        self.assertEqual(s["Required nurse-shifts"], 154)
        self.assertEqual(s["Assigned nurse-shifts"], 144)
        self.assertEqual(s["Understaffed nurse-shifts"], 10)
        self.assertEqual(s["Overstaffed nurse-shifts (above Max)"], 0)
        self.assertAlmostEqual(s["Coverage (%)"], 100 * 144 / 154, places=1)
        self.assertEqual(coverage_summary(self.ds, self.gp)["Understaffed nurse-shifts"], 14)

    def test_shiftwise_totals_add_up(self):
        t = shiftwise_staffing(self.ds, self.ip)
        self.assertEqual(int(t["Required"].sum()), 154)
        self.assertEqual(int(t["Assigned"].sum()), 144)
        self.assertEqual(int(t["Shortfall"].sum()), 10)

    def test_daywise_table(self):
        t = daywise_assignments(self.ds, self.ip)
        self.assertEqual(len(t), 14)
        self.assertEqual(int(t["Nurses working"].sum()), 144)
        self.assertEqual(int(t["Understaffed by"].sum()), 10)
        self.assertTrue((t["Nurses working"] + t["Nurses off"] == 20).all())

    def test_understaffed_slots_and_penalty(self):
        u = understaffed_slots(self.ds, self.ip)
        self.assertEqual(int(u["Short by"].sum()), 10)
        self.assertEqual(int(u["Penalty (XML weight x shortfall)"].sum()), 1000)

    def test_violations_match_the_result_object(self):
        for res in (self.ip, self.gp):
            self.assertEqual(len(violations_table(self.ds, res)), len(res.shift_request_violations))
        self.assertEqual(len(violations_table(self.ds, self.gp)), 0)
        self.assertEqual(int(violations_table(self.ds, self.ip)["Penalty weight"].sum()), 1)

    def test_workload_table(self):
        t = workload_table(self.ds, self.ip)
        self.assertEqual(len(t), 20)
        self.assertEqual(int(t["Shifts worked"].sum()), 144)
        self.assertEqual(int(t[["D shifts", "E shifts", "L shifts"]].sum().sum()), 144)
        self.assertTrue((t["Workload (min)"] >= t["Contract min (min)"]).all())
        self.assertTrue((t["Workload (min)"] <= t["Contract max (min)"]).all())
        self.assertTrue((t["Weekends worked"] <= 1).all())
        self.assertIn("GP target (min)", workload_table(self.ds, self.gp).columns)

    def test_roster_table_and_csv(self):
        r = roster_table(self.ds, self.ip)
        self.assertEqual(r.shape, (20, 14))
        self.assertEqual(int((r != "-").sum().sum()), 144)
        csv = roster_long_csv(self.ds, self.ip).decode()
        self.assertEqual(len(csv.strip().splitlines()), 1 + 20 * 14)
        self.assertIsNotNone(style_roster(r, self.ds).to_html())


if __name__ == "__main__":
    unittest.main()
