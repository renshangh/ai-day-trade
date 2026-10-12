const test=require('node:test'),assert=require('node:assert/strict');
const p=require('../ai_power.js'),fixture=require('./fixtures/nuclear_2026_10_09.json');
const copy=()=>structuredClone(fixture.stocks);
test('real October snapshot distinguishes producer recovery from a broad bottom',()=>{
 const a=p.assess(copy(),fixture.cutoff);
 assert.equal(a.date,'2026-10-08');assert.equal(a.valid,12);assert.equal(a.above,6);
 assert.equal(a.producerCount,3);assert.equal(a.confirmed,false);
 assert.match(a.status,/Selective producer/);assert.equal(a.gates[0].pass,false);assert.equal(a.gates[2].pass,false);
 assert.ok(Math.abs(a.r5-4.584395738736982)<1e-8);
});
test('in-progress sessions excluded and future observation never becomes a closed signal',()=>{
 const d=copy(),r=p.metrics(d.CEG,'2026-10-08');
 assert.equal(r.date,'2026-10-07');assert.equal(r.close,299.59);
 assert.equal(p.metrics(d.CEG,fixture.cutoff).close,285.07);
});
test('missing constituent and stale source prevent confirmation',()=>{
 const d=copy();delete d.CEG;let a=p.assess(d,fixture.cutoff);assert.equal(a.complete,false);assert.equal(a.confirmed,false);assert.equal(a.rows.CEG.close,undefined);
 d.CEG=copy().CEG;d.CEG.stale=true;a=p.assess(d,fixture.cutoff);assert.equal(a.complete,false);assert.match(a.rows.CEG.error,/Stale/);
});
test('interior missing session is surfaced instead of changing lookback meaning silently',()=>{
 const d=copy();d.BWXT.bars.splice(-10,1);const a=p.assess(d,fixture.cutoff);
 assert.equal(a.rows.BWXT.missing,1);assert.equal(a.complete,false);assert.equal(a.confirmed,false);
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
