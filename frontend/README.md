# Frontend

`app.js` replays a four-mode run on the signal grid (map, red/green signal timeline,
mode ledger, ETA error). It reads `/api/replay` from `python -m api.server`, or
`data/sample.js` (`python -m api.export`) when opened from disk.

Three Hallmark design mocks share that code and differ only in theme CSS and layout:

| Mock | Theme | Layout | Signal language |
| --- | --- | --- | --- |
| `mocks/cobalt.html` | Cobalt: cool paper, keycaps, cut corners | console (rail, map, ledger) | green, yellow, red |
| `mocks/blueprint.html` | Blueprint: cyanotype sheet, keylines, square | sheet (map, schedule, title block) | line weight and dash, no hue |
| `mocks/coral.html` | Coral: cotton stock on felt, letterpress | desk (cards and a groove switch) | green, yellow, red |

Open them via the server (`http://127.0.0.1:8000/mocks/cobalt.html`) to change the
scenario, or directly from disk for the fixed sample run. `?t=150` starts at a given second.
After a mock is chosen, the others and `frontend/mocks/` are removed.
