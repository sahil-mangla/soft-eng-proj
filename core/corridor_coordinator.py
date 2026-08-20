"""For each junction ahead of the ambulance on its route, schedules a green
phase timed to the ETA prediction, bounded by a maximum hold time for
perpendicular/cross traffic (threshold-based rule: extend current phase or
truncate opposing phase by at most X seconds).

This is the core novel logic of the project. See docs/BUILD-PLAN.md Step 4,
CLAUDE.md section 6.3.
"""
