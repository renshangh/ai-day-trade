/* Trading desk dashboard.
   Charts are drawn on one shared canvas so the price / volume / RSI / MACD panes
   keep a single x-scale and a single crosshair. Colors come from CSS custom
   properties (see style.css) so light/dark swap in one place. */

'use strict';

const LOOKBACKS = [1, 2, 3, 4, 5];
const RANGES = [
  { key: '3M', bars: 63 },
  { key: '6M', bars: 126 },
  { key: '1Y', bars: 252 },
  { key: '2Y', bars: Infinity },
];

// Overlay definitions. `slot` maps to the validated categorical palette order.
const OVERLAYS = [
  { key: 'sma20',  label: 'SMA 20',  series: 'sma20',  slot: 1, on: true },
  { key: 'sma50',  label: 'SMA 50',  series: 'sma50',  slot: 2, on: true },
  { key: 'sma200', label: 'SMA 200', series: 'sma200', slot: 3, on: true },
  { key: 'vwap20', label: 'VWAP 20', series: 'vwap20', slot: 4, on: false },
  { key: 'bb',     label: 'Bollinger 20,2', series: null, slot: 0, on: false },
];

const state = {
  lookback: 1,
  range: '6M',
  board: null,
  group: null,        // group name being shown in the leaders strip
  symbol: null,
  stock: null,
  overlays: Object.fromEntries(OVERLAYS.map(o => [o.key, o.on])),
  tableView: false,
  hover: null,        // index into the visible slice
  loading: false,
};

// ---------------------------------------------------------------- helpers
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Chart geometry. Shared by the renderer and the pointer/keyboard hit-testing so
// the two cannot drift -- these were duplicated as literals in three places, and
// changing the renderer's padding silently mis-aimed the crosshair.
const PAD = { left: 8, right: 66, top: 10, xAxis: 24, gap: 12 };
const CHART_H = 640;

const $ = id => document.getElementById(id);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const slotColor = n => css(`--series-${n}`);

const fmtPct = v => (v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`);
const fmtPx = v => (v == null ? '—' : v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const fmtNum = (v, d = 2) => (v == null ? '—' : v.toFixed(d));
const signClass = v => (v == null ? '' : v >= 0 ? 'pos' : 'neg');

function fmtVol(v) {
  if (v == null) return '—';
  if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B';
  if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return String(Math.round(v));
}

function niceTicks(min, max, count) {
  if (!isFinite(min) || !isFinite(max) || min === max) return [min];
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  // Include 2.5 -- without it the step jumps straight from 2 to 5, which on a
  // ~150-wide range collapses the axis to two gridlines.
  const step = (norm >= 5 ? 10 : norm >= 2.5 ? 5 : norm >= 2 ? 2.5 : norm >= 1 ? 2 : 1) * mag;
  const out = [];
  for (let t = Math.ceil(min / step) * step; t <= max + 1e-9; t += step) out.push(t);
  return out;
}

// ------------------------------------------------------------ data access
async function fetchBoard(force) {
  const wrap = $('hero-card');
  wrap.classList.add('refetching');
  try {
    const res = await fetch(`/api/board${force ? '?force=1' : ''}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    state.board = data;
    renderNotices();
    renderAll();
  } catch (e) {
    showError(`Could not load the board: ${e.message}`);
  } finally {
    wrap.classList.remove('refetching');
  }
}

async function fetchStock(symbol, force) {
  state.loading = true;
  $('chart-wrap').classList.add('refetching');
  try {
    const res = await fetch(`/api/stock?symbol=${encodeURIComponent(symbol)}${force ? '&force=1' : ''}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    state.stock = data;
    state.symbol = symbol;
    state.hover = null;
    renderDetail();
  } catch (e) {
    $('d-sym').textContent = symbol;
    $('d-px').textContent = '';
    showError(`Could not load ${symbol}: ${e.message}`);
  } finally {
    state.loading = false;
    $('chart-wrap').classList.remove('refetching');
  }
}

function showError(msg) {
  const box = $('notices');
  // Replace any previous error rather than appending; a flapping connection was
  // otherwise able to stack notices until they pushed the board off-screen.
  box.querySelectorAll('.notice.err').forEach(n => n.remove());
  const el = document.createElement('div');
  el.className = 'notice err';
  el.append(Object.assign(document.createElement('span'), { className: 'ico', textContent: '⚠' }));
  el.append(Object.assign(document.createElement('span'), { textContent: msg }));
  box.appendChild(el);
}

// ------------------------------------------------------------- rendering
function renderNotices() {
  const box = $('notices');
  box.innerHTML = '';
  const b = state.board;
  if (!b) return;

  if (b.stale) {
    const el = document.createElement('div');
    el.className = 'notice warn';
    el.innerHTML = `<span class="ico">⚠</span><span><strong>Showing last known-good data.</strong>
      The live refresh failed (${b.stale_reason || 'unknown error'}), so these figures are from
      ${new Date(b.generated_at).toLocaleString()} — not current.</span>`;
    box.appendChild(el);
  }

  const omitted = b.omitted || {};
  const groups = Object.keys(omitted);
  if (groups.length) {
    const total = groups.reduce((n, g) => n + omitted[g].length, 0);
    const detail = groups.map(g => `${g}: ${[...new Set(omitted[g])].join(', ')}`).join(' · ');
    const el = document.createElement('div');
    el.className = 'notice warn';
    el.innerHTML = `<span class="ico">⚠</span><span><strong>${total} symbol${total > 1 ? 's' : ''} omitted</strong>
      — no bars returned on the ${b.feed.toUpperCase()} feed, so they are excluded rather than
      substituted. ${detail}</span>`;
    box.appendChild(el);
  }
}

function renderLookbackTabs() {
  const box = $('lookback-tabs');
  box.innerHTML = '';
  LOOKBACKS.forEach(lb => {
    const btn = document.createElement('button');
    btn.textContent = `${lb}D`;
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', String(state.lookback === lb));
    btn.className = state.lookback === lb ? 'active' : '';
    btn.onclick = () => { state.lookback = lb; state.group = null; renderAll(); };
    box.appendChild(btn);
  });
}

function currentSlice() {
  if (!state.board) return null;
  return state.board.lookbacks[String(state.lookback)];
}

function activeGroup() {
  const slice = currentSlice();
  if (!slice) return null;
  if (state.group) {
    const found = slice.rankings.find(g => g.group === state.group);
    if (found) return found;
  }
  return slice.hottest;
}

function renderHero() {
  const slice = currentSlice();
  const g = slice && slice.hottest;
  const el = $('hero');
  if (!g) { el.innerHTML = '<div class="loading">No ranking available.</div>'; return; }

  const bench = slice.benchmarks.find(b => b.symbol === 'SPY');
  const vsSpy = bench && bench.return_pct != null ? g.mean_return_pct - bench.return_pct : null;

  el.innerHTML = `
    <div>
      <div class="lede">Hottest group · ${state.lookback} trading day${state.lookback > 1 ? 's' : ''}</div>
      <div class="group-name">${g.group}<span class="kind">${g.kind}</span></div>
    </div>
    <div class="stat">
      <div class="k">Mean return</div>
      <div class="v ${signClass(g.mean_return_pct)}">${fmtPct(g.mean_return_pct)}</div>
    </div>
    <div class="stat">
      <div class="k">Median</div>
      <div class="v ${signClass(g.median_return_pct)}">${fmtPct(g.median_return_pct)}</div>
    </div>
    <div class="stat">
      <div class="k">Breadth up</div>
      <div class="v">${g.breadth_pct.toFixed(0)}%</div>
    </div>
    <div class="stat">
      <div class="k">vs SPY</div>
      <div class="v ${signClass(vsSpy)}">${vsSpy == null ? '—' : fmtPct(vsSpy)}</div>
    </div>
    <div class="stat">
      <div class="k">${g.etf ? `${g.etf} proxy` : 'Members'}</div>
      <div class="v ${g.etf ? signClass(g.etf_return_pct) : ''}">${
        g.etf ? fmtPct(g.etf_return_pct) : g.member_count}</div>
    </div>`;

  $('asof').textContent = state.board.as_of_session
    ? `session ${state.board.as_of_session} · ${state.board.feed.toUpperCase()} feed · ${state.board.universe_size} symbols`
    : '';
  $('lookback-note').textContent =
    `${state.lookback} trading session${state.lookback > 1 ? 's' : ''} through ${state.board.as_of_session || '—'}`;
}

function renderRankChart() {
  const slice = currentSlice();
  const box = $('rank-chart');
  box.innerHTML = '';
  if (!slice) return;

  const rows = slice.rankings;
  const vals = rows.map(r => r.mean_return_pct);
  const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
  const span = (hi - lo) || 1;
  const zeroPct = ((0 - lo) / span) * 100;
  const active = activeGroup();

  rows.forEach(r => {
    const row = document.createElement('div');
    row.className = 'rank-row' + (active && r.group === active.group ? ' leader' : '');
    row.tabIndex = 0;
    row.setAttribute('role', 'button');
    row.setAttribute('aria-label', `${r.group}, mean return ${fmtPct(r.mean_return_pct)}`);

    const v = r.mean_return_pct;
    const from = Math.min(v, 0), to = Math.max(v, 0);
    const left = ((from - lo) / span) * 100;
    const width = ((to - from) / span) * 100;

    row.innerHTML = `
      <div class="name" title="${r.group}">${r.group}</div>
      <div class="bar-track">
        <div class="zero-rule" style="left:${zeroPct}%"></div>
        <div class="bar" style="left:${left}%;width:${Math.max(width, 0.4)}%"></div>
      </div>
      <div class="val">${fmtPct(v)}</div>`;

    const pick = () => selectGroup(r.group);
    row.onclick = pick;
    row.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } };
    box.appendChild(row);
  });

  $('rank-sub').textContent =
    `Equal-weight mean return of each group's constituents over ${state.lookback} trading ` +
    `session${state.lookback > 1 ? 's' : ''}. Click a row to load its top movers.`;
}

function sparkline(bars) {
  // Last ~30 closes, colored by net direction. Decorative context only —
  // every number it implies is also in the card text and the table view.
  if (!bars || bars.length < 2) return '';
  const w = 180, h = 30, pad = 2;
  const lo = Math.min(...bars), hi = Math.max(...bars), span = (hi - lo) || 1;
  const pts = bars.map((v, i) => {
    const x = pad + (i / (bars.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - lo) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const up = bars[bars.length - 1] >= bars[0];
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="100%" height="30" aria-hidden="true">
    <polyline points="${pts}" fill="none" stroke="${up ? css('--up') : css('--down')}"
      stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function renderLeaders() {
  const g = activeGroup();
  const box = $('leaders');
  box.innerHTML = '';
  if (!g) return;

  $('leaders-title').textContent = `Top ${g.top.length} — ${g.group}`;
  $('leaders-sub').textContent =
    `Best ${state.lookback}-day performers inside ${g.group} (${g.member_count} members priced). ` +
    `Click a card to chart it.`;

  g.top.forEach((m, i) => {
    const card = document.createElement('button');
    card.className = 'stock-card' + (state.symbol === m.symbol ? ' selected' : '');
    card.innerHTML = `
      <div class="rankno">#${i + 1}</div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">
        <span class="sym">${m.symbol}</span>
        <span class="ret ${signClass(m.return_pct)}">${fmtPct(m.return_pct)}</span>
      </div>
      <div class="px">${fmtPx(m.last_close)} · vol ${fmtVol(m.volume)}</div>
      <div class="spark-cap">30-day trend</div>
      <div class="spark-slot"></div>`;
    card.onclick = () => { selectStock(m.symbol); };
    box.appendChild(card);

    // Sparkline needs bar history, which only the per-stock endpoint has.
    // Fetch lazily so the board paints immediately.
    fetch(`/api/stock?symbol=${encodeURIComponent(m.symbol)}`)
      .then(r => r.json())
      .then(d => {
        if (!d.bars || !d.bars.length) return;
        const closes = d.bars.slice(-30).map(b => b.c);
        const slot = card.querySelector('.spark-slot');
        if (slot) slot.innerHTML = sparkline(closes);
      })
      .catch(() => { /* sparkline is optional context; card text still stands */ });
  });
}

function selectStock(symbol) {
  document.querySelectorAll('.stock-card').forEach(c => {
    c.classList.toggle('selected', c.querySelector('.sym').textContent === symbol);
  });
  fetchStock(symbol);
  $('detail-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderRangeTabs() {
  const box = $('range-tabs');
  box.innerHTML = '';
  RANGES.forEach(r => {
    const btn = document.createElement('button');
    btn.textContent = r.key;
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', String(state.range === r.key));
    btn.className = state.range === r.key ? 'active' : '';
    btn.onclick = () => { state.range = r.key; state.hover = null; renderDetail(); };
    box.appendChild(btn);
  });
}

function renderOverlayToggles() {
  const box = $('overlay-toggles');
  box.innerHTML = '';
  OVERLAYS.forEach(o => {
    const btn = document.createElement('button');
    const color = o.slot ? slotColor(o.slot) : css('--band-line');
    btn.innerHTML = `<span class="swatch" style="background:${color}"></span>${o.label}`;
    btn.setAttribute('aria-pressed', String(!!state.overlays[o.key]));
    btn.onclick = () => { state.overlays[o.key] = !state.overlays[o.key]; renderDetail(); };
    box.appendChild(btn);
  });
}

function renderLegend() {
  // A legend is always present for >= 2 series, so identity is never color-alone.
  const box = $('chart-legend');
  const on = OVERLAYS.filter(o => state.overlays[o.key] && o.series);
  const items = [
    `<span class="item"><span class="line" style="background:${css('--up')}"></span>Up day</span>`,
    `<span class="item"><span class="line" style="background:${css('--down')}"></span>Down day</span>`,
    ...on.map(o => `<span class="item"><span class="line" style="background:${slotColor(o.slot)}"></span>${o.label}</span>`),
  ];
  box.innerHTML = items.join('');
}

// --------------------------------------------------------- the main chart
function visibleSlice() {
  const s = state.stock;
  if (!s || !s.bars || !s.bars.length) return null;
  const r = RANGES.find(x => x.key === state.range) || RANGES[1];
  const n = s.bars.length;
  const start = r.bars === Infinity ? 0 : Math.max(0, n - r.bars);
  const sliceSeries = arr => (Array.isArray(arr) ? arr.slice(start) : []);
  const ind = {};
  for (const k of Object.keys(s.indicators || {})) ind[k] = sliceSeries(s.indicators[k]);
  return { bars: s.bars.slice(start), ind };
}

function drawChart() {
  const canvas = $('chart');
  const view = visibleSlice();
  if (!view) return;

  const { bars, ind } = view;
  const n = bars.length;
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.parentElement.clientWidth;
  const cssH = CHART_H;
  canvas.style.height = cssH + 'px';
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  const padL = PAD.left, padR = PAD.right, padT = PAD.top, xAxisH = PAD.xAxis, gap = PAD.gap;
  const plotW = plotWidth(cssW);
  const bodyH = cssH - padT - xAxisH;
  // Pane heights are fractions of bodyH, then scaled down to leave room for the
  // three inter-pane gaps so the last pane can't run into the x-axis band.
  const scale = (bodyH - gap * 3) / bodyH;
  const h = {
    price: bodyH * 0.52 * scale,
    vol: bodyH * 0.13 * scale,
    rsi: bodyH * 0.16 * scale,
    macd: bodyH * 0.19 * scale,
  };
  const y0 = { price: padT };
  y0.vol = y0.price + h.price + gap;
  y0.rsi = y0.vol + h.vol + gap;
  y0.macd = y0.rsi + h.rsi + gap;

  const barW = plotW / n;
  const xOf = i => padL + i * barW + barW / 2;

  const C = {
    grid: css('--grid'), axis: css('--axis'), muted: css('--text-muted'),
    text: css('--text-primary'), sec: css('--text-secondary'),
    up: css('--up'), down: css('--down'),
    band: css('--band'), bandLine: css('--band-line'),
    surface: css('--surface-2'),
  };
  ctx.font = `11px ${css('--sans')}`;

  // ---- price scale
  // Price action owns the scale. Overlays may stretch it only so far: a long
  // moving average can sit far from current price (AXTI's SMA200 is an order of
  // magnitude below spot), and letting it drive the axis squashes the candles
  // into a corner. Anything past the clamp is clipped to the pane instead.
  let barLo = Infinity, barHi = -Infinity;
  bars.forEach(b => { barLo = Math.min(barLo, b.l); barHi = Math.max(barHi, b.h); });
  const barSpan = (barHi - barLo) || 1;
  const slack = barSpan * 0.25;

  let ovLo = Infinity, ovHi = -Infinity;
  const activeSeries = OVERLAYS.filter(o => state.overlays[o.key] && o.series).map(o => o.series);
  if (state.overlays.bb) activeSeries.push('bb_upper', 'bb_lower');
  activeSeries.forEach(k => (ind[k] || []).forEach(v => {
    if (v != null) { ovLo = Math.min(ovLo, v); ovHi = Math.max(ovHi, v); }
  }));

  let lo = barLo, hi = barHi;
  if (isFinite(ovLo)) lo = Math.min(barLo, Math.max(ovLo, barLo - slack));
  if (isFinite(ovHi)) hi = Math.max(barHi, Math.min(ovHi, barHi + slack));
  const padY = (hi - lo) * 0.05 || 1;
  lo -= padY; hi += padY;
  const yPrice = v => y0.price + h.price - ((v - lo) / (hi - lo)) * h.price;

  // helpers ------------------------------------------------------------
  const hline = (yy, color) => {
    ctx.strokeStyle = color; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, Math.round(yy) + 0.5); ctx.lineTo(padL + plotW, Math.round(yy) + 0.5); ctx.stroke();
  };
  const label = (txt, xx, yy, color, align = 'left', baseline = 'middle') => {
    ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = baseline;
    ctx.fillText(txt, xx, yy);
  };
  const paneFrame = (key, title) => {
    ctx.strokeStyle = C.axis; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, Math.round(y0[key] + h[key]) + 0.5);
    ctx.lineTo(padL + plotW, Math.round(y0[key] + h[key]) + 0.5); ctx.stroke();
    if (title) label(title, padL + 4, y0[key] + 9, C.muted);
  };
  // Pane titles are drawn last, over a surface chip, so a series line running
  // through the top-left corner can't render them unreadable.
  const paneTitle = (key, title) => {
    const w = ctx.measureText(title).width + 8;
    ctx.fillStyle = C.surface;
    ctx.fillRect(padL + 1, y0[key] + 1, w, 16);
    label(title, padL + 5, y0[key] + 9, C.muted);
  };
  const drawLine = (series, color, width = 1.5) => {
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineJoin = 'round';
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < n; i++) {
      const v = series[i];
      if (v == null) { started = false; continue; }
      const px = xOf(i), py = yPrice(v);
      if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
    }
    ctx.stroke();
  };

  // ---- price pane grid + right axis (tick count follows pane height, ~44px apart)
  niceTicks(lo, hi, Math.max(4, Math.round(h.price / 44))).forEach(t => {
    const yy = yPrice(t);
    if (yy < y0.price || yy > y0.price + h.price) return;
    hline(yy, C.grid);
    label(t.toFixed(2), padL + plotW + 6, yy, C.muted);
  });

  const bodyW = Math.max(1, Math.min(barW - 2, 14));

  // Price-pane marks are clipped, so an overlay parked outside the clamped
  // scale above can't bleed down into the volume / RSI / MACD panes.
  ctx.save();
  ctx.beginPath();
  ctx.rect(padL, y0.price, plotW, h.price);
  ctx.clip();

  // ---- Bollinger band (fill first, under everything)
  if (state.overlays.bb && ind.bb_upper && ind.bb_lower) {
    ctx.fillStyle = C.band;
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < n; i++) {
      if (ind.bb_upper[i] == null) continue;
      const px = xOf(i), py = yPrice(ind.bb_upper[i]);
      if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
    }
    for (let i = n - 1; i >= 0; i--) {
      if (ind.bb_lower[i] == null) continue;
      ctx.lineTo(xOf(i), yPrice(ind.bb_lower[i]));
    }
    ctx.closePath(); ctx.fill();
    drawLine(ind.bb_upper, C.bandLine, 1);
    drawLine(ind.bb_lower, C.bandLine, 1);
  }

  // ---- candles (thin marks; wick + body, 2px surface gap between bodies)
  for (let i = 0; i < n; i++) {
    const b = bars[i];
    const up = b.c >= b.o;
    const color = up ? C.up : C.down;
    const px = xOf(i);
    ctx.strokeStyle = color; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(Math.round(px) + 0.5, yPrice(b.h));
    ctx.lineTo(Math.round(px) + 0.5, yPrice(b.l));
    ctx.stroke();
    const yo = yPrice(b.o), yc = yPrice(b.c);
    const top = Math.min(yo, yc), hgt = Math.max(Math.abs(yc - yo), 1);
    ctx.fillStyle = color;
    ctx.fillRect(px - bodyW / 2, top, bodyW, hgt);
  }

  // ---- moving-average overlay lines
  const shown = OVERLAYS.filter(o => state.overlays[o.key] && o.series);
  shown.forEach(o => drawLine(ind[o.series] || [], slotColor(o.slot), 1.5));
  ctx.restore();

  // ---- selective direct labels at each overlay's endpoint.
  // These satisfy the relief rule for the sub-3:1 light-mode slots, so they
  // must stay legible: collect, de-collide, then draw.
  const endLabels = [];
  shown.forEach(o => {
    const series = ind[o.series] || [];
    for (let i = n - 1; i >= 0; i--) {
      if (series[i] != null) {
        endLabels.push({ y: yPrice(series[i]), text: o.label, color: slotColor(o.slot) });
        break;
      }
    }
  });
  const GAP = 15;
  endLabels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < endLabels.length; i++) {
    if (endLabels[i].y - endLabels[i - 1].y < GAP) endLabels[i].y = endLabels[i - 1].y + GAP;
  }
  if (endLabels.length) {
    // Keep the whole stack inside the price pane rather than letting it run out.
    const over = endLabels[endLabels.length - 1].y - (y0.price + h.price - 9);
    if (over > 0) endLabels.forEach(l => { l.y -= over; });
    const under = (y0.price + 9) - endLabels[0].y;
    if (under > 0) endLabels.forEach(l => { l.y += under; });
  }
  endLabels.forEach(l => {
    const w = ctx.measureText(l.text).width + 8;
    const x = padL + plotW - w - 2;
    ctx.fillStyle = C.surface;
    ctx.fillRect(x, l.y - 8, w, 16);
    label(l.text, x + 4, l.y, l.color);
  });

  // ---- volume pane
  paneFrame('vol', '');
  const vMax = Math.max(...bars.map(b => b.v)) || 1;
  const yVol = v => y0.vol + h.vol - (v / vMax) * (h.vol - 12);
  for (let i = 0; i < n; i++) {
    const b = bars[i];
    ctx.fillStyle = b.c >= b.o ? C.up : C.down;
    ctx.globalAlpha = 0.45;
    const yy = yVol(b.v);
    ctx.fillRect(xOf(i) - bodyW / 2, yy, bodyW, y0.vol + h.vol - yy);
    ctx.globalAlpha = 1;
  }
  if (ind.vol_sma20) {
    ctx.strokeStyle = slotColor(1); ctx.lineWidth = 1.2;
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < n; i++) {
      const v = ind.vol_sma20[i];
      if (v == null) { started = false; continue; }
      const px = xOf(i), py = yVol(v);
      if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
    }
    ctx.stroke();
  }
  label(fmtVol(vMax), padL + plotW + 6, y0.vol + 8, C.muted);

  // ---- RSI pane (single series -> title names it, no legend box needed)
  paneFrame('rsi', '');
  const yRsi = v => y0.rsi + h.rsi - (v / 100) * h.rsi;
  [30, 70].forEach(t => {
    hline(yRsi(t), C.grid);
    label(String(t), padL + plotW + 6, yRsi(t), C.muted);
  });
  ctx.strokeStyle = slotColor(1); ctx.lineWidth = 1.5;
  ctx.beginPath();
  let rStarted = false;
  for (let i = 0; i < n; i++) {
    const v = (ind.rsi14 || [])[i];
    if (v == null) { rStarted = false; continue; }
    const px = xOf(i), py = yRsi(v);
    if (!rStarted) { ctx.moveTo(px, py); rStarted = true; } else ctx.lineTo(px, py);
  }
  ctx.stroke();

  // ---- MACD pane
  paneFrame('macd', '');
  const macdVals = [];
  ['macd', 'macd_signal', 'macd_hist'].forEach(k => (ind[k] || []).forEach(v => { if (v != null) macdVals.push(v); }));
  const mMax = Math.max(...macdVals.map(Math.abs), 0.0001);
  const yMacd = v => y0.macd + h.macd / 2 - (v / mMax) * (h.macd / 2 - 8);
  hline(yMacd(0), C.axis);
  for (let i = 0; i < n; i++) {
    const v = (ind.macd_hist || [])[i];
    if (v == null) continue;
    ctx.fillStyle = v >= 0 ? C.up : C.down;
    ctx.globalAlpha = 0.5;
    const yz = yMacd(0), yy = yMacd(v);
    ctx.fillRect(xOf(i) - bodyW / 2, Math.min(yz, yy), bodyW, Math.abs(yy - yz) || 1);
    ctx.globalAlpha = 1;
  }
  [['macd', 1], ['macd_signal', 2]].forEach(([k, slot]) => {
    ctx.strokeStyle = slotColor(slot); ctx.lineWidth = 1.5;
    ctx.beginPath();
    let st = false;
    for (let i = 0; i < n; i++) {
      const v = (ind[k] || [])[i];
      if (v == null) { st = false; continue; }
      const px = xOf(i), py = yMacd(v);
      if (!st) { ctx.moveTo(px, py); st = true; } else ctx.lineTo(px, py);
    }
    ctx.stroke();
  });
  label(mMax.toFixed(2), padL + plotW + 6, yMacd(mMax) + 6, C.muted);

  // ---- pane titles, drawn over their series on a surface chip
  paneTitle('vol', 'Volume');
  paneTitle('rsi', 'RSI 14');
  paneTitle('macd', 'MACD 12,26,9');

  // ---- x axis (dates) -- "Feb 6", with the year appended when it changes
  const tickCount = Math.max(2, Math.floor(plotW / 96));
  const step = Math.max(1, Math.floor(n / tickCount));
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  let lastYear = null;
  for (let i = 0; i < n; i += step) {
    const [y, m, d] = bars[i].t.split('-');
    let txt = `${MONTHS[+m - 1]} ${+d}`;
    if (y !== lastYear) { txt += ` '${y.slice(2)}`; lastYear = y; }
    // Keep the centered label inside the plot -- the first tick sits at
    // barW/2, so an uncorrected center-align clips its leading characters.
    const half = ctx.measureText(txt).width / 2;
    const x = Math.min(Math.max(xOf(i), padL + half), padL + plotW - half);
    ctx.fillStyle = C.muted;
    ctx.fillText(txt, x, cssH - xAxisH + 6);
  }

  // ---- crosshair
  if (state.hover != null && state.hover >= 0 && state.hover < n) {
    const i = state.hover;
    const px = Math.round(xOf(i)) + 0.5;
    ctx.strokeStyle = C.axis; ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.beginPath(); ctx.moveTo(px, padT); ctx.lineTo(px, cssH - xAxisH); ctx.stroke();
    const py = yPrice(bars[i].c);
    ctx.beginPath(); ctx.moveTo(padL, Math.round(py) + 0.5); ctx.lineTo(padL + plotW, Math.round(py) + 0.5); ctx.stroke();
    // price tag on the right axis
    const tag = bars[i].c.toFixed(2);
    const tw = ctx.measureText(tag).width + 10;
    ctx.fillStyle = C.axis;
    ctx.fillRect(padL + plotW + 2, py - 9, tw, 18);
    label(tag, padL + plotW + 7, py, C.text);
  }
}

function renderTooltip(clientX, clientY) {
  const tip = $('tooltip');
  const view = visibleSlice();
  if (!view || state.hover == null) { tip.classList.remove('on'); return; }
  const { bars, ind } = view;
  const i = state.hover;
  const b = bars[i];
  if (!b) { tip.classList.remove('on'); return; }

  const prev = i > 0 ? bars[i - 1].c : null;
  const chg = prev ? ((b.c / prev - 1) * 100) : null;
  const row = (k, v) => `<div class="t-row"><span class="k">${k}</span><span class="v">${v}</span></div>`;

  let html = `<div class="t-date">${b.t}</div>`;
  html += row('O', fmtPx(b.o)) + row('H', fmtPx(b.h)) + row('L', fmtPx(b.l)) + row('C', fmtPx(b.c));
  html += row('Chg', chg == null ? '—' : fmtPct(chg));
  html += row('Vol', fmtVol(b.v));
  html += '<div class="t-sep"></div>';
  OVERLAYS.filter(o => state.overlays[o.key] && o.series).forEach(o => {
    html += row(o.label, fmtPx((ind[o.series] || [])[i]));
  });
  if (state.overlays.bb) {
    html += row('BB upper', fmtPx((ind.bb_upper || [])[i]));
    html += row('BB lower', fmtPx((ind.bb_lower || [])[i]));
  }
  html += row('RSI 14', fmtNum((ind.rsi14 || [])[i], 1));
  html += row('MACD', fmtNum((ind.macd || [])[i], 3));
  html += row('Signal', fmtNum((ind.macd_signal || [])[i], 3));
  html += row('ATR 14', fmtNum((ind.atr14 || [])[i], 2));
  html += row('Stoch %K', fmtNum((ind.stoch_k || [])[i], 1));

  tip.innerHTML = html;
  tip.classList.add('on');

  const wrap = $('chart-wrap').getBoundingClientRect();
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  let left = clientX - wrap.left + 16;
  let top = clientY - wrap.top + 16;
  if (left + tw > wrap.width) left = clientX - wrap.left - tw - 16;
  if (top + th > wrap.height) top = Math.max(4, wrap.height - th - 4);
  tip.style.left = left + 'px';
  tip.style.top = top + 'px';
}

/** Plot width for a given canvas CSS width. Single source of truth for both
 *  the renderer and hit-testing. */
function plotWidth(cssW) { return cssW - PAD.left - PAD.right; }

/** X pixel (page coords) of bar `i`, used to place the keyboard tooltip. */
function barClientX(rect, n, i) {
  const barW = plotWidth(rect.width) / n;
  return rect.left + PAD.left + i * barW + barW / 2;
}

function indexFromEvent(e) {
  const view = visibleSlice();
  if (!view) return null;
  const rect = $('chart').getBoundingClientRect();
  const n = view.bars.length;
  const barW = plotWidth(rect.width) / n;
  const i = Math.floor((e.clientX - rect.left - PAD.left) / barW);
  return Math.max(0, Math.min(n - 1, i));
}

function renderTableView() {
  const box = $('table-view');
  const view = visibleSlice();
  if (!view) { box.innerHTML = ''; return; }
  const { bars, ind } = view;
  // Most recent first, capped so the DOM stays light; the range tabs control depth.
  const rows = [];
  for (let i = bars.length - 1; i >= Math.max(0, bars.length - 120); i--) {
    const b = bars[i];
    rows.push(`<tr>
      <td>${b.t}</td><td>${fmtPx(b.o)}</td><td>${fmtPx(b.h)}</td><td>${fmtPx(b.l)}</td>
      <td>${fmtPx(b.c)}</td><td>${fmtVol(b.v)}</td>
      <td>${fmtPx((ind.sma20 || [])[i])}</td><td>${fmtPx((ind.sma50 || [])[i])}</td>
      <td>${fmtPx((ind.sma200 || [])[i])}</td><td>${fmtNum((ind.rsi14 || [])[i], 1)}</td>
      <td>${fmtNum((ind.macd || [])[i], 3)}</td><td>${fmtNum((ind.macd_signal || [])[i], 3)}</td>
      <td>${fmtNum((ind.atr14 || [])[i], 2)}</td><td>${fmtPx((ind.vwap20 || [])[i])}</td>
    </tr>`);
  }
  box.innerHTML = `<table>
    <thead><tr>
      <th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th>
      <th>SMA20</th><th>SMA50</th><th>SMA200</th><th>RSI14</th>
      <th>MACD</th><th>Signal</th><th>ATR14</th><th>VWAP20</th>
    </tr></thead><tbody>${rows.join('')}</tbody></table>`;
}

function renderRankTable() {
  const slice = currentSlice();
  const box = $('rank-table');
  if (!slice) { box.innerHTML = ''; return; }
  const active = activeGroup();
  const rows = slice.rankings.map((r, i) => {
    const isActive = active && r.group === active.group;
    // No role="button" here: overriding a <tr>'s implicit row role breaks the
    // table's structure for screen readers. aria-current is valid on any element
    // and is what conveys "this is the group being shown".
    return `<tr class="pick-row${isActive ? ' selected' : ''}" data-group="${r.group
      .replace(/"/g, '&quot;')}" tabindex="0"${isActive ? ' aria-current="true"' : ''}>
      <td>${i + 1}</td><td>${r.group}</td><td>${r.kind}</td>
      <td>${fmtPct(r.mean_return_pct)}</td><td>${fmtPct(r.median_return_pct)}</td>
      <td>${r.breadth_pct.toFixed(0)}%</td><td>${r.member_count}</td>
      <td>${r.etf || '—'}</td><td>${r.etf_return_pct == null ? '—' : fmtPct(r.etf_return_pct)}</td>
      <td>${r.top.map(m => `${m.symbol} ${fmtPct(m.return_pct)}`).join(', ')}</td>
    </tr>`;
  }).join('');
  const bench = slice.benchmarks
    .map(b => `${b.symbol} ${b.return_pct == null ? '—' : fmtPct(b.return_pct)}`).join(' · ');
  // Read the count off the payload so the header can't drift from the server.
  const topN = slice.rankings.length ? slice.rankings[0].top.length : 5;
  box.innerHTML = `<table>
    <thead><tr>
      <th>#</th><th>Group</th><th>Kind</th><th>Mean</th><th>Median</th><th>Breadth</th>
      <th>Members</th><th>ETF</th><th>ETF ret</th><th>Top ${topN}</th>
    </tr></thead><tbody>${rows}</tbody></table>
    <p class="sub" style="margin-top:10px">Benchmarks over the same window: ${bench}</p>`;

  // Rows drive the Top 5 strip, same as the bar chart above.
  box.querySelectorAll('.pick-row').forEach(tr => {
    const pick = () => selectGroup(tr.dataset.group);
    tr.onclick = pick;
    tr.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } };
  });
}

/** Switch the Top 5 strip (and the chart) to a group, from either picker. */
function selectGroup(name) {
  state.group = name;
  renderAll();
  $('leaders-title').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function renderDetail() {
  const s = state.stock;
  if (!s || !s.bars || !s.bars.length) return;
  const last = s.bars[s.bars.length - 1];
  const prev = s.bars.length > 1 ? s.bars[s.bars.length - 2] : null;
  const chg = prev ? (last.c / prev.c - 1) * 100 : null;

  $('d-sym').textContent = s.symbol;
  $('d-px').innerHTML =
    `${fmtPx(last.c)} <span class="${signClass(chg)}">${fmtPct(chg)}</span>
     <span style="color:var(--text-muted)"> · ${last.t}</span>`;

  renderRangeTabs();
  renderOverlayToggles();
  renderLegend();
  drawChart();
  renderTableView();
}

function renderAll() {
  renderLookbackTabs();
  renderHero();
  renderRankChart();
  renderLeaders();
  renderRankTable();

  // Auto-load the leader's #1 name so the desk opens on something useful.
  const g = activeGroup();
  if (g && g.top.length) {
    const wanted = g.top.some(m => m.symbol === state.symbol) ? state.symbol : g.top[0].symbol;
    if (wanted !== state.symbol || !state.stock) fetchStock(wanted);
    else renderDetail();
  }
}

// -------------------------------------------------------------- listeners
function init() {
  const canvas = $('chart');

  canvas.addEventListener('mousemove', e => {
    state.hover = indexFromEvent(e);
    drawChart();
    renderTooltip(e.clientX, e.clientY);
  });
  canvas.addEventListener('mouseleave', () => {
    state.hover = null;
    drawChart();
    $('tooltip').classList.remove('on');
  });
  // Keyboard focus shows the same as hover.
  canvas.addEventListener('keydown', e => {
    const view = visibleSlice();
    if (!view) return;
    const n = view.bars.length;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      e.preventDefault();
      const cur = state.hover == null ? n - 1 : state.hover;
      state.hover = Math.max(0, Math.min(n - 1, cur + (e.key === 'ArrowRight' ? 1 : -1)));
      drawChart();
      const rect = canvas.getBoundingClientRect();
      renderTooltip(barClientX(rect, n, state.hover), rect.top + 60);
    } else if (e.key === 'Escape') {
      state.hover = null; drawChart(); $('tooltip').classList.remove('on');
    }
  });

  $('table-toggle').onclick = () => {
    state.tableView = !state.tableView;
    $('table-view').classList.toggle('hidden', !state.tableView);
    $('table-toggle').setAttribute('aria-pressed', String(state.tableView));
  };

  $('refresh').onclick = () => {
    $('notices').innerHTML = '';
    fetchBoard(true);
    if (state.symbol) fetchStock(state.symbol, true);
  };

  const applyTheme = next => {
    document.documentElement.dataset.theme = next;
    $('theme').textContent = next === 'dark' ? 'Light' : 'Dark';
    try { localStorage.setItem('desk-theme', next); } catch { /* private mode */ }
  };
  try {
    const saved = localStorage.getItem('desk-theme');
    if (saved === 'light' || saved === 'dark') applyTheme(saved);
  } catch { /* private mode */ }

  $('theme').onclick = () => {
    applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
    renderLegend();
    renderOverlayToggles();
    drawChart();
  };

  let resizeTimer = null;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(drawChart, 120);
  });

  renderLookbackTabs();
  fetchBoard(false);
}

document.addEventListener('DOMContentLoaded', init);
