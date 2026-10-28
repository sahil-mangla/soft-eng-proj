"""Computes ambulance total transit time and background-traffic delay per run,
and compares across modes (no-preemption baseline, naive-reactive, corridor
without recovery, predictive corridor + recovery).

Background delay is measured over the *same* vehicle population in every
mode: the engine runs on until every background vehicle has finished, so a
faster ambulance no longer shrinks the sample.

See docs/BUILD-PLAN.md Step 7.
"""

import math
from dataclasses import dataclass

from simulation.engine import RunLog, RunMode

# Two-sided 95% Student-t critical values, df 1..30; 1.96 beyond.
_T95 = [
    12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
    2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
    2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042,
]


@dataclass(frozen=True)
class ModeMetrics:
    transit_s: float
    avg_delay_s: float
    p95_delay_s: float
    total_delay_s: float
    unfinished: int
    max_nongreen_s: float


@dataclass(frozen=True)
class Estimate:
    """Mean over seeds with a 95% confidence half-width."""

    mean: float
    ci95: float
    n: int

    def __str__(self) -> str:
        return f"{self.mean:.1f} ± {self.ci95:.1f}"


@dataclass
class ComparisonReport:
    metrics: dict[RunMode, ModeMetrics]

    @property
    def transit_times_s(self) -> dict[RunMode, float]:
        return {m: v.transit_s for m, v in self.metrics.items()}

    @property
    def avg_background_delays_s(self) -> dict[RunMode, float]:
        return {m: v.avg_delay_s for m, v in self.metrics.items()}


def estimate(values: list[float]) -> Estimate:
    """Mean and 95% CI over the finite values. A run that never finished has a NaN
    transit time; it is left out here (and counted by the caller) instead of
    turning every aggregate into NaN."""
    values = [v for v in values if math.isfinite(v)]
    n = len(values)
    if n == 0:
        return Estimate(float("nan"), float("nan"), 0)
    mean = sum(values) / n
    if n < 2:
        return Estimate(mean, float("nan"), n)
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    t = _T95[n - 2] if n - 1 <= len(_T95) else 1.96
    return Estimate(mean, t * math.sqrt(var / n), n)


def paired_difference(a: list[float], b: list[float]) -> Estimate:
    """Mean of (a_i - b_i) over matched seeds. Pairing removes the large
    seed-to-seed variance in traffic, which is why a mode's effect on
    background delay is only visible this way."""
    if len(a) != len(b):
        raise ValueError("paired samples must be the same length")
    return estimate([x - y for x, y in zip(a, b) if math.isfinite(x) and math.isfinite(y)])


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


class MetricsEvaluator:
    @staticmethod
    def compute_transit_time(log: RunLog) -> float:
        return log.ambulance_transit_time_s if log.ambulance_transit_time_s is not None else float("nan")

    @staticmethod
    def compute_avg_delay(log: RunLog) -> float:
        if not log.background_delays_s:
            return 0.0
        return sum(log.background_delays_s) / len(log.background_delays_s)

    def summarize(self, log: RunLog) -> ModeMetrics:
        return ModeMetrics(
            transit_s=self.compute_transit_time(log),
            avg_delay_s=self.compute_avg_delay(log),
            p95_delay_s=percentile(log.background_delays_s, 0.95),
            total_delay_s=sum(log.background_delays_s),
            unfinished=log.background_unfinished,
            max_nongreen_s=log.max_nongreen_s,
        )

    def compare(self, runs: dict[RunMode, RunLog]) -> ComparisonReport:
        return ComparisonReport(metrics={mode: self.summarize(log) for mode, log in runs.items()})
