"""Runs one ambulance agent from a start junction (A) to a destination (B)
through the network with NO preemption at all, alongside background traffic.
This is the control condition / working scaffold milestone.

Also supports --mode naive, which runs the naive-reactive preemption variant
(reacts only within ~200m, resets instantly) as the "existing systems"
comparison point (CLAUDE.md section 6.5).

See docs/BUILD-PLAN.md Step 2.
"""

import argparse

from network.generate_grid import generate_grid
from simulation.engine import RunMode, SimulationEngine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["none", "naive"], default="none")
    parser.add_argument("--grid-size", type=int, default=5)
    parser.add_argument("--background-vehicles", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    network = generate_grid(n=args.grid_size)
    mode = RunMode.NAIVE_REACTIVE if args.mode == "naive" else RunMode.NO_PREEMPTION
    start = "J0_0"
    end = f"J{args.grid_size - 1}_{args.grid_size - 1}"

    engine = SimulationEngine(
        network=network,
        ambulance_start=start,
        ambulance_end=end,
        background_vehicle_count=args.background_vehicles,
        mode=mode,
        seed=args.seed,
    )
    log = engine.run()

    print(f"Mode: {mode.value}")
    print(f"Ambulance transit time: {log.ambulance_transit_time_s:.1f} s")
    if log.background_delays_s:
        avg_delay = sum(log.background_delays_s) / len(log.background_delays_s)
        print(f"Avg background delay: {avg_delay:.1f} s over {len(log.background_delays_s)} vehicles")


if __name__ == "__main__":
    main()
