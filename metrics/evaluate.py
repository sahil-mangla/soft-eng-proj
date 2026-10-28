"""Computes ambulance total transit time and average background-traffic delay
per run, and compares across modes (no-preemption baseline, naive-reactive,
predictive corridor + recovery).

See docs/BUILD-PLAN.md Step 7.
"""

from dataclasses import dataclass

from simulation.engine import RunLog, RunMode


@dataclass
class ComparisonReport:
    transit_times_s: dict[RunMode, float]
    avg_background_delays_s: dict[RunMode, float]


class MetricsEvaluator:
    @staticmethod
    def compute_transit_time(log: RunLog) -> float:
        return log.ambulance_transit_time_s if log.ambulance_transit_time_s is not None else float("nan")

    @staticmethod
    def compute_avg_delay(log: RunLog) -> float:
        if not log.background_delays_s:
            return 0.0
        return sum(log.background_delays_s) / len(log.background_delays_s)

    def compare(self, runs: dict[RunMode, RunLog]) -> ComparisonReport:
        return ComparisonReport(
            transit_times_s={mode: self.compute_transit_time(log) for mode, log in runs.items()},
            avg_background_delays_s={mode: self.compute_avg_delay(log) for mode, log in runs.items()},
        )
