"""Multi-seed comparison and parameter sweeps.

A single seed is one traffic draw; the ambulance-time gap between modes is
large enough to see in one, but the effect on background delay is small next
to seed-to-seed variance. So everything here runs the *same* seeds through
every mode and reports means with 95% confidence intervals, plus paired
differences against a reference mode.

Usage:  python -m metrics.sweep --seeds 24 --out outputs
"""

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
import math
from dataclasses import asdict, dataclass

from metrics.evaluate import Estimate, MetricsEvaluator, ModeMetrics, estimate, paired_difference
from metrics.serialize import to_jsonable
from simulation.engine import RunMode
from simulation.scenario import Scenario, run_scenario

ALL_MODES = tuple(RunMode)


def _run_one(args: tuple[Scenario, RunMode]) -> ModeMetrics:
    scenario, mode = args
    _, log = run_scenario(scenario, mode)
    return MetricsEvaluator().summarize(log)


def run_many(
    jobs: list[tuple[Scenario, RunMode]],
    workers: int | None = None,
    executor: ProcessPoolExecutor | None = None,
) -> list[ModeMetrics]:
    """Runs every job. A caller that serves many requests (the API) passes one
    long-lived `executor` so each request does not spawn its own process pool."""
    if workers == 1 or len(jobs) < 8:
        return [_run_one(j) for j in jobs]
    if executor is not None:
        return list(executor.map(_run_one, jobs, chunksize=4))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_run_one, jobs, chunksize=4))


@dataclass
class ModeSummary:
    mode: str
    transit: Estimate
    avg_delay: Estimate
    p95_delay: Estimate
    max_nongreen: Estimate
    # Paired differences against the reference mode (None for the reference itself).
    transit_vs_ref: Estimate | None = None
    delay_vs_ref: Estimate | None = None
    # Per-seed values in seed order, so the frontend can show the spread.
    transit_samples: list[float] | None = None
    delay_samples: list[float] | None = None
    max_nongreen_samples: list[float] | None = None
    unfinished_runs: int = 0  # runs whose ambulance never arrived; left out of the estimates


def compare_modes(
    scenario: Scenario,
    seeds: list[int],
    modes: tuple[RunMode, ...] = ALL_MODES,
    reference: RunMode = RunMode.NO_PREEMPTION,
    workers: int | None = None,
    executor: ProcessPoolExecutor | None = None,
) -> dict[RunMode, ModeSummary]:
    jobs = [(scenario.with_(seed=s), m) for m in modes for s in seeds]
    results = run_many(jobs, workers, executor)
    by_mode: dict[RunMode, list[ModeMetrics]] = {
        m: results[i * len(seeds) : (i + 1) * len(seeds)] for i, m in enumerate(modes)
    }
    ref = by_mode.get(reference)
    out: dict[RunMode, ModeSummary] = {}
    for mode, rows in by_mode.items():
        summary = ModeSummary(
            mode=mode.value,
            transit=estimate([r.transit_s for r in rows]),
            avg_delay=estimate([r.avg_delay_s for r in rows]),
            p95_delay=estimate([r.p95_delay_s for r in rows]),
            max_nongreen=estimate([r.max_nongreen_s for r in rows]),
            transit_samples=[r.transit_s for r in rows],
            delay_samples=[r.avg_delay_s for r in rows],
            max_nongreen_samples=[r.max_nongreen_s for r in rows],
            unfinished_runs=sum(1 for r in rows if not math.isfinite(r.transit_s)),
        )
        if ref is not None and mode != reference:
            summary.transit_vs_ref = paired_difference([r.transit_s for r in rows], [r.transit_s for r in ref])
            summary.delay_vs_ref = paired_difference([r.avg_delay_s for r in rows], [r.avg_delay_s for r in ref])
        out[mode] = summary
    return out


def sweep_parameter(
    base: Scenario,
    name: str,
    values: list,
    seeds: list[int],
    modes: tuple[RunMode, ...],
    workers: int | None = None,
) -> dict[str, dict[RunMode, ModeSummary]]:
    """One compare_modes() per parameter value, keyed by the value."""
    return {
        str(v): compare_modes(base.with_(**{name: v}), seeds, modes, workers=workers) for v in values
    }


def run_standard_suite(seeds: list[int], base: Scenario, workers: int | None = None) -> dict:
    corridor = (RunMode.CORRIDOR_RECOVERY,)
    pre = (RunMode.NO_PREEMPTION, RunMode.NAIVE_REACTIVE, RunMode.CORRIDOR_RECOVERY)
    return {
        "scenario": asdict(base),
        "seeds": len(seeds),
        "modes": compare_modes(base, seeds, workers=workers),
        "load": sweep_parameter(base, "background_vehicles", [20, 40, 80, 140, 200], seeds, pre, workers),
        "max_hold": sweep_parameter(
            base, "corridor_max_hold_s", [5.0, 10.0, 15.0, 20.0, 30.0], seeds,
            (RunMode.NO_PREEMPTION,) + corridor, workers,
        ),
        "horizon": sweep_parameter(
            base, "corridor_horizon_s", [20.0, 40.0, 60.0, 90.0], seeds,
            (RunMode.NO_PREEMPTION,) + corridor, workers,
        ),
        "recovery_cycles": sweep_parameter(
            base, "recovery_cycles", [0, 1, 2, 3, 4], seeds,
            (RunMode.NO_PREEMPTION,) + corridor, workers,
        ),
        "slew": sweep_parameter(
            base, "slew_rate", [None, 0.4, 0.25, 0.15, 0.1], seeds,
            (RunMode.NO_PREEMPTION,) + corridor, workers,
        ),
        "reactive_trigger": sweep_parameter(
            base, "reactive_trigger_m", [100.0, 200.0, 300.0, 400.0], seeds,
            (RunMode.NO_PREEMPTION, RunMode.NAIVE_REACTIVE), workers,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=24)
    parser.add_argument("--vehicles", type=int, default=Scenario().background_vehicles)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--out", default="outputs")
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    base = Scenario(background_vehicles=args.vehicles)
    suite = run_standard_suite(seeds, base, args.workers)

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "sweep_results.json")
    with open(path, "w") as f:
        json.dump(to_jsonable(suite), f, indent=2, allow_nan=False)
    print(f"wrote {path}")

    print(f"\n{'mode':<24}{'transit (s)':>16}{'avg bg delay (s)':>20}{'max non-green (s)':>20}")
    for mode, s in suite["modes"].items():
        print(f"{mode.value:<24}{s.transit!s:>16}{s.avg_delay!s:>20}{s.max_nongreen!s:>20}")
    print("\npaired vs no_preemption (negative = better)")
    for mode, s in suite["modes"].items():
        if s.transit_vs_ref:
            print(f"{mode.value:<24}{s.transit_vs_ref!s:>16}{s.delay_vs_ref!s:>20}")


if __name__ == "__main__":
    main()
