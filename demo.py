"""Runs all three modes (no-preemption, naive-reactive, corridor+recovery) on
the same sample scenario and prints/plots the before/after comparison — the
MVP "definition of done" from CLAUDE.md section 3.

Usage: python demo.py
"""

from metrics.evaluate import MetricsEvaluator
from network.generate_grid import generate_grid
from simulation.engine import RunLog, RunMode, SimulationEngine
from viz.plots import plot_comparison, plot_signal_timeline

GRID_SIZE = 5
BACKGROUND_VEHICLES = 25
SEED = 42
START = "J0_0"
END = f"J{GRID_SIZE - 1}_{GRID_SIZE - 1}"


def run_mode(mode: RunMode) -> tuple[RunLog, list[str]]:
    # Fresh network per mode so all three start from identical signal state,
    # same seed so background traffic is identical across modes too.
    network = generate_grid(n=GRID_SIZE)
    engine = SimulationEngine(
        network=network,
        ambulance_start=START,
        ambulance_end=END,
        background_vehicle_count=BACKGROUND_VEHICLES,
        mode=mode,
        seed=SEED,
    )
    log = engine.run()
    return log, engine.route.junction_ids


def main() -> None:
    runs: dict[RunMode, RunLog] = {}
    corridor_log = None
    corridor_route_ids = None

    for mode in (RunMode.NO_PREEMPTION, RunMode.NAIVE_REACTIVE, RunMode.CORRIDOR_RECOVERY):
        log, route_ids = run_mode(mode)
        runs[mode] = log
        if mode == RunMode.CORRIDOR_RECOVERY:
            corridor_log, corridor_route_ids = log, route_ids

    report = MetricsEvaluator().compare(runs)

    print(f"{'Mode':<22}{'Transit time (s)':>18}{'Avg bg delay (s)':>20}")
    for mode, log in runs.items():
        print(
            f"{mode.value:<22}{report.transit_times_s[mode]:>18.1f}"
            f"{report.avg_background_delays_s[mode]:>20.1f}"
        )

    plot_comparison(report)
    plot_signal_timeline(corridor_log, corridor_route_ids)
    print("\nCharts written to outputs/comparison.png and outputs/signal_timeline.png")


if __name__ == "__main__":
    main()
