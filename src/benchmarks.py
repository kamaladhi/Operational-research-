"""
Registry of the published Nurse Rostering Benchmark instances (Curtois & Qu).

Source: https://www.schedulingbenchmarks.org/nrp/  (columns "Best known lower bound"
and "Best known solution" - saved copy of the page: data/raw/nrp.html).

For instances 1-8 the best known solution equals the best known lower bound, i.e.
the published value is the proven optimum of the benchmark model.

An uploaded XML file is matched to an instance through a structural fingerprint
(horizon, headcount, shift IDs, request/fixed-assignment/cover record counts), not
through its filename.  Files that do not match any instance simply get no benchmark
reference - the application never applies one instance's value to another's data.
"""

from typing import Dict, Optional, Tuple

from src.data_model import ParsedDataset

# name -> (best_known_solution, best_known_lower_bound)
_PUBLISHED: Dict[str, Tuple[int, int]] = {
    "Instance1": (607, 607),
    "Instance2": (828, 828),
    "Instance3": (1001, 1001),
    "Instance4": (1716, 1716),
    "Instance5": (1143, 1143),
    "Instance6": (1950, 1950),
    "Instance7": (1056, 1056),
    "Instance8": (1300, 1300),
}

# fingerprint = (days, employees, shift IDs, #ShiftOn, #ShiftOff, #fixed, #cover records)
_FINGERPRINTS: Dict[Tuple, str] = {
    (14, 8, ("D",), 21, 5, 8, 14): "Instance1",
    (14, 14, ("E", "L"), 50, 12, 14, 28): "Instance2",
    (14, 20, ("D", "E", "L"), 39, 25, 20, 42): "Instance3",
    (28, 10, ("E", "L"), 52, 19, 20, 56): "Instance4",
    (28, 16, ("E", "L"), 79, 27, 32, 56): "Instance5",
    (28, 18, ("D", "E", "L"), 87, 48, 36, 84): "Instance6",
    (28, 20, ("D", "E", "L"), 104, 64, 40, 84): "Instance7",
    (28, 30, ("D", "E", "L", "N"), 139, 86, 60, 112): "Instance8",
}


def instance_description(name: str) -> str:
    """'Instance3: 20 nurses, 14 days, 3 shift types - published optimum 1001' (from the registry)."""
    for fp, inst in _FINGERPRINTS.items():
        if inst == name:
            days, emps, shifts = fp[0], fp[1], fp[2]
            best, lower = _PUBLISHED[name]
            ref = f"published optimum {best}" if best == lower else f"best known {best} (lower bound {lower})"
            return f"{name}: {emps} nurses, {days} days, {len(shifts)} shift type(s) - {ref}"
    return name


def fingerprint(dataset: ParsedDataset) -> Tuple:
    on = sum(1 for r in dataset.shift_requests if r.is_on_request)
    off = len(dataset.shift_requests) - on
    return (
        dataset.planning_period.days,
        len(dataset.employees),
        tuple(sorted(dataset.shift_types)),
        on,
        off,
        len(dataset.fixed_assignments),
        len(dataset.cover_requirements),
    )


def identify_instance(dataset: ParsedDataset) -> Optional[str]:
    """Return 'Instance3' etc. if the dataset matches a published instance, else None."""
    return _FINGERPRINTS.get(fingerprint(dataset))


def benchmark_info(dataset: ParsedDataset) -> Optional[dict]:
    """Published reference for the dataset, or None if it is not a known instance."""
    name = identify_instance(dataset)
    if name is None:
        return None
    best, lower = _PUBLISHED[name]
    return {
        "instance": name,
        "best_known": float(best),
        "lower_bound": float(lower),
        "proven_optimal": best == lower,
    }


def benchmark_for(dataset: ParsedDataset) -> Optional[float]:
    """Best-known objective value for the dataset (None if unknown)."""
    info = benchmark_info(dataset)
    return info["best_known"] if info else None


def gap_percent(objective: Optional[float], reference: Optional[float]) -> Optional[float]:
    """(objective - reference) / reference * 100, or None if either is missing."""
    if objective is None or not reference:
        return None
    return (objective - reference) / reference * 100.0
