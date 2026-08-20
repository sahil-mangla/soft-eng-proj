"""Given the ambulance's current position/speed and route, estimates
seconds-to-arrival at each upcoming junction. Updated on a rolling basis (every
simulation tick or every N meters traveled) as the ambulance moves, not just
once at t=0.

See docs/BUILD-PLAN.md Step 3, CLAUDE.md section 6.2.
"""
