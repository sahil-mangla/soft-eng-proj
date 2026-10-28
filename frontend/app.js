/* Green corridor frontend: replays a simulated ambulance run on the signal
 * grid and compares the four control modes. Colours live in CSS (classes
 * only here); data comes from /api/replay, or from window.__REPLAY__ (made by
 * `python -m api.export`) when opened from disk. */
(() => {
  'use strict';

  const MODES = ['no_preemption', 'naive_reactive', 'corridor_no_recovery', 'corridor_recovery'];
  const MODE_LABEL = {
    no_preemption: 'No preemption',
    naive_reactive: 'Naive reactive',
    corridor_no_recovery: 'Corridor, no recovery',
    corridor_recovery: 'Corridor and recovery',
  };
  const MODE_NOTE = {
    no_preemption: 'Signals keep their fixed cycle.',
    naive_reactive: 'Forces green within 200 m, resets at once.',
    corridor_no_recovery: 'Greens timed to the predicted arrival, then resets at once.',
    corridor_recovery: 'Greens timed to the predicted arrival, then eased back to the cycle.',
  };
  const PARAMS = [
    { key: 'seed', label: 'Seed', min: 0, max: 10000, step: 1, def: 42 },
    { key: 'vehicles', label: 'Vehicles', min: 0, max: 400, step: 10, def: 80 },
    { key: 'hold', label: 'Max hold (s)', min: 0, max: 40, step: 1, def: 15 },
    { key: 'horizon', label: 'Look-ahead (s)', min: 10, max: 180, step: 5, def: 60 },
    { key: 'recovery', label: 'Recovery cycles', min: 0, max: 6, step: 1, def: 2 },
    { key: 'trigger', label: 'Trigger (m)', min: 50, max: 400, step: 10, def: 200 },
  ];
  const SLEW = [
    ['', 'Off, shift at once'],
    ['0.4', 'Eased, 0.4 s per s'],
    ['0.25', 'Eased, 0.25 s per s'],
    ['0.15', 'Eased, 0.15 s per s'],
  ];
  const PRESETS = [['Light', 40], ['Typical', 80], ['Rush hour', 200]];
  const STATE_WORD = { G: 'Green', Y: 'Yellow', R: 'Red' };
  const APPEARANCE_KEY = 'green-corridor-appearance';
  const NS = 'http://www.w3.org/2000/svg';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const svgEl = (tag, attrs = {}, parent) => {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  };
  // Figures arrive as null when a run never finished (JSON has no NaN), so every formatter accepts null.
  const ok = (n) => n != null && Number.isFinite(n);
  const f0 = (n) => (ok(n) ? Math.round(n).toString() : 'n/a');
  const f1 = (n) => (ok(n) ? n.toFixed(1) : 'n/a');
  const NB = '\u202f'; // narrow no-break space keeps a figure and its unit together
  const sec = (n) => (ok(n) ? `${Math.round(n)}${NB}s` : 'n/a');
  const sec1 = (n) => (ok(n) ? `${n.toFixed(1)}${NB}s` : 'n/a');
  const signed = (n, digits = 1) => (!ok(n) ? 'n/a' : (n > 0 ? '+' : n < 0 ? '\u2212' : '') + Math.abs(n).toFixed(digits));

  const state = {
    replay: null,
    compare: null,
    mode: 'corridor_recovery',
    pos: 0,
    playing: false,
    speed: 4,
    status: 'loading', // loading | ready | error
    source: 'api', // api | sample
    error: '',
    map: null,
    last: 0,
    params: null,
    sel: null,
    opener: null,
    shownTransit: null,
    maxShift: {},
  };

  /* ---- URL state ---------------------------------------------------- */
  function readUrl() {
    const q = new URLSearchParams(location.search);
    const values = {};
    for (const p of PARAMS) values[p.key] = q.has(p.key) ? q.get(p.key) : String(p.def);
    values.slew = q.get('slew') || '';
    const mode = q.get('mode');
    if (MODES.includes(mode)) state.mode = mode;
    const at = Number(q.get('t'));
    state.startAt = Number.isFinite(at) && at > 0 ? at : 0;
    const speed = Number(q.get('speed'));
    if ([1, 4, 16].includes(speed)) state.speed = speed;
    return values;
  }
  function writeUrl(values) {
    const q = new URLSearchParams();
    for (const p of PARAMS) if (String(values[p.key]) !== String(p.def)) q.set(p.key, values[p.key]);
    if (values.slew) q.set('slew', values.slew);
    if (state.mode !== 'corridor_recovery') q.set('mode', state.mode);
    if (state.speed !== 4) q.set('speed', state.speed);
    const s = q.toString();
    history.replaceState(null, '', s ? `?${s}` : location.pathname);
  }

  /* ---- shell -------------------------------------------------------- */
  function field(p) {
    return `<label class="field"><span class="field__label">${p.label}</span>
      <input class="input num" type="number" name="${p.key}" min="${p.min}" max="${p.max}" step="${p.step}" inputmode="numeric"></label>`;
  }

  function shell() {
    const group = (title, keys, extra = '') => `<fieldset class="group"><legend class="group__title">${title}</legend>
      ${keys.map((k) => field(PARAMS.find((p) => p.key === k))).join('')}${extra}</fieldset>`;
    const slew = SLEW.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
    document.getElementById('app').innerHTML = `
      <a class="skip" href="#stage">Skip to the replay</a>
      <header class="topbar">
        <div class="topbar__brand">
          <h1 class="brand">Green corridor</h1>
          <p class="topbar__sub">Predictive signal coordination for emergency vehicles, simulated on a 5 by 5 grid</p>
        </div>
        <div class="topbar__right">
          <p class="topbar__status" id="status" role="status"></p>
          <div class="seg" role="radiogroup" aria-label="Appearance" id="appearance">
            <button type="button" class="seg__btn" role="radio" data-pref="light">Light</button>
            <button type="button" class="seg__btn" role="radio" data-pref="dark">Dark</button>
            <button type="button" class="seg__btn" role="radio" data-pref="system">System</button>
          </div>
        </div>
      </header>
      <main class="shell" id="shell">
        <section class="panel params" aria-labelledby="h-params">
          <h2 id="h-params" class="panel__title">Scenario</h2>
          <div class="presets" role="radiogroup" aria-label="Traffic preset" id="presets">
            ${PRESETS.map(([name, n]) => `<button type="button" class="mode" role="radio" aria-checked="false" data-vehicles="${n}"><span class="mode__name">${name}</span><span class="mode__fig num">${n}</span></button>`).join('')}
          </div>
          <form id="params" class="fields" autocomplete="off">
            ${group('Traffic', ['seed', 'vehicles'])}
            ${group('Corridor controller', ['hold', 'horizon', 'recovery'],
              `<label class="field field--wide"><span class="field__label">Signal shift</span><select class="input" name="slew">${slew}</select></label>`)}
            ${group('Reactive baseline', ['trigger'])}
            <div class="field field--wide">
              <button class="btn btn--primary" type="submit" id="run">Run scenario</button>
              <p class="hint" id="run-hint" aria-live="polite"></p>
            </div>
          </form>
        </section>

        <div class="main">
          <section class="panel stage" id="stage" aria-labelledby="h-stage">
            <h2 id="h-stage" class="panel__title">Replay</h2>
            <div class="modes" role="radiogroup" aria-label="Control mode" id="modes"></div>
            <p class="mode-note" id="mode-note"></p>
            <div class="readout" id="readout" aria-live="polite">
              <p class="readout__head" id="readout-head"></p>
              <p class="readout__body" id="readout-body"></p>
            </div>
            <div class="map" id="map" data-state="loading">
              <div class="map__skeleton" aria-hidden="true"></div>
              <div class="map__error" role="alert"><p id="map-error"></p><button class="btn" type="button" id="retry">Try again</button></div>
              <svg class="map__svg" id="map-svg" role="img" aria-label="Signal grid with the ambulance route"></svg>
            </div>
            <div class="legend" aria-hidden="true">
              <span class="legend__item"><i class="swatch swatch--go"></i>Green</span>
              <span class="legend__item"><i class="swatch swatch--amber"></i>Yellow</span>
              <span class="legend__item"><i class="swatch swatch--stop"></i>Red</span>
              <span class="legend__item"><i class="swatch swatch--held"></i>Phase shifted by the controller</span>
              <span class="legend__item"><i class="swatch swatch--queue"></i>Stopped vehicle</span>
              <span class="legend__item"><span class="legend__fig num">12 s</span>Predicted arrival of the ambulance</span>
            </div>
            <div class="transport" id="transport">
              <button class="btn btn--primary" type="button" id="play" aria-label="Play replay">Play</button>
              <button class="btn" type="button" id="restart">Restart</button>
              <input class="scrub" type="range" id="scrub" min="0" max="0" step="1" value="0" aria-label="Replay time">
              <output class="clock num" id="clock" for="scrub">0 s</output>
              <label class="speed"><span class="visually-hidden">Playback speed</span>
                <select class="input" id="speed"><option value="1">1×</option><option value="4">4×</option><option value="16">16×</option></select></label>
            </div>
          </section>

          <section class="panel timeline" aria-labelledby="h-time">
            <h2 id="h-time" class="panel__title">Signal on the ambulance's approach</h2>
            <div id="gantt" class="gantt"></div>
          </section>
        </div>

        <div class="side">
          <section class="panel detail" id="detail" aria-labelledby="h-detail" hidden>
            <div class="panel__head"><h2 id="h-detail" class="panel__title">Junction</h2>
              <button class="btn" type="button" id="detail-close">Close</button></div>
            <dl class="facts" id="facts"></dl>
          </section>

          <section class="panel ledger" aria-labelledby="h-ledger">
            <div class="panel__head"><h2 id="h-ledger" class="panel__title">Four modes, one scenario</h2>
              <button class="btn" type="button" id="export">Export CSV</button></div>
            <div id="ledger"></div>
            <div id="seeds" class="seeds"></div>
          </section>

          <section class="panel eta" aria-labelledby="h-eta">
            <h2 id="h-eta" class="panel__title">ETA error by time to junction</h2>
            <div id="eta"></div>
          </section>
        </div>
      </main>`;
  }

  function fillForm(values) {
    const form = $('#params');
    for (const [k, v] of Object.entries(values)) if (form.elements[k]) form.elements[k].value = v;
  }
  function readForm() {
    const form = $('#params');
    const values = {};
    for (const p of PARAMS) {
      const raw = form.elements[p.key].value;
      const n = Number(raw);
      values[p.key] = raw === '' || Number.isNaN(n) ? p.def : Math.min(p.max, Math.max(p.min, n));
    }
    values.slew = form.elements.slew.value;
    return values;
  }

  /* ---- loading ------------------------------------------------------ */
  async function load(values) {
    state.params = { ...values }; // the scenario the replay on screen belongs to
    state.status = 'loading';
    state.playing = false;
    paintStatus();
    const qs = new URLSearchParams(values).toString();
    try {
      if (location.protocol === 'file:') throw new Error('file');
      const res = await fetch(`/api/replay?${qs}`);
      if (!res.ok) {
        // The server is there and said no: show its reason, not stand-in data.
        const refused = new Error((await res.json().catch(() => ({}))).error || res.statusText);
        refused.refused = true;
        throw refused;
      }
      state.replay = await res.json();
      state.source = 'api';
      state.compare = null;
    } catch (err) {
      if (err.refused) {
        state.status = 'error';
        state.error = `The simulation rejected these settings: ${err.message}.`;
        paintStatus();
        return;
      }
      if (window.__REPLAY__) {
        state.replay = window.__REPLAY__;
        state.compare = window.__COMPARE__ || null;
        state.source = 'sample';
      } else {
        state.status = 'error';
        state.error = 'The simulation server is not running. Start it with: python -m api.server';
        paintStatus();
        return;
      }
    }
    state.status = 'ready';
    state.sel = null;
    state.maxShift = {};
    $('#detail').hidden = true;
    state.pos = state.startAt || 0;
    state.startAt = 0;
    state.map = null;
    paintAll();
  }

  /* ---- map ---------------------------------------------------------- */
  const modeRoute = () => state.replay.modes[state.mode].route;

  function buildMap() {
    const { network, route } = state.replay;
    const svg = $('#map-svg');
    svg.replaceChildren();
    const xs = network.junctions.map((j) => j.x);
    const ys = network.junctions.map((j) => j.y);
    const pad = network.spacing_m * 0.42;
    const x0 = Math.min(...xs) - pad, y0 = Math.min(...ys) - pad;
    const w = Math.max(...xs) - Math.min(...xs) + pad * 2;
    const h = Math.max(...ys) - Math.min(...ys) + pad * 2;
    svg.setAttribute('viewBox', `${x0} ${y0} ${w} ${h}`);
    const byId = Object.fromEntries(network.junctions.map((j) => [j.id, j]));

    const roads = svgEl('g', { class: 'roads' }, svg);
    for (const [u, v] of network.edges) {
      svgEl('line', { class: 'road', x1: byId[u].x, y1: byId[u].y, x2: byId[v].x, y2: byId[v].y }, roads);
    }
    const routeLine = svgEl('polyline', { class: 'route' }, svg);

    const jg = svgEl('g', { class: 'junctions' }, svg);
    const junctionNodes = network.junctions.map((j) => {
      const g = svgEl('g', { class: 'jn', 'data-id': j.id, tabindex: 0, role: 'button', 'aria-label': `Junction ${j.id}, show details`, transform: `translate(${j.x} ${j.y})` }, jg);
      svgEl('circle', { class: 'jn__held', r: 78 }, g);
      svgEl('rect', { class: 'jn__box', x: -44, y: -44, width: 88, height: 88 }, g);
      const ns = svgEl('line', { class: 'sig sig--ns s-R', x1: 0, y1: -32, x2: 0, y2: 32 }, g);
      const ew = svgEl('line', { class: 'sig sig--ew s-R', x1: -32, y1: 0, x2: 32, y2: 0 }, g);
      return { id: j.id, g, ns, ew, held: $('.jn__held', g) };
    });
    for (const [idx, label] of [[0, 'A'], [route.length - 1, 'B']]) {
      const j = byId[route[idx]];
      const t = svgEl('text', { class: 'tag', x: j.x, y: j.y - 66, 'text-anchor': 'middle' }, svg);
      t.textContent = label === 'A' ? 'Start' : 'Hospital';
    }
    const etaIds = [...new Set(Object.values(state.replay.modes).flatMap((m) => Object.keys(m.eta.predicted)))];
    const etaNodes = etaIds.map((id) => {
      const j = byId[id];
      return { id, node: svgEl('text', { class: 'eta-tag num', x: j.x + 58, y: j.y - 50 }, svg) };
    });
    const vehicles = svgEl('g', { class: 'vehicles' }, svg);
    const amb = svgEl('g', { class: 'amb' }, svg);
    svgEl('circle', { class: 'amb__ring', r: 54 }, amb);
    svgEl('circle', { class: 'amb__dot', r: 36 }, amb);
    svgEl('path', { class: 'amb__plus', d: 'M0 -20V20M-20 0H20' }, amb);
    state.map = { junctionNodes, vehicles, amb, pool: [], etaNodes, routeLine, byId };
    paintRoute();
  }

  function paintRoute() {
    const m = state.map;
    if (!m) return;
    m.routeLine.setAttribute('points', modeRoute().map((id) => `${m.byId[id].x},${m.byId[id].y}`).join(' '));
  }

  function drawFrame(pos) {
    const m = state.map;
    if (!m) return;
    const fr = state.replay.modes[state.mode].frames;
    const i = Math.max(0, Math.min(fr.t.length - 1, Math.floor(pos)));
    const j = Math.min(fr.t.length - 1, i + 1);
    const f = pos - i;
    const nsRow = fr.ns[i], ewRow = fr.ew[i], shifts = fr.shifts[i];
    m.junctionNodes.forEach((n, k) => {
      n.ns.setAttribute('class', `sig sig--ns s-${nsRow[k]}`);
      n.ew.setAttribute('class', `sig sig--ew s-${ewRow[k]}`);
      n.held.style.display = Math.abs(shifts[k]) > 0.5 ? '' : 'none';
    });
    const tNow = fr.t[i];
    const etaData = state.replay.modes[state.mode].eta.predicted;
    for (const { id, node } of m.etaNodes) {
      const e = (etaData[id] || [])[Math.floor(tNow / 2)];
      const left = e ? e[1] - tNow : -1;
      if (left < 0 || left > 90) { node.style.display = 'none'; continue; }
      node.style.display = '';
      node.textContent = `${f0(left)} s`;
      node.setAttribute('class', left < 15 ? 'eta-tag eta-tag--soon num' : 'eta-tag num');
    }
    const a0 = fr.ambulance[i], a1 = fr.ambulance[j];
    m.amb.setAttribute('transform', `translate(${a0[0] + (a1[0] - a0[0]) * f} ${a0[1] + (a1[1] - a0[1]) * f})`);

    const bg = fr.background[i];
    const count = bg.length / 3;
    while (m.pool.length < count) m.pool.push(svgEl('circle', { class: 'veh', r: 13 }, m.vehicles));
    m.pool.forEach((c, k) => {
      if (k >= count) { c.style.display = 'none'; return; }
      c.style.display = '';
      c.setAttribute('cx', bg[k * 3]);
      c.setAttribute('cy', bg[k * 3 + 1]);
      c.setAttribute('class', bg[k * 3 + 2] ? 'veh' : 'veh veh--stopped');
    });
    paintClock(fr, i);
    if (state.sel) paintDetail();
  }

  /* ---- timeline ----------------------------------------------------- */
  function approachAxes(route, byId) {
    return route.map((id, k) => {
      const a = byId[route[k === 0 ? 0 : k - 1]], b = byId[route[k === 0 ? 1 : k]];
      return a.row === b.row ? 'ew' : 'ns';
    });
  }

  function buildGantt() {
    const { replay } = state;
    const mode = replay.modes[state.mode];
    const fr = mode.frames;
    const total = fr.t.length;
    const order = replay.network.junctions.map((j) => j.id);
    const byId = Object.fromEntries(replay.network.junctions.map((j) => [j.id, j]));
    const route = modeRoute();
    const axes = approachAxes(route, byId);
    const root = $('#gantt');
    root.replaceChildren();

    const rows = document.createElement('div');
    rows.className = 'gantt__rows';
    route.forEach((id, r) => {
      const idx = order.indexOf(id);
      const row = document.createElement('div');
      row.className = 'gantt__row';
      const label = document.createElement('span');
      label.className = 'gantt__label num';
      label.textContent = id;
      const track = document.createElement('div');
      track.className = 'gantt__track';
      let start = 0, cur = fr[axes[r]][0][idx];
      const flush = (end) => {
        const run = document.createElement('i');
        run.className = `run run--${cur}`;
        run.style.left = `${(start / total) * 100}%`;
        run.style.width = `${((end - start) / total) * 100}%`;
        track.appendChild(run);
      };
      for (let t = 1; t < total; t++) {
        const c = fr[axes[r]][t][idx];
        if (c !== cur) { flush(t); start = t; cur = c; }
      }
      flush(total);
      row.append(label, track);
      rows.appendChild(row);
    });
    const body = document.createElement('div');
    body.className = 'gantt__body';
    body.appendChild(rows);

    const overlay = document.createElement('div');
    overlay.className = 'gantt__overlay';
    const line = svgEl('svg', { class: 'gantt__path', viewBox: `0 0 ${total} ${route.length}`, preserveAspectRatio: 'none', 'aria-hidden': 'true' });
    const pts = [`0,0.5`];
    route.slice(1).forEach((id, k) => {
      const t = mode.arrivals[id];
      if (t == null) return;
      pts.push(`${t},${k + 0.5}`, `${t},${k + 1.5}`);
    });
    svgEl('polyline', { class: 'gantt__trace', points: pts.join(' '), 'vector-effect': 'non-scaling-stroke' }, line);
    overlay.appendChild(line);
    const head = document.createElement('div');
    head.className = 'gantt__head';
    overlay.appendChild(head);
    body.appendChild(overlay);
    root.appendChild(body);
    overlay.addEventListener('click', (ev) => {
      const r = overlay.getBoundingClientRect();
      seek(((ev.clientX - r.left) / r.width) * total);
    });

    const axis = document.createElement('div');
    axis.className = 'gantt__axis num';
    for (let t = 0; t < total * 0.94; t += 60) {
      const tick = document.createElement('span');
      tick.style.left = `${(t / total) * 100}%`;
      tick.textContent = `${t} s`;
      axis.appendChild(tick);
    }
    root.appendChild(axis);
    state.gantt = { head, total };
  }

  /* ---- ledger, seeds, eta ------------------------------------------ */
  function delta(value, { tol = 0, digits = 0, lowerIsBetter = true, unit = ' s' } = {}) {
    // A signed difference whose colour says whether it helped, not just which way it went.
    const kind = Math.abs(value) <= tol ? 'flat' : (value < 0) === lowerIsBetter ? 'good' : 'bad';
    const text = Math.abs(value) <= tol && digits === 0 ? `0${unit}` : `${signed(value, digits)}${unit}`;
    return `<span class="delta delta--${kind}">${text}</span>`;
  }

  function paintLedger() {
    const ms = state.replay.modes;
    const base = ms.no_preemption.metrics;
    const maxT = Math.max(1, ...MODES.map((k) => ms[k].metrics.transit_s).filter(ok));
    const rows = MODES.map((k) => {
      const m = ms[k].metrics;
      const ref = k === 'no_preemption';
      return `<tr data-mode="${k}" ${k === state.mode ? 'aria-current="true"' : ''}>
        <th scope="row"><button type="button" class="rowbtn" data-mode="${k}" aria-pressed="${k === state.mode}">${MODE_LABEL[k]}</button></th>
        <td class="num"><span class="fig">${sec(m.transit_s)}</span><span class="meter" aria-hidden="true"><i style="width:${ok(m.transit_s) ? (m.transit_s / maxT) * 100 : 0}%"></i></span></td>
        <td class="num">${ref ? 'Reference' : ok(m.transit_s) && ok(base.transit_s) ? delta(m.transit_s - base.transit_s, { tol: 1 }) : 'n/a'}</td>
        <td class="num"><span class="fig">${sec1(m.avg_delay_s)}</span>${ref ? '' : `<span class="sub">${delta(m.avg_delay_s - base.avg_delay_s, { tol: 0.5, digits: 1 })}</span>`}</td>
        <td class="num"><span class="fig">${sec(m.max_nongreen_s)}</span>${ref ? '' : `<span class="sub">${delta(m.max_nongreen_s - base.max_nongreen_s, { tol: 0 })}</span>`}</td>
      </tr>`;
    }).join('');
    $('#ledger').innerHTML = `<table class="table">
      <caption class="visually-hidden">Seed ${state.replay.scenario.seed}, one traffic draw per mode</caption>
      <thead><tr><th scope="col">Mode</th><th scope="col">Transit</th><th scope="col">Against none</th><th scope="col">Bg delay</th><th scope="col">Longest wait</th></tr></thead>
      <tbody>${rows}</tbody></table>
      <p class="note">One seed is one traffic draw. Longest wait is the longest stretch any signal showed red or yellow to one direction; a fixed cycle gives ${f0(base.max_nongreen_s)} s. Differences are against no preemption, and green means better. A difference of half a second or less on delay counts as none.</p>`;
    $$('#ledger .rowbtn').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
  }

  function paintSeeds() {
    const box = $('#seeds');
    const c = state.compare;
    if (!c) {
      const live = state.source === 'api';
      box.innerHTML = `<h3 class="seeds__title">Across seeds</h3>
        <p class="note">A single draw hides the spread. Run the same scenario over twelve traffic seeds to get means with 95% confidence intervals and paired differences.</p>
        <button class="btn" type="button" id="seeds-run" ${live ? '' : 'disabled'}>Compare over 12 seeds</button>
        ${live ? '' : '<p class="hint">Needs the server.</p>'}`;
      $('#seeds-run')?.addEventListener('click', runCompare);
      return;
    }
    const est = (e) => `${f1(e.mean)} ± ${f1(e.ci95)}`;
    const rows = MODES.map((k) => {
      const m = c.modes[k];
      return `<tr><th scope="row">${MODE_LABEL[k]}</th>
        <td class="num">${est(m.transit)} s</td>
        <td class="num">${m.transit_vs_ref ? signed(m.transit_vs_ref.mean) + ' ± ' + f1(m.transit_vs_ref.ci95) + ' s' : 'Reference'}</td>
        <td class="num">${m.delay_vs_ref ? signed(m.delay_vs_ref.mean) + ' ± ' + f1(m.delay_vs_ref.ci95) + ' s' : 'Reference'}</td></tr>`;
    }).join('');
    box.innerHTML = `<h3 class="seeds__title">Across ${c.seeds} seeds</h3>
      <table class="table table--compact"><thead><tr><th scope="col">Mode</th><th scope="col">Transit</th><th scope="col">Transit vs none</th><th scope="col">Delay vs none</th></tr></thead><tbody>${rows}</tbody></table>
      <p class="note">Paired by seed. Where the delay interval spans zero, the modes are not distinguishable on background delay.</p>${strips(c)}`;
  }

  function strips(c) {
    const mode = c.modes[state.mode], ref = c.modes.no_preemption;
    if (state.mode === 'no_preemption') {
      return '<p class="note strips-hint">Pick another control mode above to see it against no preemption, seed by seed.</p>';
    }
    if (!mode.transit_samples || !ref.transit_samples) return '';
    const one = (label, a, b, unit, digits) => {
      const diffs = a.map((v, i) => (ok(v) && ok(b[i]) ? v - b[i] : null)).filter(ok);
      if (!diffs.length) return '';
      const max = Math.max(...diffs.map(Math.abs), 1e-9);
      const better = diffs.filter((d) => d < 0).length;
      const bars = diffs.map((d, i) => {
        const h = Math.max(2, (Math.abs(d) / max) * 50);
        const up = d > 0, kind = d < 0 ? 'good' : 'bad';
        return `<span class="sbar" title="Seed ${i}: ${signed(d, digits)} ${unit}"><i class="sbar__fill sbar__fill--${kind} ${up ? 'sbar__fill--up' : 'sbar__fill--down'}" style="height:${h}%"></i></span>`;
      }).join('');
      return `<div class="strip"><p class="strip__head"><span>${label}</span><span class="num">lower in ${better} of ${diffs.length} seeds</span></p>
        <div class="strip__bars" role="img" aria-label="${label} against no preemption for each seed: lower in ${better} of ${diffs.length}">${bars}</div>
        <p class="strip__scale num"><span>−${f1(max)} ${unit}</span><span>+${f1(max)} ${unit}</span></p></div>`;
    };
    const skipped = (mode.unfinished_runs || 0) + (ref.unfinished_runs || 0);
    const skippedNote = skipped ? `<p class="note">${skipped} run${skipped === 1 ? '' : 's'} where the ambulance did not arrive left out.</p>` : '';
    return `<div class="strips"><h3 class="seeds__title">${MODE_LABEL[state.mode]} against no preemption, seed by seed</h3>
      ${one('Ambulance transit', mode.transit_samples, ref.transit_samples, 's', 0)}
      ${one('Background delay', mode.delay_samples, ref.delay_samples, 's', 1)}${skippedNote}</div>`;
  }

  async function runCompare() {
    const btn = $('#seeds-run');
    btn.disabled = true;
    btn.textContent = 'Running 48 simulations';
    try {
      const res = await fetch(`/api/compare?seeds=12&${new URLSearchParams(state.params)}`);
      if (!res.ok) throw new Error((await res.json()).error || res.statusText);
      state.compare = await res.json();
      paintSeeds();
      paintReading();
    } catch (err) {
      const note = document.createElement('p');
      note.className = 'error';
      note.setAttribute('role', 'alert');
      note.textContent = `Comparison failed: ${err.message}`; // text, never markup
      $('#seeds').appendChild(note);
      btn.disabled = false;
      btn.textContent = 'Compare over 12 seeds';
    }
  }

  function paintEta() {
    const eta = state.replay.modes[state.mode].eta.by_lead.filter((b) => b.n > 0 && b.mae != null);
    const max = Math.max(...eta.map((b) => b.mae), 1);
    const rows = eta.map((b) => {
      const label = b.hi == null ? `${b.lo}+ s` : `${b.lo} to ${b.hi} s`;
      return `<tr><th scope="row" class="num">${label}</th>
        <td class="num"><span class="fig">${f1(b.mae)} s</span><span class="meter" aria-hidden="true"><i style="width:${(b.mae / max) * 100}%"></i></span></td>
        <td class="num">${b.n}</td></tr>`;
    }).join('');
    $('#eta').innerHTML = `<table class="table table--compact"><thead><tr><th scope="col">Time to junction</th><th scope="col">Mean absolute error</th><th scope="col">Predictions</th></tr></thead><tbody>${rows}</tbody></table>
      <p class="note">${MODE_LABEL[state.mode]}: the prediction is rebuilt every second from the ambulance's position and the current speed of each road.</p>`;
  }

  /* ---- reading, status, clock -------------------------------------- */
  function paintReading() {
    const ms = state.replay.modes;
    const m = ms[state.mode].metrics, base = ms.no_preemption.metrics;
    const head = `${MODE_LABEL[state.mode]}: <span class="num">${sec(m.transit_s)}</span> door to door`;
    let body;
    if (!ok(m.transit_s) || (state.mode !== 'no_preemption' && !ok(base.transit_s))) {
      body = 'The ambulance did not arrive within the simulation limit, so there is no transit time to compare.';
    } else if (state.mode === 'no_preemption') {
      body = `Fixed cycle. The ambulance waits at red lights; background traffic averages <span class="num">${sec1(m.avg_delay_s)}</span> of delay.`;
    } else {
      const gain = base.transit_s - m.transit_s;
      const dd = m.avg_delay_s - base.avg_delay_s;
      body = `<span class="num">${sec(gain)}</span> (${f0((gain / base.transit_s) * 100)}%) faster than no preemption. Background delay <span class="num">${sec1(m.avg_delay_s)}</span>, ${signed(dd)}${NB}s against it; the longest any signal waited was <span class="num">${sec(m.max_nongreen_s)}</span>.`;
      const c = state.compare && state.compare.modes[state.mode];
      if (c && c.delay_vs_ref) {
        const d = c.delay_vs_ref;
        body += Math.abs(d.mean) <= d.ci95
          ? ` Over ${state.compare.seeds} seeds the background delay is not distinguishable from no preemption.`
          : ` Over ${state.compare.seeds} seeds background delay moves ${signed(d.mean)} s.`;
      }
    }
    $('#readout-head').innerHTML = head;
    $('#readout-body').innerHTML = body;
    const fig = $('#readout-head .num');
    if (fig && state.shownTransit != null && state.shownTransit !== m.transit_s) tween(fig, state.shownTransit, m.transit_s);
    state.shownTransit = m.transit_s;
  }

  function paintStatus() {
    const s = $('#status');
    const map = $('#map');
    map.dataset.state = state.status;
    $('#map-error').textContent = state.error;
    const run = $('#run');
    if (state.status === 'loading') s.textContent = 'Running the simulation';
    else if (state.status === 'error') s.textContent = 'Simulation unavailable';
    else if (state.source === 'sample') s.textContent = `Sample run, seed ${state.replay.scenario.seed}. Start the server to change the scenario.`;
    else s.textContent = `Live run, seed ${state.replay.scenario.seed}`;
    const live = state.source === 'api' || state.status !== 'ready';
    run.disabled = state.status === 'loading' || (state.status === 'ready' && !live);
    $$('#presets .mode').forEach((b) => { b.disabled = state.status === 'loading' || (state.status === 'ready' && state.source === 'sample'); });
    $('#run-hint').textContent = state.status === 'ready' && state.source === 'sample' ? 'Opened from disk, so scenarios are fixed. Run python -m api.server to change them.' : '';
    $('#shell').setAttribute('aria-busy', state.status === 'loading');
  }

  function paintClock(fr, i) {
    const end = fr.t[fr.t.length - 1];
    $('#clock').textContent = `${f0(fr.t[i])} s of ${f0(end)} s`;
    $('#scrub').value = i;
    if (state.gantt) state.gantt.head.style.left = `${(i / state.gantt.total) * 100}%`;
    const amb = state.replay.modes[state.mode].metrics.transit_s;
    $('#map-svg').setAttribute('aria-label', `Signal grid at ${f0(fr.t[i])} seconds. Ambulance arrives at ${f0(amb)} seconds.`);
  }

  function paintModes() {
    const box = $('#modes');
    box.innerHTML = MODES.map((k) => {
      const m = state.replay.modes[k].metrics;
      return `<button type="button" class="mode" role="radio" aria-checked="${k === state.mode}" data-mode="${k}" tabindex="${k === state.mode ? 0 : -1}">
        <span class="mode__name">${MODE_LABEL[k]}</span><span class="mode__fig num">${sec(m.transit_s)}</span></button>`;
    }).join('');
    $$('.mode', box).forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
    $('#mode-note').textContent = MODE_NOTE[state.mode];
  }

  function paintAll() {
    paintStatus();
    if (state.status !== 'ready') return;
    buildMap();
    paintModes();
    paintLedger();
    paintSeeds();
    paintEta();
    paintReading();
    buildGantt();
    const fr = state.replay.modes[state.mode].frames;
    const scrub = $('#scrub');
    scrub.max = fr.t.length - 1;
    $('#speed').value = String(state.speed);
    drawFrame(state.pos);
    paintPlay();
  }

  /* ---- interaction -------------------------------------------------- */
  function setMode(mode) {
    if (!MODES.includes(mode) || mode === state.mode) return;
    state.mode = mode;
    const fr = state.replay.modes[mode].frames;
    state.pos = Math.min(state.pos, fr.t.length - 1);
    $('#scrub').max = fr.t.length - 1;
    paintModes();
    paintRoute();
    paintReading();
    paintEta();
    if (state.compare) paintSeeds();
    buildGantt();
    $$('#ledger tr[data-mode]').forEach((r) => {
      if (r.dataset.mode === mode) r.setAttribute('aria-current', 'true');
      else r.removeAttribute('aria-current');
    });
    $$('#ledger .rowbtn').forEach((b) => b.setAttribute('aria-pressed', b.dataset.mode === mode));
    drawFrame(state.pos);
    writeUrl(state.params);
  }

  function seek(pos) {
    const fr = state.replay.modes[state.mode].frames;
    state.pos = Math.max(0, Math.min(fr.t.length - 1, pos));
    drawFrame(state.pos);
  }

  function paintPlay() {
    const b = $('#play');
    b.textContent = state.playing ? 'Pause' : 'Play';
    b.setAttribute('aria-label', state.playing ? 'Pause replay' : 'Play replay');
  }

  function tick(now) {
    if (!state.playing) return;
    const dt = Math.min(0.1, (now - state.last) / 1000);
    state.last = now;
    const fr = state.replay.modes[state.mode].frames;
    state.pos += dt * state.speed;
    if (state.pos >= fr.t.length - 1) {
      state.pos = fr.t.length - 1;
      state.playing = false;
      paintPlay();
    }
    drawFrame(state.pos);
    if (state.playing) requestAnimationFrame(tick);
  }

  function togglePlay() {
    if (state.status !== 'ready') return;
    const fr = state.replay.modes[state.mode].frames;
    if (!state.playing && state.pos >= fr.t.length - 1) state.pos = 0;
    state.playing = !state.playing;
    state.last = performance.now();
    paintPlay();
    if (state.playing) requestAnimationFrame(tick);
  }

  /* ---- count-up, appearance, presets, export ----------------------- */
  const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function tween(el, from, to, ms = 240) {
    if (reducedMotion()) return;
    const start = performance.now();
    const step = (now) => {
      const k = Math.min(1, (now - start) / ms);
      const eased = 1 - Math.pow(1 - k, 4);
      el.textContent = sec(from + (to - from) * eased);
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function storedAppearance() {
    try { return localStorage.getItem(APPEARANCE_KEY) || 'system'; } catch (err) { return 'system'; }
  }
  function applyAppearance(pref) {
    const dark = pref === 'dark' || (pref === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.mode = dark ? 'dark' : 'light';
    $$('#appearance .seg__btn').forEach((b) => {
      b.setAttribute('aria-checked', String(b.dataset.pref === pref));
      b.tabIndex = b.dataset.pref === pref ? 0 : -1;
    });
    try { localStorage.setItem(APPEARANCE_KEY, pref); } catch (err) { /* private window: keep the choice for this page only */ }
  }

  function paintDirty() {
    // Edits that have not been run: say so, rather than letting them sit next to a replay they did not produce.
    if (state.status !== 'ready' || state.source !== 'api' || !state.params) return;
    const now = readForm();
    const dirty = Object.keys(now).some((k) => String(now[k]) !== String(state.params[k]));
    $('#run-hint').textContent = dirty ? 'Changed, not run yet. The replay and comparison still show the last run.' : '';
  }

  function paintPresets() {
    const n = Number($('#params').elements.vehicles.value);
    $$('#presets .mode').forEach((b) => b.setAttribute('aria-checked', String(Number(b.dataset.vehicles) === n)));
  }

  function exportCsv() {
    const r = state.replay, ms = r.modes;
    const lines = [
      `# Green corridor: seed ${r.scenario.seed}, ${r.scenario.background_vehicles} background vehicles, hold ${r.scenario.corridor_max_hold_s} s, look-ahead ${r.scenario.corridor_horizon_s} s, recovery ${r.scenario.recovery_cycles} cycles`,
      'mode,transit_s,avg_background_delay_s,p95_background_delay_s,longest_wait_s',
      ...MODES.map((k) => { const m = ms[k].metrics; return [k, m.transit_s, m.avg_delay_s.toFixed(2), m.p95_delay_s.toFixed(2), m.max_nongreen_s].join(','); }),
    ];
    const c = state.compare;
    if (c) {
      lines.push('', `# Across ${c.seeds} seeds, mean and 95% confidence half-width, differences paired against no_preemption`,
        'mode,transit_mean_s,transit_ci95_s,transit_vs_none_s,delay_mean_s,delay_ci95_s,delay_vs_none_s,delay_vs_none_ci95_s');
      for (const k of MODES) {
        const m = c.modes[k];
        lines.push([k, m.transit.mean.toFixed(2), m.transit.ci95.toFixed(2), m.transit_vs_ref ? m.transit_vs_ref.mean.toFixed(2) : '',
          m.avg_delay.mean.toFixed(2), m.avg_delay.ci95.toFixed(2), m.delay_vs_ref ? m.delay_vs_ref.mean.toFixed(2) : '', m.delay_vs_ref ? m.delay_vs_ref.ci95.toFixed(2) : ''].join(','));
      }
    }
    const url = URL.createObjectURL(new Blob([lines.join('\n') + '\n'], { type: 'text/csv' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: `green-corridor-seed${r.scenario.seed}.csv` });
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  /* ---- junction detail ---------------------------------------------- */
  function selectJunction(id, opener) {
    state.sel = id;
    state.opener = opener || null;
    $$('.jn', $('#map-svg')).forEach((g) => g.classList.toggle('jn--selected', g.dataset.id === id));
    $('#detail').hidden = false;
    paintDetail();
  }

  function closeDetail() {
    const opener = state.opener;
    state.sel = null;
    state.opener = null;
    $('#detail').hidden = true;
    $$('.jn', $('#map-svg')).forEach((g) => g.classList.remove('jn--selected'));
    if (opener && document.contains(opener)) opener.focus();
  }

  function paintDetail() {
    if (!state.sel || !state.replay) return;
    const { replay } = state;
    const mode = replay.modes[state.mode];
    const fr = mode.frames;
    const i = Math.max(0, Math.min(fr.t.length - 1, Math.floor(state.pos)));
    const id = state.sel;
    const order = replay.network.junctions.map((j) => j.id);
    const idx = order.indexOf(id);
    const byId = Object.fromEntries(replay.network.junctions.map((j) => [j.id, j]));
    const route = modeRoute();
    const stop = route.indexOf(id);
    const shift = fr.shifts[i][idx];
    const key = `${state.mode}:${id}`;
    if (state.maxShift[key] == null) state.maxShift[key] = Math.max(...fr.shifts.map((row) => Math.abs(row[idx])));
    const facts = [
      ['Position', stop < 0 ? 'Not on the ambulance route' : stop === 0 ? 'Start of the route' : `Stop ${stop} of ${route.length - 1} on the route`],
      ['North-south signal', STATE_WORD[fr.ns[i][idx]]],
      ['East-west signal', STATE_WORD[fr.ew[i][idx]]],
      ['Phase shift now', Math.abs(shift) < 0.05 ? 'None, on its own cycle' : `${signed(shift)} s`],
      ['Largest shift this run', `${f1(state.maxShift[key])} s`],
    ];
    if (stop > 0) {
      const axis = approachAxes(route, byId)[stop];
      const arrival = mode.arrivals[id];
      const pred = (mode.eta.predicted[id] || []);
      const left = pred[Math.floor(fr.t[i] / 2)] ? pred[Math.floor(fr.t[i] / 2)][1] - fr.t[i] : null;
      facts.push(['Predicted arrival', left == null || left < 0 ? 'Passed' : `${f0(left)} s from now`]);
      if (arrival != null) {
        facts.push(['Ambulance arrived', sec(arrival)]);
        for (const ahead of [30, 10]) {
          const e = pred[Math.floor((arrival - ahead) / 2)];
          if (e) facts.push([`Prediction ${ahead} s ahead`, `${signed(e[1] - arrival)} s off`]);
        }
        let lead = 0;
        for (let t = Math.floor(arrival); t >= 0 && fr[axis][t][idx] === 'G'; t--) lead++;
        const at = fr[axis][Math.min(fr.t.length - 1, Math.floor(arrival))][idx];
        facts.push(['Signal at arrival', at === 'G' ? `Green, for ${lead} s already` : `${STATE_WORD[at]}, the ambulance waited`]);
      }
    }
    $('#h-detail').textContent = `Junction ${id}`;
    $('#facts').innerHTML = facts.map(([k, v]) => `<div class="fact"><dt>${k}</dt><dd class="num">${v}</dd></div>`).join('');
  }

  function bind() {
    $('#params').addEventListener('submit', (e) => {
      e.preventDefault();
      const v = readForm();
      writeUrl(v);
      load(v);
    });
    $('#retry').addEventListener('click', () => load(readForm()));
    $('#export').addEventListener('click', exportCsv);
    $('#detail-close').addEventListener('click', closeDetail);
    $('#presets').addEventListener('click', (e) => {
      const b = e.target.closest('.mode');
      if (!b || b.disabled) return;
      $('#params').elements.vehicles.value = b.dataset.vehicles;
      paintPresets();
      $('#params').requestSubmit();
    });
    $('#params').elements.vehicles.addEventListener('input', paintPresets);
    $('#params').addEventListener('input', paintDirty);
    $('#params').addEventListener('change', paintDirty);
    $('#appearance').addEventListener('click', (e) => {
      const b = e.target.closest('.seg__btn');
      if (b) applyAppearance(b.dataset.pref);
    });
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (storedAppearance() === 'system') applyAppearance('system');
    });
    const svg = $('#map-svg');
    svg.addEventListener('click', (e) => {
      const g = e.target.closest('.jn');
      if (g) selectJunction(g.dataset.id, g);
    });
    svg.addEventListener('keydown', (e) => {
      const g = e.target.closest?.('.jn');
      if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); e.stopPropagation(); selectJunction(g.dataset.id, g); }
    });
    $('#play').addEventListener('click', togglePlay);
    $('#restart').addEventListener('click', () => { seek(0); });
    $('#scrub').addEventListener('input', (e) => seek(Number(e.target.value)));
    $('#speed').addEventListener('change', (e) => { state.speed = Number(e.target.value); writeUrl(state.params); });
    $('#modes').addEventListener('keydown', (e) => {
      const dir = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      if (!dir) return;
      e.preventDefault();
      const next = MODES[(MODES.indexOf(state.mode) + dir + MODES.length) % MODES.length];
      setMode(next);
      $(`.mode[data-mode="${next}"]`)?.focus();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && state.sel) { closeDetail(); return; }
      if (e.code !== 'Space' || e.target.closest('input, select, textarea, button')) return;
      e.preventDefault();
      togglePlay();
    });
  }

  shell();
  applyAppearance(storedAppearance());
  const initial = readUrl();
  fillForm(initial);
  paintPresets();
  bind();
  load(initial);
})();
