# Dataset Schema: Instance 3

## 1. General Problem Information
- **Number of employees:** 20 (Employees A through T)
- **Number of days:** 14 days (0 through 13)
- **Number of weeks:** 2 weeks
- **Number of shift types:** 3 (E, D, L)
- **Planning period:** 2014-01-06 to 2014-01-19
- **Metadata:** 
  - root element `<SchedulingPeriod>`
  - `xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"`
  - `xsi:noNamespaceSchemaLocation="SchedulingPeriod-3.0.xsd"`

## 2. SECTION_STAFF (`Employees`)
Documenting fields for `<Employee>`:
- **XML field:** `Employee` (Element) / `ID` (Attribute)
  - **Meaning:** Unique identifier for the employee.
  - **Data Type:** String
  - **Example Value:** `A`
  - **Relevant to optimization:** Yes
- **XML field:** `ContractID` (Element)
  - **Meaning:** The contract(s) assigned to this employee. An employee can have multiple contracts (e.g., "All" and "A").
  - **Data Type:** String
  - **Example Value:** `All`
  - **Relevant to optimization:** Yes

## 3. SECTION_SHIFTS (`ShiftTypes`)
Documenting fields for `<Shift>`:
- **XML field:** `Shift` (Element) / `ID` (Attribute)
  - **Meaning:** Unique identifier for the shift type.
  - **Data Type:** String
  - **Example Value:** `E`
  - **Relevant to optimization:** Yes
- **XML field:** `Color` (Element)
  - **Meaning:** Color code for visualization purposes.
  - **Data Type:** String
  - **Example Value:** `FireBrick`
  - **Relevant to optimization:** No
- **XML field:** `StartTime` (Element)
  - **Meaning:** The starting time of the shift.
  - **Data Type:** String
  - **Example Value:** `6:0`
  - **Relevant to optimization:** No (Optimization primarily uses shift sequence constraints rather than actual time)
- **XML field:** `Duration` (Element)
  - **Meaning:** Length of the shift in minutes.
  - **Data Type:** Integer
  - **Example Value:** `480`
  - **Relevant to optimization:** Yes (Used for calculating workload constraints)

## 4. SECTION_COVER (`CoverRequirements`)
Documenting fields for `<DateSpecificCover>` and `<Cover>`:
- **XML field:** `Day` (Element)
  - **Meaning:** Integer index of the day in the planning period (0-indexed).
  - **Data Type:** Integer
  - **Example Value:** `0`
  - **Relevant to optimization:** Yes
- **XML field:** `Cover/Shift` (Element)
  - **Meaning:** The shift type for the requirement.
  - **Data Type:** String
  - **Example Value:** `E`
  - **Relevant to optimization:** Yes
- **XML field:** `Min` (Element) / `weight` (Attribute)
  - **Meaning:** Minimum number of nurses required for this shift on this day, and the penalty weight for understaffing.
  - **Data Type:** Integer (Value and Attribute)
  - **Example Value:** Value: `2`, Attribute `weight`: `100`
  - **Relevant to optimization:** Yes
- **XML field:** `Max` (Element) / `weight` (Attribute)
  - **Meaning:** Maximum number of nurses permitted, and the penalty weight for overstaffing.
  - **Data Type:** Integer (Value and Attribute)
  - **Example Value:** Value: `2`, Attribute `weight`: `1`
  - **Relevant to optimization:** Yes

## 5. SECTION_DAYS_OFF (`FixedAssignments`)
There is no "DaysOff" section, but there is `<FixedAssignments>` which explicitly assigns a "day off" shift (`-`).
- **XML field:** `EmployeeID` (Element)
  - **Meaning:** Identifier of the employee receiving the fixed assignment.
  - **Data Type:** String
  - **Example Value:** `A`
  - **Relevant to optimization:** Yes
- **XML field:** `Assign/Shift` (Element)
  - **Meaning:** The shift type to assign. `-` represents a day off.
  - **Data Type:** String
  - **Example Value:** `-`
  - **Relevant to optimization:** Yes
- **XML field:** `Assign/Day` (Element)
  - **Meaning:** The day index for the fixed assignment.
  - **Data Type:** Integer
  - **Example Value:** `0`
  - **Relevant to optimization:** Yes

## 6. SECTION_SHIFT_ON_REQUESTS (`ShiftOnRequests`)
Documenting fields for `<ShiftOn>`:
- **XML field:** `ShiftOn` (Element) / `weight` (Attribute)
  - **Meaning:** Penalty weight if the request to work this shift is NOT satisfied.
  - **Data Type:** Integer
  - **Example Value:** `1`
  - **Relevant to optimization:** Yes
- **XML field:** `Shift` (Element)
  - **Meaning:** The requested shift type.
  - **Data Type:** String
  - **Example Value:** `D`
  - **Relevant to optimization:** Yes
- **XML field:** `EmployeeID` (Element)
  - **Meaning:** The employee making the request.
  - **Data Type:** String
  - **Example Value:** `B`
  - **Relevant to optimization:** Yes
- **XML field:** `Day` (Element)
  - **Meaning:** The day index of the request.
  - **Data Type:** Integer
  - **Example Value:** `0`
  - **Relevant to optimization:** Yes

## 7. SECTION_SHIFT_OFF_REQUESTS (`ShiftOffRequests`)
Documenting fields for `<ShiftOff>`:
- **XML field:** `ShiftOff` (Element) / `weight` (Attribute)
  - **Meaning:** Penalty weight if the request NOT to work this shift is violated.
  - **Data Type:** Integer
  - **Example Value:** `2`
  - **Relevant to optimization:** Yes
- **XML field:** `Shift` (Element)
  - **Meaning:** The shift type requested off.
  - **Data Type:** String
  - **Example Value:** `E`
  - **Relevant to optimization:** Yes
- **XML field:** `EmployeeID` (Element)
  - **Meaning:** The employee making the request.
  - **Data Type:** String
  - **Example Value:** `A`
  - **Relevant to optimization:** Yes
- **XML field:** `Day` (Element)
  - **Meaning:** The day index of the request.
  - **Data Type:** Integer
  - **Example Value:** `9`
  - **Relevant to optimization:** Yes

## 8. Other Sections (`Contracts`)
The XML uses a generic `<Contracts>` section to define complex constraints.
- **XML field:** `Contract` (Element) / `ID` (Attribute)
  - **Meaning:** Contract identifier referenced by Employees.
  - **Data Type:** String
  - **Example Value:** `A`
  - **Relevant to optimization:** Yes
- **XML field:** `MinRestTime` (Element)
  - **Meaning:** Minimum rest minutes required after a shift.
  - **Data Type:** Integer
  - **Example Value:** `840`
  - **Relevant to optimization:** Yes
- **XML field:** `MaxSeq` / `MinSeq` (Element) / `shift` (Attribute) / `value` (Attribute)
  - **Meaning:** Maximum or minimum consecutive shifts. The `shift` attribute specifies the shift type (`$` means any shift, `-` means days off).
  - **Data Type:** Integer (`value`), String (`shift`)
  - **Example Value:** `value="5" shift="$"`
  - **Relevant to optimization:** Yes
- **XML field:** `MaxTot` (Element) / `shift` (Attribute) / `value` (Attribute)
  - **Meaning:** Maximum total shifts of a specific type.
  - **Data Type:** Integer, String
  - **Example Value:** `value="5" shift="L"`
  - **Relevant to optimization:** Yes
- **XML field:** `Workload/TimeUnits/Max/Count` and `Min/Count` (Elements)
  - **Meaning:** Maximum and minimum total workload in minutes.
  - **Data Type:** Integer
  - **Example Value:** `4320`
  - **Relevant to optimization:** Yes
- **XML field:** `Patterns/Match` (Elements)
  - **Meaning:** Defines forbidden or restricted shift patterns (e.g., maximum of 1 working weekend).
  - **Data Type:** Complex XML Structure
  - **Relevant to optimization:** Yes
- **XML field:** `ValidShifts` (Element) / `shift` (Attribute)
  - **Meaning:** Comma-separated list of allowed shifts for this contract.
  - **Data Type:** String
  - **Example Value:** `E,D,`
  - **Relevant to optimization:** Yes
