# From XML to model: interpretation decisions

How the XML of Instance 3 is turned into model inputs, and the interpretation choices behind it. (The formulations
themselves: `docs/MATHEMATICAL_MODEL.md`.)

## Calendar

* 2014-01-06 to 2014-01-19 = 14 days, day 0 = Monday. Weekend w consists of day 5+7w (Saturday) and day 6+7w (Sunday). The
  parser warns if a file does not start on a Monday.

## Contracts stack

Every employee holds the generic contract `All` plus one personal contract (A-T). The constraints of **all** of an employee's
contracts apply together:

* valid shifts: **intersection** of the lists,
* MaxTot / MaxSeq / workload maximum / maximum weekends: the **smallest** value; MinSeq / workload minimum: the **largest**,
* MinRestTime (840 min) comes from `All`; sequence, workload, weekend and valid-shift rules from the personal contract.

## Minimum rest time (derived, not typed in)

For shifts s1 (today) and s2 (tomorrow): rest = (start(s2) + 24 h) - (start(s1) + duration(s1)). A pair is forbidden if rest < 840 min.
Instance 3 (E 6:00, D 9:00, L 14:00, 8 h each): Day->Early 780 min, Late->Early 480 min, Late->Day 660 min are forbidden; all others
(>= 840) are allowed.

## Soft requirements

* **Cover**: `Min` (weight 100 per missing nurse) and `Max` (weight 1 per surplus nurse) are soft. In Instance 3 Min = Max for every
  day-shift.
* **ShiftOn / ShiftOff requests**: soft, with the weight in the XML (1-3 in Instance 3).
* All contract limits in this XML carry **no weight attribute**, so they are hard constraints (the parser warns if a file marks them as soft).

## Boundary convention for minimum sequences

`MinSeq` for working days and for days off applies to blocks that **start inside** the horizon; a block that touches day 0 or the
last day is exempt, because the schedule before and after the horizon is unknown (the instances ship without history).

## Weekend pattern

The XML's `Patterns` (Saturday work with / without Sunday work, "Max 1 weekends") means a weekend counts as worked if the nurse
works Saturday or Sunday or both; each nurse may work at most one of the two weekends.

## Nothing is dropped

All parsed information is used by the models or reported: the colour (`<Color>`) is used only for charts; every other element
feeds a constraint or an objective term. Unsupported features of other files are listed as warnings (`PARSER_DOCS.md`).
