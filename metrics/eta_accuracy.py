"""ETA prediction accuracy (BUILD-PLAN Step 3 validation): how far off the
per-junction arrival prediction was, as a function of how close the
ambulance actually was to that junction when the prediction was made.

Every tick the engine logs (t, junction, predicted absolute arrival); the
actual arrival is the tick the ambulance crossed that junction (so the
comparison resolves to one simulation tick, `dt`).
"""

from dataclasses import dataclass

from simulation.engine import RunLog

DEFAULT_BINS_S = (0.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0, float("inf"))


@dataclass(frozen=True)
class LeadBucket:
    lead_lo_s: float
    lead_hi_s: float
    n: int
    mae_s: float  # mean absolute error
    bias_s: float  # mean signed error; positive = predicted late


def eta_error_by_lead(log: RunLog, bins: tuple[float, ...] = DEFAULT_BINS_S) -> list[LeadBucket]:
    """Buckets prediction error by true time-to-go at prediction time."""
    errors: list[list[float]] = [[] for _ in range(len(bins) - 1)]
    for t, junction_id, predicted_arrival in log.eta_samples:
        actual = log.actual_arrival_s.get(junction_id)
        if actual is None:
            continue
        lead = actual - t
        if lead < 0:
            continue
        for i in range(len(bins) - 1):
            if bins[i] <= lead < bins[i + 1]:
                errors[i].append(predicted_arrival - actual)
                break
    out = []
    for i, errs in enumerate(errors):
        n = len(errs)
        out.append(
            LeadBucket(
                lead_lo_s=bins[i],
                lead_hi_s=bins[i + 1],
                n=n,
                mae_s=sum(abs(e) for e in errs) / n if n else float("nan"),
                bias_s=sum(errs) / n if n else float("nan"),
            )
        )
    return out
