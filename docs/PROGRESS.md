# Project progress

- [x] **Phase 1: Specification** - plan, requirements, architecture, mathematical model
- [x] **Phase 2: Dataset acquisition** - Instance 3 (+ 1, 2, 4); Instance 3 checked byte-identical to the official file
- [x] **Phase 3: Data processing** - parser, validation, compatibility warnings, structured DataFrames and CSV export
- [x] **Phase 4: Exploratory analysis** - on-demand statistics (5 groups) and 10 charts
- [x] **Phase 5: Optimisation** - Integer Programming and Goal Programming (formulations unchanged)
  - IP reaches the published optimum, proven by CBC: Instance 1 = 607, 2 = 828, **3 = 1001**, 4 = 1716
  - GP optimal with default weights: 716 / 1694 / **2000** / 2021 (not comparable with the IP objective)
- [x] **Phase 6: Evaluation and comparison** - independent validator and evaluator, component-wise comparison, GP weight-sensitivity study
- [x] **Phase 7: Interface** - 8-page Streamlit app, honest solver status, saved verified solutions, downloads
- [x] **Phase 8: Quality assurance** - 117 tests passing (incl. live solves of Instances 1-4), model-fingerprint guard, real-browser walkthrough
- [x] **Phase 9: Finalisation** - README, docs, user guide, viva guide, final report (`docs/Final_Report.docx`)
