# Streamlit application (`app.py`)

Run: `run_app.bat` or `streamlit run app.py` (needs `pip install -r requirements.txt`).

## Pages

| Page | What the user does | Notes |
|---|---|---|
| 📁 **Dataset** | Upload an NRP file (`.xml` / `.ros`) **or** load a bundled sample (Instances 1-4) | Parsed automatically, never edited. Shows whether the file is a **recognised published instance** (and its best-known value), **parser warnings** for unsupported XML features, key counts, shift/contract/nurse/cover tables, ZIP download of the structured tables |
| 📊 **Statistics** | Chooses which statistics to generate: *Overview*, *Staffing demand*, *Nurses & contracts*, *Requests & fixed days off*, *Data tables* | 10 charts + tables + CSV downloads, all computed from the XML only (demand vs contractual capacity, demand heat map, demand per day / shift, weekday profile, per-nurse shift limits, shift eligibility vs peak demand, requests per nurse, request map, weight distribution) |
| 📘 **Model** | Reads the two models | Sets, variables, hard constraints, IP objective, GP goals and weights (LaTeX), including the honest reading of the weights |
| ⚙️ **Optimization** | Runs **Integer Programming** and/or **Goal Programming** (separate *Run* buttons), sets time limits, optionally edits the GP weights, or **loads a saved verified solution** | Status banner distinguishes *proven optimal* from *feasible, not proven*; non-default GP weights trigger a warning |
| 📈 **Results** | Inspects each model | Status, objective, solve time, hard-constraint validation, benchmark gap (IP), objective components, **staffing coverage**, **shift-wise staffing**, **day-wise assignments**, understaffed slots, request violations, workload per nurse |
| 🖼️ **Visualizations** | Views solution charts | Coverage, shortfall map, roster heat map, shift distribution, workload and fairness, request violations, benchmark indicator |
| ⚖️ **Comparison** | Compares IP and GP | Overview (status, source, time, gap, validation), coverage, requests, workload, trade-off summary, JSON download |
| 📅 **Roster** | Reads the roster | Nurse x day table in the XML shift colours, per-day staffing, CSV downloads (long and nurse x day) |

## Design rules

* **Solvers run only on a button click** - never on a Streamlit re-run. Results are kept in `st.session_state`
  (`dataset`, `ip_result`, `gp_result`, `val_ip`, `val_gp`, `comparison`) and cleared when a new dataset is loaded.
* **Nothing is hard-coded.** Every displayed figure comes from the solver, from the independent evaluator, or from the XML. The
  benchmark reference is looked up for the *loaded* instance (`src/benchmarks.py`); for an unknown file no reference is shown.
* **Honest statuses.** "Optimal" appears only when CBC proved optimality. A solve that returns nothing is reported as an error
  and every page still renders (a previous version crashed here).
* **Saved solutions are verified on load**: the roster is re-validated against all hard constraints and the objective is
  recomputed; a mismatch raises an error instead of displaying numbers. They are labelled "saved reference run".
* **GP weights** default to the documented values (1, 1, 1, 0.5); changing them only affects the GP run you start.
* Streamlit-version compatibility: width handling is wrapped in one helper (`STRETCH`) so the app runs on current and older versions.

## Typical demo (2 minutes)

Dataset -> *Load sample* -> Statistics (open two panels) -> Optimization -> *Load saved reference solution* (IP and GP) ->
Results -> Comparison -> Roster. For a live solve use Instance 1 or 2 (about 1 second) or set the Instance 3 IP limit to 300 s.

## Known limits

* A live Instance 3 IP solve blocks the browser tab for about 3 minutes (single-threaded CBC); use the saved solution for demos.
* Session state is in memory only: closing the tab discards results (the downloads are the persistence mechanism).
* No authentication, database or deployment configuration is included.
