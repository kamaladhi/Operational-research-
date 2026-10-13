from dataclasses import dataclass
from typing import Dict, List, Tuple
from src.data_model import ParsedDataset
from src.integer_program import get_employee_contract_constraints, time_to_mins

@dataclass
class ValidationReport:
    is_feasible: bool
    errors: List[str]

def validate_solution(dataset: ParsedDataset, assignments: Dict[Tuple[str, int], str]) -> ValidationReport:
    errors = []
    
    employees = list(dataset.employees.keys())
    days = list(range(dataset.planning_period.days))
    shifts = list(dataset.shift_types.keys())
    
    # Pre-calculate what everyone is working
    # n, d -> shift or None
    works = {}
    for n in employees:
        for d in days:
            works[(n, d)] = assignments.get((n, d), None)
            
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        
        # 1. Single shift per day is guaranteed by dict structure of works[(n,d)] = string
        
        # 2. Valid assignments
        if c['valid_shifts']:
            for d in days:
                s = works[(n, d)]
                if s is not None and s not in c['valid_shifts']:
                    errors.append(f"Invalid shift {s} for employee {n} on day {d}")
                    
        # 3. Fixed assignments
        for fa in dataset.fixed_assignments:
            if fa.employee_id == n:
                s = works[(n, fa.day)]
                if fa.shift == '-' and s is not None:
                    errors.append(f"Employee {n} worked {s} on day {fa.day} but should have fixed day off")
                elif fa.shift != '-' and s != fa.shift:
                    errors.append(f"Employee {n} worked {s} on day {fa.day} but should have fixed shift {fa.shift}")
                    
        # 4. Workload
        workload = sum(dataset.shift_types[works[(n, d)]].duration for d in days if works[(n, d)] is not None)
        if c['max_workload'] is not None and workload > c['max_workload']:
            errors.append(f"Employee {n} workload {workload} exceeds max {c['max_workload']}")
        if c['min_workload'] is not None and workload < c['min_workload']:
            errors.append(f"Employee {n} workload {workload} below min {c['min_workload']}")
            
        # 5. Shift limits
        for s_type, max_val in c['max_tot'].items():
            count = sum(1 for d in days if works[(n, d)] == s_type)
            if count > max_val:
                errors.append(f"Employee {n} worked {count} {s_type} shifts, exceeding max {max_val}")
                
        # 6. Consecutive working days
        if c['max_seq'] is not None or (c['min_seq'] is not None and c['min_seq'] > 1):
            d = 0
            while d < len(days):
                if works[(n, d)] is not None:
                    # Find end of working block
                    block_start = d
                    while d < len(days) and works[(n, d)] is not None:
                        d += 1
                    block_len = d - block_start
                    # Only check min-seq if the block started strictly after day 0
                    # (block_start > 0 means it didn't start at the horizon boundary)
                    if c['max_seq'] is not None and block_len > c['max_seq']:
                        errors.append(f"Employee {n} working block length {block_len} exceeds max {c['max_seq']} (days {block_start}-{d-1})")
                    if c['min_seq'] is not None and c['min_seq'] > 1 and block_start > 0 and d < len(days) and block_len < c['min_seq']:
                        errors.append(f"Employee {n} working block length {block_len} below min {c['min_seq']} (days {block_start}-{d-1})")
                else:
                    d += 1
                    
        # 7. Consecutive days off
        if c['min_days_off'] is not None and c['min_days_off'] > 1:
            d = 0
            while d < len(days):
                if works[(n, d)] is None:
                    block_start = d
                    while d < len(days) and works[(n, d)] is None:
                        d += 1
                    block_len = d - block_start
                    # Only enforce min if block started after day 0 AND ends before last day
                    if block_start > 0 and d < len(days) and block_len < c['min_days_off']:
                        errors.append(f"Employee {n} rest block length {block_len} below min {c['min_days_off']} (days {block_start}-{d-1})")
                else:
                    d += 1
                
        # 8. Rest transitions
        if c['min_rest'] is not None:
            for d in range(len(days) - 1):
                s1 = works[(n, d)]
                s2 = works[(n, d + 1)]
                if s1 is not None and s2 is not None:
                    end1 = time_to_mins(dataset.shift_types[s1].start_time) + dataset.shift_types[s1].duration
                    start2 = time_to_mins(dataset.shift_types[s2].start_time) + 24 * 60
                    if start2 - end1 < c['min_rest']:
                        errors.append(f"Employee {n} rest time violation between {s1} (day {d}) and {s2} (day {d+1})")
                        
        # 9. Weekends
        if c['max_weekends'] is not None:
            num_weekends = len(days) // 7
            working_weekends = 0
            for w in range(num_weekends):
                sat = 5 + 7 * w
                sun = 6 + 7 * w
                if works[(n, sat)] is not None or works[(n, sun)] is not None:
                    working_weekends += 1
            if working_weekends > c['max_weekends']:
                errors.append(f"Employee {n} worked {working_weekends} weekends, exceeding max {c['max_weekends']}")

    return ValidationReport(
        is_feasible=len(errors) == 0,
        errors=errors
    )
