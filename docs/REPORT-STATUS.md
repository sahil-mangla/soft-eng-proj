# Report status against the UCS503L structure

Estimated by artefact completeness (a chapter written and backed by evidence = 100%).
Code is further along than the report: the simulation core is ~85% of the MVP, the
report as a whole is ~40%.

| Ch | Title | Status | Where it lives / what is missing |
| --- | --- | --- | --- |
| 1 | Introduction | Drafted (100%) | `docs/report/Chapter1-Introduction.md`, headings match 1.1–1.7 |
| 2 | Feasibility Study | Drafted (100%) | `docs/report/Chapter2-Feasibility-Study.md`, headings match 2.1–2.6 |
| 3 | SDLC Model Selection | Not written (0%) | Build followed an iterative, increment-per-step plan (`docs/BUILD-PLAN.md` Steps 0–9, v1 then v2 after evaluation). Needs 3.1–3.4 written around that real history |
| 4 | Requirements Engineering | Not written (0%) | FR/NFR can be drawn from CLAUDE.md §3, §6 and the metrics. The existing "Chapter 4" file is system design, not this |
| 5 | System Analysis | Partial (40%) | Use-case diagram exists inside `Chapter4-System-Design.md` (D6); use-case descriptions, existing/proposed system text not written |
| 6 | System Design | Partial (60%) | DFD, use case, activity, sequence, class diagrams (`Chapter4-System-Design.md`) and design sheets (`Chapter3-Design-Sheets.md`) belong here. Missing: architecture write-up, state diagram, deployment diagram, interface design (frontend mocks now exist), ER diagram (no database; say so explicitly) |
| 7 | Planning and Management | Partial (30%) | `BUILD-PLAN.md` is the WBS. Missing: Gantt chart, task allocation, risk register |
| 8 | Implementation | Code ~85%, writing 0% | Stack, modules, algorithms (shift search, hysteresis, recovery decay, queue discharge) all exist in code. Input validation (API clamping) and error handling exist; no auth (out of scope) |
| 9 | Software Testing | Partial (30%) | 69 pytest tests (unit, integration via engine runs, API). Missing: written test plan, strategy, acceptance tests, coverage numbers |
| 10 | Test Case Design | Not written (10%) | Needs EP/BVA tables (e.g. `max_hold`, `vehicles`, `recovery_cycles` ranges), state transitions (signal cycle, recovery), defect log. Real defects found and fixed so far are listed below |
| 11 | Deployment and Maintenance | Partial (20%) | README has install/run. Missing: user manual, maintenance strategy |
| 12 | Conclusion | Not written (0%) | Results exist in `RESULTS.md`; the honest finding is that corridor does not beat reactive in this model |

**Overall: about 40%**, with the heavy-evidence chapters (3, 4, 9, 10) still empty.

## Real defects already found and fixed (seed for Chapter 10.5)

| ID | Defect | Root cause | Fix | Retest |
| --- | --- | --- | --- | --- |
| BUG-01 | Ambulance slowed ~15% by itself | It counted toward edge vehicle density | M1: excluded from congestion | `test_ambulance_does_not_count_toward_congestion` |
| BUG-02 | Background delay compared different vehicle sets per mode | Metric cut off at ambulance arrival | M2: run to completion | `test_background_population_is_identical_across_modes` |
| BUG-03 | `recovery_cycles=0` raised ZeroDivisionError | Division by recovery duration | Instant reset when duration is 0 | `test_recovery_with_zero_cycles_resets_instantly` |
| BUG-04 | Same start and end crashed with IndexError | No validation | Clear `ValueError` | `test_same_start_and_end_is_rejected` |
| BUG-05 | Signal flipped between −12 s and +11 s | Shift chosen nearest to zero each tick | M4: anchored search | `test_anchor_gives_hysteresis` |
| BUG-06 | Tick-limit run printed `None` and crashed formatting | Unhandled `None` transit time | Runners report "did not arrive" | `test_tick_limit_reports_no_transit_time_instead_of_crashing` |
| BUG-07 | `max_hold` did not bound cross-traffic waiting (59 s observed against a 41 s promise) | Bound applied to the shift, not the wait; shifts could swing −15 s to +15 s | M7: guarded writes refuse a non-green stretch past the cap | `test_corridor_never_starves_a_direction_beyond_cycle_plus_hold` |
| BUG-08 | Shifts skipped yellow clearance (green straight to red) | Phase shifts applied as a discontinuous jump | M6: illegal changes refused. The new test caught a second case, a yellow that time had already used up | `test_signals_never_skip_a_yellow` |
| BUG-09 | Ambulance never re-routed | Route computed once at t=0 when every edge was uncongested | M8: recompute on entering a road, switch on a 10% gain | `test_ambulance_reroutes_when_the_road_ahead_gets_congested` |
| BUG-10 | `?slew=nan` dropped the connection; NaN passed the clamp | NaN comparisons are always false; only `ValueError` was caught | Non-finite values rejected with 400; unexpected errors return 500 JSON | `test_server_answers_nan_with_400_and_compare_with_samples` |
| BUG-11 | A run with no traffic lasted two idle recovery cycles longer in corridor mode | Recovery started for junctions that were never shifted | M9: skip unshifted junctions | `test_idle_corridor_recovery_does_not_pad_the_run` |
| BUG-12 | `python -m api.export --out sample.js` crashed after the long run | `os.makedirs('')` | Use `.` and create the directory before simulating | `test_export_accepts_a_bare_filename` |
| BUG-13 | Compare and shared URL used unsubmitted form edits | Read the live form instead of the scenario on screen | Track the run scenario; flag unrun edits | verified in browser (no frontend test harness yet) |
| BUG-14 | One unfinished run turned every aggregate and the JSON into NaN | No filtering; `json.dumps` writes bare NaN | Aggregates skip unfinished runs and count them; non-finite becomes null | `test_estimates_ignore_runs_that_never_finished`, `test_unfinished_runs_serialise_as_null_not_nan` |
| BUG-15 | CLI runners duplicated the reporting block and bypassed MetricsEvaluator | Copy and paste | `simulation/cli.py` | `test_cli_report_uses_the_shared_metrics` |
| BUG-16 | `/api/compare` spawned a process pool per request; API imported a private helper | Per-request executor; underscore name used across packages | One shared pool, at most two comparisons at once; public `metrics/serialize.py` | `test_compare_modes_returns_per_seed_samples` |
