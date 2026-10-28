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
| 9 | Software Testing | Partial (30%) | 48 pytest tests (unit, integration via engine runs, API). Missing: written test plan, strategy, acceptance tests, coverage numbers |
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
