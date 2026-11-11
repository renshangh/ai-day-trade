const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process');
const root=path.resolve(__dirname,'../..');
function actual(now='2026-10-12T13:34:10Z'){
 const code=`import json,copy
from trading_desk.btc_data import read,ROOT
from trading_desk.ibit_hours import Calendar,epoch,signal_hours,PLAN,PROFILE
r=read(ROOT/'trading_desk/tests/fixtures/ibit_hours_reference.json')
d=dict(models=[],rows=[],events=[],selected_model='0.1',health='running')
entry=copy.deepcopy(r['signal']);entry['detected_at']=entry['interval_end'];d['signals']=[entry]
d['events']=[r['exit'],dict(type='entry_rejected',reference_time=entry['time_utc'],detected_at=entry['interval_end'])]
now='${now}';n=epoch(now);doc=read(ROOT/'trading_desk/tests/fixtures/ibit_calendar_2025_2027.json');doc['fetched_at']=now;c=Calendar(doc,n);current=c.at(n)
d['ibit_hours']=dict(now=now,current=current,planned_23_5=PLAN,manual_profile=PROFILE,signals=[signal_hours(s,current,c,n) for s in d['signals']],events=[signal_hours(e,current,c,n,event=True) for e in d['events']])
print(json.dumps(d))`;
 return JSON.parse(cp.execFileSync('python3',['-c',code],{cwd:root,maxBuffer:3*1024*1024}));
}
function render(d){const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{value:id==='model'?'0.1':'',dataset:{},innerHTML:'',textContent:'',hidden:false});return nodes.get(id);};let source=fs.readFileSync(path.join(root,'trading_desk/btc_live.js'),'utf8');source=source.slice(0,source.indexOf("$('start').onclick="))+'globalThis.draw=render;})();';const ctx=vm.createContext({document:{getElementById:get},Intl,Date,URLSearchParams});vm.runInContext(source,ctx);ctx.draw(d);return get;}
test('actual recent entry gets a timing badge, not a fill or eligibility claim',()=>{const d=actual();assert.equal(d.signals.length,1);const get=render(d);assert.match(get('ibit-hours-status').textContent,/regular window open/);assert.match(get('live-signals').innerHTML,/Recent · IBIT regular window/);assert.match(get('live-signals').innerHTML,/13:34|09:34/);assert.match(get('live-signals').innerHTML,/data-state="review"/);assert.match(get('model-cards').innerHTML,/Closed benchmark net|actual warmup/);});
test('old signals stay historical when another regular session is open',()=>{const get=render(actual('2026-11-11T16:00:00Z'));assert.match(get('live-signals').innerHTML,/Historical · Regular at detection/);assert.doesNotMatch(get('live-signals').innerHTML,/data-state="review"/);assert.match(get('ibit-hours-plan').textContent,/reported by owner/);});
test('closed current window and informative events remain separate from worker health',()=>{const get=render(actual('2026-11-14T17:00:00Z'));assert.equal(get('ibit-hours-status').dataset.state,'closed');assert.match(get('ibit-hours-next').textContent,/Next trading window/);assert.match(get('live-events').innerHTML,/Info only/);assert.match(get('live-events').innerHTML,/Historical/);});
test('unavailable metadata fails visibly without suppressing BTC records',()=>{const d=actual();delete d.ibit_hours;const get=render(d);assert.equal(get('ibit-hours-status').dataset.state,'unknown');assert.match(get('live-signals').innerHTML,/IBIT hours unavailable/);assert.match(get('live-signals').innerHTML,/73,332|Model reference/);assert.match(get('model-cards').innerHTML,/Closed benchmark net|actual warmup/);});
test('overlay adds no order path or change to the strategy worker',()=>{const html=fs.readFileSync(path.join(root,'trading_desk/btc_live.html'),'utf8');assert.match(html,/Manual thinkorswim EXTO timing only/);assert.match(html,/BTC continues 24\/7/);const source=fs.readFileSync(path.join(root,'trading_desk/btc_live.js'),'utf8');assert.match(source,/function hoursBadge/);assert.doesNotMatch(source,/\/api\/schwab|PLACE BUY|PLACE SELL/);});

test('overnight current window is open separately from regular hours',()=>{const get=render(actual('2026-11-11T02:00:10Z'));assert.equal(get('ibit-hours-status').dataset.state,'overnight');assert.match(get('ibit-hours-next').textContent,/Outside regular hours: LIMIT \/ EXTO/);assert.match(get('ibit-hours-plan').textContent,/API overnight routing is not established/);});
