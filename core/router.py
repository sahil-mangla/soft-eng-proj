"""Shortest-TIME (not shortest-distance) path computation for the ambulance,
weighting edges by current travel time given traffic density. Recomputes if
conditions change materially.

See docs/BUILD-PLAN.md Step 2, CLAUDE.md section 6.1.
"""

from dataclasses import dataclass

import networkx as nx

from network.generate_grid import Edge, RoadNetwork


@dataclass
class Route:
    junction_ids: list[str]
    network: RoadNetwork

    @property
    def edges(self) -> list[Edge]:
        return [
            self.network.edge(u, v)
            for u, v in zip(self.junction_ids[:-1], self.junction_ids[1:])
        ]

    def total_length_m(self) -> float:
        return sum(e.length_m for e in self.edges)


def compute_route(network: RoadNetwork, start: str, end: str) -> Route:
    """Shortest-time path: edge weight is length / current congestion-adjusted
    speed, not raw distance, so a busier route can lose out to a longer but
    faster one.
    """

    def weight(u: str, v: str, _data: dict) -> float:
        edge = network.edge(u, v)
        return edge.length_m / edge.current_speed_mps()

    path = nx.shortest_path(network.graph, start, end, weight=weight)
    return Route(junction_ids=path, network=network)
