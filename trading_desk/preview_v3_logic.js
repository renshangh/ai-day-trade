/* Pure preview calculations. Missing or unsourced inputs never produce a score. */
(function (root, factory) {
  const logic = factory();
  if (typeof module === 'object' && module.exports) module.exports = logic;
  else root.PreviewV3Logic = logic;
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
  return { economyScore, latestChanges, validSource };
});
