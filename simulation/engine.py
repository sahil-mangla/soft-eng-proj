"""The shared tick-loop simulator (D9's `SimulationEngine`) that
run_baseline.py and run_corridor.py both drive. One engine, one `RunMode`
field, rather than separate simulator classes per mode — this is what keeps
the three-way comparison in CLAUDE.md section 7 fair, since baseline,
naive-reactive, and corridor+recovery all run through the identical tick
loop and only differ in how a junction's Signal.phase_offset_shift gets set.
"""

from dataclasses import dataclass, field
from enum import Enum

from core.corridor_coordinator import CorridorCoordinator
from core.eta_predictor import ETAPredictor
from core.recovery import RecoveryManager
from core.router import Route, compute_route
from network.generate_grid import RoadNetwork
from simulation.traffic_agents import (
    BackgroundVehicle,
    Vehicle,
    advance_vehicle,
    spawn_background_traffic,
)

REACTIVE_TRIGGER_DISTANCE_M = 200.0  # CLAUDE.md 6.5: naive baseline reacts within ~200m


class RunMode(Enum):
    NO_PREEMPTION = "no_preemption"
    NAIVE_REACTIVE = "naive_reactive"
    CORRIDOR_RECOVERY = "corridor_recovery"


@dataclass
class Ambulance(Vehicle):
    pass


@dataclass
class TickRecord:
    t: float
    ambulance_junction: str
    junction_shifts: dict[str, float]


@dataclass
class RunLog:
    mode: RunMode
    ticks: list[TickRecord] = field(default_factory=list)
    ambulance_transit_time_s: float | None = None
    background_delays_s: list[float] = field(default_factory=list)


class SimulationEngine:
    def __init__(
        self,
        network: RoadNetwork,
        ambulance_start: str,
        ambulance_end: str,
        background_vehicle_count: int = 25,
        mode: RunMode = RunMode.NO_PREEMPTION,
        dt: float = 1.0,
        max_ticks: int = 1200,
        seed: int = 42,
        corridor_horizon_s: float = 60.0,
        corridor_max_hold_s: float = 15.0,
        recovery_cycles: int = 2,
    ):
        self.network = network
        self.mode = mode
        self.dt = dt
        self.max_ticks = max_ticks

        self.route: Route = compute_route(network, ambulance_start, ambulance_end)
        self.ambulance = Ambulance(id="ambulance", route=self.route.junction_ids)
        self.background_vehicles: list[BackgroundVehicle] = spawn_background_traffic(
            network, count=background_vehicle_count, seed=seed
        )

        self.eta_predictor = ETAPredictor()
        self.corridor_coordinator = CorridorCoordinator(
            network, horizon_s=corridor_horizon_s, max_hold_s=corridor_max_hold_s
        )
        self.recovery_manager = RecoveryManager(recovery_cycles=recovery_cycles)

        self._approach_axis_by_junction = {
            self.route.junction_ids[i + 1]: edge.axis
            for i, edge in enumerate(self.route.edges)
        }
        self._passed_junctions: set[str] = set()
        self.time = 0.0
        self._tick_count = 0
        self.log = RunLog(mode=mode)

    def run(self) -> RunLog:
        while self._tick_count < self.max_ticks and self.ambulance.finished_tick is None:
            self._tick()
        return self.log

    def _tick(self) -> None:
        t = self.time

        if self.mode == RunMode.CORRIDOR_RECOVERY:
            etas = self.eta_predictor.predict(
                self.route, self.ambulance.edge_index, self.ambulance.distance_into_edge_m
            )
            self.corridor_coordinator.coordinate(t, etas, self._approach_axis_by_junction)
        elif self.mode == RunMode.NAIVE_REACTIVE:
            self._apply_naive_reactive(t)

        for vehicle in self.background_vehicles:
            if t >= vehicle.spawn_tick and not vehicle.finished:
                advance_vehicle(vehicle, self.network, t, self.dt)

        cleared = advance_vehicle(self.ambulance, self.network, t, self.dt)
        if cleared is not None:
            self._passed_junctions.add(cleared)
            junction = self.network.junctions[cleared]
            if self.mode == RunMode.CORRIDOR_RECOVERY:
                self.recovery_manager.begin_recovery(cleared, junction.signal)
            elif self.mode == RunMode.NAIVE_REACTIVE:
                junction.signal.phase_offset_shift = 0.0  # instant reset, no easing

        if self.mode == RunMode.CORRIDOR_RECOVERY:
            for junction_id in self._passed_junctions:
                if self.recovery_manager.is_recovering(junction_id):
                    self.recovery_manager.step(
                        junction_id, self.network.junctions[junction_id].signal, self.dt
                    )

        self._log_tick(t)
        self.time += self.dt
        self._tick_count += 1

        if self.ambulance.finished_tick is not None:
            self.log.ambulance_transit_time_s = self.ambulance.finished_tick
            self._finalize_background_delays()

    def _apply_naive_reactive(self, t: float) -> None:
        next_junction_id = self.ambulance.next_junction
        if next_junction_id in self._passed_junctions:
            return
        edge = self.network.edge(self.ambulance.current_junction, next_junction_id)
        remaining_m = edge.length_m - self.ambulance.distance_into_edge_m
        if remaining_m > REACTIVE_TRIGGER_DISTANCE_M:
            return
        eta_s = remaining_m / edge.current_speed_mps()
        junction = self.network.junctions[next_junction_id]
        axis = self._approach_axis_by_junction[next_junction_id]
        # Naive reactive ignores the cross-traffic bound entirely (unlike
        # CorridorCoordinator's max_hold_s) — force green as soon as it reacts.
        shift = junction.signal.best_shift_for_green(
            axis, t + eta_s, max_shift=junction.signal.cycle_plan.cycle_length
        )
        junction.signal.phase_offset_shift = shift

    def _log_tick(self, t: float) -> None:
        shifts = {
            jid: self.network.junctions[jid].signal.phase_offset_shift
            for jid in self.route.junction_ids
        }
        self.log.ticks.append(
            TickRecord(t=t, ambulance_junction=self.ambulance.current_junction, junction_shifts=shifts)
        )

    def _finalize_background_delays(self) -> None:
        # Scoped to vehicles that finished within the ambulance's transit
        # window, so all three modes are compared over the same timeframe.
        for vehicle in self.background_vehicles:
            if vehicle.finished_tick is None:
                continue
            free_flow_time_s = self._free_flow_time(vehicle.route)
            actual_time_s = vehicle.finished_tick - vehicle.spawn_tick
            self.log.background_delays_s.append(max(0.0, actual_time_s - free_flow_time_s))

    def _free_flow_time(self, junction_ids: list[str]) -> float:
        total = 0.0
        for u, v in zip(junction_ids[:-1], junction_ids[1:]):
            edge = self.network.edge(u, v)
            total += edge.length_m / edge.free_flow_speed_mps
        return total
