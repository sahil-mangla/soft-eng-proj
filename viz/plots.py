"""Before/after comparison charts, plus a Gantt-style hold timeline per
junction with the ambulance's position overlaid.

See docs/BUILD-PLAN.md Step 7.
"""

import os

import matplotlib.pyplot as plt

from metrics.evaluate import ComparisonReport
from simulation.engine import RunLog, RunMode

_MODE_LABELS = {
    RunMode.NO_PREEMPTION: "No preemption",
    RunMode.NAIVE_REACTIVE: "Naive reactive",
    RunMode.CORRIDOR_RECOVERY: "Corridor + recovery",
}


def plot_comparison(report: ComparisonReport, out_path: str = "outputs/comparison.png") -> None:
    modes = list(report.transit_times_s.keys())
    labels = [_MODE_LABELS[m] for m in modes]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].bar(labels, [report.transit_times_s[m] for m in modes], color="#1f7a4c")
    axes[0].set_title("Ambulance transit time")
    axes[0].set_ylabel("seconds")

    axes[1].bar(labels, [report.avg_background_delays_s[m] for m in modes], color="#a9701a")
    axes[1].set_title("Avg background traffic delay")
    axes[1].set_ylabel("seconds")

    fig.tight_layout()
    _save(fig, out_path)


def plot_signal_timeline(
    log: RunLog, junction_ids: list[str], out_path: str = "outputs/signal_timeline.png"
) -> None:
    """Shows, per junction on the ambulance's route, the intervals where its
    signal was actively shifted (held/preempted) away from its normal
    fixed-cycle schedule, with the ambulance's junction-by-junction position
    overlaid on the same time axis.
    """
    fig, ax = plt.subplots(figsize=(10, 0.6 * len(junction_ids) + 1))

    for i, junction_id in enumerate(junction_ids):
        held_intervals = _held_intervals(log, junction_id)
        ax.broken_barh(held_intervals, (i - 0.4, 0.8), facecolors="#1f7a4c")

    times = [tick.t for tick in log.ticks]
    positions = [junction_ids.index(tick.ambulance_junction) for tick in log.ticks]
    ax.plot(times, positions, color="#c0392b", linewidth=1.5, label="Ambulance")

    ax.set_yticks(range(len(junction_ids)))
    ax.set_yticklabels(junction_ids)
    ax.set_xlabel("time (s)")
    ax.set_title("Signal-hold timeline along ambulance route")
    ax.legend(loc="upper right")
    fig.tight_layout()
    _save(fig, out_path)


def _held_intervals(log: RunLog, junction_id: str) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    start: float | None = None
    for tick in log.ticks:
        held = abs(tick.junction_shifts.get(junction_id, 0.0)) > 1e-6
        if held and start is None:
            start = tick.t
        elif not held and start is not None:
            intervals.append((start, tick.t - start))
            start = None
    if start is not None:
        intervals.append((start, log.ticks[-1].t - start))
    return intervals


def _save(fig, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
