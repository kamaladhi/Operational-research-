# Project plan (all phases completed)

| Phase | Content | Result |
|---|---|---|
| 1. Specification | Scope, requirements, architecture, mathematical model | `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `docs/MATHEMATICAL_MODEL.md`, `docs/PROJECT_PROPOSAL.md` |
| 2. Dataset | Official NRP Instance 3 (plus Instances 1, 2, 4) | `data/raw/` (Instance 3 verified byte-identical to the official file) |
| 3. Data processing | XML parser, validation, compatibility diagnostics, DataFrames | `src/parser.py`, `src/data_model.py`, `src/tables.py`, `data/processed/` |
| 4. Exploratory analysis | Dataset / staffing / nurse / request statistics and charts, on demand | `src/data_statistics.py`, `src/stat_charts.py`, Statistics page |
| 5. Optimisation | Integer Programming and Goal Programming (CBC via PuLP) | `src/integer_program.py`, `src/goal_program.py` |
| 6. Evaluation | Independent validator and evaluator, comparison metrics, benchmark gap | `src/validation.py`, `src/evaluation.py`, `src/comparison.py` |
| 7. Interface | 8-page Streamlit app, charts, downloads, saved verified solutions | `app.py`, `src/visualization.py`, `src/reporting.py` |
| 8. Quality assurance | 117 automated tests, model fingerprint, real-browser walkthrough | `tests/`, `docs/TESTING.md` |
| 9. Finalisation | Documentation, results, user guide, viva guide, final report | `README.md`, `docs/` |
