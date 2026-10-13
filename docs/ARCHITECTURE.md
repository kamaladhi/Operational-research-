# System architecture

```
XML (NRP instance)                                   data/raw/*.xml  or  user upload
   |
   v
parser.py  ->  data_model.py (ParsedDataset + warnings)  ->  tables.py (DataFrames / CSV)
   |                                   |
   |                                   +--> data_statistics.py -> stat_charts.py        (Statistics page, on demand)
   |
   +--> integer_program.py  (MODEL 1)  --+
   +--> goal_program.py     (MODEL 2)  --+--> solver_utils.py (honest CBC status)
                                          |
        validation.py (hard constraints) <+--> evaluation.py (objectives recomputed from the roster)
                                          |
                      reference_solutions.py (saved, re-verified rosters)
                                          |
        comparison.py -> reporting.py -> visualization.py -> app.py (Streamlit, 8 pages)
        benchmarks.py (published values, instance identification)
```

## Layers

| Layer | Modules | Responsibility |
|---|---|---|
| Data | `parser.py`, `data_model.py`, `tables.py` | Read the XML (never edited), validate references, report unsupported features, build DataFrames |
| Analysis | `data_statistics.py`, `stat_charts.py` | Descriptive statistics and charts of the raw data, computed on demand |
| Optimisation | `integer_program.py`, `goal_program.py`, `solver_utils.py` | The two models (CBC via PuLP) and truthful status reporting |
| Verification | `validation.py`, `evaluation.py`, `reference_solutions.py`, `benchmarks.py` | Independent hard-constraint check, objective recomputation, verified saved solutions, published reference values |
| Evaluation | `comparison.py`, `reporting.py` | Common-component comparison; coverage / day-wise / shift-wise / request / workload tables |
| Presentation | `visualization.py`, `app.py` | Solution charts and the Streamlit interface |
| Tooling | `scripts/`, `tests/` | Reproduce results, 117 automated tests, model-fingerprint guard |

## Principles

* **Models untouched, everything around them verified** - `tests/test_model_unchanged.py` pins both formulations.
* **No trust without a check** - every roster is validated; every objective is recomputed independently; saved solutions are
  re-verified on load.
* **No invented data, no fabricated numbers** - all figures come from the XML, the solver or the evaluator.
* **Solvers only on explicit request** - UI re-runs never trigger a solve.
