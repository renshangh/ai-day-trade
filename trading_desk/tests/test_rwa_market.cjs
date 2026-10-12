const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../rwa_market.js'), 'utf8');
const coin = (symbol, cap, volume) => ({id:symbol.toLowerCase(),symbol,name:symbol,role:'Infrastructure',
  url:`https://www.coingecko.com/en/coins/${symbol.toLowerCase()}`,market_cap:cap,volume_24h:volume,
  cap_rank:1,volume_rank:1,coinbase_product:symbol+'-USD',updated_at:'2026-10-12T14:00:00Z'});
const tick = () => new Promise(resolve => setImmediate(resolve));
function setup(responses, onSelect=null) {
  const events = {}, requests = [], select = {value:''};
  const container = {innerHTML:'',querySelector:()=>select,addEventListener:(name,cb)=>events[name]=cb};
  const context = vm.createContext({Intl,Date,AbortSignal,document:{getElementById:()=>null},
    fetch:async url=>{requests.push(url);const response=responses.shift();if(response instanceof Error)throw response;
      return {ok:true,json:async()=>response && typeof response==='object'?{coinbase_checked_at:'2026-10-12T14:00:00Z',...response}:response};}});
  vm.runInContext(source,context);
  context.RwaMarket.mount(container,false,onSelect);
  const refresh=()=>events.click({target:{closest:selector=>selector==='[data-rwa-refresh]'}});
  const clickCoin=(symbol,modifiers={})=>{
    let prevented=false;
    events.click({...modifiers,target:{closest:selector=>selector==='[data-rwa-coin]'?{dataset:{rwaCoin:symbol}}:null},preventDefault:()=>{prevented=true;}});
    return prevented;
  };
  const sort=value=>{const target={matches:()=>true,value};events.change({target});};
  return {container,requests,refresh,sort,context,clickCoin};
}

test('malformed refresh withholds coins until Coinbase verification succeeds',async()=>{
  const original={coins:[coin('LINK',200e6,20e6)],fetched_at:'2026-10-12T14:01:00Z'};
  const harness=setup([original,{coins:[null]}]);
  await tick();
  assert.match(harness.container.innerHTML,/LINK/);
  harness.refresh();await tick();
  assert.doesNotMatch(harness.container.innerHTML,/>LINK</);
  assert.match(harness.container.innerHTML,/token list is withheld/);
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
  assert.match(harness.container.innerHTML,/token list is withheld/);
});


test('RWA tickers select the chart and link to the same board when opened elsewhere',async()=>{
  const selected=[];
  const harness=setup([{coins:[coin('QNT',200e6,20e6)]}],symbol=>selected.push(symbol));
  await tick();
  assert.match(harness.container.innerHTML,/href="\/board\?view=rwa&amp;symbol=QNT&amp;asset=crypto#detail-card"/);
  assert.doesNotMatch(harness.container.innerHTML,/href="https:\/\/www.coingecko.com\/en\/coins/);
  assert.equal(harness.clickCoin('QNT'),true);
  assert.deepEqual(selected,['QNT']);
  for(const modifiers of [{ctrlKey:true},{metaKey:true},{shiftKey:true},{altKey:true},{button:1}]){
    assert.equal(harness.clickCoin('QNT',modifiers),false);
  }
  assert.deepEqual(selected,['QNT']);
});

test('without a chart callback the board link keeps native navigation',async()=>{
  const harness=setup([{coins:[coin('LINK',200e6,20e6)]}]);await tick();
  assert.equal(harness.clickCoin('LINK'),false);
});

test('a token without explicit Coinbase product evidence is withheld',async()=>{
  const item=coin('QNT',200e6,20e6);delete item.coinbase_product;
  const harness=setup([{coins:[item]}]);await tick();
  assert.doesNotMatch(harness.container.innerHTML,/>QNT</);
  assert.match(harness.container.innerHTML,/token list is withheld/);
});
