const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {matches,volumePasses,qualityPasses,qualifies,needsReview}=require('../range_discovery.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const source=fs.readFileSync(path.join(__dirname,'../range_discovery.js'),'utf8');
// Real measurements derived from archived completed Schwab/Coinbase candles.
const rows=JSON.parse(fs.readFileSync(path.join(__dirname,'../../reports/range_trading/RANGE_QUALITY_REVIEW_V7_2026_10_17.json'),'utf8')).rows;
const bySymbol=s=>rows.find(r=>r.symbol===s);
const atom=JSON.parse(fs.readFileSync(path.join(__dirname,'../../reports/range_trading/SCREEN_2026_10_17.json'),'utf8')).results.find(r=>r.product==='ATOM-USD');
function setup(observations=rows,mountOptions={}){
 const events={},requests=[],fields={};
 const container={innerHTML:'',classList:{add(){}},querySelector:s=>fields[s]||(fields[s]={value:''}),addEventListener:(name,fn)=>events[name]=fn};
 const idle={status:'idle',rows:[],checked:0,total:0};
 const complete={status:'complete',rows:observations,checked:5,total:5,market:'both',completed_at:'2026-10-17T21:00:00Z'};
 const context=vm.createContext({Intl,Date,AbortSignal,Number,console,setTimeout,clearTimeout,
  fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>options?.method==='POST'?complete:idle};}});
 vm.runInContext(source,context);context.RangeDiscovery.mount(container,mountOptions);
 return {container,requests,events,context};
}
const mainTable=h=>h.container.innerHTML.split('data-rd-candidates')[1].split('</table>')[0];
const submit=h=>h.events.submit({target:{matches:()=>true},preventDefault(){}});
test('rounded width rule is preserved independently of mandatory range quality',()=>{
 assert.equal(matches({range_ratio:14.56,rounded_ratio:15}),true);
 assert.equal(matches({range_ratio:14,rounded_ratio:14}),false);
 assert.equal(matches({range_ratio:15,rounded_ratio:15}),true);
 assert.equal(matches({range_ratio:NaN,rounded_ratio:15}),false);
});
test('real one-way ASTS and MARA moves never qualify despite high volume and width',()=>{
 for(const symbol of ['ASTS','MARA']){
  const r=bySymbol(symbol);assert.equal(matches(r),true);assert.equal(volumePasses(r),true);
  assert.equal(r.completed_cycles,0);assert.equal(qualityPasses(r),false);assert.equal(qualifies(r),false);
  assert.equal(qualifies({...r,quality_pass:true}),false); // A stale badge cannot substitute for actual swings.
 }
});
test('real QCOM provides a repeated-swing positive control at a lower width threshold',()=>{
 const r=bySymbol('QCOM');assert.equal(r.completed_cycles,2);assert.equal(qualityPasses(r),true);
 assert.equal(qualifies(r,3),true);assert.equal(qualifies(r,15),false);
 assert.equal(qualifies({...r,qualification_version:undefined},3),false);
});
test('opening is read-only and failed shapes appear only under disqualified moves',async()=>{
 const h=setup();await tick();assert.equal(h.requests.length,1);assert.equal(h.requests[0].options?.method,undefined);
 assert.match(h.container.innerHTML,/Discover candidates/);submit(h);await tick();
 assert.equal(h.requests[1].options.method,'POST');assert.deepEqual(JSON.parse(h.requests[1].options.body),{market:'both',threshold:15,stock_mode:'45_day'});
 assert.doesNotMatch(mainTable(h),/>ASTS</);assert.doesNotMatch(mainTable(h),/>MARA</);
 assert.match(mainTable(h),/>NEAR/);assert.doesNotMatch(mainTable(h),/>DOT/);
 assert.doesNotMatch(mainTable(h),/No candidates pass all/);
 assert.match(h.container.innerHTML,/Disqualified moves — not candidates/);
 assert.match(h.container.innerHTML,/>ASTS</);assert.match(h.container.innerHTML,/>MARA</);
 assert.match(h.container.innerHTML,/0 full swings observed; require at least 1/);
 assert.match(h.container.innerHTML,/No orders are placed/);
});
test('lowering only width never bypasses the swing gate and does not rescan',async()=>{
 const h=setup();await tick();submit(h);await tick();
 h.events.change({target:{matches:s=>s==='[data-rd-threshold]',value:'3'}});
 assert.match(mainTable(h),/>QCOM</);assert.match(mainTable(h),/2 completed full swings/);
 assert.doesNotMatch(mainTable(h),/>ASTS</);assert.doesNotMatch(mainTable(h),/>MARA</);
 assert.equal(h.requests.length,2);
});
test('dollar-volume gate still retains DOT liquidity and rejects thin or unknown volume',()=>{
 assert.equal(volumePasses(bySymbol('NEAR')),true);assert.equal(volumePasses(bySymbol('DOT')),true);
 assert.equal(volumePasses({asset:'crypto',volume_usd:atom.daily_turnover_proxy}),false);
 assert.equal(volumePasses({...bySymbol('NEAR'),volume_usd:null}),false);
 assert.equal(volumePasses({...bySymbol('NEAR'),volume_usd:NaN}),false);
});
test('mounting twice does not duplicate polling or handlers',async()=>{
 const h=setup();h.context.RangeDiscovery.mount(h.container);await tick();assert.equal(h.requests.length,1);
});
test('disqualification reasons render as text, not executable HTML',async()=>{
 const h=setup(rows.map(r=>({...r,warnings:['<img src=x onerror=alert(1)>']})));await tick();submit(h);await tick();
 assert.match(h.container.innerHTML,/&lt;img src=x onerror=alert\(1\)&gt;/);
 assert.doesNotMatch(h.container.innerHTML,/<img src=x/);
});

test('longer window labels and recent confirmation are explicit',async()=>{
 const h=setup();await tick();
 assert.match(h.container.innerHTML,/14-DAY CRYPTO · 45-DAY STOCKS/);
 assert.match(h.container.innerHTML,/one full swing within the latest 7 days/);
 const r=bySymbol('QCOM');
 assert.equal(qualifies({...r,recent_range_pass:false},3),false);
 assert.equal(qualifies({...r,qualification_version:2},3),false);
});

test('one-swing stocks stay in review and cannot become qualified entries',async()=>{
 const h=setup();await tick();submit(h);await tick();
 const review=h.container.innerHTML.split('data-rd-review-table')[1].split('</table>')[0];
 for(const symbol of ['COIN','MSTR']){
  const r=bySymbol(symbol);
  assert.equal(needsReview(r),true);assert.equal(qualifies(r),false);
  assert.equal(needsReview({...r,recent_range_pass:false}),false);
  assert.doesNotMatch(mainTable(h),new RegExp('>'+symbol+'<'));
  assert.match(review,new RegExp('>'+symbol+'<'));
 }
 assert.doesNotMatch(review,/>ASTS</);assert.doesNotMatch(review,/>MARA</);
 assert.match(h.container.innerHTML,/ranking factor/);
});

const longRows=JSON.parse(fs.readFileSync(path.join(__dirname,'../../reports/range_trading/TWO_YEAR_DESK_ROWS_2026_10_17.json'),'utf8')).rows;
test('two-year mode qualifies three-swing stocks with complete annual evidence',()=>{
 for(const r of longRows){
  assert.equal(qualifies(r),true);
  assert.equal(needsReview({...r,completed_cycles:1}),false);
  assert.equal(qualifies({...r,completed_cycles:2}),false);
  assert.equal(qualifies({...r,annual_cycles:[3,0]}),false);
  assert.equal(qualifies({...r,volume_usd_5:1}),false);
 }
});
test('two-year selector requests a fresh long-term scan and displays price charts',async()=>{
 const h=setup(longRows);await tick();
 h.events.change({target:{matches:s=>s==='[data-rd-stock-mode]',value:'two_year'}});
 submit(h);await tick();
 assert.equal(JSON.parse(h.requests[1].options.body).stock_mode,'two_year');
 assert.match(h.container.innerHTML,/2-YEAR STOCKS/);
 assert.match(h.container.innerHTML,/at least 3 full swings/);
 assert.match(mainTable(h),/>SWKS</);
 assert.match(h.container.innerHTML,/Review two-year price charts/);
 assert.match(h.container.innerHTML,/actual daily closing prices/);
 assert.doesNotMatch(h.container.innerHTML,/Needs review — one completed/);
});

function clickSymbol(h,symbol,asset){let prevented=false;h.events.click({target:{closest:()=>({getAttribute:k=>k==='data-rd-symbol'?symbol:asset})},preventDefault(){prevented=true;}});return prevented;}
test('snapshot selection loads the lower chart for stocks and crypto without navigation',async()=>{
 const selections=[];const h=setup(rows,{onSelect:(row,options)=>selections.push([row.symbol,row.asset,options.scroll])});
 await tick();submit(h);await tick();
 assert.deepEqual(selections[0],['NEAR','crypto',false]);
 assert.equal(clickSymbol(h,'COIN','stock'),true);
 assert.deepEqual(selections.at(-1),['COIN','stock',true]);
 assert.equal(clickSymbol(h,'DOT','crypto'),true);
 assert.deepEqual(selections.at(-1),['DOT','crypto',true]);
 assert.match(h.container.innerHTML,/symbol=NEAR&asset=crypto#detail-card/);
});
test('asset-aware deep link is respected instead of replacing it with first candidate',async()=>{
 const selections=[];const h=setup(rows,{initialSymbol:'DOT',initialAsset:'crypto',onSelect:r=>selections.push(r.symbol)});
 await tick();submit(h);await tick();
 assert.deepEqual(selections,['DOT']);
});
