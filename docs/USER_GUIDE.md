# User guide

## Start the application

Double-click `run_app.bat` (first run installs the packages, about a minute), or run
`streamlit run app.py`. The app opens at <http://localhost:8501>. Navigation is the radio list in the left sidebar; the sidebar
also shows the session status (dataset loaded? IP / GP solved? proven optimal?) and a *Reset session* button.

## 1. Dataset

* **Bundled benchmark sample** (default): choose *Instance3* and press **Load sample**. Instances 1, 2 and 4 are also available.
* **Upload an XML file**: any NRP instance in the standard format (`.xml` or the official `.ros`).

After loading, the page tells you whether the file is a *recognised published instance* (with its best-known value), lists parser
warnings if the file uses features the models do not cover, and shows the nurses, days, shift types and four tables (shift types,
contracts, nurses, coverage requirements). The structured tables can be downloaded as a ZIP of CSV files.

## 2. Statistics (on demand)

Pick what you want to see - nothing is computed until you choose it:

* **Overview** - dataset size, demand, contractual capacity (demand = 154 nurse-shifts vs capacity 155 for Instance 3), request counts
* **Staffing demand** - heat map day x shift, demand per day (stacked by shift), distribution per shift, weekday profile, tables
* **Nurses & contracts** - each nurse's [min, max] shifts, which shifts each nurse may work vs the peak demand, types of nurse
* **Requests & fixed days off** - requests per nurse, a nurse x day request map, weight distribution
* **Data tables** - any structured table, downloadable as CSV

## 3. Model

The two models written out: variables, hard constraints, IP objective, GP goals and weights.

## 4. Optimization

Two columns - **Integer Programming** and **Goal Programming**.

* Set the **time limit**. For Instance 3 the IP needs roughly 2-3 minutes to *prove* optimality; Instances 1-2 take about a second.
  If the limit is reached first the result is labelled *feasible, not proven optimal*.
* **Run** solves live. **Load saved reference solution** loads a verified, proven-optimal solution instantly (ideal for a demonstration);
  the roster is re-validated and the objective recomputed when it loads.
* GP: open **Goal weights** to change w1-w4 (defaults 1, 1, 1, 0.5). A warning reminds you that non-default weights no longer match the documented run.

## 5. Results

For each model: status banner, objective, solve time, hard-constraint validation. IP: benchmark table (published value, gap, proof status) and objective components.
GP: the four weighted goal penalties and the weights used. Both: coverage figures and tabs for **shift-wise staffing**, **day-wise assignments**,
**understaffed slots**, **request violations** and **workload per nurse**.

## 6. Visualizations

Tabs: Coverage (required vs assigned, shortfall map), Roster (heat map, shift distribution), Workload & fairness, Requests & benchmark. Single-model charts
follow the IP / GP selector; comparison charts appear when both models have a solution.

## 7. Comparison

Run or load both models. The page compares them on status, solve time, benchmark gap (IP only), validation, coverage, requests and workload, with a trade-off
summary and a JSON download. The raw objective values are deliberately not compared.

## 8. Roster

The nurse x day roster in the shift colours of the XML (grey - = day off), the day-by-day staffing, and CSV downloads.

## Troubleshooting

| Problem | Remedy |
|---|---|
| `streamlit` not found | Use `run_app.bat`, or `python -m pip install -r requirements.txt` |
| A page says "Load a dataset first" | Go to Dataset and press *Load sample* |
| The IP stops as "Feasible, not proven optimal" | Raise the time limit (about 300 s for Instance 3) or load the saved reference solution |
| Upload rejected with "Parsing failed" | The file is not a valid NRP XML; the message names the problem |
| An unfamiliar warning on the Dataset page | The file uses XML features the models do not implement; the roster would ignore them |
