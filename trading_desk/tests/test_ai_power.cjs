const test=require('node:test'),assert=require('node:assert/strict');
const p=require('../ai_power.js'),fixture=require('./fixtures/nuclear_2026_10_09.json');
const copy=()=>structuredClone(fixture.stocks);
test('neocloud watchlist excludes the prior nuclear universe and requires its own data',()=>{
 assert.deepEqual(p.universe,['CORZ','GLXY','HUT','RIOT']);
 const a=p.assess(copy(),fixture.cutoff);
 assert.equal(a.valid,0);assert.equal(a.complete,false);assert.equal(a.confirmed,false);
 assert.equal(a.rows.CORZ.error,'No data');
 assert.ok(p.research.every(r=>r.eps>0&&r.href.startsWith('https:')));
});
test('in-progress sessions excluded and future observation never becomes a closed signal',()=>{
 const d=copy(),r=p.metrics(d.CEG,'2026-10-08');
 assert.equal(r.date,'2026-10-07');assert.equal(r.close,299.59);
 assert.equal(p.metrics(d.CEG,fixture.cutoff).close,285.07);
});
test('missing constituent and stale source prevent confirmation',()=>{
 const d=copy();delete d.CORZ;let a=p.assess(d,fixture.cutoff);assert.equal(a.complete,false);assert.equal(a.confirmed,false);assert.equal(a.rows.CORZ.close,undefined);
 d.CORZ={stale:true};a=p.assess(d,fixture.cutoff);assert.equal(a.complete,false);assert.match(a.rows.CORZ.error,/Stale/);
});
test('interior missing session is surfaced instead of changing lookback meaning silently',()=>{
 const d=copy();d.BWXT.bars.splice(-10,1);
 const r=p.metrics(d.BWXT,fixture.cutoff,p.metrics(d.SPY,fixture.cutoff).dates);
 assert.equal(r.missing,1);
});
test('duplicate and invalid observations cannot produce metrics',()=>{
 const d=copy();d.CEG.bars.push(d.CEG.bars.at(-2));assert.match(p.metrics(d.CEG,fixture.cutoff).error,/Invalid/);
 const e=copy();delete e.CEG.bars.at(-2).c;assert.match(p.metrics(e.CEG,fixture.cutoff).error,/Invalid/);
});
test('short history leaves 200 day average unavailable',()=>{
 assert.equal(p.metrics(copy().STDN,fixture.cutoff).sma200,null);
});
test('stale snapshot does not become confirmation days later',()=>{
 const a=p.assess(copy(),'2026-10-20');assert.equal(a.fresh,false);assert.equal(a.confirmed,false);
});
test('cash and risk both constrain whole shares; no rounding up risk',()=>{
 const a=p.sizeTrade({entry:100,stop:95,target:110,risk:24,budget:1000});assert.equal(a.shares,4);assert.equal(a.loss,20);
 const b=p.sizeTrade({entry:100,stop:95,target:110,risk:500,budget:250});assert.equal(b.shares,2);
});
test('sub-2R, reversed stops, unavailable values and unaffordable trades are rejected',()=>{
 for(const change of [{target:109},{stop:100},{entry:NaN},{risk:null},{budget:99}])assert.ok(p.sizeTrade({entry:100,stop:95,target:110,risk:100,budget:1000,...change}).error);
});
test('sourced journal rejects script URLs and empty evidence',()=>{
 const e={theme:p.theme,date:'2026-10-09',title:'Review',detail:'Interpretation',source:'https://www.energy.gov/'};
 assert.equal(p.validateEntry(e),null);assert.ok(p.validateEntry({...e,source:'javascript:alert(1)'}));assert.ok(p.validateEntry({...e,detail:''}));
});

test('AI Power stays on the Hot Sector Board without loading on the home page',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const read=name=>fs.readFileSync(path.join(__dirname,'..',name),'utf8');
 const home=read('v3.html'),script=read('v3.js'),board=read('index.html'),boardScript=read('app.js');
 assert.doesNotMatch(home,/id="ai-power(?:-desk)?"|href="#ai-power"|\/ai_power\.(?:js|css)/);
 assert.doesNotMatch(script,/AIPower\.mount|aiPowerReview|['"]#ai-power['"]/);
 assert.match(home,/id="brief"/);
 assert.match(board,/id="ai-power-card"/);
 assert.match(board,/\/ai_power\.js/);
 assert.match(board,/\/ai_power\.css/);
 assert.match(boardScript,/key: 'ai-power'/);
 assert.match(boardScript,/AIPower\.mount/);
});

test('mounted watchlist renders new earnings cards without nuclear plans or broker reads',async()=>{
 const original=global.fetch,requests=[],listeners={};
 const box={innerHTML:'',addEventListener:(name,fn)=>{listeners[name]=fn;}};
 global.fetch=async url=>{requests.push(url);return {ok:true,json:async()=>({error:'No real bars available'})};};
 try{
  const board=p.mount(box);
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(box.innerHTML,/CORZ.*Core Scientific/);
  assert.match(box.innerHTML,/GLXY.*Galaxy Digital/);
  assert.match(box.innerHTML,/HUT.*Hut 8/);
  assert.match(box.innerHTML,/RIOT.*Riot Platforms/);
  assert.match(box.innerHTML,/positive free cash flow/);
  assert.match(box.innerHTML,/Debt &amp; rate resilience|Debt & rate resilience/);
  assert.match(box.innerHTML,/\$1\.5M \/ year/);
  assert.match(box.innerHTML,/not a survival percentage or bankruptcy probability/);
  listeners.change({target:{matches:()=>true,value:'300'}});
  assert.match(box.innerHTML,/\$2\.3M \/ year/);
  assert.match(box.innerHTML,/value="300" selected/);
  await board.reload();
  assert.match(box.innerHTML,/value="300" selected/);
  assert.doesNotMatch(box.innerHTML,/nuclear|CEG|18,000|account_last4|funded trade plan/i);
  assert.equal(requests.length,12);
  assert.ok(requests.every(url=>url.startsWith('/api/stock?')));
  assert.equal(typeof board.reload,'function');
  let selected; p.mount(box,{onSelect:s=>{selected=s;}});
  listeners.click({target:{closest:selector=>selector==='[data-power-symbol]'?{dataset:{powerSymbol:'RIOT'}}:null},button:0,preventDefault:()=>{}});
  assert.equal(selected,'RIOT');
  await new Promise(resolve=>setImmediate(resolve));
 }finally{global.fetch=original;}
});

test('debt metrics use cash alone and preserve missing inputs and operating losses',()=>{
 const row={cash:10,restricted:1000,debt:100,operating:12,operatingGain:20,interest:4};
 assert.deepEqual(p.debtMetrics(row),{cashDebt:.1,coverage:-2});
 assert.deepEqual(p.debtMetrics({...row,cash:null,interest:0}),{cashDebt:null,coverage:null});
 assert.equal(p.debtMetrics({...row,operatingGain:null}).coverage,null);
 assert.equal(p.debtMetrics({...row,debt:0}).cashDebt,null);
 assert.equal(p.debtMetrics({...row,operating:null}).coverage,null);
});

test('rate scenarios use basis points and unknown exposure never becomes zero',()=>{
 assert.equal(p.rateStress(75.120,200),1.5024);
 assert.equal(p.rateStress(1000,100),10);
 assert.equal(p.rateStress(0,300),0);
 for(const amount of [null,undefined,NaN,-1,'75'])assert.equal(p.rateStress(amount,200),null);
 assert.equal(p.rateStress(75,-100),null);
});

test('dated disclosures keep GLXY financing gaps and HUT asset gains explicit',()=>{
 assert.deepEqual(p.debtProfiles.map(x=>x.symbol),p.universe);
 const rows=Object.fromEntries(p.debtProfiles.map(x=>[x.symbol,x]));
 assert.equal(p.debtMetrics(rows.GLXY).coverage,null);
 assert.equal(rows.GLXY.floating,null);
 assert.ok(p.debtMetrics(rows.HUT).coverage<0);
 assert.ok(p.debtMetrics(rows.RIOT).coverage<1);
 assert.ok(p.debtMetrics(rows.CORZ).coverage>1);
 assert.ok(rows.HUT.restricted>rows.HUT.cash*40);
 assert.ok(p.debtProfiles.every(x=>x.href.startsWith('https://')));
});
