> **Note:** this is the original project proposal, written before implementation. It describes the plan; for the final design, verified results and the corrections made along the way see `README.md`, `docs/RESULTS.md` and `docs/Final_Report.docx`.

# Operations Research Project

# Hospital Staff Scheduling and Assignment Optimization

## 1. Project Overview

This project develops an **Operations Research based decision-support
system for hospital nurse scheduling**.

The system takes a publicly available nurse rostering benchmark dataset,
analyzes the scheduling information, and uses mathematical optimization
to generate an improved nurse roster.

The main problem is:

> **How can nurses be assigned to shifts over a planning period while
> satisfying hospital staffing requirements and scheduling constraints,
> while also improving the overall quality and fairness of the roster?**

Instead of manually preparing a roster, the proposed system formulates
the scheduling problem mathematically and allows the user to select an
optimization method through an interactive interface.

The project uses two Operations Research techniques covered in the
course:

1.  **Integer Programming**
2.  **Goal Programming**

The final application will allow the user to upload the dataset, view
statistics, select an optimization method, generate an optimized roster,
and compare the resulting schedules.

------------------------------------------------------------------------

## 2. Dataset

### Dataset Name

**Nurse Rostering Benchmark Instance 3 (NRP)**

### Dataset Source

**Scheduling Benchmarks - Nurse Rostering Benchmark Instances**

Official source:

https://www.schedulingbenchmarks.org/nrp/

The benchmark collection provides nurse rostering instances in both
plain-text and XML formats. We will use the **XML version of Instance
3**.

### Instance 3 Characteristics

  Property                         Value
  ---------------------------- ---------
  Planning period                2 weeks
  Employees/Nurses                    20
  Shift types                          3
  Best known objective value        1001
  Format used                        XML

The official benchmark page lists Instance 3 as a two-week problem with
20 employees and 3 shift types. Its reported best-known solution has an
objective value of 1001.

The benchmark collection is designed for staff/nurse rostering research
and contains scheduling constraints and objectives. The benchmark
website also provides an integer-programming formulation for these nurse
rostering instances.

------------------------------------------------------------------------

## 3. Why This Dataset Was Selected

The dataset is suitable for an Operations Research project because the
problem is naturally a **resource allocation and scheduling optimization
problem**.

A hospital has:

-   A fixed number of nurses
-   A fixed scheduling period
-   Multiple shifts
-   Required staffing levels
-   Employee-specific scheduling restrictions
-   Shift transition restrictions
-   Limits on the number of shifts
-   Preferences or requests that affect roster quality

The decisions are discrete. A nurse is either assigned to a particular
shift on a particular day or is not assigned.

This makes the dataset particularly suitable for **Integer
Programming**.

It also contains multiple objectives and soft constraints, making it
suitable for **Goal Programming**.

------------------------------------------------------------------------

## 4. Problem Statement

Hospital staff scheduling is difficult because the scheduler must
satisfy several requirements at the same time.

For every day and shift, the hospital needs an appropriate number of
nurses. At the same time, individual nurses cannot simply be assigned to
arbitrary shifts because there may be restrictions on availability,
maximum workload, rest/shift sequences, and requested assignments or
days off.

A manually generated roster can therefore result in:

-   Understaffed shifts
-   Excessive workload for some nurses
-   Uneven distribution of shifts
-   Invalid shift sequences
-   Violation of employee requests
-   Poor overall roster quality

The proposed system addresses this problem using mathematical
optimization.

------------------------------------------------------------------------

## 5. Project Objectives

The main objectives are:

1.  Parse the nurse rostering XML dataset automatically.
2.  Convert the XML data into structured tables suitable for analysis.
3.  Provide descriptive statistics about the roster.
4.  Formulate the nurse scheduling problem as an Integer Programming
    model.
5.  Formulate a multi-objective version using Goal Programming.
6.  Generate optimized nurse schedules.
7.  Measure the quality of generated schedules.
8.  Compare Integer Programming and Goal Programming results.
9.  Provide the major functions through an interactive user interface.

------------------------------------------------------------------------

## 6. Overall System Architecture

``` text
             Nurse Rostering XML
                     |
                     v
              XML Data Parser
                     |
                     v
          Data Cleaning & Structuring
                     |
                     v
             Statistical Analysis
                     |
          +----------+----------+
          |                     |
          v                     v
 Integer Programming      Goal Programming
          |                     |
          v                     v
   Optimized Roster       Optimized Roster
          |                     |
          +----------+----------+
                     |
                     v
             Result Comparison
                     |
                     v
             Interactive UI
```

------------------------------------------------------------------------

## 7. XML Data Processing

The original dataset is provided in XML format.

The XML should **not be manually edited**.

Python will read the XML and extract the information required for
optimization.

A Python XML parser such as `xml.etree.ElementTree` can be used to read
the file.

The parser will identify relevant sections of the dataset, such as:

-   Employees
-   Shift types
-   Scheduling days
-   Staffing requirements
-   Employee constraints
-   Shift transition rules
-   Maximum shift limits
-   Requests/preferences
-   Objective-related information

The exact fields will be determined from the actual Instance 3 XML file.
We will not invent fields that are not present in the dataset.

After parsing, the information will be converted into Pandas DataFrames
or equivalent structured Python objects.

Example employee information:

  Employee     Maximum shifts Other restrictions
  ---------- ---------------- --------------------
  Nurse 1       Dataset value Dataset value
  Nurse 2       Dataset value Dataset value

Example shift requirement information:

  Day     Shift       Required staff
  ------- --------- ----------------
  Day 1   Shift 1      Dataset value
  Day 1   Shift 2      Dataset value
  Day 1   Shift 3      Dataset value

------------------------------------------------------------------------

## 8. Statistical Analysis

Before optimization, the application will provide a statistics
dashboard.

The purpose is to understand the dataset before constructing the
optimization model.

Possible statistics include:

### Dataset-level statistics

-   Number of nurses
-   Number of scheduling days
-   Number of shift types
-   Total possible nurse-shift assignments
-   Number of staffing requirements
-   Number of scheduling constraints
-   Number of employee requests

### Staffing statistics

-   Required staff by day
-   Required staff by shift
-   Average staffing requirement
-   Minimum staffing requirement
-   Maximum staffing requirement

### Employee statistics

-   Maximum shifts per nurse
-   Distribution of scheduling limits
-   Number of requests per nurse
-   Workload-related information

### Visualizations

The UI can include:

-   Bar chart of staffing requirements by shift
-   Heatmap of shift requirements by day
-   Nurse request distribution
-   Workload distribution
-   Shift-type distribution

These statistics provide a baseline before optimization.

------------------------------------------------------------------------

## 9. Optimization Model 1: Integer Programming

### Why Integer Programming?

Nurse scheduling involves discrete decisions.

For a particular nurse, day, and shift:

-   Assigned = 1
-   Not assigned = 0

Therefore, binary decision variables are appropriate.

Integer Programming is explicitly included in the Operations Research
course syllabus and is a natural mathematical formulation for nurse
rostering.

------------------------------------------------------------------------

## 10. Decision Variables

The main decision variable will be:

$$
x_{n,d,s} =
\begin{cases}
1 & \text{if nurse } n \text{ is assigned to shift } s \text{ on day } d \\
0 & \text{otherwise}
\end{cases}
$$

Where:

-   $n$ = nurse
-   $d$ = day
-   $s$ = shift type

For Instance 3, there are 20 nurses, 14 days, and 3 shift types, giving
a maximum of:

$$
20 \times 14 \times 3 = 840
$$

binary nurse-day-shift assignment variables before additional variables
are introduced.

This is a manageable optimization model for modern solvers.

------------------------------------------------------------------------

## 11. Integer Programming Constraints

The exact constraints will be extracted from Instance 3.

### 11.1 At Most One Shift Per Nurse Per Day

A nurse cannot work multiple shifts on the same day.

$$
\sum_s x_{n,d,s} \leq 1
$$

for every nurse $n$ and day $d$.

### 11.2 Staffing Coverage

Each shift must receive the required number of nurses.

$$
\sum_n x_{n,d,s} \geq R_{d,s}
$$

where $R_{d,s}$ is the required number of nurses for shift $s$ on day
$d$.

### 11.3 Maximum Number of Shifts

If a nurse has a maximum permitted number of shifts of a particular
type:

$$
\sum_d x_{n,d,s} \leq M_{n,s}
$$

where $M_{n,s}$ is the maximum allowed number of that shift for nurse
$n$.

### 11.4 Shift Rotation Constraints

Certain shifts may not be allowed to follow other shifts.

For example, if a night shift cannot be followed immediately by a
morning shift, the model will prevent that assignment combination.

The exact prohibited transitions will be extracted from the dataset.

### 11.5 Employee Requests

If the dataset contains requests such as a nurse requesting a particular
shift or requesting not to work a particular shift, these will be
represented in the optimization model.

Hard requests can be enforced directly.

Soft requests can be represented through penalties or Goal Programming.

------------------------------------------------------------------------

## 12. Objective of Integer Programming

The objective function will be constructed using the actual objective
structure of the benchmark.

The basic principle is:

> **Generate a feasible roster while minimizing the total penalty
> associated with undesirable scheduling decisions.**

Depending on the exact objective fields present in Instance 3, the
objective may include:

-   Staffing-related penalties
-   Preference/request penalties
-   Workload-related penalties
-   Scheduling constraint penalties

The benchmark's objective value will be used as a reference for
evaluating the quality of our generated schedule.

The reported benchmark best-known objective value for Instance 3 is
**1001**.

**Important:** 1001 is an objective score, not the number of nurses,
shifts, or assignments.

------------------------------------------------------------------------

## 13. Optimization Model 2: Goal Programming

### Why Goal Programming?

Hospital scheduling is not necessarily a single-objective problem.

A schedule can satisfy staffing requirements but still be undesirable
because:

-   Workload may be uneven
-   Employee preferences may be violated
-   Some undesirable shifts may be concentrated on a few nurses
-   Some staffing targets may be exceeded unnecessarily

Goal Programming allows multiple objectives to be considered
simultaneously.

Goal Programming is also explicitly included in the Operations Research
course syllabus.

------------------------------------------------------------------------

## 14. Goals

The exact goals will be based on information available in Instance 3.

Possible goals include:

### Goal 1: Minimize understaffing

Try to keep actual staffing as close as possible to the required
staffing level.

### Goal 2: Minimize preference violations

Try to satisfy as many employee requests as possible.

### Goal 3: Balance workload

Try to distribute the number of assigned shifts more evenly among
nurses.

### Goal 4: Reduce unnecessary overstaffing

Avoid assigning significantly more nurses than required when doing so
creates unnecessary workload.

These goals may conflict with each other.

For example, giving every nurse exactly the same workload may conflict
with individual availability or staffing requirements.

Goal Programming provides a systematic way to manage such trade-offs.

------------------------------------------------------------------------

## 15. Goal Programming Formulation

For each goal, positive and negative deviation variables can be
introduced.

For a staffing goal:

$$
ActualStaffing_{d,s} + d^-_{d,s} - d^+_{d,s}
= RequiredStaffing_{d,s}
$$

where:

-   $d^-$ = underachievement
-   $d^+$ = overachievement

The objective can then minimize weighted deviations:

$$
\min Z =
w_1\sum d^-_{staffing}
+
w_2\sum d_{preference}
+
w_3\sum d_{workload}
+
w_4\sum d^+_{overstaffing}
$$

The weights will determine the importance of each goal.

The final weights will be chosen and justified in the project rather
than being arbitrary.

------------------------------------------------------------------------

## 16. Integer Programming vs Goal Programming

  -----------------------------------------------------------------------
  Aspect                  Integer Programming     Goal Programming
  ----------------------- ----------------------- -----------------------
  Main purpose            Generate a valid        Balance multiple
                          optimized schedule      objectives

  Decision variables      Binary assignments      Binary assignments +
                                                  deviation variables

  Hard constraints        Enforced                Enforced

  Multiple objectives     Combined into an        Naturally handles
                          objective               multiple goals

  Preferences             Can be penalized        Can be represented as
                                                  goals

  Workload balance        Can be included         Can be explicitly
                                                  prioritized

  Output                  Optimized roster        Balanced
                                                  multi-objective roster
  -----------------------------------------------------------------------

The application will allow users to run both models and compare their
results.

------------------------------------------------------------------------

## 17. User Interface

A **Streamlit** web application will be used.

### Page 1: Dataset Upload

The user uploads:

`Instance3.xml`

The system will:

1.  Validate the file.
2.  Parse the XML.
3.  Extract scheduling information.
4.  Display a dataset summary.

### Page 2: Dataset Statistics

Display:

-   Number of nurses
-   Number of days
-   Number of shifts
-   Staffing requirements
-   Employee constraints
-   Requests
-   Workload-related statistics

Charts will make the information easier to understand.

### Page 3: Optimization Selection

The user can select:

-   **Integer Programming**
-   **Goal Programming**

The selected model can then be executed using a **Run Optimization**
button.

### Page 4: Optimization Results

Display:

-   Optimized nurse schedule
-   Day-wise assignments
-   Shift-wise staffing
-   Staffing coverage
-   Objective value
-   Constraint violations
-   Workload distribution
-   Preference satisfaction where applicable

------------------------------------------------------------------------

## 18. Example Output

The application can display a schedule in a table such as:

  Nurse     Mon       Tue       Wed       Thu       Fri     Sat       Sun
  --------- --------- --------- --------- --------- ------- --------- ---------
  Nurse 1   Morning   Off       Night     Morning   Off     Evening   Off
  Nurse 2   Off       Evening   Morning   Off       Night   Off       Morning
  Nurse 3   Night     Off       Evening   Morning   Off     Morning   Off

The actual values will be generated from the dataset and optimization
model.

------------------------------------------------------------------------

## 19. Result Metrics

The application will calculate meaningful metrics such as:

### Staffing Coverage

$$
Coverage = \frac{Actual\ Staff}{Required\ Staff}
$$

### Understaffing

Difference between required and assigned staff where applicable.

### Workload

Number of shifts assigned to each nurse.

### Workload Imbalance

Difference between the most-loaded and least-loaded nurses, or another
clearly defined balance metric.

### Preference Satisfaction

Percentage or number of requests successfully satisfied, when
applicable.

### Objective Value

The objective value produced by the optimization solver.

### Computation Time

Time required to solve each model.

------------------------------------------------------------------------

## 20. Comparison Dashboard

The system will provide a direct comparison.

  Metric                    Integer Programming   Goal Programming
  ----------------------- --------------------- ------------------
  Staffing violations          Generated result   Generated result
  Preference violations        Generated result   Generated result
  Workload imbalance           Generated result   Generated result
  Objective value              Generated result   Generated result
  Solver time                  Generated result   Generated result

The actual numbers will only be reported after running the models.

**No numerical results should be fabricated.**

------------------------------------------------------------------------

## 21. Benchmark Validation

The Nurse Rostering Benchmark provides a **best-known objective value**
for each instance.

For Instance 3, the listed best-known objective value is:

**1001**

After generating our solution, we can compare our objective value with
this benchmark.

For a minimization objective:

$$
Gap(\%) =
\frac{OurObjective - BestKnownObjective}
{BestKnownObjective}
\times 100
$$

A smaller non-negative gap indicates a solution closer to the benchmark
reference.

The benchmark value will be treated as a reference rather than
automatically claiming that our model is optimal.

------------------------------------------------------------------------

## 22. Technology Stack

### Programming

**Python**

### Data Processing

-   Pandas
-   NumPy
-   Python XML parser (`xml.etree.ElementTree`)

### Optimization

One of:

-   PuLP
-   OR-Tools
-   Gurobi, if an appropriate academic license is available

For accessibility, **PuLP or OR-Tools** will be preferred.

### Interface

**Streamlit**

### Visualization

-   Matplotlib
-   Plotly

Machine learning is **not necessary** for the core project. The project
is primarily an Operations Research optimization system.

------------------------------------------------------------------------

## 23. Complete Methodology

### Step 1: Dataset Acquisition

Download the official XML version of Nurse Rostering Benchmark Instance
3.

### Step 2: XML Parsing

Read the XML file using Python.

### Step 3: Data Extraction

Extract employees, days, shifts, staffing requirements, constraints,
requests, and objective information.

### Step 4: Data Structuring

Convert the XML information into Pandas DataFrames and Python data
structures.

### Step 5: Exploratory Analysis

Generate statistics and visualizations.

### Step 6: Mathematical Formulation

Define decision variables, constraints, and objective functions.

### Step 7: Integer Programming

Solve the scheduling problem using binary assignment variables.

### Step 8: Goal Programming

Introduce deviation variables and multiple scheduling goals.

### Step 9: Optimization

Run the selected model using an optimization solver.

### Step 10: Evaluation

Calculate:

-   Staffing coverage
-   Violations
-   Workload balance
-   Preference satisfaction
-   Objective value
-   Solver time

### Step 11: Comparison

Compare Integer Programming and Goal Programming.

### Step 12: Visualization

Display the optimized roster and performance metrics.

### Step 13: User Interface

Integrate the workflow into Streamlit.

------------------------------------------------------------------------

## 24. Why This Is an Operations Research Project

The project is fundamentally based on Operations Research rather than
machine learning.

The core components are:

-   Decision variables
-   Objective functions
-   Constraints
-   Integer Programming
-   Goal Programming
-   Resource allocation
-   Scheduling
-   Multi-objective optimization
-   Quantitative decision support

The system uses mathematical optimization to make scheduling decisions.

------------------------------------------------------------------------

## 25. Expected Benefits

The proposed system can help a hospital scheduler:

1.  Generate schedules faster.
2.  Satisfy staffing requirements systematically.
3.  Reduce scheduling violations.
4.  Balance employee workload.
5.  Improve satisfaction of employee requests.
6.  Compare different optimization strategies.
7.  Make scheduling decisions transparent and explainable.

------------------------------------------------------------------------

## 26. Limitations

The benchmark is a research benchmark rather than live hospital
operational data.

Therefore:

-   It does not represent every real-world hospital rule.
-   The dataset has a fixed planning horizon.
-   The number of nurses and shifts is limited.
-   Real hospitals may have additional skills, departments, leave
    policies, emergency requirements, and legal regulations.
-   The benchmark objective may not represent every hospital's
    managerial priorities.

The system should therefore be presented as a **decision-support and
optimization prototype**, not as a production hospital scheduling
system.

------------------------------------------------------------------------

## 27. Future Scope

The system can later be extended to:

-   Multi-department hospital scheduling
-   Nurse skill matching
-   Emergency staffing
-   Larger hospital datasets
-   Leave and vacation integration
-   Real-time schedule changes
-   Staff preference learning
-   Multi-ward scheduling
-   Fairness-aware optimization
-   Robust scheduling under uncertain demand
-   Integration with hospital management systems

------------------------------------------------------------------------

## 28. Expected Final Deliverables

### 1. Dataset

Official NRP Instance 3 XML file.

### 2. Data Processing Module

XML parser and structured dataset generation.

### 3. Statistics Module

Interactive statistical analysis and visualizations.

### 4. Integer Programming Module

Mathematical nurse assignment and scheduling model.

### 5. Goal Programming Module

Multi-objective scheduling model.

### 6. Comparison Module

Comparison of both optimization methods.

### 7. Interactive UI

Streamlit-based application.

### 8. Final Report/PPT

Including:

-   Problem background
-   Dataset
-   Mathematical formulation
-   Methodology
-   Optimization techniques
-   Results
-   Comparison
-   Limitations
-   Future scope

------------------------------------------------------------------------

## 29. Final Project Summary

The proposed project is a **Hospital Staff Scheduling and Assignment
Optimization System** based on Nurse Rostering Benchmark Instance 3.

The system will convert the XML benchmark data into a structured
representation, analyze scheduling requirements, and formulate the nurse
rostering problem as an Integer Programming model.

A second Goal Programming model will be developed to handle multiple
competing scheduling objectives such as staffing coverage, workload
balance, and preference satisfaction.

Both models will be integrated into an interactive Streamlit
application. Users will be able to upload the dataset, inspect
statistics, select an optimization method, generate a schedule, and
compare the resulting solutions.

The project therefore combines **data processing, mathematical modeling,
optimization, multi-objective decision making, and interactive
visualization** while remaining aligned with the Operations Research
course syllabus.

------------------------------------------------------------------------

## 30. Official References

1.  Nurse Rostering Benchmark Instances\
    https://www.schedulingbenchmarks.org/nrp/

2.  Nurse Rostering Benchmark Instance 3\
    Available through the official NRP benchmark page above.

3.  Strandmark, P., Qu, Y., and Curtois, T.\
    *First-order linear programming in a column generation-based
    heuristic approach to the nurse rostering problem.* Computers &
    Operations Research, 2020.

4.  Rahimian, E., Akartunalı, K., and Levine, J.\
    *A hybrid integer programming and variable neighbourhood search
    algorithm to solve nurse rostering problems.* European Journal of
    Operational Research, 2017.

