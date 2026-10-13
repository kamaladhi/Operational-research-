# Parser and structured data

## Architecture

[`src/parser.py`](../src/parser.py) reads an NRP XML file with `xml.etree.ElementTree` into the dataclasses of
[`src/data_model.py`](../src/data_model.py); [`src/tables.py`](../src/tables.py) turns those into Pandas DataFrames / CSV files.
The XML is never edited.

| Dataclass | Source in the XML |
|---|---|
| `PlanningPeriod` | `StartDate`, `EndDate` (days and weeks computed) |
| `ShiftType` | `ShiftTypes/Shift` - ID, start time, duration, colour |
| `Contract` | `Contracts/Contract` - `MinRestTime`, `MaxSeq`, `MinSeq`, `MaxTot`, `Workload`, `Patterns` (max working weekends), `ValidShifts` |
| `Employee` | `Employees/Employee` - IDs of **all** its contracts (constraints of all contracts apply together) |
| `FixedAssignment` | `FixedAssignments` - a day off (`-`) or fixed shift |
| `ShiftRequest` | `ShiftOnRequests/ShiftOn` and `ShiftOffRequests/ShiftOff` - nurse, day, shift, weight |
| `CoverRequirement` | `CoverRequirements/DateSpecificCover/Cover` - Min/Max nurses and their penalty weights |

`ParsedDataset.validate()` runs right after parsing: referential integrity (employees -> contracts, requests / fixed
assignments -> employees, valid days and shifts) with all problems collected into one `ValueError`.

## Structured tables (DataFrames)

`dataset_to_tables(dataset)` returns six tables - `shifts`, `contracts`, `employees` (one row per nurse with the *merged* limits
and counts of requests / fixed days off), `cover`, `requests`, `fixed_assignments`. They feed the Statistics page, the downloads
and `data/processed/<Instance>/*.csv` (`python scripts/export_tables.py`).

## Compatibility diagnostics

The models implement the constraint families present in NRP Instances 1-8. Anything else in an uploaded file is **reported, not
silently ignored** (`dataset.warnings`, shown on the Dataset page):

* unknown top-level sections, unsupported cover sections (e.g. `DayOfWeekCover`), unknown contract elements,
* shift-specific `MaxSeq` / `MinSeq` limits (only the any-shift `$` and days-off `-` variants are modelled),
* contract limits carrying `weight` / `on` attributes (treated as hard),
* more than one `<Match>` in a contract's `Patterns` (only the first is read),
* requests using the `$` / `-` wildcard shift,
* a planning period that does not start on a Monday (the weekend constraint assumes Saturday = day 5).

All eight official instances (1-8) parse without warnings.

## Instance identification

`src/benchmarks.py` matches a parsed file to a published instance through a structural fingerprint (days, nurses, shift IDs,
numbers of ShiftOn / ShiftOff requests, fixed assignments and cover records) - not through the filename - so the benchmark
gap is only ever shown against the right instance.

## Limits

* No validation against `SchedulingPeriod-3.0.xsd`.
* Only the weekend pattern family (Saturday/Sunday, "max N working weekends") is read from `Patterns`.
* Parsing is not hardened against hostile XML (entity expansion); the app is meant for benchmark files.
