"""
Guard: the two optimisation models must stay exactly as originally delivered.

The fingerprints below were produced by the ORIGINAL project code (before the polishing work) for
Instance 3, and the polished code was verified to generate byte-identical LP files.  If a future edit
changes a variable, a bound, a constraint or the objective of either model, these tests fail.
"""

import unittest

from tests.common import dataset
from tests.model_signature import build_models, signature

PINNED = {
    "IP": (1308, 2547, "7131d5649dfa2c0212d014a87d34a3d5dbb55d1b1d758e7fa5541d79ad0a050d"),
    "GP": (1348, 2525, "a0f8a8bc08fc161de7004a9e28dc3bf93e2b6cd96f7dc79b7806c0a21e6beae5"),
}


class TestModelsUnchanged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = build_models(dataset("Instance3"))

    def test_integer_programming_model_is_unchanged(self):
        n_vars, n_cons, digest = signature(self.models["IP"])
        self.assertEqual((n_vars, n_cons), PINNED["IP"][:2])
        self.assertEqual(digest, PINNED["IP"][2], "The Integer Programming formulation has changed.")

    def test_goal_programming_model_is_unchanged(self):
        n_vars, n_cons, digest = signature(self.models["GP"])
        self.assertEqual((n_vars, n_cons), PINNED["GP"][:2])
        self.assertEqual(digest, PINNED["GP"][2], "The Goal Programming formulation has changed.")

    def test_ip_variable_inventory(self):
        """840 x + 280 y + 40 z + 42 u + 42 o + 39 v_on + 25 v_off = 1308 variables (Instance 3)."""
        names = [v.name for v in self.models["IP"].variables()]
        counts = {p: sum(1 for n in names if n.startswith(p + "_")) for p in ("x", "y", "z", "u", "o", "v_on", "v_off")}
        self.assertEqual(counts, {"x": 840, "y": 280, "z": 40, "u": 42, "o": 42, "v_on": 39, "v_off": 25})


if __name__ == "__main__":
    unittest.main()
