"""Given the ambulance's current position/speed and route, estimates
seconds-to-arrival at each upcoming junction. Updated on a rolling basis (every
simulation tick or every N meters traveled) as the ambulance moves, not just
once at t=0.

See docs/BUILD-PLAN.md Step 3, CLAUDE.md section 6.2.
"""

from core.router import Route


class ETAPredictor:
    """Recomputed every tick against each edge's *current* congestion-adjusted
    speed (not a static free-flow assumption), so the prediction sharpens as
    the ambulance gets closer and conditions along the route change.
    """

    def predict(
        self, route: Route, current_edge_index: int, distance_into_edge_m: float
    ) -> dict[str, float]:
        etas: dict[str, float] = {}
        elapsed = 0.0
        for i, edge in enumerate(route.edges):
            if i < current_edge_index:
                continue
            remaining_m = (
                edge.length_m - distance_into_edge_m
                if i == current_edge_index
                else edge.length_m
            )
            elapsed += remaining_m / edge.current_speed_mps()
            etas[route.junction_ids[i + 1]] = elapsed
        return etas
