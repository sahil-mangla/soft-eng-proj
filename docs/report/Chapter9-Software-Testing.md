# Chapter 9 – Software Testing

This chapter describes how the system was tested and what the tests showed. Test cases and their individual results are in Chapter 10. All counts and percentages below come from the final run of the suite (`pytest`, `pytest-cov`, and the browser smoke script) on the committed code.

## 9.1 Test Plan

| Item | Plan |
| --- | --- |
| **Scope** | The simulation core (network, traffic, router, ETA, coordinator, recovery, engine), the metrics and sweeps, the charts, the command-line tools, the local HTTP service, and the browser interface |
| **Not tested** | Real traffic controllers or hardware (out of scope, Chapter 1.5); accounts and authentication (none exist); behaviour on operating systems other than macOS; browsers other than Chrome (the page uses standard features, but only Chrome was driven); load from many simultaneous users (a single-user tool) |
| **Approach** | Automated tests at four levels, run together in about 12 seconds (`python -m pytest`), plus a browser script for the interface |
| **Environment** | macOS (Apple silicon, 10 cores), Python 3.15.0, Chrome driven by `puppeteer-core`; random seeds fixed in every test, so results repeat |
| **Entry criteria** | The code runs; the previous suite passes |
| **Exit criteria** | All tests pass; statement coverage at least 90% (NFR-08); every functional requirement has a test (Chapter 4.2); no open defect of critical or major severity |
| **Test data** | Generated, not stored: scenarios are built in code from a seed. Boundary values come from the parameter ranges in Chapter 8.5 |
| **Defects** | Recorded with cause, correction and the test that now guards it (Chapter 10.5) |
| **Regression** | The whole suite runs after every change; every fixed defect has a test that failed before the fix |
| **Risks to testing** | A simulator can pass its tests and still be wrong about the world; the experiment in Chapter 12 and the stated limitations address that, the tests cannot |

## 9.2 Testing Objectives

1. Show that each functional requirement (FR-01 to FR-15) is met.
2. Show that the safety and fairness rules hold in **every** run, not just on average: no skipped yellow, no signal waiting beyond the bound, the same traffic in every mode.
3. Show that invalid input is refused with a clear message and never crashes the service.
4. Show that results are reproducible.
5. Find defects early, and keep each fix from coming back.
6. Measure performance, coverage and security properties and compare them with the non-functional requirements.

## 9.3 Testing Strategy

| Level | What is tested | Technique | Tool | Tests |
| --- | --- | --- | --- | --- |
| Unit | One function or class at a time | White-box: branches, boundaries, invariants | pytest | 33 |
| Integration | Modules working together through the engine | White-box and behavioural | pytest | 29 |
| System | The service over HTTP; charts; command-line tools; the sweep | Behavioural | pytest, a real HTTP server on a free port | 22 |
| Black-box | Specification-derived cases: equivalence classes, boundaries, states, use cases | Black-box | pytest, with a result-table generator | 37 |
| Browser | The interface in a real browser | Scripted use cases | `puppeteer-core`, Chrome | 19 checks |
| **Total automated tests** | | | | **121** |

Two principles shaped the tests:

- **Properties over examples.** The safety rule is tested by scanning every recorded frame of every mode and failing if any direction ever goes green to red, red to yellow or yellow to green. The wait bound is tested over several seeds at several hold values. These catch violations that a hand-picked example would miss.
- **Specification, not implementation, for black-box cases.** A black-box case states the expected result from the requirement. Where the requirement gives only a rule (for example "within the cap") the case checks the rule, not a number copied from the program's output.

## 9.4 Unit Testing

**33 unit tests** in `tests/test_network.py` (13), `tests/test_core.py` (13) and `tests/test_traffic.py` (7).

| Module | Examples of what is checked |
| --- | --- |
| Grid and signals | 25 junctions and 80 directed edges for 5 × 5; every road exists in both directions; axes are correct; each junction has its own signal; the two directions are never green together; the cycle is 46 s; coordinates scale with spacing; `nongreen_remaining` agrees with brute force for every second of three cycles |
| Shift search | Already-green returns zero; a reachable green is found within the bound; an unreachable green stays within the bound; a restricted band is honoured; a shift near the current one is preferred (hysteresis); a NaN band returns zero instead of crashing |
| Router | Prefers a faster path over a congested one; the path is connected and has the right ends |
| ETA predictor | Increases along the route; skips roads already passed; shrinks as the ambulance advances; slows with congestion |
| Coordinator | Ignores junctions beyond the look-ahead; never exceeds the maximum hold; produces a green at the predicted arrival when reachable; eased shifts change by at most the rate per tick; writes only through the supplied setter |
| Recovery | Eases back over the configured cycles and ends at exactly zero; zero cycles resets at once; a junction that was never shifted does not enter recovery |
| Vehicles and queues | Waits at red and crosses on green; leaves a queue first in, first out with a 2 s gap; the ambulance does not add to congestion; traffic is deterministic per seed; a zero arterial share leaves the traffic exactly as before; arterial vehicles drive a forward stretch of the corridor |

## 9.5 Integration Testing

**29 integration tests** in `tests/test_engine.py` (28) and `tests/test_cli.py` (1). Each runs a full simulation, so it exercises the network, traffic, router, ETA predictor, coordinator, recovery, guard and metrics together.

| Interaction | Test |
| --- | --- |
| All modes complete with the same background population | `test_every_mode_finishes_with_full_background_population`, `test_background_population_is_identical_across_modes` |
| Determinism | `test_runs_are_deterministic` |
| The ambulance cannot beat free flow; any preemption beats none | `test_transit_cannot_beat_free_flow`, `test_preemption_beats_no_preemption_for_the_ambulance` |
| Coordinator, guard and starvation tracker | `test_corridor_never_starves_a_direction_beyond_cycle_plus_hold` (2 holds × 6 seeds × 2 modes) |
| Guard and signals in every mode | `test_signals_never_skip_a_yellow` (all four modes, every frame) |
| Engine, router and congestion | `test_ambulance_reroutes_when_the_road_ahead_gets_congested`, `test_no_reroute_when_disabled_or_not_materially_better` |
| Recovery and engine | `test_signals_return_to_schedule_after_run`, `test_naive_resets_promptly_while_recovery_eases`, `test_idle_corridor_recovery_does_not_pad_the_run` |
| ETA predictor and log | `test_eta_error_shrinks_as_ambulance_nears_the_junction` |
| Frame recording for the interface | `test_frames_are_recorded_for_the_frontend` |
| Error paths | `test_same_start_and_end_is_rejected`, `test_tick_limit_reports_no_transit_time_instead_of_crashing`, `test_recovery_cycles_zero_runs` |
| Metrics and the command line | `test_estimates_ignore_runs_that_never_finished`, `test_cli_report_uses_the_shared_metrics` |

## 9.6 System Testing

**22 system tests** in `tests/test_api.py` (11) and `tests/test_viz_cli_server.py` (11), plus the **19-check browser script** `frontend/tests/smoke.mjs`.

- **Service.** A real server is started on a free port and queried with real HTTP: replay shape and JSON validity, per-mode routes, the comparison with per-seed samples, 400 for bad parameters, 500 for an internal failure, 404 for missing files and path escapes, 501 for POST, the last sweep (present and absent).
- **Charts and tools.** All charts are written and non-empty; a route that changed mid-run still plots; the demo and both run scripts report through the shared helper; the full sweep suite runs and serialises as strict JSON.
- **Browser.** The script drives the page as a user would: load, play, switch mode, open and close a junction, edit without running, compare over seeds, run the edited scenario, export CSV, switch appearance, send a bad parameter, try a markup injection, and check phone width. Results are in Chapter 10.4.

## 9.7 Acceptance Testing

Acceptance asks whether the system satisfies what was promised in Chapter 1.4 and Chapter 4. The criteria are stated here, and each is judged against measured evidence (24 seeds, 80 background vehicles, `docs/RESULTS.md`).

| Objective (Chapter 1.4) | Acceptance criterion | Evidence | Verdict |
| --- | --- | --- | --- |
| 1. Reduce ambulance transit time | Corridor mode's paired difference against no preemption is negative and its 95% interval excludes zero | −42.8 ± 8.8 s (300.4 to 257.6 s) | **Met** |
| 2a. Background delay not dramatically worse than no preemption | Under 5% worse | +0.4 ± 0.3 s of 68 s (0.6%) | **Met** |
| 2b. Background delay better than naive reactive | Paired difference against naive is negative | **+0.6 ± 0.3 s** (corridor slightly worse; recovery adds no benefit) | **Not met** |
| 3. ETA error shrinks as the ambulance approaches | Mean absolute error at arrival below the error 60 s out | 0.5 s against 6.9 s; the test asserts it | **Met** |
| 4. Cross traffic never held beyond the bound | Longest non-green wait at most (cycle − green) + max hold in every run | Worst single run equals the cap, never above it, at holds of 5, 10, 15 and 20 s | **Met** |
| 5. Automated, reproducible reporting | A command regenerates metrics, charts and tables from a seed | `python -m metrics.sweep`, `scripts/make_report_figures.py`, CSV export | **Met** |

Functional requirements: every one of FR-01 to FR-15 has at least one passing test (Chapter 4.2 gives the matrix). **Four of five objectives are met; objective 2b is not**, and Chapter 12 discusses why.
