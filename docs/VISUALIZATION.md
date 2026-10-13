# Visualization

Two modules, both returning Plotly `Figure` objects rendered with `st.plotly_chart`:

* [`src/stat_charts.py`](../src/stat_charts.py) - **before optimisation**, from the raw data (Statistics page)
* [`src/visualization.py`](../src/visualization.py) - **after optimisation**, from solutions (Visualizations / Results pages)

Shift colours come from the XML's own `<Color>` elements (Instance 3: E = FireBrick, D = DeepSkyBlue, L = DarkCyan), so a shift has
the same colour in every chart and in the roster table.

## Statistics charts (`stat_charts.py`)

| Function | Shows |
|---|---|
| `demand_vs_capacity_chart` | Required nurse-shifts against the sum of contractual min / max shifts |
| `demand_heatmap` | Required nurses for every day x shift |
| `demand_by_day_chart` | Daily requirement stacked by shift |
| `demand_by_shift_chart` | Box plot of the daily requirement per shift (every day shown) |
| `weekday_profile_chart` | Average total requirement by weekday |
| `nurse_shift_limits_chart` | Each nurse's contractual [min, max] shifts (floating bars) |
| `eligibility_chart` | Nurses allowed to work each shift vs its peak demand |
| `requests_per_nurse_chart` | ShiftOn / ShiftOff requests and fixed days off per nurse |
| `request_heatmap` | Nurse x day map: green ShiftOn, red ShiftOff, grey X fixed day off |
| `request_weight_chart` | Distribution of request penalty weights |

## Solution charts (`visualization.py`)

| Function | Shows |
|---|---|
| `create_coverage_chart` | Required vs assigned nurses for each day-shift |
| `create_shortfall_heatmap` | Day x shift map of assigned - required (red = understaffed) |
| `create_roster_heatmap` | Nurse x day roster in shift colours, shift letter in each cell, blank = day off |
| `create_ip_breakdown_chart` / `create_gp_breakdown_chart` | Components of **one** model's objective (not comparable across models) |
| `create_ip_gp_coverage_chart` | Aggregate under-/overstaffing, IP vs GP |
| `create_workload_chart` | Minutes worked per nurse, IP vs GP |
| `create_fairness_chart` | Workload range, standard deviation, Jain's index |
| `create_request_chart` | ShiftOn / ShiftOff violations, IP vs GP |
| `create_shift_distribution_chart` | Number of E / D / L shifts assigned (shift types read from the rosters) |
| `create_benchmark_chart` | IP objective vs the published best-known value; states whether the IP solution is proven optimal. **The GP objective is deliberately never shown here.** Without a published reference the chart shows the IP objective only |

## Design principles

1. **Actual data only** - every chart is computed from the parsed dataset / result objects; nothing hard-coded.
2. **Benchmark integrity** - only the IP is plotted against the benchmark.
3. **Readable without a legend** - roster cells carry the shift letter; colours are fixed per shift.
4. Charts were rendered and inspected visually in a real browser during development; `tests/test_statistics.py` and
   `tests/test_visualization.py` check their content (e.g. the heat-map totals equal the data, the shortfall map sums to the
   solution's understaffing).
