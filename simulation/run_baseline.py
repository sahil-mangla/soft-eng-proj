"""Runs one ambulance agent from a start junction (A) to a destination (B)
through the network with NO preemption at all, alongside background traffic.
This is the control condition / working scaffold milestone.

Also supports --mode naive, which runs the naive-reactive preemption variant
(reacts only within ~200m, resets instantly) as the "existing systems"
comparison point (CLAUDE.md section 6.5).

Run from the repo root:  python -m simulation.run_baseline [--mode naive]

See docs/BUILD-PLAN.md Step 2.
"""

import argparse

from simulation.engine import RunMode
from simulation.scenario import Scenario, run_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["none", "naive"], default="none")
    parser.add_argument("--grid-size", type=int, default=Scenario().grid_size)
    parser.add_argument("--background-vehicles", type=int, default=Scenario().background_vehicles)
    parser.add_argument("--seed", type=int, default=Scenario().seed)
    args = parser.parse_args()

    scenario = Scenario(
        grid_size=args.grid_size, background_vehicles=args.background_vehicles, seed=args.seed
    )
    mode = RunMode.NAIVE_REACTIVE if args.mode == "naive" else RunMode.NO_PREEMPTION
    _, log = run_scenario(scenario, mode)

    print(f"Mode: {mode.value}")
    if log.ambulance_transit_time_s is None:
        print("Ambulance did not arrive within the tick limit")
    else:
        print(f"Ambulance transit time: {log.ambulance_transit_time_s:.1f} s")
    avg_delay = sum(log.background_delays_s) / max(1, len(log.background_delays_s))
    print(f"Avg background delay: {avg_delay:.1f} s over {len(log.background_delays_s)} vehicles")


if __name__ == "__main__":
    main()
