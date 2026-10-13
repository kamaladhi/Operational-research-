from dataclasses import dataclass, field
from typing import List, Dict, Optional
import datetime

@dataclass
class PlanningPeriod:
    start_date: str
    end_date: str
    days: int
    weeks: int

@dataclass
class ShiftType:
    id: str
    duration: int
    start_time: str = ""
    label: str = ""

@dataclass
class Workload:
    max_count: Optional[int] = None
    min_count: Optional[int] = None

@dataclass
class SequenceConstraint:
    shift: str
    value: int

@dataclass
class PatternEntry:
    start_day: str
    shift_sequence: List[str]

@dataclass
class Contract:
    id: str
    min_rest_time: Optional[int] = None
    max_seq: List[SequenceConstraint] = field(default_factory=list)
    min_seq: List[SequenceConstraint] = field(default_factory=list)
    max_tot: List[SequenceConstraint] = field(default_factory=list)
    workload: Optional[Workload] = None
    valid_shifts: List[str] = field(default_factory=list)
    weekend_patterns_max: Optional[int] = None
    weekend_patterns: List[PatternEntry] = field(default_factory=list)

@dataclass
class Employee:
    id: str
    contract_ids: List[str]

@dataclass
class FixedAssignment:
    employee_id: str
    shift: str
    day: int

@dataclass
class ShiftRequest:
    employee_id: str
    day: int
    shift: str
    weight: int
    is_on_request: bool

@dataclass
class CoverRequirement:
    day: int
    shift: str
    min_nurses: int
    min_weight: int
    max_nurses: int
    max_weight: int

@dataclass
class ParsedDataset:
    planning_period: PlanningPeriod
    shift_types: Dict[str, ShiftType]
    contracts: Dict[str, Contract]
    employees: Dict[str, Employee]
    fixed_assignments: List[FixedAssignment]
    shift_requests: List[ShiftRequest]
    cover_requirements: List[CoverRequirement]
    # Parser diagnostics: XML features present in the file that the models do not use.
    warnings: List[str] = field(default_factory=list)
    source_name: str = ""

    def validate(self):
        errors = []
        # Validate employees
        if not self.employees:
            errors.append("No employees found.")
        for emp_id, emp in self.employees.items():
            for cid in emp.contract_ids:
                if cid not in self.contracts:
                    errors.append(f"Employee {emp_id} references unknown contract {cid}")
        
        # Validate shifts
        if not self.shift_types:
            errors.append("No shift types found.")
        for st_id in self.shift_types:
            if not st_id:
                errors.append("Empty shift type ID found.")
                
        valid_shift_ids = set(self.shift_types.keys())
        valid_shift_ids.add('-') # Day off shift
        valid_shift_ids.add('$') # Any shift wildcard
        
        # Validate fixed assignments
        for fa in self.fixed_assignments:
            if fa.employee_id not in self.employees:
                errors.append(f"Fixed assignment references unknown employee {fa.employee_id}")
            if fa.shift not in valid_shift_ids:
                errors.append(f"Fixed assignment references unknown shift {fa.shift}")
            if fa.day < 0 or fa.day >= self.planning_period.days:
                errors.append(f"Fixed assignment references out of bounds day {fa.day}")
                
        # Validate requests
        for req in self.shift_requests:
            if req.employee_id not in self.employees:
                errors.append(f"Request references unknown employee {req.employee_id}")
            if req.shift not in valid_shift_ids:
                errors.append(f"Request references unknown shift {req.shift}")
            if req.day < 0 or req.day >= self.planning_period.days:
                errors.append(f"Request references out of bounds day {req.day}")
                
        # Validate cover requirements
        for req in self.cover_requirements:
            if req.shift not in self.shift_types:
                errors.append(f"Cover requirement references unknown shift {req.shift}")
            if req.day < 0 or req.day >= self.planning_period.days:
                errors.append(f"Cover requirement references out of bounds day {req.day}")
        
        if errors:
            raise ValueError(f"Dataset validation failed: {'; '.join(errors)}")
        return True

    def summary(self):
        min_staff = min(c.min_nurses for c in self.cover_requirements) if self.cover_requirements else 0
        max_staff = max(c.max_nurses for c in self.cover_requirements) if self.cover_requirements else 0
        
        summary_info = {
            "Number of employees": len(self.employees),
            "Number of days": self.planning_period.days,
            "Number of weeks": self.planning_period.weeks,
            "Number of shift types": len(self.shift_types),
            "Number of contracts": len(self.contracts),
            "Number of employee-contract relationships": sum(len(e.contract_ids) for e in self.employees.values()),
            "Number of fixed assignments": len(self.fixed_assignments),
            "Number of shift-on requests": sum(1 for r in self.shift_requests if r.is_on_request),
            "Number of shift-off requests": sum(1 for r in self.shift_requests if not r.is_on_request),
            "Number of cover requirement records": len(self.cover_requirements),
            "Actual minimum staffing in requirements": min_staff,
            "Actual maximum staffing in requirements": max_staff,
            "Total required nurse-shifts (sum of Min cover)": sum(c.min_nurses for c in self.cover_requirements),
        }
        return summary_info
