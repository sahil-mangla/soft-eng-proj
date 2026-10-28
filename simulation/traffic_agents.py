"""Generates simple background vehicle agents that move across the network
according to each junction's fixed-cycle signal, producing "normal" congestion
with no preemption logic.

Also defines the shared `Vehicle` movement model used by both background
traffic and the ambulance (simulation/engine.py) — one physics routine, so
"the ambulance obeys the same signal as everyone else, unless a mode chooses
to move the signal" stays true by construction rather than by convention.

See docs/BUILD-PLAN.md Step 2.
"""

import random
from dataclasses import dataclass

from network.generate_grid import RoadNetwork, SignalState


@dataclass
class Vehicle:
    id: str
    route: list[str]
    spawn_tick: int = 0
    edge_index: int = 0
    distance_into_edge_m: float = 0.0
    speed_mps: float = 0.0
    started: bool = False
    finished_tick: float | None = None

    @property
    def finished(self) -> bool:
        return self.finished_tick is not None

    @property
    def current_junction(self) -> str:
        return self.route[self.edge_index]

    @property
    def next_junction(self) -> str:
        return self.route[self.edge_index + 1]

    @property
    def is_on_last_edge(self) -> bool:
        return self.edge_index == len(self.route) - 2


@dataclass
class BackgroundVehicle(Vehicle):
    pass


def _random_walk_route(
    network: RoadNetwork, start: str, hops: int, rng: random.Random
) -> list[str]:
    route = [start]
    current = start
    for _ in range(hops):
        neighbors = network.neighbors(current)
        if not neighbors:
            break
        current = rng.choice(neighbors)
        route.append(current)
    return route


def spawn_background_traffic(
    network: RoadNetwork,
    count: int,
    seed: int = 42,
    min_hops: int = 3,
    max_hops: int = 8,
    spawn_window_ticks: int = 20,
) -> list[BackgroundVehicle]:
    """Simple background vehicles on random-walk routes, staggered over the
    first `spawn_window_ticks` seconds so they don't all appear at t=0. They
    carry no route-awareness of the ambulance — they just obey whatever
    signal state each junction currently shows.
    """
    rng = random.Random(seed)
    junction_ids = list(network.junctions.keys())
    vehicles = []
    for i in range(count):
        start = rng.choice(junction_ids)
        hops = rng.randint(min_hops, max_hops)
        route = _random_walk_route(network, start, hops, rng)
        if len(route) < 2:
            continue
        vehicles.append(
            BackgroundVehicle(
                id=f"bg{i}", route=route, spawn_tick=rng.randint(0, spawn_window_ticks)
            )
        )
    return vehicles


def advance_vehicle(
    vehicle: Vehicle,
    network: RoadNetwork,
    t: float,
    dt: float,
    stop_buffer_m: float = 0.5,
) -> str | None:
    """Advances a vehicle by one tick. Returns the id of a junction the
    vehicle just crossed this tick (not raised for reaching the final
    destination), so callers can hook corridor/recovery logic to a real
    "junction cleared" event.
    """
    if vehicle.finished:
        return None

    edge = network.edge(vehicle.current_junction, vehicle.next_junction)
    if not vehicle.started:
        edge.vehicle_count += 1
        vehicle.started = True

    speed = edge.current_speed_mps()
    distance_this_tick = speed * dt
    tentative = vehicle.distance_into_edge_m + distance_this_tick

    if tentative < edge.length_m:
        vehicle.distance_into_edge_m = tentative
        vehicle.speed_mps = speed
        return None

    if vehicle.is_on_last_edge:
        edge.vehicle_count = max(0, edge.vehicle_count - 1)
        vehicle.edge_index += 1
        vehicle.distance_into_edge_m = 0.0
        vehicle.speed_mps = speed
        vehicle.finished_tick = t
        return None

    junction = network.junctions[vehicle.next_junction]
    if junction.signal.state_for_axis(edge.axis, t) in (
        SignalState.GREEN,
        SignalState.YELLOW,
    ):
        overflow_m = tentative - edge.length_m
        cleared_junction = vehicle.next_junction
        edge.vehicle_count = max(0, edge.vehicle_count - 1)
        vehicle.edge_index += 1
        next_edge = network.edge(vehicle.current_junction, vehicle.next_junction)
        next_edge.vehicle_count += 1
        vehicle.distance_into_edge_m = min(overflow_m, next_edge.length_m)
        vehicle.speed_mps = speed
        return cleared_junction

    vehicle.distance_into_edge_m = edge.length_m - stop_buffer_m
    vehicle.speed_mps = 0.0
    return None
