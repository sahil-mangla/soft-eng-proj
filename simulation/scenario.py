"""One place that defines a comparison scenario (network, traffic, ambulance
trip, controller parameters) and builds an engine for any RunMode from it —
so demo.py, the CLI runners, the sweeps and the API server all run the same
thing and only differ in `mode`.
"""

from dataclasses import dataclass, replace

from network.generate_grid import generate_grid
from simulation.engine import RunLog, RunMode, SimulationEngine


@dataclass(frozen=True)
class Scenario:
    grid_size: int = 5
    edge_length_m: float = 400.0
    green_duration_s: float = 20.0
    yellow_duration_s: float = 3.0
    background_vehicles: int = 80
    discharge_headway_s: float = 2.0
    seed: int = 42
    corridor_horizon_s: float = 60.0
    corridor_max_hold_s: float = 15.0
    recovery_cycles: int = 2
    slew_rate: float | None = None
    reactive_trigger_m: float = 200.0
    start: str | None = None  # default: top-left corner
    end: str | None = None  # default: bottom-right corner

    @property
    def start_id(self) -> str:
        return self.start or "J0_0"

    @property
    def end_id(self) -> str:
        return self.end or f"J{self.grid_size - 1}_{self.grid_size - 1}"

    def with_(self, **changes) -> "Scenario":
        return replace(self, **changes)


def build_engine(scenario: Scenario, mode: RunMode, record_frames: bool = False) -> SimulationEngine:
    # A fresh network per run so every mode starts from identical signal state.
    network = generate_grid(
        n=scenario.grid_size,
        edge_length_m=scenario.edge_length_m,
        green_duration=scenario.green_duration_s,
        yellow_duration=scenario.yellow_duration_s,
        discharge_headway_s=scenario.discharge_headway_s,
    )
    return SimulationEngine(
        network=network,
        ambulance_start=scenario.start_id,
        ambulance_end=scenario.end_id,
        background_vehicle_count=scenario.background_vehicles,
        mode=mode,
        seed=scenario.seed,
        corridor_horizon_s=scenario.corridor_horizon_s,
        corridor_max_hold_s=scenario.corridor_max_hold_s,
        recovery_cycles=scenario.recovery_cycles,
        slew_rate=scenario.slew_rate,
        reactive_trigger_m=scenario.reactive_trigger_m,
        record_frames=record_frames,
    )


def run_scenario(
    scenario: Scenario, mode: RunMode, record_frames: bool = False
) -> tuple[SimulationEngine, RunLog]:
    engine = build_engine(scenario, mode, record_frames)
    return engine, engine.run()
