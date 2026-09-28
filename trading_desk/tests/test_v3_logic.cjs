const assert = require('node:assert/strict');
const test = require('node:test');
const { economyScore, latestChanges, cryptoSnapshot, healthScore } = require('../v3_logic.js');

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

test('crypto snapshot uses only real complete returned bars', () => {
  const bars = Array.from({ length: 8 }, (_, i) => ({
    t: `2026-09-${String(i + 1).padStart(2, '0')}`, c: 100 + i, v: 200 + i,
  }));
  assert.deepEqual(cryptoSnapshot(bars), {
    date: '2026-09-08', close: 107, volume: 207,
    dayPct: (107 / 106 - 1) * 100,
    weekPct: (107 / 100 - 1) * 100,
  });
  assert.equal(cryptoSnapshot([{ t: '2026-09-08', c: 107 }]), null);
  assert.equal(cryptoSnapshot([]), null);
});

test('altcoin health score needs all eight sourced assessments', () => {
  const items = Array.from({ length: 8 }, () => ({ state: 'Healthy', source: 'https://example.com' }));
  assert.equal(healthScore(items), 100);
  items[0].state = 'Weak';
  assert.equal(healthScore(items), 80);
  items[1].state = 'Mixed';
  assert.equal(healthScore(items), 70);
  items[4].source = '';
  assert.equal(healthScore(items), null);
});
