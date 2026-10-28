"""Black-box test cases for Chapter 10. Each case names the technique (equivalence
partitioning, boundary value analysis, state transition, use case), the requirement it
checks, the input, and the expected result; `run()` executes it and returns what actually
happened. `tests/test_blackbox.py` asserts every case passes and
`scripts/blackbox_report.py` writes the table with the actual outputs."""

import json
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from typing import Callable

from api.server import Handler, scenario_from_query
from core.recovery import RecoveryManager
from network.generate_grid import CyclePlan, Signal, generate_grid
from simulation.engine import RunMode
from simulation.scenario import Scenario, build_engine, run_scenario


@dataclass
class Case:
    id: str
    technique: str
    requirement: str
    description: str
    input: str
    expected: str
    run: Callable[[], str]  # returns the actual result, as text
    # Most cases expect exact text. Where the specification only gives a rule (a bound, a
    # property) the case supplies a predicate instead of inventing an exact number.
    accept: Callable[[str], bool] | None = None

    def execute(self) -> tuple[str, bool]:
        try:
            actual = self.run()
        except Exception as exc:  # a crash is a result too
            actual = f"raised {type(exc).__name__}: {exc}"
        return actual, (self.accept(actual) if self.accept else actual == self.expected)


def _param(key: str, raw: str, attr: str) -> Callable[[], str]:
    def run() -> str:
        try:
            value = getattr(scenario_from_query({key: [raw]}), attr)
        except ValueError as exc:
            return f"rejected (400): {exc}"
        return f"accepted as {value}"

    return run


def _engine_ok(**kw) -> Callable[[], str]:
    def run() -> str:
        _, log = run_scenario(Scenario(**kw), RunMode.CORRIDOR_RECOVERY)
        return "arrived" if log.ambulance_transit_time_s is not None and log.background_unfinished == 0 else "did not finish"

    return run


def _worst_wait(hold: float) -> Callable[[], str]:
    def run() -> str:
        worst = max(
            run_scenario(Scenario(background_vehicles=80, seed=s, corridor_max_hold_s=hold), RunMode.CORRIDOR_RECOVERY)[1].max_nongreen_s
            for s in range(4)
        )
        return f"{'within' if worst <= 26 + hold else 'OVER'} the cap: worst wait {worst:.0f} s, cap {26 + hold:.0f} s"

    return run


def _signal_sequence() -> str:
    plan = CyclePlan(20, 3)
    states = [plan.phase_at(t)["NS"].value[0] for t in range(46)]
    changes = [f"{a}>{b}" for a, b in zip(states, states[1:]) if a != b] + [f"{states[-1]}>{states[0]}"]
    return " ".join(changes)


def _recovery(initial: float, cycles: int, ticks: int) -> Callable[[], str]:
    def run() -> str:
        net = generate_grid(n=2)
        sig = net.junctions["J0_0"].signal
        sig.phase_offset_shift = initial
        mgr = RecoveryManager(recovery_cycles=cycles)
        mgr.begin_recovery("J0_0", sig)
        started = mgr.is_recovering("J0_0")
        for _ in range(ticks):
            mgr.step("J0_0", sig, 1.0)
        return f"recovering at start={started}, recovering after {ticks} s={mgr.is_recovering('J0_0')}, shift={sig.phase_offset_shift:.1f}"

    return run


def _illegal_shift_is_held_back() -> str:
    engine = build_engine(Scenario(background_vehicles=0), RunMode.NAIVE_REACTIVE)
    engine._now = 19.0  # NS is green, one second from its yellow
    engine._set_shift("J1_1", 10.0)  # +10 would put NS straight into red
    sig = engine.network.junctions["J1_1"].signal
    shown = sig.state_for_axis("NS", 19.0).value
    return f"NS shows {shown} after the request; applied shift {sig.phase_offset_shift:.0f} of 10 requested"


def _tick_limit() -> str:
    engine = build_engine(Scenario(background_vehicles=5), RunMode.NO_PREEMPTION)
    engine.max_ticks = 10
    log = engine.run()
    return f"transit time {log.ambulance_transit_time_s}"


def _api(path: str, check: Callable[[dict], str]) -> Callable[[], str]:
    def run() -> str:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            try:
                body = json.load(urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_address[1]}{path}"))
            except urllib.error.HTTPError as exc:
                return f"HTTP {exc.code}"
            return check(body)
        finally:
            httpd.shutdown()

    return run


def _replay_check(body: dict) -> str:
    modes = sorted(body["modes"])
    ends = {(m["route"][0], m["route"][-1]) for m in body["modes"].values()}
    return f"{len(modes)} modes, route ends {sorted(ends)}"


CASES: list[Case] = [
    # --- equivalence partitioning: the `vehicles` parameter ---------------------------------
    Case("TC-01", "EP", "FR-15", "Valid in-range value", "vehicles=80", "accepted as 80", _param("vehicles", "80", "background_vehicles")),
    Case("TC-02", "EP", "FR-15", "Below the valid range is clamped", "vehicles=-5", "accepted as 0", _param("vehicles", "-5", "background_vehicles")),
    Case("TC-03", "EP", "FR-15", "Above the valid range is clamped", "vehicles=1000", "accepted as 400", _param("vehicles", "1000", "background_vehicles")),
    Case("TC-04", "EP", "FR-15", "Non-numeric text is rejected", "vehicles=abc", "rejected (400): vehicles must be a number", _param("vehicles", "abc", "background_vehicles")),
    Case("TC-05", "EP", "FR-15", "Empty value uses the default", "vehicles=", "accepted as 80", _param("vehicles", "", "background_vehicles")),
    Case("TC-06", "EP", "FR-15", "NaN is rejected, not clamped", "slew=nan", "rejected (400): slew must be a finite number", _param("slew", "nan", "slew_rate")),
    Case("TC-07", "EP", "FR-15", "Infinity is rejected", "horizon=inf", "rejected (400): horizon must be a finite number", _param("horizon", "inf", "corridor_horizon_s")),
    Case("TC-08", "EP", "FR-15", "Eased shifts: valid rate", "slew=0.25", "accepted as 0.25", _param("slew", "0.25", "slew_rate")),
    Case("TC-09", "EP", "FR-15", "Eased shifts: off", "slew=off", "accepted as None", _param("slew", "off", "slew_rate")),
    # --- boundary value analysis ------------------------------------------------------------
    Case("TC-10", "BVA", "FR-15", "vehicles lower boundary minus one", "vehicles=-1", "accepted as 0", _param("vehicles", "-1", "background_vehicles")),
    Case("TC-11", "BVA", "FR-15", "vehicles lower boundary", "vehicles=0", "accepted as 0", _param("vehicles", "0", "background_vehicles")),
    Case("TC-12", "BVA", "FR-15", "vehicles lower boundary plus one", "vehicles=1", "accepted as 1", _param("vehicles", "1", "background_vehicles")),
    Case("TC-13", "BVA", "FR-15", "vehicles upper boundary", "vehicles=400", "accepted as 400", _param("vehicles", "400", "background_vehicles")),
    Case("TC-14", "BVA", "FR-15", "vehicles upper boundary plus one", "vehicles=401", "accepted as 400", _param("vehicles", "401", "background_vehicles")),
    Case("TC-15", "BVA", "FR-15", "max hold upper boundary plus one", "hold=41", "accepted as 40.0", _param("hold", "41", "corridor_max_hold_s")),
    Case("TC-16", "BVA", "FR-15", "grid size lower boundary minus one", "grid=2", "accepted as 3", _param("grid", "2", "grid_size")),
    Case("TC-17", "BVA", "FR-15", "grid size upper boundary plus one", "grid=9", "accepted as 8", _param("grid", "9", "grid_size")),
    Case("TC-18", "BVA", "FR-15", "arterial share upper boundary plus", "arterial=1.1", "accepted as 1.0", _param("arterial", "1.1", "arterial_share")),
    Case("TC-19", "BVA", "FR-01", "Smallest grid completes a run", "grid_size=3, 40 vehicles", "arrived", _engine_ok(grid_size=3, background_vehicles=40)),
    Case("TC-20", "BVA", "FR-01", "Largest grid completes a run", "grid_size=8, 80 vehicles", "arrived", _engine_ok(grid_size=8, background_vehicles=80)),
    Case("TC-21", "BVA", "FR-02", "No background traffic completes a run", "vehicles=0", "arrived", _engine_ok(background_vehicles=0)),
    Case("TC-22", "BVA", "FR-08", "Recovery cycles lower boundary completes", "recovery_cycles=0", "arrived", _engine_ok(recovery_cycles=0)),
    Case("TC-23", "BVA", "FR-08", "Recovery cycles upper boundary completes", "recovery_cycles=6", "arrived", _engine_ok(recovery_cycles=6)),
    Case("TC-24", "BVA", "FR-06", "Hold of 0 s allows no extra waiting", "hold=0 (4 seeds)", "within the cap (26 s, the fixed cycle's own)", _worst_wait(0.0), lambda a: a.startswith("within the cap")),
    Case("TC-25", "BVA", "FR-06", "Hold of 15 s stays within its cap", "hold=15 (4 seeds)", "within the cap (26 + 15 = 41 s)", _worst_wait(15.0), lambda a: a.startswith("within the cap")),
    Case("TC-26", "BVA", "FR-06", "Hold of 40 s stays within its cap", "hold=40 (4 seeds)", "within the cap (26 + 40 = 66 s)", _worst_wait(40.0), lambda a: a.startswith("within the cap")),
    # --- state transition --------------------------------------------------------------------
    Case("TC-27", "State", "FR-07", "A signal cycle runs green, yellow, red", "NS axis over one 46 s cycle", "G>Y Y>R R>G", _signal_sequence),
    Case("TC-28", "State", "FR-08", "Recovery starts for a shifted junction and ends at zero", "shift 12 s, 2 cycles, run 92 s", "recovering at start=True, recovering after 92 s=False, shift=0.0", _recovery(12.0, 2, 92)),
    Case("TC-29", "State", "FR-08", "A junction that was never shifted does not enter recovery", "shift 0 s", "recovering at start=False, recovering after 5 s=False, shift=0.0", _recovery(0.0, 2, 5)),
    Case("TC-30", "State", "FR-08", "Zero recovery cycles resets at once", "shift 12 s, 0 cycles", "recovering at start=False, recovering after 1 s=False, shift=0.0", _recovery(12.0, 0, 1)),
    Case("TC-31", "State", "FR-07", "A shift that would skip the yellow is held back", "request +10 s while NS is green", "NS shows yellow, never red; the applied shift is less than requested", _illegal_shift_is_held_back, lambda a: a.startswith("NS shows YELLOW") and "applied shift 10 of" not in a),
    Case("TC-32", "State", "FR-09", "A run that hits its tick limit reports no transit time", "max_ticks=10", "transit time None", _tick_limit),
    # --- use-case based (through the HTTP interface) ------------------------------------------
    Case("TC-33", "Use case", "FR-13", "UC-01: run a scenario and get all four modes", "GET /api/replay?vehicles=20&seed=3", "4 modes, route ends [('J0_0', 'J4_4')]", _api("/api/replay?vehicles=20&seed=3", _replay_check)),
    Case("TC-34", "Use case", "FR-11", "UC-04: compare across seeds returns per-seed samples", "GET /api/compare?seeds=2&vehicles=10", "2 samples per mode", _api("/api/compare?seeds=2&vehicles=10", lambda b: f"{len(b['modes']['corridor_recovery']['transit_samples'])} samples per mode")),
    Case("TC-35", "Use case", "FR-13", "A bad parameter is a client error", "GET /api/replay?vehicles=abc", "HTTP 400", _api("/api/replay?vehicles=abc", lambda b: "HTTP 200")),
    Case("TC-36", "Use case", "FR-13", "The page itself is served", "GET /", "HTTP 200", lambda: "HTTP " + str(_static_status("/"))),
    Case("TC-37", "Use case", "FR-13", "A path outside the frontend folder is refused", "GET /..%2fapi%2fserver.py", "HTTP 404", lambda: "HTTP " + str(_static_status("/..%2fapi%2fserver.py"))),
]


def _static_status(path: str) -> int:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        try:
            return urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_address[1]}{path}").status
        except urllib.error.HTTPError as exc:
            return exc.code
    finally:
        httpd.shutdown()
