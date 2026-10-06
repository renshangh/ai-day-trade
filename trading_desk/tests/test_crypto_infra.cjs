const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const { layers, render } = require('../crypto_infra.js');

test('infrastructure map includes eight layers and 37 entries and 31 genuine market links', () => {
  assert.equal(layers.length, 8);
  assert.equal(layers.flatMap(([, entries]) => entries).length, 37);
  const html = render();
  assert.equal((html.match(/target="_blank"/g) || []).length, 31);
  assert.equal((html.match(/data-chart-symbol=/g) || []).length, 31);
  assert.equal((html.match(/scope="row"/g) || []).length, 8);
  for (const [, entries] of layers) {
    for (const [, url, ticker, kind] of entries) {
      if (!url) { assert.equal(kind, 'unlisted'); assert.equal(ticker, 'No public ticker'); continue; }
      assert.equal(new URL(url).protocol, 'https:');
      assert.ok(['finance.yahoo.com', 'www.coingecko.com'].includes(new URL(url).hostname));
      assert.ok(html.includes(`href="${url}" target="_blank" rel="noopener noreferrer"`));
    }
  }
  assert.ok(html.includes('Coinbase x402/Bazaar'));
  assert.ok(html.includes('Ethereum/L2s'));
});

test('both pages load the shared map before their page scripts', () => {
  for (const [page, script] of [['v3.html', '/v3.js'], ['index.html', 'app.js']]) {
    const html = fs.readFileSync(path.join(__dirname, '..', page), 'utf8');
    assert.ok(html.includes('id="crypto-infra-map"'));
    assert.ok(html.indexOf('src="/crypto_infra.js"') < html.indexOf(`src="${script}"`));
    assert.ok(html.includes('href="/crypto_infra.css"'));
    assert.ok(!html.includes('AI Coins &amp; Agent Economy'));
  }
});

test('platform stocks and associated tokens use explicit market tickers', () => {
  const entries = new Map(layers.flatMap(([, entries]) => entries).map(entry => [entry[0], entry]));
  for (const [name, ticker] of [['Coinbase Prime', 'COIN'], ['JPMorgan Kinexys', 'JPM'], ['Circle CCTP', 'CRCL'], ['Securitize', 'SECZ']]) {
    assert.equal(entries.get(name)[2], ticker);
    assert.equal(entries.get(name)[3], 'stock');
  }
  assert.equal(entries.get('Ripple')[2], 'XRP');
  assert.equal(entries.get('Ripple')[3], 'crypto');
  for (const name of ['Anchorage Digital', 'Fireblocks', 'Stripe/Bridge', 'Superstate', 'DTCC']) assert.equal(entries.get(name)[1], null);
});

const { theme, reviewLayers, validateEntry, metricDelta, renderReview } = require('../crypto_infra.js');
const entry = (overrides = {}) => ({theme, date:'2026-10-06', layer:'Digital Money', title:'Offline fixture', detail:'Test evidence', impact:'Test implication', evidence:'Live usage', metric:'USDC supply', value:'110', unit:'USD', source:'https://example.org/supply', ...overrides});

test('five-layer daily review keeps anchors, empty states and original reference map', () => {
  assert.deepEqual(reviewLayers.map(x=>x.name), ['Digital Money','Onchain Markets','TradFi Bridge','Infrastructure Rails','Agentic Finance']);
  const html = renderReview([], '2026-10-06', true);
  assert.ok(html.includes('What changed since yesterday?'));
  assert.ok(html.includes('quote/COIN/'));
  assert.ok(html.includes('quote/CRCL/'));
  assert.equal((html.match(/Not reviewed for this date/g)||[]).length, 5);
  assert.ok(html.includes('eight original layers'));
  assert.ok(html.includes('Save daily entry'));
  assert.ok(!renderReview([], '2026-10-06').includes('Save daily entry'));
});

test('metric deltas require exactly one matching, sourced yesterday observation', () => {
  const prior=entry({date:'2026-10-05',value:'100'});
  assert.equal(metricDelta(entry(),[prior]).change,10);
  assert.equal(metricDelta(entry(),[prior]).percent,10);
  for (const override of [{date:'2026-10-04'},{value:''},{value:null},{unit:'tokens'},{metric:'USDT supply'},{layer:'Onchain Markets'},{theme:'RWA Dashboard'},{source:'javascript:alert(1)'}]) {
    assert.equal(metricDelta(entry(),[entry({...prior,...override})]),null);
  }
  assert.equal(metricDelta(entry({value:''}),[prior]),null);
  assert.equal(metricDelta(entry(),[prior,prior]),null);
  assert.equal(metricDelta(entry(),[entry({date:'2026-10-05',value:'0'})]).percent,null);
  assert.equal(metricDelta(entry({date:'2026-03-01'}),[entry({date:'2026-02-28',value:'100'})]).change,10);
});

test('daily entries require evidence and source, reject invalid metrics and dates', () => {
  assert.equal(validateEntry(entry()),null);
  assert.equal(validateEntry(entry({value:'',metric:'',unit:''})),null);
  for (const override of [{date:'2026-02-30'},{title:''},{detail:''},{impact:''},{layer:'unknown'},{evidence:'guess'},{source:'javascript:alert(1)'},{value:'NaN'},{value:'-1'},{unit:''},{metric:''}]) assert.ok(validateEntry(entry(override)));
});

test('rendering uses selected date, preserves legacy observations, and escapes entries', () => {
  const notes=[entry({title:'<script>alert(1)</script>',impact:'<img src=x>',source:'javascript:alert(1)'}),entry({date:'2026-10-05',title:'Yesterday only'}),{theme:'Agent Economy',title:'Legacy observation'}];
  const html=renderReview(notes,'2026-10-06');
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<script>'));
  assert.ok(!html.includes('href="javascript:'));
  assert.ok(!html.includes('Yesterday only'));
  assert.equal(notes.length,3);
});


test('every market symbol routes to the right chart including Canton CCCAUSD', () => {
  const {assetKind, chartHref, watchEntries} = require('../crypto_infra.js');
  assert.equal(assetKind('CCCAUSD'), 'crypto');
  assert.equal(assetKind('COIN'), 'stock');
  assert.equal(assetKind('CC'), undefined); // not Chemours stock
  assert.equal(assetKind('DTCC'), undefined);
  const html=renderReview([], '2026-10-06');
  assert.ok(html.includes('data-chart-symbol="CCCAUSD" data-chart-asset="crypto"'));
  for (const item of [...layers.flatMap(([,rows])=>rows), ...watchEntries.flat()]) {
    if (!item[1]) continue;
    assert.equal(assetKind(item[2]),item[3]);
    assert.ok(chartHref(item[2],item[3]).includes(`symbol=${encodeURIComponent(item[2])}&asset=${item[3]}`));
  }
});

test('board clicks select charts while modified clicks retain the normal link', () => {
  const {mount}=require('../crypto_infra.js');
  const listeners={}, calls=[];
  const box={addEventListener:(type,handler)=>{listeners[type]=handler;},innerHTML:''};
  mount(box,{onSelect:(...args)=>calls.push(args)});
  let prevented=false;
  const link={dataset:{chartSymbol:'CCCAUSD',chartAsset:'crypto'}};
  const event={target:{closest:()=>link},preventDefault:()=>{prevented=true;},button:0};
  listeners.click(event);
  assert.ok(prevented);
  assert.deepEqual(calls,[['CCCAUSD','crypto']]);
  listeners.click({...event,ctrlKey:true});
  assert.equal(calls.length,1);
});
