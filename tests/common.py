"""Shared helpers for the test-suite (cached datasets and saved reference results)."""

import functools
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, "data", "raw")

from src.parser import parse_xml  # noqa: E402
from src.reference_solutions import load_reference  # noqa: E402

#: Published proven-optimal values of the benchmark objective (best known = lower bound).
PUBLISHED_OPTIMUM = {"Instance1": 607.0, "Instance2": 828.0, "Instance3": 1001.0, "Instance4": 1716.0}

SLOW = os.environ.get("RUN_SLOW_TESTS") == "1"


@functools.lru_cache(maxsize=None)
def dataset(name: str = "Instance3"):
    """Parsed bundled instance (treat as read-only)."""
    return parse_xml(os.path.join(DATA, f"{name}.xml"))


@functools.lru_cache(maxsize=None)
def reference(name: str, model: str):
    """Verified saved reference result (re-validated and objective-recomputed on load)."""
    return load_reference(dataset(name), model)
