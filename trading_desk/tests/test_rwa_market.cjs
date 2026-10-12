const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../rwa_market.js'), 'utf8');
const coin = (symbol, cap, volume) => ({id:symbol.toLowerCase(),symbol,name:symbol,role:'Infrastructure',
  url:`https://www.coingecko.com/en/coins/${symbol.toLowerCase()}`,market_cap:cap,volume_24h:volume,
  cap_rank:1,volume_rank:1,updated_at:'2026-10-12T14:00:00Z'});
const tick = () => new Promise(resolve => setImmediate(resolve));
function setup(responses) {
  const events = {}, requests = [], select = {value:''};
  const container = {innerHTML:'',querySelector:()=>select,addEventListener:(name,cb)=>events[name]=cb};
  const context = vm.createContext({Intl,Date,AbortSignal,document:{getElementById:()=>null},
    fetch:async url=>{requests.push(url);const response=responses.shift();if(response instanceof Error)throw response;
      return {ok:true,json:async()=>response};}});
  vm.runInContext(source,context);
  context.RwaMarket.mount(container);
  const refresh=()=>events.click({target:{closest:()=>true}});
  const sort=value=>{const target={matches:()=>true,value};events.change({target});};
  return {container,requests,refresh,sort,context};
}

test('malformed refresh preserves the previous sourced observations',async()=>{
  const original={coins:[coin('LINK',200e6,20e6)],fetched_at:'2026-10-12T14:01:00Z'};
  const harness=setup([original,{coins:[null]}]);
  await tick();
  assert.match(harness.container.innerHTML,/LINK/);
  harness.refresh();await tick();
  assert.match(harness.container.innerHTML,/LINK/);
  assert.match(harness.container.innerHTML,/Market refresh unavailable/);
  assert.match(harness.container.innerHTML,/200(?:\.00)?M/);
  assert.deepEqual(harness.requests,['/api/rwa-market','/api/rwa-market?force=1']);
});

test('volume and market-cap sorting reorder the same shortlist',async()=>{
  const harness=setup([{coins:[coin('LINK',900e6,20e6),coin('ONDO',200e6,50e6)]}]);
  await tick();
  harness.sort('volume');
  assert.ok(harness.container.innerHTML.indexOf('>ONDO<')<harness.container.innerHTML.indexOf('>LINK<'));
  harness.sort('cap');
  assert.ok(harness.container.innerHTML.indexOf('>LINK<')<harness.container.innerHTML.indexOf('>ONDO<'));
  harness.context.RwaMarket.mount(harness.container);
  assert.equal(harness.requests.length,1);
});

test('unavailable initial response displays empty state with warning',async()=>{
  const harness=setup([new Error('Offline')]);await tick();
  assert.match(harness.container.innerHTML,/Market observations unavailable/);
  assert.match(harness.container.innerHTML,/Market refresh unavailable/);
});
