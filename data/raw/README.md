# Raw data - provenance

All files come from the **Nurse Rostering Benchmark** (Curtois & Qu), <https://www.schedulingbenchmarks.org/nrp/>.
They are used unmodified.

| File | Source | Content |
|---|---|---|
| `Instance3.xml` | `.../nrp/data/Instance3.ros` | **Main dataset** - 20 nurses, 14 days, 3 shift types. Byte-identical to the official file (SHA-256 starts `932bcf7d9e0804d1`) |
| `Instance1.xml` | `.../nrp/data/Instance1.ros` | 8 nurses, 14 days, 1 shift type (downloaded 2026-10-13) |
| `Instance2.xml` | `.../nrp/data/Instance2.ros` | 14 nurses, 14 days, 2 shift types (downloaded 2026-10-13) |
| `Instance4.xml` | `.../nrp/data/Instance4.ros` | 10 nurses, 28 days, 2 shift types (downloaded 2026-10-13) |
| `nrp.html` | the benchmark page | Saved copy of the instance table (best known lower bound and best known solution) |

The official files have the extension `.ros`; they are XML and are stored here with the extension `.xml` (the app accepts both).

Published values (best known lower bound = best known solution) for Instances 1-8: 607, 828, 1001, 1716, 1143, 1950, 1056, 1300
(`src/benchmarks.py`).
