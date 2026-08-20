"""Builds a synthetic grid road network (N x N junctions, default 5x5), each
junction with a fixed-cycle signal timing plan (red/green/yellow durations).

Per docs/DECISIONS.md D1/D2: implemented as a plain networkx graph (no SUMO
dependency yet) over a synthetic grid (no OSM dependency yet). A SUMO/OSM
variant is added later, additively, once this is validated.

See docs/BUILD-PLAN.md Step 1.
"""
