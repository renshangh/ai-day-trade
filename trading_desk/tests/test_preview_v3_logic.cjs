const assert = require('node:assert/strict');
const test = require('node:test');
const { economyScore, latestChanges } = require('../preview_v3_logic.js');

test('AI Economy score needs six scored and sourced inputs', () => {
  const factors = Array.from({ length: 6 }, () => ({ score: '60', source: 'https://example.com/source' }));
  assert.equal(economyScore(factors), 60);
  factors[0].score = '100';
  assert.equal(economyScore(factors), 67);
  factors[0].source = '';
  assert.equal(economyScore(factors), null);
  factors[0].source = 'javascript:alert(1)';
  assert.equal(economyScore(factors), null);
  assert.equal(economyScore(factors.slice(1)), null);
});

test('Top 5 changes require a prior report and use the latest dated snapshot', () => {
  const changes = Array.from({ length: 7 }, (_, i) => ({ text: String(i) }));
  assert.deepEqual(latestChanges([{ date: '2026-09-02', changes }]), []);
  const result = latestChanges([{ date: '2026-09-02', changes }, { date: '2026-09-01', changes: [] }]);
  assert.equal(result.length, 5);
  assert.equal(result[0].text, '0');
});
