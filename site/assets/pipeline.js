/* Interactive illustrations for the pipeline page. Every example is seeded synthetic data run
   through simplified versions of the real stages in src/; none of it is measurement data. */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const C = { ink: '#e9eef0', mute: '#8fa1a8', line: 'rgba(233,238,240,.14)', acc: '#9fd8ea', flag: '#f0a35e', rule: '#f2d27a' };
  const $ = id => document.getElementById(id);

  function svgEl(parent, name, attrs, text) {
    const e = document.createElementNS(NS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    parent.appendChild(e);
    return e;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function rng(seed) { let s = seed % 2147483647; if (s <= 0) s += 2147483646; return () => (s = s * 16807 % 2147483647, (s - 1) / 2147483646); }
  function gauss(r) { return Math.sqrt(-2 * Math.log(r() + 1e-12)) * Math.cos(2 * Math.PI * r()); }
  function median(a) { const s = a.slice().sort((p, q) => p - q), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
  function fmt(v, d = 2) { return v == null || !isFinite(v) ? '—' : v.toFixed(d); }
  function round1(v) { return Math.round(v * 10) / 10; }
  function svgPoint(svg, evt) {
    const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
    return { x: (evt.clientX - r.left) / r.width * vb.width, y: (evt.clientY - r.top) / r.height * vb.height };
  }
  function dl(node, rows) {
    node.innerHTML = rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
  }
  // Charts switch to a narrower drawing with larger labels on small screens, instead of shrinking.
  const isNarrow = svg => svg.getBoundingClientRect().width < 640;
  function fit(svg, H, narrowH) {
    const narrow = isNarrow(svg), W = narrow ? 600 : 1000, h = narrow ? narrowH : H;
    svg.setAttribute('viewBox', `0 0 ${W} ${h}`);
    svg.classList.toggle('narrow', narrow);
    return { W, H: h, narrow };
  }
  function onLayoutChange(svg, redraw) {
    let last = isNarrow(svg);
    addEventListener('resize', () => { const now = isNarrow(svg); if (now !== last) { last = now; redraw(); } });
  }
  function segmented(group, onPick) {
    group.addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      group.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      onPick(b.dataset.v);
    });
  }

  /* History detector for one series with one valid reading per consecutive day, following
     src/history_detector/history_detector.py: prior window [t - 28, t), at least 14 days, median and
     floored MAD spread, clipped history, and the stuck / dropout / negative rules. One threshold is
     used for both directions here; the real detector calibrates each direction per series. */
  function detect(values, o = {}) {
    const window = 28, minHist = 14, floor = 0.05, clip = 3.5, stuckDays = 7;
    const threshold = o.threshold ?? 4, rules = o.rules ?? true;
    const hist = [];
    let prev = null, run = 0, runVaried = false;
    return values.map((v, t) => {
      while (hist.length && hist[0].day < t - window) hist.shift();
      const vals = hist.map(h => h.stored);
      const enough = vals.length >= minHist;
      let med = NaN, mad = NaN, spread = NaN, rawSpread = NaN, floorSpread = NaN;
      if (enough) {
        med = median(vals); mad = median(vals.map(x => Math.abs(x - med)));
        rawSpread = 1.4826 * mad; floorSpread = floor * Math.abs(med); spread = Math.max(rawSpread, floorSpread);
      }
      if (prev !== null && v === prev) run++; else { run = 1; runVaried = enough && mad > 0; }
      const stuck = rules && run >= stuckDays && runVaried;
      const dropout = rules && v === 0 && enough && !hist.some(h => h.raw === 0);
      const negative = rules && v < 0;
      let status = 'scored', signed = NaN;
      if (!enough) status = 'insufficient'; else if (spread === 0) status = 'zero_spread'; else signed = (v - med) / spread;
      const score = Math.abs(signed);
      const stat = status === 'scored' && score >= threshold;
      const reasons = [];
      if (stuck) reasons.push('stuck'); if (dropout) reasons.push('dropout'); if (negative) reasons.push('negative');
      if (stat) reasons.push(signed > 0 ? 'unusual_high' : 'unusual_low');
      const win = hist.map(h => ({ d: h.day, v: h.stored }));
      const stored = enough && spread > 0 ? Math.min(Math.max(v, med - clip * spread), med + clip * spread) : v;
      hist.push({ day: t, stored, raw: v });
      prev = v;
      const rule = stuck || dropout || negative;
      return { t, v, days: vals.length, med, mad, spread, rawSpread, floorSpread, signed, score, status, stat, rule, flag: stat || rule, reasons, run, win };
    });
  }

  function drawSeries(svg, res, o) {
    clear(svg);
    const { W, H, narrow } = fit(svg, 300, 400), L = narrow ? 58 : 44, R = W - 12, T = 14, B = H - 34, N = res.length;
    const X = i => L + (R - L) * i / (N - 1);
    const Y = v => B - (B - T) * (Math.max(o.ymin, Math.min(o.ymax, v)) - o.ymin) / (o.ymax - o.ymin);
    o.yticks.forEach(v => {
      svgEl(svg, 'line', { x1: L, x2: R, y1: Y(v), y2: Y(v), stroke: C.line });
      svgEl(svg, 'text', { x: L - 8, y: Y(v) + 4, 'text-anchor': 'end', class: 'ax' }, v);
    });
    for (let d = 0; d < N; d += narrow ? 30 : 20) svgEl(svg, 'text', { x: X(d), y: B + 24, 'text-anchor': 'middle', class: 'ax' }, 'day ' + d);
    const first = res.findIndex(r => r.status !== 'insufficient');
    if (first > 0) {
      svgEl(svg, 'rect', { x: L, y: T, width: X(first) - L, height: B - T, fill: 'rgba(233,238,240,.035)' });
      svgEl(svg, 'text', { x: L + 8, y: T + 16, class: 'tag', fill: C.mute }, 'unscored · under 14 days');
    }
    if (o.mark) {
      const [a, b] = o.mark;
      svgEl(svg, 'rect', { x: X(a) - 4, y: T, width: X(b) - X(a) + 8, height: B - T, fill: 'rgba(240,163,94,.08)' });
      svgEl(svg, 'text', { x: X(a), y: B - 8, class: 'tag', fill: C.flag }, 'artificial fault');
    }
    const top = [], bot = [];
    res.forEach((r, i) => { if (r.status === 'scored') { top.push(X(i) + ',' + Y(r.med + o.threshold * r.spread)); bot.unshift(X(i) + ',' + Y(r.med - o.threshold * r.spread)); } });
    if (top.length) svgEl(svg, 'polygon', { points: top.concat(bot).join(' '), fill: 'rgba(159,216,234,.09)' });
    const s = o.sel != null ? res[o.sel] : null;
    if (s) {
      const a = Math.max(0, o.sel - 28);
      svgEl(svg, 'rect', { x: X(a), y: T, width: Math.max(0, X(o.sel) - X(a)), height: B - T, fill: 'rgba(159,216,234,.06)', stroke: 'rgba(159,216,234,.35)', 'stroke-dasharray': '3 4' });
      s.win.forEach(w => svgEl(svg, 'circle', { cx: X(w.d), cy: Y(w.v), r: 2.6, fill: C.acc, opacity: .85 }));
    }
    svgEl(svg, 'polyline', { points: res.map((r, i) => X(i) + ',' + Y(r.v)).join(' '), fill: 'none', stroke: C.mute, 'stroke-width': 1.5, 'stroke-opacity': .7 });
    let path = '';
    res.forEach((r, i) => { if (r.status === 'scored') path += (path ? ' L' : 'M') + X(i) + ' ' + Y(r.med); });
    if (path) svgEl(svg, 'path', { d: path, fill: 'none', stroke: C.acc, 'stroke-width': 1.8, opacity: s ? .4 : 1 });
    res.forEach((r, i) => { if (r.flag) svgEl(svg, 'circle', { cx: X(i), cy: Y(r.v), r: 5, fill: 'none', stroke: r.rule ? C.rule : C.flag, 'stroke-width': 2 }); });
    if (s) {
      if (s.status === 'scored') {
        svgEl(svg, 'line', { x1: X(Math.max(0, o.sel - 28)), x2: X(o.sel), y1: Y(s.med), y2: Y(s.med), stroke: C.acc, 'stroke-width': 2.2 });
        svgEl(svg, 'line', { x1: X(o.sel), x2: X(o.sel), y1: Y(s.med - o.threshold * s.spread), y2: Y(s.med + o.threshold * s.spread), stroke: C.acc, 'stroke-width': 7, 'stroke-linecap': 'round', opacity: .3 });
      }
      svgEl(svg, 'line', { x1: X(o.sel), x2: X(o.sel), y1: T, y2: B, stroke: C.ink, 'stroke-opacity': .3 });
      svgEl(svg, 'circle', { cx: X(o.sel), cy: Y(s.v), r: 6.5, fill: s.flag ? (s.rule ? C.rule : C.flag) : C.ink });
    }
    return { X, L, R, N };
  }

  /* 01 · Prepare: every row is kept, with provenance and flags added. */
  (function () {
    const host = $('prep-table'); if (!host) return;
    const rows = [
      ['P-1001', '2025-03-01', '412.5', 'm3', 412.5, '2025-03-01', [], 'A normal row: parsed and kept with its source file and row.'],
      ['P-1001', '2025-03-02', '', 'm3', null, '2025-03-02', ['flag_blank_value'], 'Blank value: kept and flagged. Downstream it stays unscored; it is never filled in.'],
      ['P-1001', '2025-03-03', '4O8.1', 'm3', null, '2025-03-03', ['flag_invalid_value'], 'The value does not parse (a letter O instead of a zero). Kept with the raw text; never guessed.'],
      ['P-1001', '2025-02-30', '398.0', 'm3', 398.0, null, ['flag_invalid_date'], 'There is no 30 February. Kept and flagged; the date is not moved to a nearby day.'],
      ['P-9999', '2025-03-03', '7.2', 'mg/l', 7.2, '2025-03-03', ['flag_unknown_point'], 'The point ID is not in MeasurementPoints. Kept and flagged for review.'],
      ['P-1002', '2025-03-03', '2.1', 'mg/l', 2.1, '2025-03-03', ['dup'], 'Two rows for the same point and date. Both are kept and listed as duplicate candidates; the detector later leaves both unscored rather than averaging them.'],
      ['P-1002', '2025-03-03', '2.4', 'mg/l', 2.4, '2025-03-03', ['dup'], 'The second same-day row. Neither is chosen or averaged.'],
      ['P-1002', '2025-03-04', '0.0', 'mg/l', 0, '2025-03-04', [], 'A zero is a valid number, not an error. Rules downstream may still mark it for review.'],
    ];
    let prepared = true, sel = 2;
    const chip = f => f === 'dup' ? '<span class="chip m">duplicate candidate · report</span>' : `<span class="chip f">${f}</span>`;
    function render() {
      const head = prepared
        ? '<th class="new">source_file</th><th class="new">source_row</th><th>MeasurementPointID</th><th>Date</th><th>Value</th><th>Unit</th><th class="new">parsed_date</th><th class="new">parsed_value</th><th class="new">flags</th>'
        : '<th>MeasurementPointID</th><th>Date</th><th>Value</th><th>Unit</th>';
      const body = rows.map((r, i) => {
        const raw = `<td>${r[0]}</td><td>${r[1]}</td><td>${r[2] === '' ? '<span style="color:var(--mute)">(blank)</span>' : r[2]}</td><td>${r[3]}</td>`;
        const cells = prepared
          ? `<td class="new">part-001.csv.gz</td><td class="new">${i + 2}</td>${raw}<td class="new">${r[5] ?? '—'}</td><td class="new">${r[4] ?? '—'}</td><td>${r[6].map(chip).join('') || '<span class="chip a">ok</span>'}</td>`
          : raw;
        return `<tr data-i="${i}" class="${i === sel ? 'sel' : ''}" tabindex="0">${cells}</tr>`;
      }).join('');
      host.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
      $('prep-why').textContent = prepared ? rows[sel][7] : 'Raw rows exactly as exported. Switch to "After preparation" to see what is added.';
      $('prep-counts').innerHTML = prepared
        ? `<span>Rows in <b>8</b></span><span>Rows kept <b>8</b></span><span>Deleted <b>0</b></span><span>Imputed <b>0</b></span><span>Units converted <b>0</b></span><span>Flagged <b>${rows.filter(r => r[6].length).length}</b></span>`
        : '<span>Rows in <b>8</b></span>';
    }
    host.addEventListener('click', e => { const tr = e.target.closest('tr[data-i]'); if (tr) { sel = +tr.dataset.i; render(); } });
    host.addEventListener('keydown', e => { const tr = e.target.closest('tr[data-i]'); if (tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); sel = +tr.dataset.i; render(); host.querySelector(`tr[data-i="${sel}"]`).focus(); } });
    segmented($('prep-mode'), v => { prepared = v === 'prepared'; render(); });
    render();
  })();

  /* 02 · Score: scrub through the days and see each reading against its own prior 28 days. */
  (function () {
    const svg = $('score-chart'); if (!svg) return;
    const r = rng(7), N = 120, y = [];
    for (let i = 0; i < N; i++) y.push(round1(52 + 3 * Math.sin(i / 9) + i * .04 + gauss(r) * 1.4));
    y[72] = round1(y[72] + 18); y[97] = round1(y[97] - 14);
    const day = $('score-day'), thr = $('score-thr');
    let res, geo;
    function update() {
      const t = +day.value, T = +thr.value;
      $('score-day-out').value = t; $('score-thr-out').value = T.toFixed(1);
      res = detect(y, { threshold: T });
      geo = drawSeries(svg, res, { threshold: T, sel: t, ymin: 25, ymax: 85, yticks: [30, 45, 60, 75] });
      const s = res[t];
      dl($('score-stats'), [
        ['Reading', fmt(s.v, 1)],
        ['History days', s.days + ' / 28'],
        ['Prior median', fmt(s.med)],
        ['1.4826 × MAD', fmt(s.rawSpread)],
        ['5% of |median|', fmt(s.floorSpread)],
        ['Spread', fmt(s.spread) + (s.status === 'scored' && s.floorSpread > s.rawSpread ? ' (floor)' : '')],
        ['Score', fmt(s.score)],
        ['Direction', s.status === 'scored' ? (s.signed > 0 ? 'above' : 'below') : '—'],
      ]);
      const v = $('score-verdict');
      if (s.status !== 'scored') { v.className = 'verdict'; v.textContent = `Unscored: only ${s.days} valid days of history, and 14 are needed. Unscored is not the same as normal.`; }
      else if (s.stat) { v.className = 'verdict flag'; v.textContent = `Flagged: ${fmt(s.score)} spreads ${s.signed > 0 ? 'above' : 'below'} its prior median, at or above the threshold of ${T.toFixed(1)}.`; }
      else { v.className = 'verdict ok'; v.textContent = `Not flagged: ${fmt(s.score)} spreads from its prior median, below the threshold of ${T.toFixed(1)}.`; }
      $('score-count').textContent = res.filter(x => x.stat).length + ' of ' + res.filter(x => x.status === 'scored').length + ' scored days flagged';
    }
    let drag = false;
    const pick = e => {
      const p = svgPoint(svg, e), t = Math.round((p.x - geo.L) / (geo.R - geo.L) * (N - 1));
      day.value = Math.max(0, Math.min(N - 1, t)); update();
    };
    svg.addEventListener('pointerdown', e => { drag = true; pick(e); });
    svg.addEventListener('pointermove', e => { if (drag) pick(e); });
    addEventListener('pointerup', () => { drag = false; });
    day.max = N - 1; day.addEventListener('input', update); thr.addEventListener('input', update);
    onLayoutChange(svg, update);
    update();
  })();

  /* 03 · Rules: inject one artificial fault, as src/history_detector/synthetic_faults.py does. */
  (function () {
    const svg = $('rules-chart'); if (!svg) return;
    const r = rng(11), N = 90, AT = 46, T = 4, base = [];
    for (let i = 0; i < N; i++) base.push(round1(30 + 3 * Math.sin(i / 7) + gauss(r) * 1.0));
    const sp = detect(base, { threshold: T })[AT].spread;
    const FAULTS = {
      spike: { days: 1, text: 'A one-day spike of 6 spreads.', make: y => { y[AT] = round1(y[AT] + 6 * sp); } },
      dropout: { days: 3, text: 'Three days of zeros.', make: y => { for (let i = 0; i < 3; i++) y[AT + i] = 0; } },
      stuck: { days: 10, text: 'The meter repeats one value for 10 days.', make: y => { for (let i = 1; i < 10; i++) y[AT + i] = y[AT]; } },
      drift: { days: 28, text: 'A linear drift that reaches 4 spreads after 28 days.', make: y => { for (let i = 0; i < 28; i++) y[AT + i] = round1(y[AT + i] + 4 * sp * (i + 1) / 28); } },
      negative: { days: 1, text: 'One negative reading, for example a sign error.', make: y => { y[AT] = -1.5; } },
    };
    let fault = 'stuck';
    const rulesBox = $('rules-on');
    function update() {
      const f = FAULTS[fault], y = base.slice();
      f.make(y);
      const res = detect(y, { threshold: T, rules: rulesBox.checked }), a = AT, b = AT + f.days - 1;
      drawSeries(svg, res, { threshold: T, sel: null, ymin: -4, ymax: 48, yticks: [0, 15, 30, 45], mark: [a, b] });
      const hits = res.filter(x => x.t >= a && x.t <= b && x.flag), other = res.filter(x => (x.t < a || x.t > b) && x.flag);
      const tally = {};
      hits.forEach(x => x.reasons.forEach(k => { tally[k] = (tally[k] || 0) + 1; }));
      const chips = Object.keys(tally).map(k => `<span class="chip ${['stuck', 'dropout', 'negative'].includes(k) ? 'r' : 'f'}">${k} × ${tally[k]}</span>`).join('');
      const v = $('rules-verdict');
      v.className = 'verdict ' + (hits.some(x => x.rule) ? 'rule' : hits.length ? 'flag' : '');
      v.innerHTML = `${f.text} <b>${hits.length} of ${f.days}</b> fault day${f.days > 1 ? 's' : ''} marked for review${other.length ? `, plus ${other.length} outside the fault` : ''}. ${chips}` +
        (fault === 'stuck' && !rulesBox.checked ? ' A stuck value sits close to the median, so the score alone does not catch it.' : '') +
        (fault === 'stuck' && rulesBox.checked ? ' The stuck rule fires from the 7th equal day.' : '') +
        (fault === 'drift' ? ' The baseline moves with a slow drift, so moderate drifts can go unflagged.' +
          (other.some(x => x.t > b) ? ' The flags after it come from the drop back to the old level, which the baseline had drifted away from.' : '') : '');
    }
    segmented($('rules-fault'), v => { fault = v; update(); });
    rulesBox.addEventListener('change', update);
    onLayoutChange(svg, update);
    update();
  })();

  /* 04 · Cases: flagged days of one series form a case when separated by at most the gap. */
  (function () {
    const svg = $('cases-grid'); if (!svg) return;
    const D = 28, S = ['Point A', 'Point B', 'Point C'];
    const cells = S.map(() => new Array(D).fill(0)); // 0 none, 1 score flag, 2 rule hit
    [[0, 3, 1], [0, 4, 1], [0, 6, 1], [0, 21, 1], [1, 13, 2], [1, 14, 2], [1, 15, 2], [1, 16, 2], [2, 8, 1], [2, 11, 1], [2, 24, 1], [2, 25, 1]]
      .forEach(([s, d, k]) => { cells[s][d] = k; });
    const r = rng(23), score = S.map(() => Array.from({ length: D }, () => 4 + r() * 5));
    const ruleScore = S.map(() => Array.from({ length: D }, () => .2 + r() * 1.6));
    const gapInput = $('cases-gap');
    function cases(gap) {
      const out = [];
      cells.forEach((row, s) => {
        let cur = null, last = -99;
        row.forEach((k, d) => {
          if (!k) return;
          if (!cur || d - last > gap + 1) { cur = { s, start: d, end: d, days: 0, peak: 0, rule: false }; out.push(cur); }
          cur.end = d; cur.days++; last = d;
          cur.peak = Math.max(cur.peak, k === 2 ? ruleScore[s][d] : score[s][d]);
          if (k === 2) cur.rule = true;
        });
      });
      // Rule hits first, then more flagged days, then higher peak score, then the later start.
      out.sort((p, q) => (q.rule - p.rule) || (q.days - p.days) || (q.peak - p.peak) || (q.start - p.start));
      out.forEach((c, i) => { c.rank = i + 1; });
      return out;
    }
    function update() {
      const gap = +gapInput.value; $('cases-gap-out').value = gap;
      clear(svg);
      const { W, narrow } = fit(svg, 220, 250);
      const L = narrow ? 40 : 92, cw = (W - 4 - L) / D, pad = narrow ? 1.5 : 3, top = 40, rowH = narrow ? 70 : 62;
      for (let d = 0; d < D; d += 7) svgEl(svg, 'text', { x: L + d * cw + cw / 2, y: 20, 'text-anchor': 'middle', class: 'ax' }, 'day ' + (d + 1));
      const list = cases(gap);
      list.forEach(c => {
        const y = top + c.s * rowH;
        svgEl(svg, 'rect', { x: L + c.start * cw, y: y - 4, width: (c.end - c.start + 1) * cw, height: cw - 2 * pad + 8, rx: 5, fill: 'none', stroke: c.rule ? C.rule : C.flag, 'stroke-width': 1.5, 'stroke-dasharray': '4 3' });
        svgEl(svg, 'text', { x: L + c.start * cw + 2, y: y + cw + (narrow ? 22 : 18), class: 'tag', fill: c.rule ? C.rule : C.flag }, '#' + c.rank);
      });
      cells.forEach((row, s) => {
        const y = top + s * rowH;
        svgEl(svg, 'text', { x: 0, y: y + cw / 2 + 4, class: 'tag', fill: C.mute }, narrow ? S[s].replace('Point ', '') : S[s]);
        row.forEach((k, d) => {
          const g = svgEl(svg, 'rect', {
            x: L + d * cw + pad, y: y, width: cw - 2 * pad, height: cw - 2 * pad, rx: 3,
            fill: k === 2 ? C.rule : k === 1 ? C.flag : 'rgba(233,238,240,.08)', 'data-s': s, 'data-d': d, style: 'cursor:pointer',
          });
          g.setAttribute('aria-label', `${S[s]}, day ${d + 1}: ${['not flagged', 'score flag', 'rule hit'][k]}`);
        });
      });
      $('cases-table').innerHTML = '<table><thead><tr><th>Rank</th><th>Series</th><th>Days</th><th>Flagged days</th><th>Rule hit</th><th>Peak score</th></tr></thead><tbody>' +
        list.map(c => `<tr><td>#${c.rank}</td><td>${S[c.s]}</td><td>${c.start + 1}–${c.end + 1}</td><td>${c.days}</td><td>${c.rule ? '<span class="chip r">yes</span>' : 'no'}</td><td>${fmt(c.peak)}</td></tr>`).join('') +
        '</tbody></table>';
    }
    svg.addEventListener('click', e => {
      const t = e.target; if (!t.dataset || t.dataset.s == null) return;
      const s = +t.dataset.s, d = +t.dataset.d;
      cells[s][d] = (cells[s][d] + 1) % 3; update();
    });
    gapInput.addEventListener('input', update);
    onLayoutChange(svg, update);
    update();
  })();

  /* 05 · Isolation Forest: unusual combinations are isolated by fewer random splits. */
  (function () {
    const svg = $('forest-chart'); if (!svg) return;
    const r = rng(5), pts = [];
    for (let i = 0; i < 220; i++) { const x = gauss(r) * .5; pts.push([x, .55 * x + gauss(r) * .38]); }
    [[2.3, .2], [-1.9, -1.5], [.3, 2.1], [2.5, 2.4], [-.4, -2.2], [-2.4, .9]].forEach(p => pts.push(p));
    const n = pts.length, limit = Math.ceil(Math.log2(Math.min(256, n)));
    const H = i => Math.log(i) + 0.5772156649;
    const cn = m => m > 2 ? 2 * H(m - 1) - 2 * (m - 1) / m : m === 2 ? 1 : 0;
    const tr = rng(42);
    function grow(idx, depth, maxDepth) {
      if (idx.length <= 1 || depth >= maxDepth) return { size: idx.length };
      const f = tr() < .5 ? 0 : 1;
      let lo = Infinity, hi = -Infinity;
      idx.forEach(i => { lo = Math.min(lo, pts[i][f]); hi = Math.max(hi, pts[i][f]); });
      if (lo === hi) return { size: idx.length };
      const split = lo + tr() * (hi - lo);
      return { f, split, left: grow(idx.filter(i => pts[i][f] < split), depth + 1, maxDepth), right: grow(idx.filter(i => pts[i][f] >= split), depth + 1, maxDepth) };
    }
    function pathLength(p, node, depth) { return node.size != null ? depth + cn(node.size) : pathLength(p, p[node.f] < node.split ? node.left : node.right, depth + 1); }
    // 100 trees on min(256, n) points, as in the real model; every point is used here.
    const all = pts.map((_, i) => i), trees = Array.from({ length: 100 }, () => grow(all, 0, limit));
    const avg = pts.map(p => trees.reduce((s, t) => s + pathLength(p, t, 0), 0) / trees.length);
    const ai = avg.map(h => Math.pow(2, -h / cn(n)));
    const lo = Math.min(...ai), hi = Math.max(...ai);
    const XL = 50, YT = 14, ext = 3;
    let XR = 990, YB = 470;
    const X = v => XL + (XR - XL) * (v + ext) / (2 * ext), Y = v => YB - (YB - YT) * (v + ext) / (2 * ext);
    const colour = s => { const k = Math.max(0, Math.min(1, (s - lo) / (hi - lo))) ** 1.6; return `rgb(${Math.round(143 + (240 - 143) * k)},${Math.round(161 + (163 - 161) * k)},${Math.round(168 + (94 - 168) * k)})`; };
    let sel = n - 3, timer = null;
    function base() {
      clear(svg);
      const size = fit(svg, 490, 600);
      XR = size.W - 10; YB = size.H - 22;
      [-2, -1, 0, 1, 2].forEach(v => {
        svgEl(svg, 'line', { x1: X(v), x2: X(v), y1: YT, y2: YB, stroke: C.line });
        svgEl(svg, 'line', { x1: XL, x2: XR, y1: Y(v), y2: Y(v), stroke: C.line });
        svgEl(svg, 'text', { x: X(v), y: YB + 20, 'text-anchor': 'middle', class: 'ax' }, v);
        svgEl(svg, 'text', { x: XL - 8, y: Y(v) + 4, 'text-anchor': 'end', class: 'ax' }, v);
      });
      svgEl(svg, 'text', { x: XR, y: YB - 8, 'text-anchor': 'end', class: 'tag', fill: C.mute }, 'signed deviation →');
      svgEl(svg, 'text', { x: XL + 8, y: YT + 14, class: 'tag', fill: C.mute }, '↑ one-day change');
      const box = svgEl(svg, 'g', {});
      pts.forEach((p, i) => svgEl(svg, 'circle', { cx: X(p[0]), cy: Y(p[1]), r: i === sel ? 7 : 4, fill: colour(ai[i]), stroke: i === sel ? C.ink : 'none', 'stroke-width': 2 }));
      return box;
    }
    function isolate() {
      clearTimeout(timer);
      const g = base(), p = pts[sel];
      let box = [-ext, ext, -ext, ext], idx = all.slice(), splits = [];
      const tr2 = rng(1 + Math.floor(Math.random() * 1e6));
      while (idx.length > 1 && splits.length < 60) {
        const f = tr2() < .5 ? 0 : 1;
        let a = Infinity, b = -Infinity;
        idx.forEach(i => { a = Math.min(a, pts[i][f]); b = Math.max(b, pts[i][f]); });
        if (a === b) break;
        const s = a + tr2() * (b - a);
        splits.push({ f, s, box: box.slice() });
        if (p[f] < s) { idx = idx.filter(i => pts[i][f] < s); if (f === 0) box[1] = s; else box[3] = s; }
        else { idx = idx.filter(i => pts[i][f] >= s); if (f === 0) box[0] = s; else box[2] = s; }
      }
      const shade = svgEl(g, 'rect', { fill: 'rgba(159,216,234,.08)', stroke: 'rgba(159,216,234,.4)' });
      const setBox = bx => { shade.setAttribute('x', X(bx[0])); shade.setAttribute('width', X(bx[1]) - X(bx[0])); shade.setAttribute('y', Y(bx[3])); shade.setAttribute('height', Y(bx[2]) - Y(bx[3])); };
      setBox([-ext, ext, -ext, ext]);
      let k = 0;
      const out = $('forest-out');
      const step = () => {
        if (k >= splits.length) {
          setBox(box);
          out.innerHTML = `This tree isolated the point after <b>${splits.length}</b> split${splits.length === 1 ? '' : 's'}. Averaged over 100 trees: <b>${fmt(avg[sel], 1)}</b> splits, ai_score <b>${fmt(ai[sel], 3)}</b> (range here ${fmt(lo, 2)}–${fmt(hi, 2)}).`;
          return;
        }
        const sp = splits[k++], bx = sp.box;
        if (sp.f === 0) svgEl(g, 'line', { x1: X(sp.s), x2: X(sp.s), y1: Y(bx[3]), y2: Y(bx[2]), stroke: C.acc, 'stroke-opacity': .55 });
        else svgEl(g, 'line', { x1: X(bx[0]), x2: X(bx[1]), y1: Y(sp.s), y2: Y(sp.s), stroke: C.acc, 'stroke-opacity': .55 });
        setBox(k < splits.length ? splits[k].box : box);
        out.innerHTML = `Split ${k}…`;
        timer = setTimeout(step, reduced ? 0 : Math.max(70, 380 - k * 18));
      };
      step();
    }
    svg.addEventListener('click', e => {
      const q = svgPoint(svg, e);
      let best = -1, dist = 900;
      pts.forEach((p, i) => { const d = (X(p[0]) - q.x) ** 2 + (Y(p[1]) - q.y) ** 2; if (d < dist) { dist = d; best = i; } });
      if (best >= 0) { sel = best; isolate(); }
    });
    $('forest-again').addEventListener('click', isolate);
    onLayoutChange(svg, isolate);
    $('forest-centre').addEventListener('click', () => { let best = 0; pts.forEach((p, i) => { if (Math.hypot(...p) < Math.hypot(...pts[best])) best = i; }); sel = best; isolate(); });
    isolate();
  })();

  /* 06 · Evaluate: a validation-year threshold, frozen and applied to the held-out year. */
  (function () {
    const svg = $('eval-chart'); if (!svg) return;
    function sample(seed, tail) {
      const r = rng(seed);
      return Array.from({ length: 4000 }, () => .4 + .045 * Math.abs(gauss(r)) + (r() < tail ? .05 + r() * .22 : 0));
    }
    const val = sample(101, .02), test = sample(202, .028).map(v => v + .004);
    const pct = $('eval-pct');
    function quantile(a, q) { const s = a.slice().sort((p, q2) => p - q2), i = (s.length - 1) * q, lo = Math.floor(i); return s[lo] + (s[Math.ceil(i)] - s[lo]) * (i - lo); }
    let XR = 990;
    function hist(g, data, y0, h, thr, label) {
      const lo = .38, hi = .7, bins = 64, w = (XR - 50) / bins, counts = new Array(bins).fill(0);
      data.forEach(v => { const b = Math.min(bins - 1, Math.max(0, Math.floor((v - lo) / (hi - lo) * bins))); counts[b]++; });
      const max = Math.max(...counts), sc = v => Math.sqrt(v / max) * h;
      counts.forEach((c, b) => {
        const x = 50 + b * w, edge = lo + (b + 1) * (hi - lo) / bins;
        if (c) svgEl(g, 'rect', { x: x + 1, y: y0 + h - sc(c), width: w - 2, height: sc(c), fill: edge > thr ? C.flag : 'rgba(143,161,168,.45)' });
      });
      svgEl(g, 'text', { x: 50, y: y0 - 8, class: 'tag', fill: C.mute }, label);
      const tx = 50 + (thr - lo) / (hi - lo) * (XR - 50);
      svgEl(g, 'line', { x1: tx, x2: tx, y1: y0 - 4, y2: y0 + h, stroke: C.ink, 'stroke-dasharray': '4 3' });
      return tx;
    }
    function update() {
      const q = +pct.value; $('eval-pct-out').value = q.toFixed(1);
      const thr = quantile(val, q / 100);
      clear(svg);
      const { W, narrow } = fit(svg, 345, 360);
      XR = W - 10;
      const tx = hist(svg, val, 34, 110, thr, narrow ? 'Validation 2024' : 'Validation 2024 · threshold set here');
      hist(svg, test, 206, 110, thr, narrow ? 'Held out 2025 · frozen' : 'Held out 2025 · same threshold, frozen');
      svgEl(svg, 'text', { x: tx - 8, y: 34 + (narrow ? -8 : 10), 'text-anchor': 'end', class: 'tag', fill: C.ink }, 'threshold ' + thr.toFixed(3));
      [.4, .5, .6, .7].forEach(v => svgEl(svg, 'text', { x: 50 + (v - .38) / .32 * (XR - 50), y: narrow ? 346 : 338, 'text-anchor': 'middle', class: 'ax' }, v.toFixed(1)));
      const rate = a => 100 * a.filter(v => v >= thr).length / a.length;
      $('eval-counts').innerHTML = `<span>Validation at or above <b>${rate(val).toFixed(1)}%</b></span><span>Held out at or above <b>${rate(test).toFixed(1)}%</b></span>`;
    }
    pct.addEventListener('input', update);
    onLayoutChange(svg, update);
    update();

    // Budget: each method picks its own top readings for one plant on one day, from the same eligible rows.
    const rows = [
      ['Point A', 5.8, '', .61], ['Point B', 1.2, 'stuck', .52], ['Point C', 3.9, '', .66],
      ['Point D', .8, '', .44], ['Point E', 2.7, '', .58], ['Point F', 4.4, '', .49],
    ];
    const baseOrder = rows.map((_, i) => i).sort((p, q) => ((rows[q][2] ? 1 : 0) - (rows[p][2] ? 1 : 0)) || rows[q][1] - rows[p][1]);
    const aiOrder = rows.map((_, i) => i).sort((p, q) => rows[q][3] - rows[p][3]);
    const budget = $('eval-budget');
    function updateBudget() {
      const k = +budget.value; $('eval-budget-out').value = k;
      const a = new Set(baseOrder.slice(0, k)), b = new Set(aiOrder.slice(0, k));
      $('eval-table').innerHTML = '<table><thead><tr><th>Reading</th><th>History score</th><th>Rule</th><th>ai_score</th><th>Baseline rank</th><th>Forest rank</th><th>Picked by</th></tr></thead><tbody>' +
        rows.map((row, i) => {
          const by = [a.has(i) ? '<span class="chip a">baseline</span>' : '', b.has(i) ? '<span class="chip f">forest</span>' : ''].join('');
          return `<tr class="${by ? 'pick' : ''}"><td>${row[0]}</td><td>${row[1].toFixed(1)}</td><td>${row[2] ? `<span class="chip r">${row[2]}</span>` : '—'}</td><td>${row[3].toFixed(2)}</td><td>${baseOrder.indexOf(i) + 1}</td><td>${aiOrder.indexOf(i) + 1}</td><td>${by || '<span style="color:var(--mute)">deferred</span>'}</td></tr>`;
        }).join('') + '</tbody></table>';
      $('eval-overlap').innerHTML = `<span>Budget <b>${k}</b> per method</span><span>Picked by both <b>${[...a].filter(i => b.has(i)).length}</b></span><span>Deferred is not safe</span>`;
    }
    budget.addEventListener('input', updateBudget);
    updateBudget();
  })();
})();
