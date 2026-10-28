"""Charts: three/four-way comparison, a red/green signal Gantt along the
ambulance's route with its position overlaid, ETA error by lead time, and
parameter-sweep plots.

See docs/BUILD-PLAN.md Step 7.
"""

import os

import matplotlib.pyplot as plt

from metrics.eta_accuracy import LeadBucket
from metrics.evaluate import ComparisonReport
from simulation.engine import RunLog, RunMode

_STATE_COLORS = {"G": "#2e8b57", "Y": "#e0a800", "R": "#c0392b"}
_MODE_COLORS = {
    RunMode.NO_PREEMPTION: "#7a7f87",
    RunMode.NAIVE_REACTIVE: "#b8741a",
    RunMode.CORRIDOR_NO_RECOVERY: "#4a7fb5",
    RunMode.CORRIDOR_RECOVERY: "#1f7a4c",
}


def plot_comparison(report: ComparisonReport, out_path: str = "outputs/comparison.png") -> None:
    modes = list(report.metrics)
    labels = [m.label for m in modes]
    colors = [_MODE_COLORS[m] for m in modes]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    panels = [
        ("Ambulance transit time", "seconds", [report.metrics[m].transit_s for m in modes]),
        ("Avg background delay", "seconds", [report.metrics[m].avg_delay_s for m in modes]),
        ("Longest non-green wait at any signal", "seconds", [report.metrics[m].max_nongreen_s for m in modes]),
    ]
    for ax, (title, ylabel, values) in zip(axes, panels):
        bars = ax.bar(labels, values, color=colors)
        ax.bar_label(bars, fmt="%.0f", padding=2)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", labelrotation=20)
    fig.tight_layout()
    _save(fig, out_path)


def plot_signal_timeline(
    log: RunLog, junction_ids: list[str], out_path: str = "outputs/signal_timeline.png"
) -> None:
    """Red/yellow/green state of each route junction's signal *on the axis the
    ambulance approaches by*, over time, with the ambulance's position
    overlaid — so a green corridor shows up as green lined up where the red
    line crosses each row."""
    fig, ax = plt.subplots(figsize=(11, 0.55 * len(junction_ids) + 1.4))

    for i, _ in enumerate(junction_ids):
        for state, color in _STATE_COLORS.items():
            spans = _state_spans(log, i, state)
            ax.broken_barh(spans, (i - 0.4, 0.8), facecolors=color, linewidth=0)

    times = [tick.t for tick in log.ticks]
    positions = [junction_ids.index(tick.ambulance_junction) for tick in log.ticks]
    ax.plot(times, positions, color="#111111", linewidth=2.0, label="Ambulance (at last junction cleared)")

    ax.set_yticks(range(len(junction_ids)))
    ax.set_yticklabels(junction_ids)
    ax.invert_yaxis()
    ax.set_xlabel("time (s)")
    ax.set_title(f"Signal state on the ambulance's approach: {log.mode.label}")
    ax.legend(loc="upper left", frameon=True)
    fig.tight_layout()
    _save(fig, out_path)


def plot_eta_accuracy(
    buckets_by_mode: dict[RunMode, list[LeadBucket]], out_path: str = "outputs/eta_accuracy.png"
) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for mode, buckets in buckets_by_mode.items():
        pts = [(b.lead_lo_s, b.mae_s) for b in buckets if b.n and b.lead_hi_s != float("inf")]
        if pts:
            ax.plot(*zip(*pts), marker="o", label=mode.label, color=_MODE_COLORS[mode])
    ax.set_xlabel("true time to junction when predicted (s)")
    ax.set_ylabel("mean absolute ETA error (s)")
    ax.set_title("ETA prediction error shrinks as the ambulance approaches")
    ax.legend()
    fig.tight_layout()
    _save(fig, out_path)


def plot_sweep(
    sweep: dict[str, dict],
    metric: str,
    x_label: str,
    out_path: str,
    title: str,
    y_label: str = "seconds",
) -> None:
    """One line per mode across a swept parameter, with 95% CI bars.
    `sweep` is metrics.sweep output: {value: {RunMode|str: ModeSummary}}."""
    xs = list(sweep)
    modes = list(next(iter(sweep.values())))
    fig, ax = plt.subplots(figsize=(7, 4))
    for mode in modes:
        mode_enum = mode if isinstance(mode, RunMode) else RunMode(mode)
        est = [getattr(sweep[x][mode], metric) for x in xs]
        ax.errorbar(
            range(len(xs)),
            [e.mean for e in est],
            yerr=[e.ci95 for e in est],
            marker="o",
            capsize=3,
            label=mode_enum.label,
            color=_MODE_COLORS[mode_enum],
        )
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels(xs)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    _save(fig, out_path)


def _state_spans(log: RunLog, junction_index: int, state: str) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    start: float | None = None
    prev_t = 0.0
    dt = log.ticks[1].t - log.ticks[0].t if len(log.ticks) > 1 else 1.0
    for tick in log.ticks:
        active = tick.approach_states[junction_index] == state
        if active and start is None:
            start = tick.t
        elif not active and start is not None:
            spans.append((start, tick.t - start))
            start = None
        prev_t = tick.t
    if start is not None:
        spans.append((start, prev_t + dt - start))
    return spans


def _save(fig, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
