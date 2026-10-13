import os
import tempfile
import unittest

from tests.common import DATA, dataset
from src.parser import parse_xml


def _parse_text(xml_text):
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(xml_text)
        path = f.name
    try:
        return parse_xml(path)
    finally:
        os.unlink(path)


def _instance3_text():
    with open(os.path.join(DATA, "Instance3.xml"), encoding="utf-8") as f:
        return f.read()


class TestParser(unittest.TestCase):
    def test_successful_loading(self):
        self.assertIsNotNone(dataset("Instance3"))

    def test_dimensions(self):
        summary = dataset("Instance3").summary()
        self.assertEqual(summary["Number of employees"], 20)
        self.assertEqual(summary["Number of days"], 14)
        self.assertEqual(summary["Number of weeks"], 2)
        self.assertEqual(summary["Number of shift types"], 3)
        self.assertEqual(summary["Number of contracts"], 21)  # 20 contracts A-T + 'All'
        self.assertEqual(summary["Total required nurse-shifts (sum of Min cover)"], 154)

    def test_workload_parsed(self):
        contract_a = dataset("Instance3").contracts.get("A")
        self.assertIsNotNone(contract_a.workload)
        self.assertEqual(contract_a.workload.max_count, 4320)
        self.assertEqual(contract_a.workload.min_count, 3360)

    def test_requests_parsed(self):
        ds = dataset("Instance3")
        self.assertEqual(sum(1 for r in ds.shift_requests if r.is_on_request), 39)
        self.assertEqual(sum(1 for r in ds.shift_requests if not r.is_on_request), 25)

    def test_multiple_contracts(self):
        emp_a = dataset("Instance3").employees.get("A")
        self.assertEqual(sorted(emp_a.contract_ids), ["A", "All"])

    def test_other_bundled_instances_parse(self):
        expected = {"Instance1": (8, 14, 1), "Instance2": (14, 14, 2), "Instance4": (10, 28, 2)}
        for name, (emps, days, shifts) in expected.items():
            ds = dataset(name)
            self.assertEqual((len(ds.employees), ds.planning_period.days, len(ds.shift_types)), (emps, days, shifts), name)

    def test_bundled_instances_produce_no_compatibility_warnings(self):
        for name in ("Instance1", "Instance2", "Instance3", "Instance4"):
            self.assertEqual(dataset(name).warnings, [], name)

    def test_source_name_recorded(self):
        self.assertEqual(dataset("Instance3").source_name, "Instance3.xml")


class TestParserDiagnostics(unittest.TestCase):
    """Unsupported XML features must be reported, never silently ignored."""

    def test_unknown_top_level_section_is_reported(self):
        ds = _parse_text(_instance3_text().replace("<Employees>", "<SkillTypes/><Employees>", 1))
        self.assertTrue(any("SkillTypes" in w for w in ds.warnings), ds.warnings)

    def test_unsupported_cover_section_is_reported(self):
        ds = _parse_text(_instance3_text().replace("</CoverRequirements>", "<DayOfWeekCover/></CoverRequirements>", 1))
        self.assertTrue(any("DayOfWeekCover" in w for w in ds.warnings), ds.warnings)

    def test_non_monday_start_is_reported(self):
        txt = _instance3_text().replace("<StartDate>2014-01-06</StartDate>", "<StartDate>2014-01-07</StartDate>")
        ds = _parse_text(txt.replace("<EndDate>2014-01-19</EndDate>", "<EndDate>2014-01-20</EndDate>"))
        self.assertTrue(any("Monday" in w for w in ds.warnings), ds.warnings)

    def test_shift_specific_sequence_limit_is_reported(self):
        txt = _instance3_text().replace('<MaxSeq label="Max 5 consecutive shifts" value="5" shift="$"/>',
                                        '<MaxSeq label="x" value="2" shift="L"/>', 1)
        ds = _parse_text(txt)
        self.assertTrue(any("Shift-specific" in w for w in ds.warnings), ds.warnings)

    def test_invalid_xml_raises(self):
        with self.assertRaises(Exception):
            _parse_text("<NotValidXML>")

    def test_missing_employee_reference_fails_validation(self):
        txt = _instance3_text().replace("<EmployeeID>A</EmployeeID><Assign>", "<EmployeeID>ZZZ</EmployeeID><Assign>", 1)
        with self.assertRaises(ValueError):
            _parse_text(txt)


if __name__ == "__main__":
    unittest.main()
