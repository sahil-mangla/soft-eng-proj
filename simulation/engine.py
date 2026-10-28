"""The shared tick-loop simulator (D9's `SimulationEngine`) that
run_baseline.py and run_corridor.py both drive. One engine, one `RunMode`
field, rather than separate simulator classes per mode — this is what keeps
the comparison in CLAUDE.md section 7 fair, since every mode runs through the
identical tick loop and only differs in how a junction's
Signal.phase_offset_shift gets set.

Every shift write — coordinator, naive reactive, recovery, resets — goes
through `_set_shift`, which enforces two things:

* **Signal safety (all modes).** A write may not make a signal skip its
  yellow: green may only give way to yellow, yellow to red, and red to green.
  A change that would break that is applied as far as it legally can be and
  finished on a later tick, once the signal is at a point where it is legal.
* **Bounded cross-traffic wait (corridor modes).** No signal may show a
  non-green to one direction for longer than the fixed cycle's own stretch
  plus `corridor_max_hold_s`. The naive reactive baseline deliberately has no
  such bound (it is the "existing systems" comparison point, CLAUDE.md 6.5).

A run continues past the ambulance's arrival until every background vehicle
has finished (and any recovery has completed), so background delay is
measured over the same vehicle population in every mode.
"""

import math
from dataclasses import dataclass, field
from enum import Enum

from core.corridor_coordinator import CorridorCoordinator
from core.eta_predictor import ETAPredictor
from core.recovery import RecoveryManager
from core.router import Route, compute_route
from network.generate_grid import Axis, RoadNetwork, SignalState
from simulation.traffic_agents import (
    BackgroundVehicle,
    Vehicle,
    advance_vehicle,
    spawn_background_traffic,
)

REACTIVE_TRIGGER_DISTANCE_M = 200.0  # CLAUDE.md 6.5: naive baseline reacts within ~200m

_STATE_CHAR = {SignalState.GREEN: "G", SignalState.YELLOW: "Y", SignalState.RED: "R"}
# Transitions a real controller never makes at the moment a shift is applied.
_ILLEGAL_CHANGES = {
    (SignalState.GREEN, SignalState.RED),  # skips the yellow
    (SignalState.RED, SignalState.YELLOW),
    (SignalState.YELLOW, SignalState.GREEN),  # yellow cannot be taken back
}


class RunMode(Enum):
    NO_PREEMPTION = "no_preemption"
    NAIVE_REACTIVE = "naive_reactive"
    CORRIDOR_NO_RECOVERY = "corridor_no_recovery"
    CORRIDOR_RECOVERY = "corridor_recovery"

    @property
    def label(self) -> str:
        return {
            RunMode.NO_PREEMPTION: "No preemption",
            RunMode.NAIVE_REACTIVE: "Naive reactive",
            RunMode.CORRIDOR_NO_RECOVERY: "Corridor, no recovery",
            RunMode.CORRIDOR_RECOVERY: "Corridor + recovery",
        }[self]

    @property
    def is_corridor(self) -> bool:
        return self in (RunMode.CORRIDOR_NO_RECOVERY, RunMode.CORRIDOR_RECOVERY)


@dataclass
class Ambulance(Vehicle):
    counts_toward_congestion: bool = False


@dataclass
class TickRecord:
    t: float
    ambulance_junction: str
    junction_shifts: dict[str, float]
    # junction id -> G/Y/R for the axis the ambulance approaches by, for the
    # junctions on the route at that moment (the route can change mid-run).
    approach_states: dict[str, str] = field(default_factory=dict)


@dataclass
class Frame:
    """Everything the frontend needs to draw one second of a run."""

    t: float
    ambulance: tuple[float, float]
    background: list[tuple[float, float, int]]  # x, y, moving?
    ns: str  # G/Y/R per junction, network order
    ew: str
    shifts: list[float]


@dataclass
class RunLog:
    mode: RunMode
    ticks: list[TickRecord] = field(default_factory=list)
    frames: list[Frame] = field(default_factory=list)
    ambulance_transit_time_s: float | None = None
    background_delays_s: list[float] = field(default_factory=list)  # one per vehicle, spawn order
    background_unfinished: int = 0
    end_time_s: float = 0.0
    # (time of prediction, junction, predicted absolute arrival) for every tick.
    eta_samples: list[tuple[float, str, float]] = field(default_factory=list)
    actual_arrival_s: dict[str, float] = field(default_factory=dict)
    # Longest stretch (s) any signal showed a non-green to one axis. A fixed
    # cycle gives cycle - green; corridor modes are bounded by that plus max hold.
    max_nongreen_s: float = 0.0
    reroutes: int = 0


class SimulationEngine:
    def __init__(
        self,
        network: RoadNetwork,
        ambulance_start: str,
        ambulance_end: str,
        background_vehicle_count: int = 25,
        mode: RunMode = RunMode.NO_PREEMPTION,
        dt: float = 1.0,
        max_ticks: int = 3000,
        seed: int = 42,
        corridor_horizon_s: float = 60.0,
        corridor_max_hold_s: float = 15.0,
        recovery_cycles: int = 2,
        slew_rate: float | None = None,
        reactive_trigger_m: float = REACTIVE_TRIGGER_DISTANCE_M,
        record_frames: bool = False,
        reroute: bool = True,
        reroute_gain: float = 0.10,
        arterial_share: float = 0.0,
    ):
        if ambulance_start == ambulance_end:
            raise ValueError("ambulance_start and ambulance_end must differ")
        self.network = network
        self.mode = mode
        self.dt = dt
        self.max_ticks = max_ticks
        self.reactive_trigger_m = reactive_trigger_m
        self.record_frames = record_frames
        self.max_hold_s = corridor_max_hold_s
        self.reroute = reroute
        self.reroute_gain = reroute_gain
        self._end = ambulance_end

        self.route: Route = compute_route(network, ambulance_start, ambulance_end)
        self.ambulance = Ambulance(id="ambulance", route=list(self.route.junction_ids))
        self.background_vehicles: list[BackgroundVehicle] = spawn_background_traffic(
            network,
            count=background_vehicle_count,
            seed=seed,
            corridor=list(self.route.junction_ids),  # the initial route, identical in every mode
            corridor_share=arterial_share,
        )

        self.eta_predictor = ETAPredictor()
        self.corridor_coordinator = CorridorCoordinator(
            network,
            horizon_s=corridor_horizon_s,
            max_hold_s=corridor_max_hold_s,
            slew_rate=slew_rate,
            set_shift=self._set_shift,
        )
        self.recovery_manager = RecoveryManager(recovery_cycles=recovery_cycles, set_shift=self._set_shift)

        self._approach_axis_by_junction: dict[str, Axis] = self._axes_for(self.route)
        self._junction_order = list(network.junctions)
        self._released: set[str] = set()  # junctions whose shift is being returned to zero
        self._nongreen_run_s: dict[tuple[str, Axis], float] = {}
        self._now = 0.0
        self.time = 0.0
        self._tick_count = 0
        self.log = RunLog(mode=mode)

    def _axes_for(self, route: Route) -> dict[str, Axis]:
        return {route.junction_ids[i + 1]: edge.axis for i, edge in enumerate(route.edges)}

    def run(self) -> RunLog:
        while self._tick_count < self.max_ticks and not self._done():
            self._tick()
        self._finalize()
        return self.log

    def _done(self) -> bool:
        return (
            self.ambulance.finished
            and all(v.finished for v in self.background_vehicles)
            and not self.recovery_manager.any_active()
            and not self._unreturned()
        )

    def _unreturned(self) -> list[str]:
        """Released junctions whose shift is not yet back at zero (and not easing back)."""
        return [
            jid for jid in self._released
            if not self.recovery_manager.is_recovering(jid)
            and abs(self.network.junctions[jid].signal.phase_offset_shift) > 1e-9
        ]

    # ------------------------------------------------------------------ tick

    def _tick(self) -> None:
        t = self.time
        self._now = t

        etas = {}
        if not self.ambulance.finished:
            etas = self.eta_predictor.predict(
                self.route, self.ambulance.edge_index, self.ambulance.distance_into_edge_m
            )
            for junction_id, eta_s in etas.items():
                self.log.eta_samples.append((t, junction_id, t + eta_s))

        if self.mode.is_corridor and etas:
            self.corridor_coordinator.coordinate(t, etas, self._approach_axis_by_junction, self.dt)
        elif self.mode == RunMode.NAIVE_REACTIVE and not self.ambulance.finished:
            self._apply_naive_reactive(t)

        if self.mode == RunMode.CORRIDOR_RECOVERY:
            for junction_id in self._released:
                if self.recovery_manager.is_recovering(junction_id):
                    self.recovery_manager.step(junction_id, self.network.junctions[junction_id].signal, self.dt)
        for junction_id in self._unreturned():  # a reset that was held back earlier
            self._set_shift(junction_id, 0.0)

        self._track_starvation(t)

        for vehicle in self.background_vehicles:
            if t >= vehicle.spawn_tick and not vehicle.finished:
                advance_vehicle(vehicle, self.network, t, self.dt)

        was_finished = self.ambulance.finished
        cleared = advance_vehicle(self.ambulance, self.network, t, self.dt)
        if cleared is not None:
            self.log.actual_arrival_s[cleared] = t
            self._release_junction(cleared)
            self._maybe_reroute()
        if self.ambulance.finished and not was_finished:
            self.log.ambulance_transit_time_s = self.ambulance.finished_tick
            self.log.actual_arrival_s[self.route.junction_ids[-1]] = self.ambulance.finished_tick
            # The destination (and anything still ahead) has no further use
            # for a preemption shift; release it the same way as a cleared one.
            for junction_id in self.route.junction_ids:
                if junction_id not in self._released:
                    self._release_junction(junction_id)

        self._log_tick(t)
        self.time += self.dt
        self._tick_count += 1

    # ----------------------------------------------------- shift write path

    def _set_shift(self, junction_id: str, target: float) -> None:
        """Move a junction's phase shift toward `target`, as far as is admissible
        right now (1 s at a time); the rest happens on a later tick."""
        signal = self.network.junctions[junction_id].signal
        current = signal.phase_offset_shift
        if target == current:
            return
        direction = 1.0 if target > current else -1.0
        steps = max(1, math.ceil(abs(target - current) - 1e-9))
        best = current
        for k in range(1, steps + 1):
            candidate = target if k == steps else current + direction * k
            if not self._admissible(junction_id, current, candidate):
                break
            best = candidate
        signal.phase_offset_shift = best

    def _admissible(self, junction_id: str, old: float, candidate: float) -> bool:
        plan = self.network.junctions[junction_id].signal.cycle_plan
        t = self._now
        # What was displayed last tick, against what this write would display now: the
        # pair a driver actually sees. (Comparing both shifts at the same instant would miss
        # a yellow that natural time evolution used up and the write then cut short.)
        before, after = plan.phase_at(t - self.dt + old), plan.phase_at(t + candidate)
        if any((before[axis], after[axis]) in _ILLEGAL_CHANGES for axis in ("NS", "EW")):
            return False
        if not self.mode.is_corridor:
            return True  # the naive baseline is not bounded (see module docstring)
        cap = plan.cycle_length - plan.green_duration + self.max_hold_s
        for axis in ("NS", "EW"):
            remaining = plan.nongreen_remaining(axis, t + candidate)
            if remaining <= 0.0:
                continue
            run_so_far = self._nongreen_run_s.get((junction_id, axis), 0.0)
            if run_so_far + math.ceil(remaining / self.dt - 1e-9) * self.dt > cap + 1e-9:
                return False
        return True

    def _release_junction(self, junction_id: str) -> None:
        """The ambulance is done with this junction: return its signal to schedule."""
        self._released.add(junction_id)
        signal = self.network.junctions[junction_id].signal
        if abs(signal.phase_offset_shift) < 1e-9:
            return
        if self.mode == RunMode.CORRIDOR_RECOVERY:
            self.recovery_manager.begin_recovery(junction_id, signal)  # eases back over N cycles
        else:
            self._set_shift(junction_id, 0.0)  # instant reset, no easing (completed on a later tick if held back)

    def _apply_naive_reactive(self, t: float) -> None:
        next_junction_id = self.ambulance.next_junction
        if next_junction_id in self._released:
            return
        edge = self.network.edge(self.ambulance.current_junction, next_junction_id)
        remaining_m = edge.length_m - self.ambulance.distance_into_edge_m
        if remaining_m > self.reactive_trigger_m:
            return
        eta_s = remaining_m / edge.current_speed_mps()
        junction = self.network.junctions[next_junction_id]
        axis = self._approach_axis_by_junction[next_junction_id]
        # Naive reactive ignores the cross-traffic bound entirely (unlike
        # CorridorCoordinator's max_hold_s) — force green as soon as it reacts.
        shift = junction.signal.best_shift_for_green(
            axis,
            t + eta_s,
            max_shift=junction.signal.cycle_plan.cycle_length,
            anchor=junction.signal.phase_offset_shift,
        )
        self._set_shift(next_junction_id, shift)

    # --------------------------------------------------------------- routing

    def _tail_time_s(self, junction_ids: list[str]) -> float:
        total = 0.0
        for u, v in zip(junction_ids[:-1], junction_ids[1:]):
            edge = self.network.edge(u, v)
            total += edge.length_m / edge.current_speed_mps()
        return total

    def _maybe_reroute(self) -> None:
        """CLAUDE.md 6.1: recompute the route when conditions change materially.
        Checked each time the ambulance enters a new road; the route only changes
        when the new remainder is at least `reroute_gain` faster at current speeds."""
        amb = self.ambulance
        if not self.reroute or amb.finished or amb.next_junction == self._end:
            return
        ahead = amb.next_junction
        old_tail = amb.route[amb.edge_index + 1 :]
        new_tail = compute_route(self.network, ahead, self._end).junction_ids
        if new_tail == old_tail:
            return
        if self._tail_time_s(new_tail) >= self._tail_time_s(old_tail) * (1.0 - self.reroute_gain):
            return
        amb.route = amb.route[: amb.edge_index + 1] + new_tail
        self.route = Route(junction_ids=list(amb.route), network=self.network)
        self._approach_axis_by_junction = self._axes_for(self.route)
        self.log.reroutes += 1
        for junction_id in set(old_tail) - set(new_tail):
            if junction_id not in self._released:
                self._release_junction(junction_id)  # no longer needed: ease it back

    # ------------------------------------------------------------- recording

    def _track_starvation(self, t: float) -> None:
        for junction_id, junction in self.network.junctions.items():
            for axis in ("NS", "EW"):
                key = (junction_id, axis)
                if junction.signal.state_for_axis(axis, t) == SignalState.GREEN:
                    self._nongreen_run_s[key] = 0.0
                else:
                    run = self._nongreen_run_s.get(key, 0.0) + self.dt
                    self._nongreen_run_s[key] = run
                    self.log.max_nongreen_s = max(self.log.max_nongreen_s, run)

    def _log_tick(self, t: float) -> None:
        route_ids = self.route.junction_ids
        shifts = {jid: self.network.junctions[jid].signal.phase_offset_shift for jid in route_ids}
        first_axis = self.route.edges[0].axis
        approach = {
            jid: _STATE_CHAR[
                self.network.junctions[jid].signal.state_for_axis(self._approach_axis_by_junction.get(jid, first_axis), t)
            ]
            for jid in route_ids
        }
        self.log.ticks.append(
            TickRecord(t=t, ambulance_junction=self.ambulance.current_junction, junction_shifts=shifts, approach_states=approach)
        )
        if self.record_frames:
            self.log.frames.append(self._frame(t))

    def _frame(self, t: float) -> Frame:
        net = self.network

        def where(v: Vehicle) -> tuple[float, float]:
            if v.finished:
                return net.xy(v.route[-1])
            return net.position_xy(v.current_junction, v.next_junction, v.distance_into_edge_m)

        background = [
            (*where(v), 1 if v.speed_mps > 0 else 0)
            for v in self.background_vehicles
            if v.started and not v.finished
        ]
        ns = "".join(_STATE_CHAR[net.junctions[j].signal.state_for_axis("NS", t)] for j in self._junction_order)
        ew = "".join(_STATE_CHAR[net.junctions[j].signal.state_for_axis("EW", t)] for j in self._junction_order)
        shifts = [net.junctions[j].signal.phase_offset_shift for j in self._junction_order]
        return Frame(t=t, ambulance=where(self.ambulance), background=background, ns=ns, ew=ew, shifts=shifts)

    def _finalize(self) -> None:
        self.log.end_time_s = self.time
        for vehicle in self.background_vehicles:
            free_flow_time_s = self._free_flow_time(vehicle.route)
            if vehicle.finished_tick is None:
                # Still en route when the run stopped: its delay so far is a
                # lower bound, counted rather than silently dropped.
                self.log.background_unfinished += 1
                actual_time_s = self.time - vehicle.spawn_tick
            else:
                actual_time_s = vehicle.finished_tick - vehicle.spawn_tick
            self.log.background_delays_s.append(max(0.0, actual_time_s - free_flow_time_s))

    def _free_flow_time(self, junction_ids: list[str]) -> float:
        total = 0.0
        for u, v in zip(junction_ids[:-1], junction_ids[1:]):
            edge = self.network.edge(u, v)
            total += edge.length_m / edge.free_flow_speed_mps
        return total
