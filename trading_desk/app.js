/* Trading desk dashboard.
   Charts are drawn on one shared canvas so the price / volume / RSI / MACD panes
   keep a single x-scale and a single crosshair. Colors come from CSS custom
   properties (see style.css) so light/dark swap in one place. */

'use strict';

// Momentum ranks every group by raw return, so a 1-day window is meaningful.
// Reversal needs a prior period *before* the trigger day, so it has nothing
// to show on a 1-day window -- the server omits `reversal` there too.
const VIEWS = [
  { key: 'momentum', label: 'Momentum', lookbacks: [1, 2, 3, 4, 5] },
  { key: 'reversal', label: 'Reversal candidates', lookbacks: [2, 3, 4, 5] },
  // A calendar, not a group ranking: no lookback applies, and it replaces the
  // hero/ranking/movers sections rather than re-scoping them.
  { key: 'earnings', label: 'Earnings timing', lookbacks: [], calendar: true },
  // Also a solo view: it reports on positions held, not on a ranked group, so
  // the hero/ranking/movers furniture has nothing to scope here either.
  { key: 'review', label: 'Daily review', lookbacks: [], solo: true },
];
const HORIZONS = [14, 30, 45, 90];
// Must match the server's DEFAULT_HORIZON_DAYS so the two cannot disagree.
const DEFAULT_HORIZON = 30;
// The user's stated swing horizon. A print inside this window is the case the
// whole view exists to catch, so it is named rather than inlined as `<= 21`.
const SWING_WINDOW_DAYS = 21;
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
  // Levels, not a per-bar series -- drawn from `stock.levels`.
  { key: 'sr',     label: 'Support / Resistance', series: null, slot: 5, on: true },
];

const state = {
  view: 'momentum',   // see VIEWS -- ranked screens plus the two solo views
  lookback: 1,
  range: '6M',
  board: null,
  group: null,        // group name being shown in the leaders strip
  symbol: null,
  stock: null,
  // Bumped by every fetchStock() call. A response is only committed if this
  // still matches the token it was issued -- otherwise a slower request from
  // an earlier click (e.g. LITE, whose /api/stock happens to be the slow one)
  // can resolve after a faster later click (AXTI) and overwrite it, leaving
  // the older symbol showing even though it was clicked first, not last.
  selectionSeq: 0,
  overlays: Object.fromEntries(OVERLAYS.map(o => [o.key, o.on])),
  horizon: DEFAULT_HORIZON,
  earnings: null,
  review: null,
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

/** Point the header's Yahoo Finance link at the charted symbol, or at the site
 *  root when nothing is loaded. encodeURIComponent because the symbol reaches
 *  here from the search box, where a user can type anything. */
function updateYahooLink(symbol) {
  const a = $('yahoo-link');
  if (!a) return;
  if (symbol) {
    a.href = `https://finance.yahoo.com/quote/${encodeURIComponent(symbol)}`;
    a.textContent = `Yahoo: ${symbol} ↗`;
    a.title = `Open ${symbol} on Yahoo Finance in a new tab`;
  } else {
    a.href = 'https://finance.yahoo.com';
    a.textContent = 'Yahoo Finance ↗';
    a.title = 'Open Yahoo Finance in a new tab';
  }
}

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
  const mySeq = ++state.selectionSeq;
  state.loading = true;
  $('chart-wrap').classList.add('refetching');
  try {
    const res = await fetch(`/api/stock?symbol=${encodeURIComponent(symbol)}${force ? '&force=1' : ''}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    if (mySeq !== state.selectionSeq) return;  // a newer click already superseded this one
    state.stock = data;
    state.symbol = symbol;
    state.hover = null;
    renderDetail();
    fetchDetail(symbol, mySeq);  // fundamentals/news load independently of the chart
  } catch (e) {
    if (mySeq !== state.selectionSeq) return;
    $('d-sym').textContent = symbol;
    $('d-px').textContent = '';
    showError(`Could not load ${symbol}: ${e.message}`);
  } finally {
    if (mySeq === state.selectionSeq) {
      state.loading = false;
      $('chart-wrap').classList.remove('refetching');
    }
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

function currentView() {
  return VIEWS.find(v => v.key === state.view) || VIEWS[0];
}

function renderViewTabs() {
  const box = $('view-tabs');
  box.innerHTML = '';
  VIEWS.forEach(v => {
    const btn = document.createElement('button');
    btn.textContent = v.label;
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', String(state.view === v.key));
    btn.className = state.view === v.key ? 'active' : '';
    btn.onclick = () => {
      if (state.view === v.key) return;
      state.view = v.key;
      state.group = null;
      // A lookback valid in one view may not exist in the other (reversal has
      // no 1D screen) -- clamp rather than land on an undefined slice.
      if (v.lookbacks.length && !v.lookbacks.includes(state.lookback)) {
        state.lookback = v.lookbacks[0];
      }
      renderAll();
    };
    box.appendChild(btn);
  });
  const notes = {
    reversal: 'Groups down over the prior period that turned positive on the most recent session.',
    earnings: 'When each name reports next — so a swing position is never held through a print by accident.',
    momentum: 'Groups ranked by raw return over the window.',
    review: 'Every open position against its own levels, sorted by how close it sits to support.',
  };
  $('view-note').textContent = notes[state.view] || notes.momentum;
}

function renderHorizonTabs() {
  const box = $('horizon-tabs');
  box.innerHTML = '';
  HORIZONS.forEach(h => {
    const btn = document.createElement('button');
    btn.textContent = `${h}d`;
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', String(state.horizon === h));
    btn.className = state.horizon === h ? 'active' : '';
    btn.onclick = () => { state.horizon = h; fetchEarnings(); };
    box.appendChild(btn);
  });
}

async function fetchEarnings(force) {
  const card = $('earnings-card');
  card.classList.add('refetching');
  try {
    const res = await fetch(`/api/earnings?horizon=${state.horizon}${force ? '&force=1' : ''}`);
    const d = await res.json();
    if (d.error) throw new Error(d.error);
    state.earnings = d;
    renderEarnings();
  } catch (e) {
    $('earn-table').innerHTML = '';
    showError(`Could not load the earnings calendar: ${e.message}`);
  } finally {
    card.classList.remove('refetching');
  }
}

function renderEarnings() {
  const d = state.earnings;
  renderHorizonTabs();
  if (!d) { $('earn-table').innerHTML = '<div class="loading">Loading…</div>'; return; }

  $('earn-sub').textContent =
    `Projected from each company's own SEC filing history (${d.universe_with_history} names). `
    + `Dates are estimates — median error ${d.median_error_days} days, band ±${d.uncertainty_days} — `
    + `not confirmed announcements. Confirm on the company's IR page before acting.`;

  // Alerts first: a print landing on something currently held is the one thing
  // that must not be scrolled past.
  const alerts = $('earn-alerts');
  alerts.innerHTML = '';
  (d.rows || []).filter(r => r.held).forEach(r => {
    const soon = r.days_until_earliest <= SWING_WINDOW_DAYS;
    const el = document.createElement('div');
    el.className = `notice ${soon ? 'err' : 'warn'}`;
    const pos = r.position || {};
    const mv = r.typical_move_pct != null
      ? `typically moves ±${r.typical_move_pct.toFixed(1)}% on the print`
        + (r.typical_move_1w_pct != null ? ` and ±${r.typical_move_1w_pct.toFixed(1)}% over the following week` : '')
      : 'typical move unknown';
    // Position is aggregated across lots server-side; say so when there is more
    // than one, otherwise "22 @ 511.25" looks like a single fill that never happened.
    const qty = pos.qty != null ? Number(pos.qty).toLocaleString() : '?';
    const avg = pos.avg_entry != null ? Number(pos.avg_entry).toFixed(2) : '?';
    const lots = pos.lots > 1 ? ` across ${pos.lots} lots` : '';
    el.innerHTML = `<span class="ico">${soon ? '⚠' : 'ℹ'}</span><span>`
      + `<strong>You hold ${r.symbol}</strong> (${qty} @ ${avg} avg${lots}, from ${pos.entry_date || '?'}) — `
      + (r.reports_today
          ? `reports <strong>TODAY (${r.projected_date})</strong> ${labelTiming(r.expected_timing)}. `
          : `reports about <strong>${r.projected_date}</strong>, in ${r.days_until} days `
            + `(as early as ${r.earliest_plausible}), ${labelTiming(r.expected_timing)}. `)
      + `${mv}.`
      + (soon ? ` <strong>That is inside your ${SWING_WINDOW_DAYS}-day swing window.</strong>` : '')
      + `</span>`;
    alerts.appendChild(el);
  });
  (d.held_without_dates || []).forEach(sym => {
    const el = document.createElement('div');
    el.className = 'notice warn';
    el.innerHTML = `<span class="ico">⚠</span><span><strong>You hold ${sym}</strong>, but its filing history `
      + `does not support a projection — treat its earnings date as unknown rather than distant.</span>`;
    alerts.appendChild(el);
  });

  const rows = (d.rows || []).map(r => {
    const pct = v => (v == null ? '—' : `${v.toFixed(1)}%`);
    const signed = v => (v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`);
    const split = (u, dn) => (u == null || dn == null ? '—' : `${u}/${dn}`);
    return `<tr class="earn-row${r.held ? ' held' : ''}${r.reports_today ? ' today' : ''}"
                data-symbol="${r.symbol}" tabindex="0">
      <td>${r.symbol}${r.held ? ' <span class="tag-held">HELD</span>' : ''}</td>
      <td>${r.projected_date}${r.reports_today ? ' <span class="tag-today">TODAY</span>' : ''}</td>
      <td>${r.days_until}</td>
      <td>${r.earliest_plausible}</td>
      <td>${labelTiming(r.expected_timing)}</td>
      <td>${pct(r.typical_move_pct)}</td>
      <td>${pct(r.max_move_pct)}</td>
      <td class="${r.signed_move_pct == null ? '' : signClass(r.signed_move_pct)}">${signed(r.signed_move_pct)}</td>
      <td>${pct(r.typical_move_1w_pct)}</td>
      <td class="${r.signed_move_1w_pct == null ? '' : signClass(r.signed_move_1w_pct)}">${signed(r.signed_move_1w_pct)}</td>
      <td>${split(r.up_count, r.down_count)}</td>
      <td>${r.move_sample ?? '—'}</td>
      <td>${r.group}</td>
      <td>${r.group_rank_5d ?? '—'}</td>
    </tr>`;
  }).join('');

  $('earn-table').innerHTML = `<table>
    <thead><tr>
      <th>Symbol</th><th>Projected</th><th>Days</th><th>Earliest</th><th>Timing</th>
      <th title="Median absolute 1-session reaction — size regardless of direction">Typ |1d|</th>
      <th title="Largest absolute 1-session reaction on record — the tail, not the middle">Worst |1d|</th>
      <th title="Median signed 1-session reaction — which way it has leaned">Lean 1d</th>
      <th title="Median absolute move over 5 sessions from the pre-earnings close, gap included">Typ |1w|</th>
      <th title="Median signed move over 5 sessions from the pre-earnings close">Lean 1w</th>
      <th title="Historical up/down split of the 1-session reaction">Up/Dn</th>
      <th title="Number of past prints behind these figures">n</th>
      <th>Group</th><th>5D rank</th>
    </tr></thead><tbody>${rows || '<tr><td colspan="14">No prints projected inside this horizon.</td></tr>'}</tbody></table>`;

  $('earn-table').querySelectorAll('.earn-row').forEach(tr => {
    const pick = () => selectStock(tr.dataset.symbol);
    tr.onclick = pick;
    tr.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } };
  });
}

function labelTiming(t) {
  if (t === 'after_close') return 'after close';
  if (t === 'before_open') return 'before open';
  return 'timing unknown';
}

// ------------------------------------------------------------- daily review
async function fetchReview(force) {
  const card = $('review-card');
  card.classList.add('refetching');
  try {
    const res = await fetch(`/api/review${force ? '?force=1' : ''}`);
    const d = await res.json();
    if (d.error) throw new Error(d.error);
    state.review = d;
    renderReview();
  } catch (e) {
    $('rev-table').innerHTML = '';
    $('rev-summary').innerHTML = '';
    showError(`Could not load the daily review: ${e.message}`);
  } finally {
    card.classList.remove('refetching');
  }
}

// Money, signed, no decimals -- position-level P&L in dollars is never
// interesting to the cent and the column stays readable without them.
const fmtMoney0 = v => (v == null ? '—'
  : `${v < 0 ? '−' : ''}$${Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`);

function revStopCell(e) {
  // An absent stop is an absence, not a price -- em dash, never 0.00. Through the
  // stop reads as a warning rather than as remaining room, matching the API,
  // which reports a negative risk figure and drops it from the book total.
  if (e.stop_current == null) return `<td class="lvl-none">—</td>`;
  const atr = e.stop_distance_atr;
  const cls = e.through_stop ? 'neg' : (atr != null && atr <= 1 ? 'warn-txt' : '');
  const sub = e.through_stop
    ? 'through'
    : (atr == null ? '' : `${atr.toFixed(1)} ATR`);
  const dis = e.stop_current_disagrees ? ' \u2260' : '';
  return `<td class="${cls}">${fmtPx(e.stop_current)}${dis}`
       + `<span class="lvl-meta">${fmtPct(e.stop_distance_pct)}${sub ? ' \u00b7 ' + sub : ''}</span></td>`;
}


function revLevelCell(l) {
  if (!l) return '<td class="muted">none</td>';
  const atr = l.distance_atr == null ? '' : ` · ${l.distance_atr.toFixed(1)} ATR`;
  const near = l.distance_atr != null && l.distance_atr <= 0.5 ? ' at-level' : '';
  return `<td class="level-cell${near}" title="${l.touches || 0} pivots, ${l.tests || 0} bars tested`
       + ` in range; last tested ${l.last_touch || 'unknown'}">`
       + `${fmtPx(l.level)}<span class="lvl-meta">${fmtPct(l.distance_pct)}${atr}</span></td>`;
}

function renderReview() {
  const d = state.review;
  if (!d) { $('rev-table').innerHTML = '<div class="loading">Loading…</div>'; return; }

  const stamp = d.generated_at ? new Date(d.generated_at).toLocaleTimeString('en-US') : '';
  $('rev-stamp').textContent = stamp ? `built ${stamp} · ${d.feed_note || ''}` : '';
  $('rev-sub').textContent =
    `Every open lot in ${d.journal}, priced against the same levels the chart draws. `
    + `Sorted by how close each position sits to its nearest support — the level a stop `
    + `would key off. Levels are prices the market actually turned at, not projections.`;

  // ---- portfolio summary
  const tot = d.totals || {};
  const cells = [
    ['Reviewed book', fmtMoney0(tot.market_value), null],
    ['Unrealised', fmtMoney0(tot.pnl), tot.pnl],
    ['vs cost', fmtPct(tot.pnl_pct), tot.pnl_pct],
    ['Downside to support', fmtMoney0(d.risk_to_support),
      d.risk_to_support_pct_of_book == null ? null : -1],
    ['Open lots', String(d.reviewed_open_lots ?? '—'), null,
      d.open_lots == null ? null : `${d.open_lots} in journal`],
    // Scoped to the reviewed rows so the tile agrees with the table beneath it;
    // the journal-wide figure — the one the README's "trend to zero" rule is
    // about — rides underneath rather than replacing it.
    ['Risk to stops',
      d.risk_to_stop == null ? '—' : fmtMoney0(d.risk_to_stop),
      d.risk_to_stop ? -1 : null,
      d.risk_to_stop_pct_of_book == null ? null
        : `${d.risk_to_stop_pct_of_book.toFixed(2)}% of book \u00b7 ${d.lots_with_stop_current ?? 0} lot(s)`],
    ['Lots without a stop',
      `${d.reviewed_lots_without_stop ?? '—'} of ${d.reviewed_open_lots ?? '—'}`,
      d.reviewed_lots_without_stop ? -1 : 1,
      d.lots_without_stop == null ? null : `${d.lots_without_stop} of ${d.open_lots} in journal`],
  ];
  $('rev-summary').innerHTML = `<div class="rev-stats">` + cells.map(([k, v, sign, sub]) =>
    `<div class="rev-stat"><div class="k">${k}</div>`
    + `<div class="v ${sign == null ? '' : signClass(sign)}">${v}`
    + `${sub ? `<span class="lvl-meta">${sub}</span>` : ''}</div></div>`).join('') + `</div>`;

  // ---- per-position table
  if (!d.positions.length) {
    $('rev-table').innerHTML = '<div class="loading">No reviewable open positions.</div>';
  } else {
    const rows = d.positions.map(e => {
      if (e.error) {
        return `<tr class="rev-row" data-sym="${e.symbol}"><td><b>${e.symbol}</b></td>`
             + `<td colspan="12" class="neg">${e.error}</td></tr>`;
      }
      const w = e.book_weight_pct;
      const earn = e.earnings && e.earnings.days_until != null
        ? `${e.earnings.days_until}d` : '—';
      const earnCls = e.earnings && e.earnings.days_until != null
        && e.earnings.days_until <= SWING_WINDOW_DAYS ? 'neg' : '';
      return `<tr class="rev-row" data-sym="${e.symbol}" tabindex="0">
        <td><b>${e.symbol}</b><span class="lvl-meta">${e.lots} lot${e.lots === 1 ? '' : 's'}</span></td>
        <td>${fmtPx(e.last)}<span class="lvl-meta ${signClass(e.day_pct)}">${fmtPct(e.day_pct)}</span></td>
        <td>${fmtPx(e.avg_entry)}</td>
        <td class="${signClass(e.pnl)}">${fmtMoney0(e.pnl)}<span class="lvl-meta ${signClass(e.pnl_pct)}">${fmtPct(e.pnl_pct)}</span></td>
        <td>${w == null ? '—' : w.toFixed(1) + '%'}</td>
        ${revLevelCell(e.nearest_resistance)}
        ${revLevelCell(e.nearest_support)}
        <td>${fmtMoney0(e.risk_to_support)}</td>
        ${revStopCell(e)}
        <td>${e.risk_to_stop == null ? '—' : fmtMoney0(e.risk_to_stop)}</td>
        <td>${e.rsi14 == null ? '—' : e.rsi14.toFixed(0)}</td>
        <td>${e.atr_pct == null ? '—' : e.atr_pct.toFixed(1) + '%'}</td>
        <td class="${earnCls}">${earn}</td>
      </tr>`;
    }).join('');
    $('rev-table').innerHTML = `<table class="rev-tbl">
      <thead><tr>
        <th>Symbol</th><th>Last</th><th>Avg entry</th><th>Unrealised</th><th>% book</th>
        <th>Resistance above</th><th>Support below</th><th>To support</th>
        <th>Stop</th><th>To stop</th>
        <th>RSI</th><th>ATR%</th><th>Earnings</th>
      </tr></thead><tbody>${rows}</tbody></table>`;
    // Clicking a row charts that symbol, same affordance as the calendar rows.
    $('rev-table').querySelectorAll('.rev-row').forEach(tr => {
      const go = () => { const s = tr.dataset.sym; if (s) fetchStock(s); };
      tr.onclick = go;
      tr.onkeydown = ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); go(); } };
    });
  }

  // ---- flags, grouped per position
  const flagged = d.positions.filter(e => (e.flags || []).length);
  $('rev-cards').innerHTML = !flagged.length ? '' :
    `<h3 class="rev-h3">Worth a look</h3><div class="rev-flags">` + flagged.map(e =>
      `<div class="rev-flag-card"><div class="rev-flag-sym">${e.symbol}</div><ul>`
      + e.flags.map(f => `<li class="flag-${f.level}">${f.text}</li>`).join('')
      + `</ul></div>`).join('') + `</div>`;

  // ---- theme concentration
  const g = d.group_exposure || [];
  $('rev-groups').innerHTML = !g.length ? '' :
    `<h3 class="rev-h3">Theme exposure</h3><div class="rev-bars">` + g.map(x => {
      const pct = x.pct_of_book || 0;
      return `<div class="rev-bar-row"><div class="rev-bar-lbl">${x.group}</div>`
        + `<div class="rev-bar-track"><div class="rev-bar-fill" style="width:${Math.min(pct, 100)}%"></div></div>`
        + `<div class="rev-bar-val">${pct.toFixed(1)}% <span class="lvl-meta">${fmtMoney0(x.market_value)}</span></div></div>`;
    }).join('') + `</div><p class="sub">A name in two groups counts in both, so these do not sum to 100%.</p>`;

  // ---- excluded holdings, reported but not reviewed
  const ex = d.excluded || [];
  $('rev-excluded').innerHTML = !ex.length ? '' :
    `<h3 class="rev-h3">Held, not reviewed</h3><p class="sub">${d.excluded_note || ''}</p>`
    + `<div class="rev-bars">` + ex.map(e =>
      `<div class="rev-bar-row"><div class="rev-bar-lbl">${e.symbol}`
      + `${e.exclusion_reason ? `<span class="lvl-meta">${e.exclusion_reason}</span>` : ''}</div>`
      + `<div class="rev-bar-track"><div class="rev-bar-fill muted-fill" style="width:${Math.min(e.book_weight_pct || 0, 100)}%"></div></div>`
      + `<div class="rev-bar-val">${(e.book_weight_pct || 0).toFixed(1)}% <span class="lvl-meta">${fmtMoney0(e.market_value)}</span></div></div>`
    ).join('') + `</div>`;

  // Open the chart on the position the review put first (closest to its
  // support), the same courtesy the momentum view extends by charting the
  // leading group's #1. A symbol already among the holdings is left alone, so
  // clicking a row is not undone by the next render.
  const held = d.positions.map(e => e.symbol);
  const wanted = held.includes(state.symbol) ? state.symbol : held[0];
  if (wanted && (wanted !== state.symbol || !state.stock)) fetchStock(wanted);

  $('rev-disclaimer').textContent =
    'Observations, not recommendations. Every figure here is a measurement — none of it '
    + 'says what to do, and nothing on this page is investment advice. "Downside to support" '
    + 'is measured from today’s price, not from entry, so for an underwater position it is '
    + 'remaining risk to that level rather than the risk originally taken.';
}

function renderLookbackTabs() {
  const box = $('lookback-tabs');
  box.innerHTML = '';
  currentView().lookbacks.forEach(lb => {
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

/** The momentum or reversal ranking list for the active view, or [] if the
 *  slice has no reversal block (1D) or nothing qualified. */
function activeRankings() {
  const slice = currentSlice();
  if (!slice) return [];
  if (state.view === 'reversal') return (slice.reversal && slice.reversal.rankings) || [];
  return slice.rankings;
}

function activeGroup() {
  const slice = currentSlice();
  if (!slice) return null;
  const rankings = activeRankings();
  if (state.group) {
    const found = rankings.find(g => g.group === state.group);
    if (found) return found;
  }
  if (state.view === 'reversal') return (slice.reversal && slice.reversal.leader) || null;
  return slice.hottest;
}

function renderHero() {
  const slice = currentSlice();
  const el = $('hero');

  if (slice && state.view === 'reversal') {
    renderReversalHero(slice, el);
  } else {
    renderMomentumHero(slice, el);
  }

  // Splitting this function into two branches dropped the original's early
  // return, which was what kept the header writes below from running before a
  // board existed. Guard explicitly rather than rely on the call graph.
  if (!state.board) return;

  $('asof').textContent = state.board.as_of_session
    ? `session ${state.board.as_of_session} · ${state.board.feed.toUpperCase()} feed`
      + `${state.board.feed_note ? ` (${state.board.feed_note})` : ''}`
      + ` · ${state.board.universe_size} symbols`
    : '';
  $('lookback-note').textContent =
    `${state.lookback} trading session${state.lookback > 1 ? 's' : ''} through ${state.board.as_of_session || '—'}`;
}

function renderMomentumHero(slice, el) {
  const g = slice && slice.hottest;
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
}

function renderReversalHero(slice, el) {
  const rev = slice.reversal;
  const g = rev && rev.leader;
  if (!rev || !g) {
    el.innerHTML = `<div class="loading">No reversal candidates over this window — nothing in the
      universe was down over the prior period and turned positive on the most recent session.</div>`;
    return;
  }

  const bench = rev.benchmarks_1d.find(b => b.symbol === 'SPY');
  const vsSpyToday = bench && bench.return_pct != null ? g.avg_trigger_return_pct - bench.return_pct : null;
  const priorDays = state.lookback - 1;

  el.innerHTML = `
    <div>
      <div class="lede">Top reversal candidate · down ${priorDays} day${priorDays > 1 ? 's' : ''}, up today</div>
      <div class="group-name">${g.group}<span class="kind">${g.kind}</span></div>
    </div>
    <div class="stat">
      <div class="k">Prior decline (avg)</div>
      <div class="v ${signClass(g.avg_prior_return_pct)}">${fmtPct(g.avg_prior_return_pct)}</div>
    </div>
    <div class="stat">
      <div class="k">Bounce today (avg)</div>
      <div class="v ${signClass(g.avg_trigger_return_pct)}">${fmtPct(g.avg_trigger_return_pct)}</div>
    </div>
    <div class="stat">
      <div class="k">Reversal breadth</div>
      <div class="v">${g.breadth_pct.toFixed(0)}% <span style="font-size:12px;color:var(--text-muted)">(${g.qualifying_count}/${g.evaluated_count})</span></div>
    </div>
    <div class="stat">
      <div class="k">vs SPY today</div>
      <div class="v ${signClass(vsSpyToday)}">${vsSpyToday == null ? '—' : fmtPct(vsSpyToday)}</div>
    </div>
    <div class="stat">
      <div class="k">Vol vs prior avg</div>
      <div class="v">${g.avg_volume_ratio == null ? '—' : g.avg_volume_ratio.toFixed(2) + '×'}</div>
    </div>`;
}

/** One diverging-bar row, shared by both views.
 *
 *  `getVal` must return the quantity the list is *sorted by*, so bar length and
 *  row order always agree -- encoding one measure while sorting by another makes
 *  the sort key invisible and the chart reads as mis-ordered. `getText` is what
 *  the value column prints, which may carry more than the bar encodes. */
function buildRankRow(r, lo, span, zeroPct, active, getVal, getText, getLabel) {
  const row = document.createElement('div');
  row.className = 'rank-row' + (active && r.group === active.group ? ' leader' : '');
  row.tabIndex = 0;
  row.setAttribute('role', 'button');
  row.setAttribute('aria-label', `${r.group}, ${getLabel(r)}`);

  const v = getVal(r);
  const from = Math.min(v, 0), to = Math.max(v, 0);
  const left = ((from - lo) / span) * 100;
  const width = ((to - from) / span) * 100;

  row.innerHTML = `
    <div class="name" title="${r.group}">${r.group}</div>
    <div class="bar-track">
      <div class="zero-rule" style="left:${zeroPct}%"></div>
      <div class="bar" style="left:${left}%;width:${Math.max(width, 0.4)}%"></div>
    </div>
    <div class="val">${getText(r)}</div>`;

  const pick = () => selectGroup(r.group);
  row.onclick = pick;
  row.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } };
  return row;
}

function renderRankChart() {
  const slice = currentSlice();
  const box = $('rank-chart');
  box.innerHTML = '';
  if (!slice) return;

  if (state.view === 'reversal') {
    renderReversalRankChart(box);
  } else {
    renderMomentumRankChart(slice, box);
  }
}

function renderMomentumRankChart(slice, box) {
  const rows = slice.rankings;
  const vals = rows.map(r => r.mean_return_pct);
  const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
  const span = (hi - lo) || 1;
  const zeroPct = ((0 - lo) / span) * 100;
  const active = activeGroup();

  rows.forEach(r => {
    box.appendChild(buildRankRow(
      r, lo, span, zeroPct, active,
      x => x.mean_return_pct,
      x => fmtPct(x.mean_return_pct),
      x => `mean return ${fmtPct(x.mean_return_pct)}`,
    ));
  });

  $('rank-title').textContent = 'Group ranking';
  $('rank-sub').textContent =
    `Equal-weight mean return of each group's constituents over ${state.lookback} trading ` +
    `session${state.lookback > 1 ? 's' : ''}. Click a row to load its top movers.`;
}

function renderReversalRankChart(box) {
  const rows = activeRankings();
  $('rank-title').textContent = 'Reversal candidates';
  const priorDays = state.lookback - 1;
  $('rank-sub').textContent = rows.length
    ? `Groups down over the prior ${priorDays} day${priorDays > 1 ? 's' : ''} that turned positive ` +
      `on the most recent session. Bar and first figure are the share of members that reversed; ` +
      `second figure is their average bounce. Click a row to load its movers.`
    : `No groups were down over the prior ${priorDays} day${priorDays > 1 ? 's' : ''} and up on the ` +
      `most recent session.`;
  if (!rows.length) return;

  // The bar encodes reversal breadth, which is the primary sort key, on a fixed
  // 0-100% scale -- breadth is a share of members, so a full-width bar should
  // mean "every member reversed", not merely "the most of any group here".
  const lo = 0, span = 100, zeroPct = 0;
  const active = activeGroup();

  rows.forEach(r => {
    box.appendChild(buildRankRow(
      r, lo, span, zeroPct, active,
      x => x.breadth_pct,
      x => `${x.breadth_pct.toFixed(0)}% · ${fmtPct(x.avg_trigger_return_pct)}`,
      x => `${x.breadth_pct.toFixed(0)}% of members reversed (${x.qualifying_count} of `
         + `${x.evaluated_count}), average bounce ${fmtPct(x.avg_trigger_return_pct)}`,
    ));
  });
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
  if (!g) {
    $('leaders-title').textContent = 'Top movers';
    $('leaders-sub').textContent = 'Nothing to show for this view and window.';
    return;
  }

  const isReversal = state.view === 'reversal';
  $('leaders-title').textContent = isReversal
    ? `Reversing now — ${g.group}`
    : `Top ${g.top.length} — ${g.group}`;
  $('leaders-sub').textContent = isReversal
    ? `${g.qualifying_count} of ${g.evaluated_count} members in ${g.group} were down over the prior ` +
      `${state.lookback - 1} session${state.lookback - 1 > 1 ? 's' : ''} and closed up on the most ` +
      `recent one, biggest bounce first. Click a card to chart it.`
    : `Best ${state.lookback}-day performers inside ${g.group} (${g.member_count} members priced). ` +
      `Click a card to chart it.`;

  g.top.forEach((m, i) => {
    const card = document.createElement('button');
    card.className = 'stock-card' + (state.symbol === m.symbol ? ' selected' : '');
    if (isReversal) {
      // Volume confirmation is the honest tell on a bounce: a green day on
      // below-average volume is weaker evidence that the selling is done, so
      // it is shown per name rather than buried in the group average.
      const vr = m.volume_ratio;
      const volClass = vr == null ? '' : (vr >= 1 ? 'pos' : 'neg');
      const volText = vr == null ? '—' : `${vr.toFixed(2)}×`;
      card.innerHTML = `
        <div class="rankno">#${i + 1}</div>
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">
          <span class="sym">${m.symbol}</span>
          <span class="ret ${signClass(m.trigger_return_pct)}">${fmtPct(m.trigger_return_pct)}</span>
        </div>
        <div class="px">${fmtPx(m.last_close)} · vol ${fmtVol(m.volume)}</div>
        <div class="rev-meta">
          <span>prior <b class="${signClass(m.prior_return_pct)}">${fmtPct(m.prior_return_pct)}</b></span>
          <span>vol <b class="${volClass}">${volText}</b></span>
        </div>
        <div class="spark-cap">30-day trend</div>
        <div class="spark-slot"></div>`;
    } else {
      card.innerHTML = `
        <div class="rankno">#${i + 1}</div>
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">
          <span class="sym">${m.symbol}</span>
          <span class="ret ${signClass(m.return_pct)}">${fmtPct(m.return_pct)}</span>
        </div>
        <div class="px">${fmtPx(m.last_close)} · vol ${fmtVol(m.volume)}</div>
        <div class="spark-cap">30-day trend</div>
        <div class="spark-slot"></div>`;
    }
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
  if (state.overlays.sr) {
    const n = (state.stock && state.stock.levels) ? state.stock.levels.length : 0;
    items.push(
      `<span class="item"><span class="line dash-r" style="background:${slotColor(5)}"></span>Resistance</span>`,
      `<span class="item"><span class="line dash-s" style="background:${slotColor(5)}"></span>Support</span>`,
      `<span class="item" style="color:var(--text-muted)">${n} level${n === 1 ? '' : 's'} · n× = times price turned there</span>`);
  }
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

  // ---- support / resistance levels
  // Dashed on purpose: these are thresholds, not a series, and the dash keeps
  // them from reading as another moving average. Drawn inside the clip so a
  // level outside the visible price scale simply doesn't appear.
  const srLevels = (state.overlays.sr && state.stock && state.stock.levels) ? state.stock.levels : [];
  const srColor = slotColor(5);
  srLevels.forEach(l => {
    const yy = yPrice(l.level);
    if (yy < y0.price || yy > y0.price + h.price) return;
    ctx.save();
    ctx.strokeStyle = srColor;
    ctx.lineWidth = 1;
    ctx.setLineDash(l.kind === 'resistance' ? [6, 4] : [2, 3]);
    ctx.beginPath();
    ctx.moveTo(padL, Math.round(yy) + 0.5);
    ctx.lineTo(padL + plotW, Math.round(yy) + 0.5);
    ctx.stroke();
    ctx.restore();
  });
  ctx.restore();

  // Level labels sit outside the clip so they are never half-drawn.
  srLevels.forEach(l => {
    const yy = yPrice(l.level);
    if (yy < y0.price + 8 || yy > y0.price + h.price - 8) return;
    const txt = `${l.kind === 'resistance' ? 'R' : 'S'} ${l.level.toFixed(2)} · ${l.touches}×`;
    const w = ctx.measureText(txt).width + 8;
    ctx.fillStyle = C.surface;
    ctx.fillRect(padL + 2, yy - 8, w, 16);
    label(txt, padL + 6, yy, srColor);
  });

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

  const isReversal = state.view === 'reversal';
  $('rank-table-title').textContent = isReversal ? 'Reversal table' : 'Ranking table';
  $('rank-table-sub').textContent =
    'The same board as above in text form — every value readable without color. '
    + 'Click any row to load that group\'s movers.';

  const active = activeGroup();
  const list = activeRankings();

  if (!list.length) {
    box.innerHTML = '<p class="sub">Nothing qualified for this view and window.</p>';
    return;
  }

  // No role="button" on the rows: overriding a <tr>'s implicit row role breaks
  // the table's structure for screen readers. aria-current is valid on any
  // element and is what conveys "this is the group being shown".
  const rowAttrs = (r, isActive) =>
    `class="pick-row${isActive ? ' selected' : ''}" data-group="${r.group.replace(/"/g, '&quot;')}"`
    + ` tabindex="0"${isActive ? ' aria-current="true"' : ''}`;

  let head, rows, footNote;
  if (isReversal) {
    const priorDays = state.lookback - 1;
    head = `<th>#</th><th>Group</th><th>Kind</th><th>Prior ${priorDays}D</th><th>Bounce</th>`
      + `<th>Vol ×</th><th>Reversed</th><th>Of priced</th><th>Breadth</th><th>Movers</th>`;
    rows = list.map((r, i) => {
      const isActive = active && r.group === active.group;
      return `<tr ${rowAttrs(r, isActive)}>
        <td>${i + 1}</td><td>${r.group}</td><td>${r.kind}</td>
        <td>${fmtPct(r.avg_prior_return_pct)}</td><td>${fmtPct(r.avg_trigger_return_pct)}</td>
        <td>${r.avg_volume_ratio == null ? '—' : r.avg_volume_ratio.toFixed(2) + '×'}</td>
        <td>${r.qualifying_count}</td><td>${r.evaluated_count}</td>
        <td>${r.breadth_pct.toFixed(0)}%</td>
        <td>${r.top.map(m => `${m.symbol} ${fmtPct(m.trigger_return_pct)}`).join(', ')}</td>
      </tr>`;
    }).join('');
    const b1 = (slice.reversal && slice.reversal.benchmarks_1d) || [];
    footNote = b1.length
      ? `Benchmarks on the trigger session: ${b1.map(b =>
          `${b.symbol} ${b.return_pct == null ? '—' : fmtPct(b.return_pct)}`).join(' · ')}`
      : '';
  } else {
    const topN = list[0].top.length;
    head = `<th>#</th><th>Group</th><th>Kind</th><th>Mean</th><th>Median</th><th>Breadth</th>`
      + `<th>Members</th><th>ETF</th><th>ETF ret</th><th>Top ${topN}</th>`;
    rows = list.map((r, i) => {
      const isActive = active && r.group === active.group;
      return `<tr ${rowAttrs(r, isActive)}>
        <td>${i + 1}</td><td>${r.group}</td><td>${r.kind}</td>
        <td>${fmtPct(r.mean_return_pct)}</td><td>${fmtPct(r.median_return_pct)}</td>
        <td>${r.breadth_pct.toFixed(0)}%</td><td>${r.member_count}</td>
        <td>${r.etf || '—'}</td><td>${r.etf_return_pct == null ? '—' : fmtPct(r.etf_return_pct)}</td>
        <td>${r.top.map(m => `${m.symbol} ${fmtPct(m.return_pct)}`).join(', ')}</td>
      </tr>`;
    }).join('');
    footNote = `Benchmarks over the same window: ${slice.benchmarks
      .map(b => `${b.symbol} ${b.return_pct == null ? '—' : fmtPct(b.return_pct)}`).join(' · ')}`;
  }

  box.innerHTML = `<table>
    <thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>
    ${footNote ? `<p class="sub" style="margin-top:10px">${footNote}</p>` : ''}`;

  // Rows drive the movers strip, same as the bar chart above.
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

// ------------------------------------------------------- company detail
function fmtBig(v) {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (a >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toFixed(2)}`;
}

function statBox(label, value, note, opts = {}) {
  const el = document.createElement('div');
  el.className = 'stat-box';
  const k = document.createElement('div');
  k.className = 'k';
  k.textContent = label;
  const v = document.createElement('div');
  v.className = 'v' + (opts.na ? ' v na' : '');
  v.textContent = value;
  el.append(k, v);
  if (note) {
    const n = document.createElement('div');
    n.className = 'n';
    n.textContent = note;
    el.append(n);
  }
  return el;
}

async function fetchDetail(symbol, seq) {
  const card = $('company-card');
  card.classList.add('refetching');
  $('c-title').textContent = `Company detail — ${symbol}`;
  try {
    const res = await fetch(`/api/detail?symbol=${encodeURIComponent(symbol)}`);
    const d = await res.json();
    if (d.error) throw new Error(d.error);
    // The detail fetch runs independently of the chart fetch and has its own
    // (often larger) latency, so it needs the same out-of-order guard as
    // fetchStock -- comparing against d.symbol/state.symbol alone isn't enough
    // once two different symbols can both be "the current one" at different
    // instants during the race.
    if (seq !== state.selectionSeq) return;
    renderCompany(d);
  } catch (e) {
    if (seq !== state.selectionSeq) return;
    $('c-stats').replaceChildren(statBox('Company detail', 'unavailable', e.message, { na: true }));
  } finally {
    if (seq === state.selectionSeq) card.classList.remove('refetching');
  }
}

function renderCompany(d) {
  const f = d.fundamentals || {};
  const s = d.stats || {};

  $('c-title').textContent = `Company detail — ${d.symbol}`;
  $('c-entity').textContent = f.entity_name ? `${f.entity_name}${f.cik ? ` · CIK ${f.cik}` : ''}` : '';
  $('c-source').textContent = f.available
    ? 'Fundamentals from SEC XBRL filings · news from Alpaca'
    : 'Price stats from Alpaca · fundamentals unavailable';

  // ---- key stats
  const boxes = [];
  boxes.push(statBox(
    'Market cap',
    fmtBig(f.market_cap),
    f.shares_outstanding
      ? `${f.shares_outstanding.toLocaleString('en-US')} shares as of ${f.shares_as_of}`
      : (f.available ? 'shares outstanding not reported' : (f.reason || '')),
    { na: f.market_cap == null }));

  boxes.push(statBox(
    'P/E (trailing)',
    f.pe_ratio != null ? f.pe_ratio.toFixed(1) : 'n/a',
    f.pe_note || '',
    { na: f.pe_ratio == null }));

  boxes.push(statBox(
    'EPS (trailing 12m)',
    f.ttm_eps != null ? `$${f.ttm_eps.toFixed(2)}` : 'n/a',
    f.ttm_eps != null ? 'diluted, reconstructed from filings' : (f.ttm_eps_note || ''),
    { na: f.ttm_eps == null }));

  if (s.week52_high != null) {
    const box = document.createElement('div');
    box.className = 'stat-box';
    const pos = s.range_position_pct == null ? 50 : Math.max(0, Math.min(100, s.range_position_pct));
    box.innerHTML = `<div class="k">52-week range</div>
      <div class="range-track"><div class="mark" style="left:${pos}%"></div></div>
      <div class="range-ends"><span>${fmtPx(s.week52_low)}</span><span>${fmtPx(s.week52_high)}</span></div>`;
    const n = document.createElement('div');
    n.className = 'n';
    n.textContent = `at ${pos.toFixed(0)}% of range · ${s.bars_used_for_52w} sessions`;
    box.append(n);
    boxes.push(box);
  }

  // Nearest levels on each side -- the two prices a short-horizon trade is
  // actually working between. Sourced from the chart payload so the panel and
  // the chart can never disagree.
  const lv = (state.stock && state.stock.levels) || [];
  const px = s.last_price;
  const nearestR = lv.filter(l => l.kind === 'resistance')
    .sort((a, b) => a.level - b.level)[0];
  const nearestS = lv.filter(l => l.kind === 'support')
    .sort((a, b) => b.level - a.level)[0];
  boxes.push(statBox(
    'Nearest resistance',
    nearestR ? fmtPx(nearestR.level) : 'none in range',
    nearestR
      ? `${fmtPct(nearestR.distance_pct)} away · turned ${nearestR.touches}× · last ${nearestR.last_touch}`
      : (px != null ? 'no prior level overhead — at or near highs' : ''),
    { na: !nearestR }));
  boxes.push(statBox(
    'Nearest support',
    nearestS ? fmtPx(nearestS.level) : 'none in range',
    nearestS
      ? `${fmtPct(nearestS.distance_pct)} away · turned ${nearestS.touches}× · last ${nearestS.last_touch}`
      : '',
    { na: !nearestS }));

  boxes.push(statBox(
    'Daily volatility',
    s.atr_pct != null ? `${s.atr_pct.toFixed(1)}%` : '—',
    s.atr14 != null ? `ATR(14) = ${fmtPx(s.atr14)} per day` : '',
    { na: s.atr_pct == null }));

  // TDR sits beside ATR on purpose: ATR absorbs overnight gaps, TDR does not,
  // so the shortfall between them is the share of range that arrives as a gap --
  // the part an intraday stop cannot protect against.
  boxes.push(statBox(
    'TDR (14)',
    s.tdr14 != null ? fmtPx(s.tdr14) : '—',
    s.tdr14 != null
      ? `${s.tdr_pct != null ? `${s.tdr_pct.toFixed(1)}% of price` : ''}`
        + `${s.gap_share_pct != null
              ? ` · ${s.gap_share_pct.toFixed(0)}% of ATR is gap, not intraday`
              : ''}`
      : '',
    { na: s.tdr14 == null }));

  boxes.push(statBox(
    'Avg volume (20d)',
    s.avg_volume_20d != null ? fmtVol(s.avg_volume_20d) : '—',
    s.dollar_volume_20d != null ? `${fmtBig(s.dollar_volume_20d)} traded per day` : '',
    { na: s.avg_volume_20d == null }));

  $('c-stats').replaceChildren(...boxes);

  // ---- SEC facts
  // Form/period/filed strings come from third-party XBRL, and `reason` can carry
  // an exception message, so this table is built with DOM APIs for the same
  // reason the news list is -- not interpolated into innerHTML.
  const factsBox = $('c-facts');
  factsBox.replaceChildren();
  if (f.available && (f.facts || []).length) {
    $('c-facts-hint').textContent = '— each figure with the filing it came from';
    const table = document.createElement('table');
    const thead = document.createElement('thead');
    const hrow = document.createElement('tr');
    ['Metric', 'Value', 'Form', 'Period', 'Filed'].forEach(h => {
      const th = document.createElement('th');
      th.textContent = h;
      hrow.append(th);
    });
    thead.append(hrow);
    const tbody = document.createElement('tbody');
    f.facts.forEach(x => {
      const isPerShare = (x.unit || '').includes('shares');
      const cells = [
        x.label,
        isPerShare ? `$${Number(x.value).toFixed(2)}` : fmtBig(x.value),
        `${x.form || ''} ${x.fp || ''}${x.fy || ''}`.trim(),
        x.start ? `${x.start} → ${x.end}` : (x.end || ''),
        x.filed || '',
      ];
      const tr = document.createElement('tr');
      cells.forEach(c => {
        const td = document.createElement('td');
        td.textContent = c;
        tr.append(td);
      });
      tbody.append(tr);
    });
    table.append(thead, tbody);
    factsBox.append(table);
  } else {
    $('c-facts-hint').textContent = '';
    const p = document.createElement('p');
    p.className = 'sub';
    p.textContent = f.reason || 'No SEC facts available for this symbol.';
    factsBox.append(p);
  }

  // ---- news. This is the only third-party content the page renders, so it is
  // built with DOM APIs (never innerHTML) and only http(s) links are followed.
  const newsBox = $('c-news');
  newsBox.replaceChildren();
  if (d.news_error) {
    const p = document.createElement('p');
    p.className = 'sub';
    p.textContent = `News unavailable: ${d.news_error}`;
    newsBox.append(p);
  } else if (!(d.news || []).length) {
    const p = document.createElement('p');
    p.className = 'sub';
    p.textContent = 'No recent headlines for this symbol.';
    newsBox.append(p);
  } else {
    d.news.forEach(a => {
      const safe = typeof a.url === 'string' && /^https?:\/\//i.test(a.url);
      const item = document.createElement(safe ? 'a' : 'div');
      item.className = 'news-item';
      if (safe) {
        item.href = a.url;
        item.target = '_blank';
        item.rel = 'noopener noreferrer';
      }
      const h = document.createElement('div');
      h.className = 'h';
      h.textContent = a.headline || '(untitled)';
      const m = document.createElement('div');
      m.className = 'm';
      m.textContent = `${(a.created_at || '').slice(0, 10)} · ${a.source || 'unknown source'}`;
      (a.symbols || []).filter(x => x !== d.symbol).slice(0, 3).forEach(sym => {
        const t = document.createElement('span');
        t.className = 'tag';
        t.textContent = sym;
        m.append(t);
      });
      item.append(h, m);
      newsBox.append(item);
    });
  }

  // ---- research links
  const linkBox = $('c-links');
  linkBox.replaceChildren();
  (d.links || []).forEach(l => {
    if (!/^https?:\/\//i.test(l.url || '')) return;
    const a = document.createElement('a');
    a.className = 'linkchip';
    a.href = l.url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    const t = document.createElement('span');
    t.textContent = l.label;
    const n = document.createElement('span');
    n.className = 'n';
    n.textContent = l.note || '';
    a.append(t, n);
    linkBox.append(a);
  });
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

  updateYahooLink(s.symbol);
  renderRangeTabs();
  renderOverlayToggles();
  renderLegend();
  drawChart();
  renderTableView();
}

function renderAll() {
  renderViewTabs();

  // The calendar and the daily review both report on something other than a
  // ranked group, so the group-ranking furniture (hero, ranking bars, movers
  // strip, ranking table) and the lookback filter have nothing to scope. They
  // are hidden rather than left showing stale figures.
  const v = currentView();
  const calendar = !!v.calendar;
  const review = !!v.solo;
  const soloView = calendar || review;
  ['hero-card', 'rank-card', 'leaders-card', 'rank-table-card'].forEach(id => {
    const el = $(id);
    if (el) el.classList.toggle('hidden', soloView);
  });
  $('lookback-row').classList.toggle('hidden', soloView);
  $('earnings-card').classList.toggle('hidden', !calendar);
  $('review-card').classList.toggle('hidden', !review);

  if (soloView) {
    if (calendar) {
      if (!state.earnings) fetchEarnings();
      else renderEarnings();
      // Keep whatever symbol is charted; calendar rows can change it.
      if (state.stock) renderDetail();
    } else if (!state.review) {
      fetchReview();          // renderReview() runs when it lands
    } else {
      renderReview();
    }
    return;
  }

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

  $('symbol-form').addEventListener('submit', e => {
    e.preventDefault();
    const input = $('symbol-input');
    // Mirrors the server's own check (alnum once dots are stripped, for
    // tickers like BRK.B) so a bad entry gets an immediate message instead of
    // a round trip -- though fetchStock surfaces the server's error just as
    // well if something slips past this.
    const raw = input.value.trim().toUpperCase();
    if (!raw) return;
    if (!/^[A-Z0-9]+(\.[A-Z0-9]+)*$/.test(raw)) {
      showError(`"${raw}" doesn't look like a valid ticker.`);
      return;
    }
    input.value = raw;
    selectStock(raw);
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
    // Both solo views cache server-side, so without this Refresh left them
    // stale with no way for the user to force a rebuild.
    if (currentView().calendar) fetchEarnings(true);
    if (currentView().solo) fetchReview(true);
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

  renderViewTabs();
  renderLookbackTabs();
  fetchBoard(false);
}

document.addEventListener('DOMContentLoaded', init);
