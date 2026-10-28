# Chapter 10 – Test Case Design and Management

Black-box cases are derived from the requirements, not from the code, using four techniques. Every table below was produced by **executing** the cases (`python -m scripts.blackbox_report`, which writes `docs/report/generated/blackbox-results.md`); the *Actual* column is what the system returned. The same cases run in the test suite (`tests/test_blackbox.py`), so a regression fails a test.

Case IDs: TC for black-box cases, ST for browser checks, BUG for defects. Requirement IDs are from Chapter 4.

## 10.1 Equivalence Partitioning

The input space of each parameter is split into classes the system should treat alike: *valid in range*, *below range*, *above range*, *empty*, *non-numeric text* and *non-finite*. One representative per class is tested. Shown for the `vehicles` parameter and the signal-shift parameters.

| TC ID | Requirement | Case | Input | Expected | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-01 | FR-15 | Valid in-range value | `vehicles=80` | accepted as 80 | accepted as 80 | Pass |
| TC-02 | FR-15 | Below the valid range is clamped | `vehicles=-5` | accepted as 0 | accepted as 0 | Pass |
| TC-03 | FR-15 | Above the valid range is clamped | `vehicles=1000` | accepted as 400 | accepted as 400 | Pass |
| TC-04 | FR-15 | Non-numeric text is rejected | `vehicles=abc` | rejected (400): vehicles must be a number | rejected (400): vehicles must be a number | Pass |
| TC-05 | FR-15 | Empty value uses the default | `vehicles=` | accepted as 80 | accepted as 80 | Pass |
| TC-06 | FR-15 | NaN is rejected, not clamped | `slew=nan` | rejected (400): slew must be a finite number | rejected (400): slew must be a finite number | Pass |
| TC-07 | FR-15 | Infinity is rejected | `horizon=inf` | rejected (400): horizon must be a finite number | rejected (400): horizon must be a finite number | Pass |
| TC-08 | FR-15 | Eased shifts: valid rate | `slew=0.25` | accepted as 0.25 | accepted as 0.25 | Pass |
| TC-09 | FR-15 | Eased shifts: off | `slew=off` | accepted as None | accepted as None | Pass |

## 10.2 Boundary Value Analysis

Defects cluster at the edges of ranges, so each limit is tested at, just below and just above. The last rows check behaviour at the extremes of the system (smallest and largest grid, no traffic, the recovery and hold limits), and that the starvation bound holds at three hold values.

| TC ID | Requirement | Case | Input | Expected | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-10 | FR-15 | vehicles lower boundary minus one | `vehicles=-1` | accepted as 0 | accepted as 0 | Pass |
| TC-11 | FR-15 | vehicles lower boundary | `vehicles=0` | accepted as 0 | accepted as 0 | Pass |
| TC-12 | FR-15 | vehicles lower boundary plus one | `vehicles=1` | accepted as 1 | accepted as 1 | Pass |
| TC-13 | FR-15 | vehicles upper boundary | `vehicles=400` | accepted as 400 | accepted as 400 | Pass |
| TC-14 | FR-15 | vehicles upper boundary plus one | `vehicles=401` | accepted as 400 | accepted as 400 | Pass |
| TC-15 | FR-15 | max hold upper boundary plus one | `hold=41` | accepted as 40.0 | accepted as 40.0 | Pass |
| TC-16 | FR-15 | grid size lower boundary minus one | `grid=2` | accepted as 3 | accepted as 3 | Pass |
| TC-17 | FR-15 | grid size upper boundary plus one | `grid=9` | accepted as 8 | accepted as 8 | Pass |
| TC-18 | FR-15 | arterial share upper boundary plus | `arterial=1.1` | accepted as 1.0 | accepted as 1.0 | Pass |
| TC-19 | FR-01 | Smallest grid completes a run | `grid_size=3, 40 vehicles` | arrived | arrived | Pass |
| TC-20 | FR-01 | Largest grid completes a run | `grid_size=8, 80 vehicles` | arrived | arrived | Pass |
| TC-21 | FR-02 | No background traffic completes a run | `vehicles=0` | arrived | arrived | Pass |
| TC-22 | FR-08 | Recovery cycles lower boundary completes | `recovery_cycles=0` | arrived | arrived | Pass |
| TC-23 | FR-08 | Recovery cycles upper boundary completes | `recovery_cycles=6` | arrived | arrived | Pass |
| TC-24 | FR-06 | Hold of 0 s allows no extra waiting | `hold=0 (4 seeds)` | within the cap (26 s, the fixed cycle's own) | within the cap: worst wait 26 s, cap 26 s | Pass |
| TC-25 | FR-06 | Hold of 15 s stays within its cap | `hold=15 (4 seeds)` | within the cap (26 + 15 = 41 s) | within the cap: worst wait 41 s, cap 41 s | Pass |
| TC-26 | FR-06 | Hold of 40 s stays within its cap | `hold=40 (4 seeds)` | within the cap (26 + 40 = 66 s) | within the cap: worst wait 46 s, cap 66 s | Pass |

## 10.3 State Transition Testing

The system has three stateful parts: a signal's cycle, a junction's preemption and recovery, and a run's life. Each case drives a sequence of events and checks the states reached, including transitions that must be **refused** (TC-31).

| TC ID | Requirement | Case | Input | Expected | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-27 | FR-07 | A signal cycle runs green, yellow, red | `NS axis over one 46 s cycle` | G>Y Y>R R>G | G>Y Y>R R>G | Pass |
| TC-28 | FR-08 | Recovery starts for a shifted junction and ends at zero | `shift 12 s, 2 cycles, run 92 s` | recovering at start=True, recovering after 92 s=False, shift=0.0 | recovering at start=True, recovering after 92 s=False, shift=0.0 | Pass |
| TC-29 | FR-08 | A junction that was never shifted does not enter recovery | `shift 0 s` | recovering at start=False, recovering after 5 s=False, shift=0.0 | recovering at start=False, recovering after 5 s=False, shift=0.0 | Pass |
| TC-30 | FR-08 | Zero recovery cycles resets at once | `shift 12 s, 0 cycles` | recovering at start=False, recovering after 1 s=False, shift=0.0 | recovering at start=False, recovering after 1 s=False, shift=0.0 | Pass |
| TC-31 | FR-07 | A shift that would skip the yellow is held back | `request +10 s while NS is green` | NS shows yellow, never red; the applied shift is less than requested | NS shows YELLOW after the request; applied shift 3 of 10 requested | Pass |
| TC-32 | FR-09 | A run that hits its tick limit reports no transit time | `max_ticks=10` | transit time None | transit time None | Pass |

State diagrams for these are in Chapter 6.3.

## 10.4 Use-Case-Based Testing

Use cases UC-01 to UC-07 (Chapter 5.5) are tested through the same interfaces a user uses. Service-level cases:

| TC ID | Requirement | Case | Input | Expected | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-33 | FR-13 | UC-01: run a scenario and get all four modes | `GET /api/replay?vehicles=20&seed=3` | 4 modes, route ends [('J0_0', 'J4_4')] | 4 modes, route ends [('J0_0', 'J4_4')] | Pass |
| TC-34 | FR-11 | UC-04: compare across seeds returns per-seed samples | `GET /api/compare?seeds=2&vehicles=10` | 2 samples per mode | 2 samples per mode | Pass |
| TC-35 | FR-13 | A bad parameter is a client error | `GET /api/replay?vehicles=abc` | HTTP 400 | HTTP 400 | Pass |
| TC-36 | FR-13 | The page itself is served | `GET /` | HTTP 200 | HTTP 200 | Pass |
| TC-37 | FR-13 | A path outside the frontend folder is refused | `GET /..%2fapi%2fserver.py` | HTTP 404 | HTTP 404 | Pass |

Interface-level cases, executed in a real Chrome browser against the running server (`frontend/tests/smoke.mjs`):

| ID | Check (real Chrome, against the running server) | Status |
| --- | --- | --- |
| ST-01 | page loads and shows a live run | Pass |
| ST-02 | four control modes are offered | Pass |
| ST-03 | the readout states a transit time | Pass |
| ST-04 | Play advances the replay clock | Pass |
| ST-05 | switching mode updates the readout and URL | Pass |
| ST-06 | clicking a junction opens its detail panel | Pass |
| ST-07 | Escape closes the panel and returns focus to the junction | Pass |
| ST-08 | unrun edits are flagged | Pass |
| ST-09 | compare uses the scenario on screen (80 vehicles), not the unrun edit | Pass |
| ST-10a | with No preemption selected, the seeds area explains how to see the bars | Pass |
| ST-10 | per-seed bars are drawn (12 seeds x 2 measures) | Pass |
| ST-11 | running the edited scenario applies it and clears the flag | Pass |
| ST-12 | Export CSV produces the four-mode table | Pass |
| ST-13 | dark appearance applies | Pass |
| ST-14 | light appearance applies | Pass |
| ST-15 | no console errors during the whole run | Pass |
| ST-16 | a rejected parameter shows the server's reason | Pass |
| ST-18 | markup in URL parameters is not executed | Pass |
| ST-17 | no horizontal scrolling at phone width | Pass |

## 10.5 Defect and Bug Management

Every significant defect found during development is recorded below with its severity (impact on correctness or safety), priority (urgency of fixing), and the test that now prevents it. *Critical* = invalidates results or violates a safety rule; *Major* = wrong behaviour or a crash; *Minor* = cosmetic or maintainability.

| Bug ID | Description | Severity | Priority | Status | Resolution | Found by |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-01 | The ambulance slowed itself by about 15% | Major | High | Fixed | It no longer counts toward road congestion (M1) | Readiness audit |
| BUG-02 | Background delay was measured over a different set of vehicles in each mode | **Critical** | High | Fixed | Runs continue until every vehicle finishes (M2) | Readiness audit |
| BUG-03 | `recovery_cycles = 0` raised a division by zero | Major | Medium | Fixed | Zero cycles resets at once | Audit probe |
| BUG-04 | Start equal to end raised an index error | Minor | Low | Fixed | A clear `ValueError` | Audit probe |
| BUG-05 | A junction's shift flipped between −12 s and +11 s as the arrival estimate jittered | Major | High | Fixed | Anchored search (M4) | Review of a worst-case run |
| BUG-06 | A run that never finished crashed the command-line report | Minor | Low | Fixed | Reports "did not arrive" | Audit probe |
| BUG-07 | The cross-traffic bound did not hold: waits reached 59 s against a 41 s promise | **Critical** | High | Fixed | Guarded writes refuse waits beyond the cap (M7) | Code review |
| BUG-08 | Preemption could skip a yellow phase | **Critical** | High | Fixed (reopened once) | Guarded writes refuse illegal changes (M6) | Code review |
| BUG-09 | The ambulance never re-routed | Major | Medium | Fixed | Re-route on entering a road (M8) | Code review |
| BUG-10 | `?slew=nan` dropped the connection | Major | High | Fixed | Non-finite values give 400; failures give 500 | Code review |
| BUG-11 | An idle corridor run lasted two extra recovery cycles | Minor | Low | Fixed | No recovery for unshifted junctions (M9) | Code review |
| BUG-12 | `api.export --out file.js` crashed after the long computation | Minor | Low | Fixed | Directory created first, `.` for a bare name | Code review |
| BUG-13 | Compare and the shared URL used unsubmitted form edits | Major | Medium | Fixed | Use the scenario on screen; flag unrun edits | Code review |
| BUG-14 | One unfinished run turned every average and the JSON into NaN | Major | High | Fixed | Skip and count unfinished runs; non-finite becomes `null` | Code review |
| BUG-15 | The two run scripts duplicated the reporting code | Minor | Low | Fixed | `simulation/cli.py` | Code review |
| BUG-16 | Each comparison request started its own process pool | Major | Medium | Fixed | One shared pool, two at a time | Code review |
| BUG-17 | A clamped upper bound came back as an integer where a float was expected (`40` not `40.0`) | Minor | Low | Fixed | Bounds take the parameter's type | **TC-15** |
| BUG-18 | When the server rejected a parameter the page silently showed sample data and said "start the server" | Major | Medium | Fixed | The page shows the server's reason | **ST-15, ST-16** |
| BUG-19 | After a seed comparison, the per-seed bars were silently absent in the reference mode | Minor | Low | Fixed | An explanatory note | **ST-10** |

**Test-case defects** (the test was wrong, not the system) are recorded too, because they cost time:

| ID | Description | Resolution |
| --- | --- | --- |
| TD-01 | A queue test assumed the east-west red phase started at 23 s; it is the first 23 s | Test corrected |
| TD-02 | TC-26 and TC-31 expected exact numbers copied from a guess; the specification gives only a rule ("within the cap", "not red") | Cases now check the rule (`accept` predicate) |
| TD-03 | The browser script waited for per-seed bars while the reference mode was selected, and counted a deliberate 400 as an error | Sequence and error accounting corrected |

### Defect → root cause → correction → retest

**BUG-07 (critical).** *Defect:* in 12 runs the longest non-green wait at a signal reached 59 s although the maximum hold was 15 s, so the cross-traffic guarantee in Chapter 1.4 (objective 4) was false. *Root cause:* the hold bounded the size of the phase shift, not the time a direction waited. A shift of −12 s followed by +10 s, as the ambulance's arrival estimate changed, left one direction waiting about twice the hold longer. *Correction:* every shift write now passes through one function that refuses a change if any direction would then be non-green for longer than the cycle's own stretch plus the hold (decision M7). *Retest:* `test_corridor_never_starves_a_direction_beyond_cycle_plus_hold` (hold 5 s and 15 s, six seeds, two modes) and TC-24 to TC-26; the 24-seed sweep shows the worst single run equal to the cap and never above it.

**BUG-08 (critical).** *Defect:* a signal could change from green straight to red, which no real controller does. *Root cause:* a phase shift is a jump in the cycle; nothing checked that the displayed sequence stayed legal. *Correction:* the same guard refuses green to red, red to yellow and yellow to green (decision M6). *Retest:* `test_signals_never_skip_a_yellow` scans every frame of all four modes. **It failed on its first run**, in the naive mode, exposing a second case: a yellow that time had already used up and a shift then cut short. The guard was changed to compare against the state displayed on the **previous** tick; the test then passed, and TC-27 and TC-31 cover the cycle and the held-back shift.

**BUG-02 (critical).** *Defect:* the first demo reported that background delay was lower with preemption. *Root cause:* the run stopped when the ambulance arrived, and delay was averaged over the vehicles that had finished by then, so a faster ambulance meant fewer, and different, vehicles were measured. *Correction:* every run continues until all vehicles finish. *Retest:* `test_background_population_is_identical_across_modes`. Once fixed, the apparent delay benefit disappeared.

**BUG-18 (major, found by the browser script).** *Defect:* a rejected parameter produced a page that looked like a working demo of sample data and told the user to start a server that was already running. *Root cause:* every failed request was treated as "server unreachable". *Correction:* a server answer of "no" is shown with its reason; only an unreachable server falls back to the sample. *Retest:* ST-16.

## 10.6 Test Execution Summary

| Test type | Total | Passed | Failed (final) | Failed on first execution |
| --- | --- | --- | --- | --- |
| Unit | 33 | 33 | 0 | 1 (test defect TD-01) |
| Integration | 29 | 29 | 0 | 1 (real defect, BUG-08 second case) |
| System | 22 | 22 | 0 | 0 |
| Black-box | 37 | 37 | 0 | 3 (BUG-17, TD-02 × 2) |
| **Automated total** | **121** | **121** | **0** | 5 |
| Browser checks | 19 | 19 | 0 | 2 (ST-10 exposed BUG-19; ST-17 led to BUG-18) |

The "first execution" column is shown deliberately: tests that never fail on first run are usually not testing anything. Of the seven first-run failures, four exposed real defects (BUG-08's second case, BUG-17, BUG-19 and, through ST-17, BUG-18) and three were wrong tests (TD-01 and TD-02).

## 10.7 Test Coverage

Measured with `pytest-cov` over `core`, `network`, `simulation`, `metrics`, `api` and `viz`, with branch coverage on.

| Measure | Result |
| --- | --- |
| **Statement coverage** | **98.2%** (1009 of 1027 statements) |
| **Branch coverage** | **96.2%** (252 of 262 branches) |
| Function coverage | Not reported by `coverage.py`; every function has at least one test by inspection of the table in Chapter 9.4 but this was not measured |

| File | Statements | Missed | Branches | Missed branches | Covered |
| --- | --- | --- | --- | --- | --- |
| `api/export.py` | 20 | 0 | 0 | 0 | 100.0% |
| `api/replay.py` | 36 | 0 | 12 | 0 | 100.0% |
| `api/server.py` | 108 | 9 | 16 | 0 | 92.7% |
| `core/corridor_coordinator.py` | 27 | 0 | 8 | 0 | 100.0% |
| `core/eta_predictor.py` | 12 | 0 | 4 | 0 | 100.0% |
| `core/recovery.py` | 38 | 1 | 12 | 1 | 96.0% |
| `core/router.py` | 16 | 0 | 0 | 0 | 100.0% |
| `metrics/eta_accuracy.py` | 23 | 1 | 12 | 2 | 91.4% |
| `metrics/evaluate.py` | 53 | 3 | 10 | 1 | 93.7% |
| `metrics/serialize.py` | 15 | 1 | 10 | 1 | 92.0% |
| `metrics/sweep.py` | 71 | 0 | 14 | 0 | 100.0% |
| `network/generate_grid.py` | 107 | 1 | 30 | 1 | 98.5% |
| `simulation/cli.py` | 19 | 0 | 2 | 0 | 100.0% |
| `simulation/engine.py` | 238 | 0 | 84 | 1 | 99.7% |
| `simulation/run_baseline.py` | 10 | 0 | 0 | 0 | 100.0% |
| `simulation/run_corridor.py` | 10 | 0 | 0 | 0 | 100.0% |
| `simulation/scenario.py` | 35 | 0 | 0 | 0 | 100.0% |
| `simulation/traffic_agents.py` | 103 | 2 | 28 | 2 | 96.9% |
| `viz/plots.py` | 86 | 0 | 20 | 1 | 99.1% |
| **Total** | **1027** | **18** | **262** | **10** | **97.8%** |

Lines not covered: `api/server.py` lines 155, 156, 157, 158, 159, 160, 161, 162, 163; `core/recovery.py` lines 45; `metrics/eta_accuracy.py` lines 35; `metrics/evaluate.py` lines 53, 57, 102; `metrics/serialize.py` lines 18; `network/generate_grid.py` lines 117; `simulation/traffic_agents.py` lines 63, 112. The only sizeable gap is the server's interactive start-up loop (`main`, nine lines, which blocks until interrupted; the same code path is exercised through `make_server`). The rest are single defensive lines: a guard against starting recovery twice, a skipped ETA sample with no matching arrival, two convenience accessors on the comparison report, an empty-delay average, an enum branch in the serialiser, an impossible empty candidate list in the shift search, and two loop `break` and `continue` branches in the traffic spawner. The requirement was at least 90% (NFR-08).

## 10.8 Performance Evaluation

Measured by `python -m scripts.benchmark` (median of repeated runs). Figures depend on the machine, so it is named.

Machine: macOS-26.6.2-arm64-arm-64bit-Mach-O, arm, 10 logical CPUs, Python 3.15.0.

| Measurement | Median (ms) | Fastest (ms) | Slowest (ms) | Note |
| --- | --- | --- | --- | --- |
| One run, corridor + recovery, 80 vehicles, 5x5 grid | 20 | 20 | 22 |  |
| One run, corridor + recovery, 200 vehicles, 5x5 grid | 34 | 34 | 35 |  |
| One run, corridor + recovery, 400 vehicles, 5x5 grid (upper limit) | 64 | 63 | 65 |  |
| One run, corridor + recovery, 80 vehicles, 8x8 grid (largest) | 39 | 39 | 41 |  |
| Build the four-mode replay (80 vehicles) | 145 | 145 | 154 |  |
| GET /api/replay (80 vehicles) | 199 | 197 | 219 | 1.00 MB of JSON |
| GET /api/replay (400 vehicles) | 952 | 952 | 957 |  |
| GET /api/compare (12 seeds x 4 modes = 48 runs) | 192 | 187 | 317 | shared process pool |

- Peak Python allocation during one 400-vehicle run: 0.8 MB.
- Peak resident memory of the whole benchmark process (replay builds included): 197 MB.
- CPU use of one default run: 0.02 s of CPU in 0.02 s of wall time (100% of one core); the simulation is single-threaded.


| Requirement | Target | Measured | Verdict |
| --- | --- | --- | --- |
| NFR-01 single run | under 2 s at 400 vehicles | 64 ms | Met, about 30 times faster than needed |
| NFR-02 replay served | under 1 s at the default scenario | 0.2 s (0.95 s at 400 vehicles) | Met |
| NFR-03 12-seed comparison | under 5 s | 0.2 s | Met |
| Memory | no target | about 200 MB resident for the whole benchmark process; under 1 MB of Python allocation during one run | |
| CPU | no target | one core during a run; the comparison spreads over all cores | |

**Throughput.** One default run takes 20 ms, so about 50 runs a second on one core, and the 48-run comparison finishes in about 0.2 s on ten cores. The cost grows roughly linearly with vehicle count (20, 34 and 64 ms at 80, 200 and 400 vehicles). **Response-time caveat:** these are in-process and loopback figures; they say nothing about a slow network.

## 10.9 Security Testing

The system has no accounts, so authentication and authorisation tests do not apply (Chapter 1.5). What can be attacked is the local service and the page. Cases:

| Area | Test | Expected | Actual | Test |
| --- | --- | --- | --- | --- |
| Network exposure | The server's bind address | Loopback only | `127.0.0.1` | `test_the_server_listens_on_loopback_only` |
| Path traversal | `GET /..%2fapi%2fserver.py`, `/%2e%2e/api/server.py`, `/themes/../../README.md`, an unknown file | 404 | 404 for all four | TC-37, `test_static_files_and_unsupported_methods` |
| Method restriction | `POST /api/replay` | Refused | HTTP 501 | same |
| Input handling | `slew=nan`, `hold=nan`, `horizon=inf`, `vehicles=1e999`, `seed=abc` | 400, no crash | 400 each | TC-04, TC-06, TC-07, `test_server_answers_nan_with_400_*` |
| Resource abuse | `vehicles=1000`, `grid=9`, `seeds=1000` | Clamped to the limit | Clamped (400 vehicles runs in 0.95 s) | TC-03, TC-14, TC-17, benchmark |
| Internal failure | A simulation that raises | JSON 500, connection kept | HTTP 500 with a generic message | `test_unexpected_failures_return_a_500_*` |
| Script injection | `?seed=<img onerror=...>&mode=<script>...` | Not executed | `window.__pwn` stayed undefined | ST-18 |
| Output encoding | Error text in the page | Inserted as text | `textContent` only | code review of the three insertion points; ST-16 |

**Not tested, and why:** transport encryption (the service is local, plain HTTP); dependency vulnerability scanning (not run); denial of service by many parallel requests (single-user tool, two concurrent comparisons at most); cross-origin requests (no cookies or credentials exist to steal).
