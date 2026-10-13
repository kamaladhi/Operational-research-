"""
Convert the bundled benchmark XML files into structured CSV tables (data/processed).

Usage (from the project root):
    python scripts/export_tables.py                       # every data/raw/Instance*.xml
    python scripts/export_tables.py Instance3             # one instance
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.parser import parse_xml  # noqa: E402
from src.tables import export_tables  # noqa: E402


def main(names):
    raw = os.path.join(ROOT, "data", "raw")
    out = os.path.join(ROOT, "data", "processed")
    names = names or sorted(f[:-4] for f in os.listdir(raw) if f.startswith("Instance") and f.endswith(".xml"))
    for name in names:
        ds = parse_xml(os.path.join(raw, name + ".xml"))
        paths = export_tables(ds, os.path.join(out, name))
        print(f"{name}: {len(paths)} tables -> data/processed/{name}/")


if __name__ == "__main__":
    main(sys.argv[1:])
