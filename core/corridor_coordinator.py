"""For each junction ahead of the ambulance on its route, schedules a green
phase timed to the ETA prediction, bounded by a maximum hold time for
perpendicular/cross traffic (threshold-based rule: extend current phase or
truncate opposing phase by at most X seconds).

This is the core novel logic of the project. See docs/BUILD-PLAN.md Step 4,
CLAUDE.md section 6.3.
"""

from collections.abc import Callable

from network.generate_grid import Axis, RoadNetwork


class CorridorCoordinator:
    """Schedules a green phase at every upcoming junction within the
    coordination horizon, capped at `max_hold_s` so cross-traffic is never
    starved beyond that bound — the guardrail CLAUDE.md 6.3 calls for before
    any more sophisticated optimization.

    `slew_rate` (seconds of phase shift per second, None = off) is what the
    prediction buys over a reactive controller. With it off, a junction's
    phase jumps to its target the moment the ambulance enters the horizon.
    With it on, the shift is walked toward the target at a bounded rate, and
    the target is restricted to shifts reachable before the predicted arrival
    — so the lead time is spent easing the signal over, not snapping it.
    """

    def __init__(
        self,
        network: RoadNetwork,
        horizon_s: float = 60.0,
        max_hold_s: float = 15.0,
        slew_rate: float | None = None,
        set_shift: Callable[[str, float], None] | None = None,
    ):
        """`set_shift(junction_id, value)` is where shifts are written. The engine
        passes its guarded writer (signal-safety and starvation bounds); left
        unset, the coordinator writes the signal directly."""
        self._set_shift = set_shift
        self.network = network
        self.horizon_s = horizon_s
        self.max_hold_s = max_hold_s
        self.slew_rate = slew_rate

    def coordinate(
        self,
        t: float,
        etas: dict[str, float],
        approach_axis_by_junction: dict[str, Axis],
        dt: float = 1.0,
    ) -> None:
        for junction_id, eta_s in etas.items():
            if eta_s > self.horizon_s:
                continue
            signal = self.network.junctions[junction_id].signal
            axis = approach_axis_by_junction[junction_id]

            if self.slew_rate is None:
                self._apply(junction_id, signal.best_shift_for_green(
                    axis,
                    t + eta_s,
                    max_shift=self.max_hold_s,
                    anchor=signal.phase_offset_shift,
                ))
                continue

            current = signal.phase_offset_shift
            reach = self.slew_rate * eta_s
            target = signal.best_shift_for_green(
                axis,
                t + eta_s,
                max_shift=self.max_hold_s,
                lo=current - reach,
                hi=current + reach,
                anchor=current,
            )
            max_step = self.slew_rate * dt
            self._apply(junction_id, current + max(-max_step, min(max_step, target - current)))

    def _apply(self, junction_id: str, value: float) -> None:
        if self._set_shift is not None:
            self._set_shift(junction_id, value)
        else:
            self.network.junctions[junction_id].signal.phase_offset_shift = value
