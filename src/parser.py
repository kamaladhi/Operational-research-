import os
import xml.etree.ElementTree as ET
from datetime import datetime
from src.data_model import (
    PlanningPeriod, ShiftType, Contract, SequenceConstraint, Workload, 
    Employee, FixedAssignment, ShiftRequest, CoverRequirement, ParsedDataset
)

def parse_xml(file_path: str) -> ParsedDataset:
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Parse Planning Period
    start_date_str = root.find("StartDate").text
    end_date_str = root.find("EndDate").text
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    days = (end_date - start_date).days + 1
    weeks = days // 7
    planning_period = PlanningPeriod(start_date_str, end_date_str, days, weeks)
    
    # Parse Shift Types
    shift_types = {}
    shift_types_elem = root.find("ShiftTypes")
    if shift_types_elem is not None:
        for shift_elem in shift_types_elem.findall("Shift"):
            shift_id = shift_elem.get("ID")
            duration_elem = shift_elem.find("Duration")
            duration = int(duration_elem.text) if duration_elem is not None else 0
            start_elem = shift_elem.find("StartTime")
            start_time = start_elem.text if start_elem is not None else ""
            label_elem = shift_elem.find("Color")
            label = label_elem.text if label_elem is not None else ""
            shift_types[shift_id] = ShiftType(id=shift_id, duration=duration, start_time=start_time, label=label)
            
    # Parse Contracts
    contracts = {}
    contracts_elem = root.find("Contracts")
    if contracts_elem is not None:
        for contract_elem in contracts_elem.findall("Contract"):
            cid = contract_elem.get("ID")
            c = Contract(id=cid)
            
            min_rest = contract_elem.find("MinRestTime")
            if min_rest is not None:
                c.min_rest_time = int(min_rest.text)
                
            for max_seq in contract_elem.findall("MaxSeq"):
                c.max_seq.append(SequenceConstraint(shift=max_seq.get("shift"), value=int(max_seq.get("value"))))
            for min_seq in contract_elem.findall("MinSeq"):
                c.min_seq.append(SequenceConstraint(shift=min_seq.get("shift"), value=int(min_seq.get("value"))))
            for max_tot in contract_elem.findall("MaxTot"):
                c.max_tot.append(SequenceConstraint(shift=max_tot.get("shift"), value=int(max_tot.get("value"))))
                
            workload_elem = contract_elem.find("Workload")
            if workload_elem is not None:
                wl = Workload()
                for tu in workload_elem.findall("TimeUnits"):
                    max_elem = tu.find("Max/Count")
                    if max_elem is not None:
                        wl.max_count = int(max_elem.text)
                    min_elem = tu.find("Min/Count")
                    if min_elem is not None:
                        wl.min_count = int(min_elem.text)
                c.workload = wl
                
            valid_shifts_elem = contract_elem.find("ValidShifts")
            if valid_shifts_elem is not None:
                shifts = valid_shifts_elem.get("shift", "")
                c.valid_shifts = [s for s in shifts.split(",") if s]
                
            patterns = contract_elem.find("Patterns/Match")
            if patterns is not None:
                max_elem = patterns.find("Max/Count")
                if max_elem is not None:
                    c.weekend_patterns_max = int(max_elem.text)
                for pat_elem in patterns.findall("Pattern"):
                    start_day = pat_elem.find("StartDay").text if pat_elem.find("StartDay") is not None else ""
                    shifts = [se.text for se in pat_elem.findall("Shift")]
                    from src.data_model import PatternEntry
                    c.weekend_patterns.append(PatternEntry(start_day, shifts))
                    
            contracts[cid] = c
            
    # Parse Employees
    employees = {}
    employees_elem = root.find("Employees")
    if employees_elem is not None:
        for emp_elem in employees_elem.findall("Employee"):
            eid = emp_elem.get("ID")
            cids = [c.text for c in emp_elem.findall("ContractID")]
            employees[eid] = Employee(id=eid, contract_ids=cids)
            
    # Parse Fixed Assignments
    fixed_assignments = []
    fixed_elem = root.find("FixedAssignments")
    if fixed_elem is not None:
        for fa in fixed_elem.findall("Employee"):
            eid = fa.find("EmployeeID").text
            assign = fa.find("Assign")
            if assign is not None:
                shift = assign.find("Shift").text
                day = int(assign.find("Day").text)
                fixed_assignments.append(FixedAssignment(eid, shift, day))
                
    # Parse Shift Requests
    shift_requests = []
    on_requests = root.find("ShiftOnRequests")
    if on_requests is not None:
        for req in on_requests.findall("ShiftOn"):
            weight = int(req.get("weight", 0))
            shift = req.find("Shift").text
            eid = req.find("EmployeeID").text
            day = int(req.find("Day").text)
            shift_requests.append(ShiftRequest(eid, day, shift, weight, True))
            
    off_requests = root.find("ShiftOffRequests")
    if off_requests is not None:
        for req in off_requests.findall("ShiftOff"):
            weight = int(req.get("weight", 0))
            shift = req.find("Shift").text
            eid = req.find("EmployeeID").text
            day = int(req.find("Day").text)
            shift_requests.append(ShiftRequest(eid, day, shift, weight, False))
            
    # Parse Cover Requirements
    cover_requirements = []
    cover_elem = root.find("CoverRequirements")
    if cover_elem is not None:
        for dsc in cover_elem.findall("DateSpecificCover"):
            day = int(dsc.find("Day").text)
            for cov in dsc.findall("Cover"):
                shift = cov.find("Shift").text
                min_elem = cov.find("Min")
                max_elem = cov.find("Max")
                min_val = int(min_elem.text) if min_elem is not None else 0
                min_wt = int(min_elem.get("weight", 0)) if min_elem is not None else 0
                max_val = int(max_elem.text) if max_elem is not None else 0
                max_wt = int(max_elem.get("weight", 0)) if max_elem is not None else 0
                cover_requirements.append(CoverRequirement(day, shift, min_val, min_wt, max_val, max_wt))
                
    dataset = ParsedDataset(
        planning_period=planning_period,
        shift_types=shift_types,
        contracts=contracts,
        employees=employees,
        fixed_assignments=fixed_assignments,
        shift_requests=shift_requests,
        cover_requirements=cover_requirements,
        warnings=_collect_warnings(root, start_date),
        source_name=os.path.basename(file_path),
    )

    dataset.validate()
    return dataset


# ---------------------------------------------------------------------------
# Compatibility diagnostics
# ---------------------------------------------------------------------------
# The IP/GP models implement the constraint families found in NRP Instances 1-8.
# Anything else in an uploaded file is reported here instead of being silently
# ignored, so the user knows when a model would not reflect the whole file.

_KNOWN_ROOT = {"StartDate", "EndDate", "ShiftTypes", "Contracts", "Employees", "FixedAssignments",
               "ShiftOnRequests", "ShiftOffRequests", "CoverRequirements"}
_KNOWN_CONTRACT = {"MinRestTime", "MaxSeq", "MinSeq", "MaxTot", "Workload", "Patterns", "ValidShifts"}


def _collect_warnings(root, start_date) -> list:
    warns = []

    unknown_root = sorted({c.tag for c in root} - _KNOWN_ROOT)
    if unknown_root:
        warns.append("Unsupported top-level section(s) ignored by the models: " + ", ".join(unknown_root))

    cover = root.find("CoverRequirements")
    if cover is not None:
        other = sorted({c.tag for c in cover} - {"DateSpecificCover"})
        if other:
            warns.append("Unsupported cover section(s) ignored (only DateSpecificCover is modelled): "
                         + ", ".join(other))

    unknown_contract, wildcard_seq, soft_marked, multi_match = set(), set(), set(), set()
    for c in root.findall("Contracts/Contract"):
        cid = c.get("ID")
        for child in c:
            if child.tag not in _KNOWN_CONTRACT:
                unknown_contract.add(child.tag)
            if child.tag in ("MaxSeq", "MinSeq", "MaxTot", "MinTot") and ("weight" in child.attrib or "on" in child.attrib):
                soft_marked.add(cid)
        for tag in ("MaxSeq", "MinSeq"):
            for el in c.findall(tag):
                shift = el.get("shift")
                supported = {"$"} if tag == "MaxSeq" else {"$", "-"}
                if shift not in supported:
                    wildcard_seq.add(f"{tag}[{shift}] in contract {cid}")
        patterns = c.find("Patterns")
        if patterns is not None and len(patterns.findall("Match")) > 1:
            multi_match.add(cid)
    if unknown_contract:
        warns.append("Unsupported contract element(s) ignored: " + ", ".join(sorted(unknown_contract)))
    if wildcard_seq:
        warns.append("Shift-specific sequence limits are not modelled (ignored): "
                     + "; ".join(sorted(wildcard_seq)))
    if soft_marked:
        warns.append("Contract limits carrying weight/on attributes are treated as HARD constraints (contracts: "
                     + ", ".join(sorted(soft_marked)) + ")")
    if multi_match:
        warns.append("Only the first <Match> of each contract's Patterns is read (contracts: "
                     + ", ".join(sorted(multi_match)) + ")")

    bad_requests = 0
    for tag in ("ShiftOnRequests/ShiftOn", "ShiftOffRequests/ShiftOff"):
        for r in root.findall(tag):
            s = r.findtext("Shift")
            if s in ("$", "-"):
                bad_requests += 1
    if bad_requests:
        warns.append(f"{bad_requests} request(s) use the '$' or '-' wildcard shift, which the models do not support.")

    if start_date.weekday() != 0:
        warns.append(f"The planning period starts on a {start_date.strftime('%A')}, but the weekend "
                     "constraint assumes the horizon starts on a Monday (Saturday = day 5).")
    return warns
