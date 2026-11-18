const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'trading_desk/chart_review.js'), 'utf8');
const saved = () => JSON.parse(fs.readFileSync(path.join(root, 'trading_desk/chart_review.json'), 'utf8'));
async function render(data, mode = 'full', hash = '') {
  const target = {dataset: {chartReview: mode}, innerHTML: '', textContent: ''};
  const requests = [];
  const scrolled = [];
  const context = vm.createContext({Intl, Date, URL, Set, location: {hash},
    document: {
      querySelectorAll: () => [target],
      getElementById: id => target.innerHTML.includes(`id="${id}"`)
        ? {scrollIntoView: () => scrolled.push(id)}
        : null
    },
    fetch: async (...args) => { requests.push(args); return {ok: true, json: async () => data}; }
  });
  vm.runInContext(source, context);
  await new Promise(setImmediate);
  return {html: target.innerHTML, requests, scrolled};
}
test('all five pairs and judgments are visible in both Daily Review and the full gallery', async () => {
  for (const mode of ['compact', 'full']) {
    const {html} = await render(saved(), mode);
    assert.equal((html.match(/class="chart-review-pair"/g) || []).length, 5);
    assert.equal((html.match(/Which count fits better\?/g) || []).length, 5);
    for (const asset of saved().assets.filter(a => a.comparison)) {
      for (const url of [asset.comparison.original_url, asset.comparison.updated_url]) {
        // Full history must not silently duplicate either comparison image.
        assert.equal(html.split(`src="${url}"`).length - 1, 1);
      }
    }
    assert.match(html, /not the impulse/);
    assert.match(html, /cannot restore/);
    assert.match(html, /\/NQZ26/);
    assert.match(html, /\/ESZ26/);
  }
});
test('cash and futures keep independent quote sources, points, baselines and image labels', async () => {
  const {html} = await render(saved());
  assert.match(html, /27,001\.79 points/);
  assert.match(html, /7,340\.53 points/);
  assert.match(html, /separate futures evidence/);
  assert.match(html, /No futures percentage return is shown/);
  assert.match(html, /10minutes delayed/);
  assert.match(html, /26,570\.00 \/ 26,658\.50/);
  assert.match(html, /7,308\.00/);
});
test('missing capture or futures quote remains unavailable and comparison prose is escaped', async () => {
  const data = saved();
  const ndx = data.assets.find(a => a.symbol === 'NDX');
  ndx.comparison.original_url = 'javascript:alert(1)';
  ndx.comparison.verdict = '<img src=x onerror=alert(1)>';
  ndx.futures.quote = {price: null};
  const {html} = await render(data);
  assert.match(html, /Saved capture unavailable; no substitute drawing/);
  assert.match(html, /Quote unavailable/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(html, /href="javascript:|<img src=x/);
});
test('saved completed futures candles contain no maintenance fills or partial pseudo-bars', () => {
  for (const asset of saved().assets.filter(a => a.futures)) {
    const f = asset.futures;
    assert.equal(f.rth_15m_coverage, 26);
    for (const b of f.completed_15m) {
      assert.equal(b.start % 900, 0);
      assert.ok((b.start + 900) * 1000 <= Date.parse(f.history_cutoff));
      for (const k of ['open', 'high', 'low', 'close', 'volume']) assert.ok(Number.isFinite(b[k]));
      assert.ok(b.low <= b.open && b.low <= b.close && b.high >= b.open && b.high >= b.close);
      assert.ok(b.time.slice(11, 19) >= '18:00:00');
    }
  }
});
test('view reads only its saved manifest without refreshing accounts or starting a monitor', async () => {
  const {requests} = await render(saved());
  assert.equal(requests.length, 1);
  assert.equal(requests[0][0], '/chart_review.json');
  assert.doesNotMatch(source, /method:\s*['"]POST|setInterval|\/api\/schwab/);
});
test('next-session plan is complete in Daily Review and gallery with dated independent market tests', async () => {
  const data = saved();
  const plan = data.next_session_plan;
  assert.equal(plan.date, '2026-11-18');
  assert.deepEqual(plan.holdings.map(h => h.symbol), ['COIN', 'CRCL', 'IBIT']);
  assert.doesNotMatch(JSON.stringify(plan), /0071|1638|2840|3652|6434|accountNumber|hashValue/);
  for (const mode of ['compact', 'full']) {
    const {html, requests} = await render(data, mode);
    const section = html.slice(html.indexOf('id="next-session-plan"'), html.indexOf('Watch first.'));
    for (const item of plan.holdings) {
      for (const field of ['hold', 'sell_first', 'sell_next', 'warning', 'invalidation']) assert.ok(section.includes(item[field]));
    }
    for (const level of ['27,382', '27,560.75–27,609.75', '7,434.75–7,437.00', '$63,833.47', '$66,100–$66,369.12', '$61,946.17']) assert.ok(section.includes(level), level);
    assert.match(section, /2026-11-18/);
    assert.match(section, /Nov 17, 06:55:59/);
    assert.match(section, /not a live quote/);
    assert.match(section, /FOMC minutes/);
    assert.match(section, /https:\/\/www.federalreserve.gov\/newsevents\/2026-november.htm/);
    assert.equal(requests.length, 1);
  }
});
test('expired plans are labeled historical; missing plan quotes and unsafe text remain safe', async () => {
  const data = saved();
  data.next_session_plan.date = '2000-01-01';
  data.next_session_plan.title = '<script>alert(1)</script>';
  data.next_session_plan.holdings[0].quote = {price:null};
  data.next_session_plan.event.source = 'javascript:alert(1)';
  const {html} = await render(data);
  assert.match(html, /HISTORICAL PLAN — REFRESH REQUIRED/);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(html, /Unavailable/);
  assert.doesNotMatch(html, /<script>|href="javascript:/);
});

test('Daily Review puts the Elliott study links ahead of the plan and exposes saved scenario conditions', async () => {
  const data = saved();
  const {html} = await render(data, 'compact');
  const shortcuts = html.slice(0, html.indexOf('id="next-session-plan"'));
  assert.match(shortcuts, /Elliott Wave scenarios/);
  for (const symbol of ['NDX', 'SPX', 'BTC', 'COIN', 'CRCL']) {
    const start = html.indexOf(`id="chart-${symbol}"`);
    const card = html.slice(start, html.indexOf('</article>', start));
    assert.ok(shortcuts.includes(`href="#chart-${symbol}"`));
    assert.match(card, /<strong>Confirmation:<\/strong>/);
    assert.match(card, /<strong>Invalidation \/ warning:<\/strong>/);
    assert.match(card, /<th>Review test<\/th>/);
  }
});

test('direct gallery links scroll to the requested ticker after rendering the manifest', async () => {
  assert.deepEqual((await render(saved(), 'full', '#chart-CRCL')).scrolled, ['chart-CRCL']);
  assert.deepEqual((await render(saved(), 'full', '#chart-unavailable')).scrolled, []);
});
