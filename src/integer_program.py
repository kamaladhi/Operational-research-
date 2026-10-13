import pulp
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from src.data_model import ParsedDataset
from src.solver_utils import make_cbc_solver, interpret_cbc_status
from src.benchmarks import benchmark_for, gap_percent
import time

@dataclass
class OptimizationResult:
    status: str                               # "Optimal" (proven) | "Feasible" (not proven) | ...
    objective_value: Optional[float]
    solve_time: float
    assignments: Dict[Tuple[str, int], str]  # (employee, day) -> shift
    coverage_by_day_shift: Dict[Tuple[int, str], int]
    understaffing: Dict[Tuple[int, str], int]
    overstaffing: Dict[Tuple[int, str], int]
    shift_request_violations: List[str]
    workload_per_employee: Dict[str, int]
    benchmark_reference: Optional[float]      # published best-known value; None if instance unknown
    benchmark_gap_percent: Optional[float]
    proven_optimal: bool = False              # True only if CBC proved optimality
    time_limit: Optional[float] = None        # seconds given to the solver (None for saved runs)
    source: str = "live solve"                # "live solve" or "saved reference run"

def get_employee_contract_constraints(dataset: ParsedDataset, employee_id: str):
    emp = dataset.employees[employee_id]
    
    # Merge constraints from all contracts
    valid_shifts = set()
    first_contract = True
    
    max_tot = {}
    max_seq = None
    min_seq = None
    min_days_off = None
    min_rest = None
    max_workload = None
    min_workload = None
    max_weekends = None
    
    for cid in emp.contract_ids:
        c = dataset.contracts[cid]
        
        # valid shifts intersection
        if c.valid_shifts:
            if first_contract:
                valid_shifts = set(c.valid_shifts)
                first_contract = False
            else:
                valid_shifts = valid_shifts.intersection(set(c.valid_shifts))
                
        # max tot (take min if multiple)
        for seq in c.max_tot:
            shift = seq.shift
            if shift not in max_tot or seq.value < max_tot[shift]:
                max_tot[shift] = seq.value
                
        # sequences for '$' (any shift)
        for seq in c.max_seq:
            if seq.shift == '$':
                if max_seq is None or seq.value < max_seq:
                    max_seq = seq.value
        for seq in c.min_seq:
            if seq.shift == '$':
                if min_seq is None or seq.value > min_seq:
                    min_seq = seq.value
            elif seq.shift == '-':
                if min_days_off is None or seq.value > min_days_off:
                    min_days_off = seq.value
                    
        # rest time
        if c.min_rest_time is not None:
            if min_rest is None or c.min_rest_time > min_rest:
                min_rest = c.min_rest_time
                
        # workload
        if c.workload:
            if c.workload.max_count is not None:
                if max_workload is None or c.workload.max_count < max_workload:
                    max_workload = c.workload.max_count
            if c.workload.min_count is not None:
                if min_workload is None or c.workload.min_count > min_workload:
                    min_workload = c.workload.min_count
                    
        # weekends
        if c.weekend_patterns_max is not None:
            if max_weekends is None or c.weekend_patterns_max < max_weekends:
                max_weekends = c.weekend_patterns_max
                
    return {
        'valid_shifts': valid_shifts,
        'max_tot': max_tot,
        'max_seq': max_seq,
        'min_seq': min_seq,
        'min_days_off': min_days_off,
        'min_rest': min_rest,
        'max_workload': max_workload,
        'min_workload': min_workload,
        'max_weekends': max_weekends
    }


def time_to_mins(time_str: str) -> int:
    # "6:0" or "14:0"
    if not time_str:
        return 0
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])

def solve_integer_program(dataset: ParsedDataset, time_limit: int = 60) -> OptimizationResult:
    start_time = time.time()
    prob = pulp.LpProblem("Nurse_Rostering_IP", pulp.LpMinimize)
    
    # Employees, Days, Shifts
    employees = list(dataset.employees.keys())
    days = list(range(dataset.planning_period.days))
    shifts = list(dataset.shift_types.keys())
    
    # 3. Decision Variables
    x = pulp.LpVariable.dicts("x", [(n, d, s) for n in employees for d in days for s in shifts], 0, 1, pulp.LpBinary)
    y = pulp.LpVariable.dicts("y", [(n, d) for n in employees for d in days], 0, 1, pulp.LpBinary)
    
    # Weekends (0: days 5,6 / 1: days 12,13)
    num_weekends = dataset.planning_period.days // 7
    z = pulp.LpVariable.dicts("z", [(n, w) for n in employees for w in range(num_weekends)], 0, 1, pulp.LpBinary)
    
    # Deviations
    u = pulp.LpVariable.dicts("u", [(d, s) for d in days for s in shifts], 0, None, pulp.LpInteger)
    o = pulp.LpVariable.dicts("o", [(d, s) for d in days for s in shifts], 0, None, pulp.LpInteger)
    
    v_on = pulp.LpVariable.dicts("v_on", range(len([r for r in dataset.shift_requests if r.is_on_request])), 0, 1, pulp.LpBinary)
    v_off = pulp.LpVariable.dicts("v_off", range(len([r for r in dataset.shift_requests if not r.is_on_request])), 0, 1, pulp.LpBinary)
    
    # 4. Hard Constraints
    
    # Single shift per day & relation to y
    for n in employees:
        for d in days:
            prob += pulp.lpSum([x[n, d, s] for s in shifts]) == y[n, d], f"Y_Relation_{n}_{d}"
            prob += y[n, d] <= 1, f"SingleShift_{n}_{d}"
            
    # Valid shifts
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        valid_shifts = c['valid_shifts']
        if valid_shifts:
            for d in days:
                for s in shifts:
                    if s not in valid_shifts:
                        prob += x[n, d, s] == 0, f"InvalidShift_{n}_{d}_{s}"
                        
    # Fixed assignments
    for fa in dataset.fixed_assignments:
        n = fa.employee_id
        d = fa.day
        s = fa.shift
        if s == '-':
            prob += y[n, d] == 0, f"FixedAssignmentOff_{n}_{d}"
        else:
            if s in shifts:
                prob += x[n, d, s] == 1, f"FixedAssignmentOn_{n}_{d}_{s}"

    # Workload
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        workload = pulp.lpSum([dataset.shift_types[s].duration * x[n, d, s] for d in days for s in shifts])
        if c['max_workload'] is not None:
            prob += workload <= c['max_workload'], f"MaxWorkload_{n}"
        if c['min_workload'] is not None:
            prob += workload >= c['min_workload'], f"MinWorkload_{n}"

    # Max Total Shifts
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        for s, mx in c['max_tot'].items():
            prob += pulp.lpSum([x[n, d, s] for d in days]) <= mx, f"MaxTot_{n}_{s}"
            
    # Prohibited shift transitions (MinRestTime)
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        if c['min_rest'] is not None:
            min_rest = c['min_rest']
            for d in range(len(days) - 1):
                for s1 in shifts:
                    for s2 in shifts:
                        end1 = time_to_mins(dataset.shift_types[s1].start_time) + dataset.shift_types[s1].duration
                        start2 = time_to_mins(dataset.shift_types[s2].start_time) + 24 * 60
                        if start2 - end1 < min_rest:
                            prob += x[n, d, s1] + x[n, d+1, s2] <= 1, f"MinRest_{n}_{d}_{s1}_{s2}"
                            
    # Max Consecutive Shifts
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        if c['max_seq'] is not None:
            max_seq = c['max_seq']
            for d in range(len(days) - max_seq):
                prob += pulp.lpSum([y[n, d + k] for k in range(max_seq + 1)]) <= max_seq, f"MaxSeq_{n}_{d}"
                
    # Min Consecutive Shifts
    # Standard NRP formulation: if a working block of length < min_seq starts after day 0
    # (i.e., transitions from off to on), it must last at least min_seq days.
    # Blocks touching the horizon boundary are NOT forced (cannot know prior/future schedule).
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        if c['min_seq'] is not None and c['min_seq'] > 1:
            min_seq = c['min_seq']
            # For each day d that could be the start of a working block strictly inside the horizon:
            # y[n,d]=1 and y[n,d-1]=0 => y[n,d+1]..y[n,d+min_seq-1] must all be 1
            for d in range(1, len(days)):
                for k in range(1, min_seq):
                    if d + k < len(days):
                        prob += y[n, d] - y[n, d-1] <= y[n, d+k], f"MinSeq_{n}_{d}_k{k}"
                    
    # Min Consecutive Days Off
    # Standard NRP formulation: if a rest block of length < min_days_off starts after day 0
    # (i.e., transitions from work to rest), it must last at least min_days_off days.
    # Blocks touching the horizon boundary are NOT forced.
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        if c['min_days_off'] is not None and c['min_days_off'] > 1:
            min_do = c['min_days_off']
            # y[n,d-1]=1 and y[n,d]=0 => y[n,d+1]..y[n,d+min_do-1] must all be 0
            for d in range(1, len(days)):
                for k in range(1, min_do):
                    if d + k < len(days):
                        prob += y[n, d-1] - y[n, d] + y[n, d+k] <= 1, f"MinDaysOff_{n}_{d}_k{k}"
                    
    # Weekends
    for n in employees:
        c = get_employee_contract_constraints(dataset, n)
        for w in range(num_weekends):
            sat = 5 + 7 * w
            sun = 6 + 7 * w
            prob += z[n, w] >= y[n, sat], f"WkndSat_{n}_{w}"
            prob += z[n, w] >= y[n, sun], f"WkndSun_{n}_{w}"
            prob += z[n, w] <= y[n, sat] + y[n, sun], f"WkndSum_{n}_{w}"
            
        if c['max_weekends'] is not None:
            prob += pulp.lpSum([z[n, w] for w in range(num_weekends)]) <= c['max_weekends'], f"MaxWknd_{n}"
            
    # Cover Requirements
    obj_terms = []
    
    for cr in dataset.cover_requirements:
        d = cr.day
        s = cr.shift
        assigned = pulp.lpSum([x[n, d, s] for n in employees])
        
        # Soft constraints
        prob += assigned + u[d, s] >= cr.min_nurses, f"CoverMin_{d}_{s}"
        prob += assigned - o[d, s] <= cr.max_nurses, f"CoverMax_{d}_{s}"
        
        obj_terms.append(cr.min_weight * u[d, s])
        obj_terms.append(cr.max_weight * o[d, s])
        
    # Requests
    on_idx = 0
    off_idx = 0
    for req in dataset.shift_requests:
        n = req.employee_id
        d = req.day
        s = req.shift
        if req.is_on_request:
            prob += x[n, d, s] + v_on[on_idx] >= 1, f"ReqOn_{n}_{d}_{s}"
            obj_terms.append(req.weight * v_on[on_idx])
            on_idx += 1
        else:
            prob += x[n, d, s] - v_off[off_idx] <= 0, f"ReqOff_{n}_{d}_{s}"
            obj_terms.append(req.weight * v_off[off_idx])
            off_idx += 1
            
    prob += pulp.lpSum(obj_terms)
    
    # Solve
    solver = make_cbc_solver(time_limit)
    prob.solve(solver)

    end_time = time.time()
    # PuLP reports "Optimal" even when CBC stopped on the time limit; use the real solution status.
    status, proven_optimal = interpret_cbc_status(prob)
    obj_val = pulp.value(prob.objective) if status in ['Optimal', 'Feasible'] else None
    
    assignments = {}
    coverage = {}
    under = {}
    over = {}
    workload = {n: 0 for n in employees}
    violations = []
    
    if obj_val is not None:
        for n in employees:
            for d in days:
                for s in shifts:
                    if pulp.value(x[n, d, s]) and pulp.value(x[n, d, s]) > 0.5:
                        assignments[(n, d)] = s
                        coverage[(d, s)] = coverage.get((d, s), 0) + 1
                        workload[n] += dataset.shift_types[s].duration
        for d in days:
            for s in shifts:
                if (d, s) not in coverage:
                    coverage[(d, s)] = 0
                if pulp.value(u[d, s]) and pulp.value(u[d, s]) > 0:
                    under[(d, s)] = int(pulp.value(u[d, s]))
                if pulp.value(o[d, s]) and pulp.value(o[d, s]) > 0:
                    over[(d, s)] = int(pulp.value(o[d, s]))
                    
        on_idx = 0
        off_idx = 0
        for req in dataset.shift_requests:
            if req.is_on_request:
                if pulp.value(v_on[on_idx]) and pulp.value(v_on[on_idx]) > 0.5:
                    violations.append(f"On-request violated: {req.employee_id} {req.shift} on day {req.day}")
                on_idx += 1
            else:
                if pulp.value(v_off[off_idx]) and pulp.value(v_off[off_idx]) > 0.5:
                    violations.append(f"Off-request violated: {req.employee_id} {req.shift} on day {req.day}")
                off_idx += 1

    # Published best-known value for this instance (None if the file is not a known benchmark instance)
    reference = benchmark_for(dataset)
    gap = gap_percent(obj_val, reference)

    return OptimizationResult(
        status=status,
        objective_value=obj_val,
        solve_time=end_time - start_time,
        assignments=assignments,
        coverage_by_day_shift=coverage,
        understaffing=under,
        overstaffing=over,
        shift_request_violations=violations,
        workload_per_employee=workload,
        benchmark_reference=reference,
        benchmark_gap_percent=gap,
        proven_optimal=proven_optimal,
        time_limit=time_limit,
    )
