"""For each junction ahead of the ambulance on its route, schedules a green
phase timed to the ETA prediction, bounded by a maximum hold time for
perpendicular/cross traffic (threshold-based rule: extend current phase or
truncate opposing phase by at most X seconds).

This is the core novel logic of the project. See docs/BUILD-PLAN.md Step 4,
CLAUDE.md section 6.3.
"""

from network.generate_grid import Axis, RoadNetwork


class CorridorCoordinator:
    """Schedules a green phase at every upcoming junction within the
    coordination horizon, capped at `max_hold_s` so cross-traffic is never
    starved beyond that bound — the guardrail CLAUDE.md 6.3 calls for before
    any more sophisticated optimization.
    """

    def __init__(
        self, network: RoadNetwork, horizon_s: float = 60.0, max_hold_s: float = 15.0
    ):
        self.network = network
        self.horizon_s = horizon_s
        self.max_hold_s = max_hold_s

    def coordinate(
        self,
        t: float,
        etas: dict[str, float],
        approach_axis_by_junction: dict[str, Axis],
    ) -> None:
        for junction_id, eta_s in etas.items():
            if eta_s > self.horizon_s:
                continue
            junction = self.network.junctions[junction_id]
            axis = approach_axis_by_junction[junction_id]
            shift = junction.signal.best_shift_for_green(
                axis, t + eta_s, max_shift=self.max_hold_s
            )
            junction.signal.phase_offset_shift = shift
