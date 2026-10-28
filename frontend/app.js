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
    { key: 'seed', label: 'Traffic seed', min: 0, max: 10000, step: 1, def: 42 },
    { key: 'vehicles', label: 'Background vehicles', min: 0, max: 400, step: 10, def: 80 },
    { key: 'hold', label: 'Max hold, seconds', min: 0, max: 40, step: 1, def: 15 },
    { key: 'horizon', label: 'Look-ahead, seconds', min: 10, max: 180, step: 5, def: 60 },
    { key: 'recovery', label: 'Recovery cycles', min: 0, max: 6, step: 1, def: 2 },
    { key: 'trigger', label: 'Reactive trigger, metres', min: 50, max: 400, step: 10, def: 200 },
  ];
  const SLEW = [
    ['', 'Off, shift at once'],
    ['0.4', 'Eased, 0.4 s per s'],
    ['0.25', 'Eased, 0.25 s per s'],
    ['0.15', 'Eased, 0.15 s per s'],
  ];
  const NS = 'http://www.w3.org/2000/svg';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const svgEl = (tag, attrs = {}, parent) => {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  };
  const f0 = (n) => Math.round(n).toString();
  const f1 = (n) => n.toFixed(1);
  const signed = (n, digits = 1) => (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(n).toFixed(digits);

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
  function shell() {
    const fields = PARAMS.map(
      (p) => `<label class="field"><span class="field__label">${p.label}</span>
        <input class="input num" type="number" name="${p.key}" min="${p.min}" max="${p.max}" step="${p.step}" inputmode="numeric"></label>`,
    ).join('');
    const slew = SLEW.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
    document.getElementById('app').innerHTML = `
      <a class="skip" href="#stage">Skip to the replay</a>
      <header class="topbar">
        <div class="topbar__brand">
          <h1 class="brand">Green corridor</h1>
          <p class="topbar__sub">Predictive signal coordination for emergency vehicles, simulated on a 5 by 5 grid</p>
        </div>
        <p class="topbar__status" id="status" role="status"></p>
      </header>
      <main class="shell" id="shell">
        <section class="panel params" aria-labelledby="h-params">
          <h2 id="h-params" class="panel__title">Scenario</h2>
          <form id="params" class="fields" autocomplete="off">
            ${fields}
            <label class="field field--wide"><span class="field__label">Signal shift</span>
              <select class="input" name="slew">${slew}</select></label>
            <div class="field field--wide">
              <button class="btn btn--primary" type="submit" id="run">Run scenario</button>
              <p class="hint" id="run-hint"></p>
            </div>
          </form>
        </section>

        <section class="panel stage" id="stage" aria-labelledby="h-stage">
          <div class="panel__head">
            <h2 id="h-stage" class="panel__title">Replay</h2>
            <div class="modes" role="radiogroup" aria-label="Control mode" id="modes"></div>
          </div>
          <p class="mode-note" id="mode-note"></p>
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
          </div>
          <div class="transport" id="transport">
            <button class="btn btn--primary" type="button" id="play" aria-label="Play replay">Play</button>
            <button class="btn" type="button" id="restart">Restart</button>
            <input class="scrub" type="range" id="scrub" min="0" max="0" step="1" value="0" aria-label="Replay time">
            <output class="clock num" id="clock" for="scrub">0 s</output>
            <label class="speed"><span class="visually-hidden">Playback speed</span>
              <select class="input" id="speed"><option value="1">1×</option><option value="4">4×</option><option value="16">16×</option></select></label>
          </div>
          <p class="reading" id="reading"></p>
        </section>

        <section class="panel timeline" aria-labelledby="h-time">
          <h2 id="h-time" class="panel__title">Signal on the ambulance's approach</h2>
          <div id="gantt" class="gantt"></div>
        </section>

        <section class="panel ledger" aria-labelledby="h-ledger">
          <h2 id="h-ledger" class="panel__title">Four modes, one scenario</h2>
          <div id="ledger"></div>
          <div id="seeds" class="seeds"></div>
        </section>

        <section class="panel eta" aria-labelledby="h-eta">
          <h2 id="h-eta" class="panel__title">ETA error by time to junction</h2>
          <div id="eta"></div>
        </section>
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
    state.status = 'loading';
    state.playing = false;
    paintStatus();
    const qs = new URLSearchParams(values).toString();
    try {
      if (location.protocol === 'file:') throw new Error('file');
      const res = await fetch(`/api/replay?${qs}`);
      if (!res.ok) throw new Error((await res.json()).error || res.statusText);
      state.replay = await res.json();
      state.source = 'api';
      state.compare = null;
    } catch (err) {
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
    state.pos = state.startAt || 0;
    state.startAt = 0;
    state.map = null;
    paintAll();
  }

  /* ---- map ---------------------------------------------------------- */
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
    svgEl('polyline', { class: 'route', points: route.map((id) => `${byId[id].x},${byId[id].y}`).join(' ') }, svg);

    const jg = svgEl('g', { class: 'junctions' }, svg);
    const junctionNodes = network.junctions.map((j) => {
      const g = svgEl('g', { class: 'jn', transform: `translate(${j.x} ${j.y})` }, jg);
      svgEl('circle', { class: 'jn__held', r: 62 }, g);
      svgEl('rect', { class: 'jn__box', x: -34, y: -34, width: 68, height: 68 }, g);
      const ns = svgEl('line', { class: 'sig sig--ns s-R', x1: 0, y1: -24, x2: 0, y2: 24 }, g);
      const ew = svgEl('line', { class: 'sig sig--ew s-R', x1: -24, y1: 0, x2: 24, y2: 0 }, g);
      return { ns, ew, held: $('.jn__held', g) };
    });
    for (const [idx, label] of [[0, 'A'], [route.length - 1, 'B']]) {
      const j = byId[route[idx]];
      const t = svgEl('text', { class: 'tag', x: j.x, y: j.y - 52, 'text-anchor': 'middle' }, svg);
      t.textContent = label === 'A' ? 'Start' : 'Hospital';
    }
    const vehicles = svgEl('g', { class: 'vehicles' }, svg);
    const amb = svgEl('g', { class: 'amb' }, svg);
    svgEl('circle', { class: 'amb__ring', r: 46 }, amb);
    svgEl('circle', { class: 'amb__dot', r: 30 }, amb);
    svgEl('path', { class: 'amb__plus', d: 'M0 -16V16M-16 0H16' }, amb);
    state.map = { junctionNodes, vehicles, amb, pool: [] };
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
    const axes = approachAxes(replay.route, byId);
    const root = $('#gantt');
    root.replaceChildren();

    const rows = document.createElement('div');
    rows.className = 'gantt__rows';
    replay.route.forEach((id, r) => {
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
    const line = svgEl('svg', { class: 'gantt__path', viewBox: `0 0 ${total} ${replay.route.length}`, preserveAspectRatio: 'none', 'aria-hidden': 'true' });
    const pts = [`0,0.5`];
    replay.route.slice(1).forEach((id, k) => {
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
  function paintLedger() {
    const ms = state.replay.modes;
    const base = ms.no_preemption.metrics;
    const maxT = Math.max(...MODES.map((k) => ms[k].metrics.transit_s));
    const rows = MODES.map((k) => {
      const m = ms[k].metrics;
      const d = m.transit_s - base.transit_s;
      return `<tr data-mode="${k}" ${k === state.mode ? 'aria-current="true"' : ''}>
        <th scope="row"><button type="button" class="rowbtn" data-mode="${k}" aria-pressed="${k === state.mode}">${MODE_LABEL[k]}</button></th>
        <td class="num"><span class="fig">${f0(m.transit_s)} s</span><span class="meter" aria-hidden="true"><i style="width:${(m.transit_s / maxT) * 100}%"></i></span></td>
        <td class="num">${k === 'no_preemption' ? 'Reference' : signed(d, 0) + ' s'}</td>
        <td class="num">${f1(m.avg_delay_s)} s</td>
        <td class="num">${f0(m.max_nongreen_s)} s</td>
      </tr>`;
    }).join('');
    $('#ledger').innerHTML = `<table class="table">
      <caption class="visually-hidden">Seed ${state.replay.scenario.seed}, one traffic draw per mode</caption>
      <thead><tr><th scope="col">Mode</th><th scope="col">Transit</th><th scope="col">Against none</th><th scope="col">Background delay</th><th scope="col">Longest non-green</th></tr></thead>
      <tbody>${rows}</tbody></table>
      <p class="note">One seed is one traffic draw. Longest non-green is the longest stretch any signal showed red or yellow to one direction; a fixed cycle gives ${f0(base.max_nongreen_s)} s.</p>`;
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
      <table class="table table--compact"><thead><tr><th scope="col">Mode</th><th scope="col">Transit</th><th scope="col">Transit against none</th><th scope="col">Background delay against none</th></tr></thead><tbody>${rows}</tbody></table>
      <p class="note">Paired by seed. Where the delay interval spans zero, the modes are not distinguishable on background delay.</p>`;
  }

  async function runCompare() {
    const btn = $('#seeds-run');
    btn.disabled = true;
    btn.textContent = 'Running 48 simulations';
    try {
      const res = await fetch(`/api/compare?seeds=12&${new URLSearchParams(readForm())}`);
      if (!res.ok) throw new Error((await res.json()).error || res.statusText);
      state.compare = await res.json();
      paintSeeds();
    } catch (err) {
      $('#seeds').insertAdjacentHTML('beforeend', `<p class="error" role="alert">Comparison failed: ${err.message}</p>`);
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
    const el = $('#reading');
    if (state.mode === 'no_preemption') {
      el.textContent = `Fixed cycle: the ambulance needs ${f0(m.transit_s)} s and waits at red lights along the way. Background traffic averages ${f1(m.avg_delay_s)} s of delay.`;
      return;
    }
    const gain = base.transit_s - m.transit_s;
    const dd = m.avg_delay_s - base.avg_delay_s;
    el.textContent = `${f0(m.transit_s)} s door to door, ${f0(gain)} s (${f0((gain / base.transit_s) * 100)}%) faster than no preemption. Background delay ${f1(m.avg_delay_s)} s, ${signed(dd)} s against it.`;
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
    $('#run-hint').textContent = state.status === 'ready' && state.source === 'sample' ? 'Opened from disk, so scenarios are fixed. Run python -m api.server to change them.' : '';
    $('#shell').setAttribute('aria-busy', state.status === 'loading');
  }

  function paintClock(fr, i) {
    const end = fr.t[fr.t.length - 1];
    $('#clock').textContent = `${f0(fr.t[i])} s of ${f0(end)} s`;
    $('#scrub').value = i;
    if (state.gantt) state.gantt.head.style.left = `${(i / state.gantt.total) * 100}%`;
    const amb = state.replay.modes[state.mode].metrics.transit_s;
    $('#map').dataset.arrived = fr.t[i] >= amb;
    $('#map-svg').setAttribute('aria-label', `Signal grid at ${f0(fr.t[i])} seconds. Ambulance arrives at ${f0(amb)} seconds.`);
  }

  function paintModes() {
    const box = $('#modes');
    box.innerHTML = MODES.map(
      (k) => `<button type="button" class="mode" role="radio" aria-checked="${k === state.mode}" data-mode="${k}" tabindex="${k === state.mode ? 0 : -1}">${MODE_LABEL[k]}</button>`,
    ).join('');
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
    paintReading();
    paintEta();
    buildGantt();
    $$('#ledger tr[data-mode]').forEach((r) => {
      if (r.dataset.mode === mode) r.setAttribute('aria-current', 'true');
      else r.removeAttribute('aria-current');
    });
    $$('#ledger .rowbtn').forEach((b) => b.setAttribute('aria-pressed', b.dataset.mode === mode));
    drawFrame(state.pos);
    writeUrl(readForm());
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

  function bind() {
    $('#params').addEventListener('submit', (e) => {
      e.preventDefault();
      const v = readForm();
      writeUrl(v);
      load(v);
    });
    $('#retry').addEventListener('click', () => load(readForm()));
    $('#play').addEventListener('click', togglePlay);
    $('#restart').addEventListener('click', () => { seek(0); });
    $('#scrub').addEventListener('input', (e) => seek(Number(e.target.value)));
    $('#speed').addEventListener('change', (e) => { state.speed = Number(e.target.value); writeUrl(readForm()); });
    $('#modes').addEventListener('keydown', (e) => {
      const dir = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      if (!dir) return;
      e.preventDefault();
      const next = MODES[(MODES.indexOf(state.mode) + dir + MODES.length) % MODES.length];
      setMode(next);
      $(`.mode[data-mode="${next}"]`)?.focus();
    });
    document.addEventListener('keydown', (e) => {
      if (e.code !== 'Space' || e.target.closest('input, select, textarea, button')) return;
      e.preventDefault();
      togglePlay();
    });
  }

  shell();
  const initial = readUrl();
  fillForm(initial);
  bind();
  load(initial);
})();
