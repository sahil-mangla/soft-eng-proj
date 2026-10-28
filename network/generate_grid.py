"""Builds a synthetic grid road network (N x N junctions, default 5x5), each
junction with a fixed-cycle signal timing plan (red/green/yellow durations).

Per docs/DECISIONS.md D1/D2: implemented as a plain networkx graph (no SUMO
dependency yet) over a synthetic grid (no OSM dependency yet). A SUMO/OSM
variant is added later, additively, once this is validated.

See docs/BUILD-PLAN.md Step 1.
"""

from dataclasses import dataclass, field
from enum import Enum

import networkx as nx

Axis = str  # "NS" or "EW"


class SignalState(Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


_STATE_SCORE = {SignalState.RED: 0, SignalState.YELLOW: 1, SignalState.GREEN: 2}


@dataclass
class CyclePlan:
    """A two-phase fixed cycle: NS green -> NS yellow -> EW green -> EW
    yellow -> repeat. Both axes never show green at once."""

    green_duration: float = 20.0
    yellow_duration: float = 3.0

    @property
    def half_cycle(self) -> float:
        return self.green_duration + self.yellow_duration

    @property
    def cycle_length(self) -> float:
        return 2 * self.half_cycle

    def phase_at(self, t: float) -> dict[Axis, SignalState]:
        """The *unshifted* fixed-cycle phase for both axes at time t."""
        phase_t = t % self.cycle_length
        if phase_t < self.green_duration:
            return {"NS": SignalState.GREEN, "EW": SignalState.RED}
        if phase_t < self.half_cycle:
            return {"NS": SignalState.YELLOW, "EW": SignalState.RED}
        if phase_t < self.half_cycle + self.green_duration:
            return {"NS": SignalState.RED, "EW": SignalState.GREEN}
        return {"NS": SignalState.RED, "EW": SignalState.YELLOW}


@dataclass
class Signal:
    """A junction's signal. `phase_offset_shift` is the single hook every
    control mode acts through: corridor coordination, naive-reactive
    preemption, and recovery all just set/decay this one number rather than
    touching signal state directly (CLAUDE.md 6.3/6.4) — that shared
    mechanism is what lets recovery ease a preemption back out instead of
    snapping to it.
    """

    cycle_plan: CyclePlan = field(default_factory=CyclePlan)
    phase_offset_shift: float = 0.0

    def state_for_axis(self, axis: Axis, t: float) -> SignalState:
        return self.cycle_plan.phase_at(t + self.phase_offset_shift)[axis]

    def best_shift_for_green(
        self,
        axis: Axis,
        arrival_t: float,
        max_shift: float,
        step: float = 1.0,
        lo: float | None = None,
        hi: float | None = None,
        anchor: float = 0.0,
    ) -> float:
        """Smallest-magnitude shift (bounded by max_shift) that makes `axis`
        as green as possible at arrival_t. This is the one routine behind
        both "extend current green" and "truncate opposing phase" — which
        of the two happens falls out of which direction of shift improves
        the score, not a separate code path.

        `lo`/`hi` optionally narrow the search band further (e.g. to the
        shifts reachable from the current one at a bounded slew rate); the
        band's own edges are always candidates so a fractional band is never
        missed by the 1s grid.

        `anchor` is the shift the search prefers to stay near (the junction's
        current one). Ranking candidates by distance from the anchor rather
        than from zero is the hysteresis that stops a jittering ETA from
        flipping a junction between, say, -12s and +11s tick to tick.
        """
        cycle = self.cycle_plan
        low = -max_shift if lo is None else max(lo, -max_shift)
        high = max_shift if hi is None else min(hi, max_shift)
        if low > high:
            return (low + high) / 2.0

        n = int(max_shift / step + 1e-9)
        grid = {0.0} | {k * step for k in range(1, n + 1)} | {-k * step for k in range(1, n + 1)}
        candidates = sorted(
            (c for c in grid | {low, high, anchor} if low - 1e-9 <= c <= high + 1e-9),
            key=lambda c: (round(abs(c - anchor), 9), abs(c), c < 0),
        )
        best_shift = candidates[0]
        best_score = -1
        for c in candidates:
            score = _STATE_SCORE[cycle.phase_at(arrival_t + c)[axis]]
            if score > best_score:
                best_score, best_shift = score, c
                if score == _STATE_SCORE[SignalState.GREEN]:
                    break
        return best_shift


@dataclass
class Junction:
    id: str
    row: int
    col: int
    signal: Signal = field(default_factory=Signal)


@dataclass
class Edge:
    u: str
    v: str
    axis: Axis
    length_m: float
    free_flow_speed_mps: float = 13.9  # ~50 km/h
    vehicle_count: int = 0
    # Stop-line queue: ids of vehicles waiting to cross at v, in arrival order,
    # and the earliest time the next vehicle may cross (discharge headway).
    queue: list[str] = field(default_factory=list)
    next_release_t: float = 0.0

    def current_speed_mps(self, congestion_k: float = 0.15) -> float:
        return self.free_flow_speed_mps / (1.0 + congestion_k * self.vehicle_count)


@dataclass
class RoadNetwork:
    junctions: dict[str, Junction]
    edges: dict[tuple[str, str], Edge]
    graph: nx.DiGraph
    spacing_m: float = 200.0
    # Seconds between successive vehicles crossing a stop line (saturation
    # flow ~1800 veh/h/lane = 2.0s). 0 disables queue discharge limits.
    discharge_headway_s: float = 2.0

    def xy(self, junction_id: str) -> tuple[float, float]:
        """Metre coordinates of a junction (x east, y south), for rendering."""
        j = self.junctions[junction_id]
        return (j.col * self.spacing_m, j.row * self.spacing_m)

    def position_xy(self, u: str, v: str, distance_m: float) -> tuple[float, float]:
        """Point `distance_m` along the edge u -> v."""
        (x0, y0), (x1, y1) = self.xy(u), self.xy(v)
        f = min(max(distance_m / self.edges[(u, v)].length_m, 0.0), 1.0)
        return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)

    def edge(self, u: str, v: str) -> Edge:
        return self.edges[(u, v)]

    def neighbors(self, junction_id: str) -> list[str]:
        return list(self.graph.successors(junction_id))


def _junction_id(row: int, col: int) -> str:
    return f"J{row}_{col}"


def generate_grid(
    n: int = 5,
    edge_length_m: float = 200.0,
    green_duration: float = 20.0,
    yellow_duration: float = 3.0,
    discharge_headway_s: float = 2.0,
) -> RoadNetwork:
    """Build an n x n synthetic grid network (per DECISIONS.md D2). Every
    junction gets its own independent Signal instance, so corridor
    coordination/recovery can shift one junction's phase without affecting
    its neighbors.
    """
    junctions: dict[str, Junction] = {}
    for r in range(n):
        for c in range(n):
            jid = _junction_id(r, c)
            junctions[jid] = Junction(
                id=jid,
                row=r,
                col=c,
                signal=Signal(cycle_plan=CyclePlan(green_duration, yellow_duration)),
            )

    graph = nx.DiGraph()
    graph.add_nodes_from(junctions)

    edges: dict[tuple[str, str], Edge] = {}

    def add_bidirectional(u: str, v: str, axis: Axis) -> None:
        for a, b in ((u, v), (v, u)):
            edges[(a, b)] = Edge(u=a, v=b, axis=axis, length_m=edge_length_m)
            graph.add_edge(a, b)

    for r in range(n):
        for c in range(n):
            jid = _junction_id(r, c)
            if c + 1 < n:
                add_bidirectional(jid, _junction_id(r, c + 1), axis="EW")
            if r + 1 < n:
                add_bidirectional(jid, _junction_id(r + 1, c), axis="NS")

    return RoadNetwork(junctions=junctions, edges=edges, graph=graph, spacing_m=edge_length_m, discharge_headway_s=discharge_headway_s)
