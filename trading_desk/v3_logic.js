/* Pure v3 calculations. Missing or unsourced inputs never produce a score. */
(function (root, factory) {
  const logic = factory();
  if (typeof module === 'object' && module.exports) module.exports = logic;
  else root.TradingDeskV3Logic = logic;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  function validSource(value) {
    try { return ['http:', 'https:'].includes(new URL(value).protocol); }
    catch { return false; }
  }
  function economyScore(factors) {
    if (!Array.isArray(factors) || factors.length !== 6) return null;
    if (!factors.every(f => /^(100|[1-9]?\d)$/.test(String(f?.score ?? '')) && validSource(f?.source))) return null;
    return Math.round(factors.reduce((total, f) => total + Number(f.score), 0) / 6);
  }
  function latestChanges(reports) {
    if (!Array.isArray(reports) || reports.length < 2) return [];
    const sorted = [...reports].sort((a, b) => String(b.date).localeCompare(String(a.date)));
    return Array.isArray(sorted[0].changes) ? sorted[0].changes.slice(0, 5) : [];
  }
  function cryptoSnapshot(bars) {
    if (!Array.isArray(bars) || !bars.length) return null;
    const valid = bars.filter(bar => /^\d{4}-\d{2}-\d{2}$/.test(String(bar?.t)) &&
      bar?.c !== '' && bar?.c != null && Number.isFinite(Number(bar.c)) && Number(bar.c) > 0 &&
      bar?.v !== '' && bar?.v != null && Number.isFinite(Number(bar.v)) && Number(bar.v) >= 0)
      .sort((a, b) => String(a.t).localeCompare(String(b.t)));
    if (!valid.length) return null;
    const current = valid.at(-1);
    const pct = previous => previous ? (Number(current.c) / Number(previous.c) - 1) * 100 : null;
    return {
      date: current.t, close: Number(current.c), volume: Number(current.v),
      dayPct: pct(valid.at(-2)), weekPct: pct(valid.at(-8)),
    };
  }
  function healthScore(items) {
    const weights = [20, 20, 15, 10, 10, 10, 5, 10];
    if (!Array.isArray(items) || items.length !== weights.length) return null;
    const values = { Healthy: 100, Mixed: 50, Weak: 0 };
    if (!items.every(item => Object.hasOwn(values, item?.state) && validSource(item.source))) return null;
    return Math.round(items.reduce((sum, item, i) => sum + values[item.state] * weights[i] / 100, 0));
  }
  return { economyScore, latestChanges, validSource, cryptoSnapshot, healthScore };
});
