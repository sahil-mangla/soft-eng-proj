# Frontend

`index.html` + `app.js`: replays a four-mode run on the signal grid and compares the
modes. Vanilla JS and SVG, no build step. Theme: Cobalt (Hallmark), light and dark.

- Served by `python -m api.server` at `http://127.0.0.1:8000/` (live scenarios), or open
  `index.html` from disk for the fixed sample run (`python -m api.export` writes
  `data/sample.js`; it is generated, not committed).
- State lives in the URL: `?seed=7&vehicles=200&mode=naive_reactive&t=150&speed=16`.

## What is on the screen

| Element | Purpose |
| --- | --- |
| Mode buttons with transit time | Switch control mode at the same moment in the replay |
| Graphite readout | The finding in one sentence; adds the multi-seed verdict once compared |
| Signal grid | Red/green/yellow per direction, shifted junctions ringed, stopped vehicles, live seconds-to-arrival tags on the route |
| Junction detail | Click or Enter on a junction: signal state, phase shift, predicted vs actual arrival, how long green led the ambulance. Esc closes and returns focus |
| Signal timeline | Approach-axis state per route junction over time; click to seek |
| Ledger | Four modes with deltas coloured by whether they helped; Export CSV for the report |
| Across seeds | 12-seed means with CIs, and one bar per seed for transit and background delay |
| Presets | Light (40), Typical (80), Rush hour (200) vehicles |
| Appearance | Light, Dark, System (remembered in the browser) |

Design references reviewed (ObsidianUI analytics dashboard and components, RewampUI): adopted
the delta semantics, rolling figures, range-style presets, details panel behaviour, status-bar
strips, export and appearance setting; skipped sparkline KPI cards, sidebar pages, assistant
composer and decorative effects (see docs/DECISIONS.md F2).

The Coral and Blueprint design mocks were removed after review; they live in git history at
commit `13fcc6b`.
