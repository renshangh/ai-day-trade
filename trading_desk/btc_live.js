(()=>{
'use strict';
const $=id=>document.getElementById(id);
const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cash=x=>x==null?'—':Number(x).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const tm=x=>x?new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false,timeZoneName:'short'}).format(new Date(x)):'—';
const pct=x=>x==null?'—':(x*100).toFixed(0)+'%';
const secs=x=>x==null?'—':Math.max(0,Math.round(x))+'s';
function hoursBadge(m){
 if(!m)return '<span class="ibit-hours-badge" data-state="unknown">IBIT hours unavailable</span>';
 const context=m.is_entry_or_exit?'<small>Available '+esc(tm(m.available_at))+' · reference '+esc(m.reference_session==='regular'?'regular':m.reference_session||'hours unknown')+(m.delay_after_completed_minute_seconds>180?' · delayed '+secs(m.delay_after_completed_minute_seconds):'')+'</small>':'';
 return '<span class="ibit-hours-badge" data-state="'+esc(m.state)+'" title="'+esc(m.note)+'">'+esc(m.label)+'</span>'+context;
}
function renderHours(h){
 const c=h?.current;$('ibit-hours-status').textContent=c?.label||'IBIT hours unverified';$('ibit-hours-status').dataset.state=c?.code||'unknown';
 $('ibit-hours-next').textContent=c?.trading_open?('Continuous trading window until '+tm(c.closes_at)+(c.regular_open?' · Regular hours':' · Outside regular hours: LIMIT / EXTO')+' · checked '+tm(h.now)):c?.next_open?'Next trading window '+tm(c.next_open)+' → '+tm(c.next_close)+' · checked '+tm(h.now):h?.calendar_error||'Calendar unavailable; no open session is assumed.';
 $('ibit-hours-plan').textContent=h?.manual_profile?(h.manual_profile.eligibility+'. '+h.manual_profile.order_note):'IBIT eligibility and channel are unverified.';
}
function invalidateHours(){renderHours(null);for(const node of (document.querySelectorAll?.('.ibit-hours-badge')||[])){node.dataset.state='unknown';node.textContent='IBIT hours unavailable';}}
const names={entry:'Model entry',target_25:'First 25% target',stop:'Hard-stop exit',stop_entry_minute_ambiguous:'Entry-minute stop (ambiguous order)',stop_raised:'Hard stop raised',structure_reference_raised:'15m structure protection',structure_exit_remaining:'Structure exit',failed_rebound_reference:'Failed-rebound protection',failed_rebound_exit_remaining:'Failed-rebound exit',early_exit_confirmed:'E1/E2 complete-bar confirmation',e1_exit_remaining:'E1 remainder exit',e2_exit_remaining:'E2 remainder exit',giveback_exit_remaining:'Profit-giveback exit',turning_exit_remaining:'New-high failure exit',wick_exit_all:'Upper-wick exit',midpoint_warning:'Midpoint warning only',entry_rejected:'Entry not qualified',entry_skipped:'Entry skipped',data_gap_exposure:'Missing observations during holding'};
const decisions={entry:'Model entry reference',held_position:'Qualified; model already holding',risk_rejected:'No positive net target space',structure_rejected:'Structure checks failed',exit_minute_no_reentry:'No same-minute re-entry'};
let serial=0,inflight=false,queued=false;
const empty=(columns,text)=>'<tr><td colspan="'+columns+'" class="muted">'+esc(text)+'</td></tr>';
function card(m,selected){
 const p=m.position,ref=p?.references||{},row=(a,b)=>'<dt>'+a+'</dt><dd>'+b+'</dd>';
 let h='<article class="model-card'+(m.model===selected?' selected':'')+'"><h3>'+esc(m.model)+'</h3><p>'+ (p?'Model holding · #'+p.id+' / '+esc(p.entry_rule):'Flat · no model position')+'</p><dl>';
 h+=row('Closed / wins / losses',m.closed+' / '+m.wins+' / '+m.losses)+row('Closed benchmark net','$'+cash(m.closed_net))+row('Realized exit-leg net','$'+cash(m.realized_leg_net));
 h+=row('Open benchmark net','$'+cash(m.open_benchmark_net))+row('Combined marked net','$'+cash(m.marked_benchmark_net));
 if(p)h+=row('Mark: observed 1m close','$'+cash(m.mark_price)+'<small>'+esc(tm(m.mark_minute))+'</small>');
 if(p)h+=row('Entry reference','$'+cash(p.entry)+'<small>'+esc(tm(p.entry_time))+'</small>')+row('Original D','$'+cash(ref.l1?.price)+'<small>known '+esc(tm(ref.l1?.known_at))+'</small>')+row('L2 reference',ref.l2?'$'+cash(ref.l2.price)+'<small>'+esc(tm(ref.l2.known_at))+'</small>':'B1 / no L2')+row('Initial / current stop','$'+cash(p.initial_stop)+' / $'+cash(p.stop))+row('First 25% target','$'+cash(p.t1))+row('Model remainder',pct(p.remaining))+row('Holding quality',p.gap_exposed||p.context_partial?'Flagged gap / incomplete context':'No flagged gap');
 else h+=row('Previous-high reference','$'+cash(m.next_previous_high_trigger)+'<small>Not an entry approval</small>');
 h+='</dl><details><summary>Current scanned setups</summary>';
 const setups=Object.entries(m.setups||{});
 h+=setups.length?setups.map(([k,v])=>'<p><b>'+esc(k)+'</b> D $'+cash(v.d?.price)+' · HL '+(v.hl?'$'+cash(v.hl.price):'not formed')+'<small>D known '+esc(tm(v.d?.known_at?new Date(v.d.known_at*1000).toISOString():null))+'</small></p>').join(''):'<p class="muted">No current setup. All entry conditions must pass before a model signal.</p>';
 h+='</details>';
 if(p?.legs?.length)h+='<details><summary>Recorded model exits</summary>'+p.legs.map(l=>'<p>'+esc(tm(l.time_utc))+' · '+pct(l.fraction)+' · $'+cash(l.price)+'<small>'+esc(names[l.reason]||l.reason)+' · net $'+cash(l.net)+'</small></p>').join('')+'</details>';
 return h+'</article>';
}
function render(d){
 renderHours(d.ibit_hours);
 $('health').textContent=d.health||'starting';$('health').dataset.health=d.health||'starting';
 $('start').disabled=d.enabled;$('pause').disabled=!d.enabled;
 $('source-status').innerHTML='<strong>Session '+esc(d.session?.id||'not started')+'</strong> · '+(d.online?'worker heartbeat '+esc(tm(d.heartbeat)):'worker offline / not yet installed')+'<br>Forward signal start: '+esc(d.session?tm(new Date(d.session.start*1000).toISOString()):null)+(d.error?'<p class="warning">'+esc(d.error)+'</p>':'');
 const metric=(label,value)=>'<div class="metric"><span class="muted">'+label+'</span><strong>'+esc(value)+'</strong></div>';
 $('live-metrics').innerHTML=metric('Last observed minute end',tm(d.minute_end))+metric('Observation age',secs(d.data_age_seconds))+metric('BTC quote midpoint',d.quote_fresh?'$'+cash(d.quote.mid):'Unavailable / stale')+metric('Broker orders','Disabled');
 $('supervision-status').textContent=d.supervision?.mode==='launchd'&&d.supervision.login_startup_verified?'Automatic login startup enabled. macOS restarts the worker if needed; this page can stay closed.':'Automatic login startup is not verified for this worker.';
 $('live-cost').textContent=(d.cost_note||'')+(d.supervision?.login_startup_verified===false?' Login auto-start is not verified; the local background supervisor is active.':'');$('quote-status').textContent=d.quote_fresh?'Quote '+tm(d.quote.time)+' · bid $'+cash(d.quote.bid)+' / ask $'+cash(d.quote.ask)+' · reference only, not a fill':d.quote_error||'No fresh BTC/USD quote; no substitution.';
 $('model-cards').innerHTML=(d.models||[]).map(m=>card(m,d.selected_model)).join('')||'<p class="muted">Models appear after the actual warmup is processed.</p>';
 $('live-signals').innerHTML=(d.signals||[]).map((s,i)=>'<tr><td>'+esc(s.route)+'<small>'+esc(decisions[s.decision]||s.decision)+'</small></td><td>'+esc(tm(s.time_utc))+'<small>full 1m known no earlier than '+esc(tm(s.interval_end))+'</small></td><td>'+esc(tm(s.detected_at))+'<small>lag from minute start '+secs(s.detection_delay_seconds)+'</small></td><td>$'+cash(s.entry_reference)+'<small>stop $'+cash(s.initial_stop)+' / T1 $'+cash(s.t1)+'</small></td><td>D $'+cash(s.references.l1.price)+'<small>L2 '+(s.references.l2?'$'+cash(s.references.l2.price):'not required for B1')+'</small></td><td class="ibit-hours-cell">'+(s.context_partial?'Incomplete entry context':'No flagged entry gap')+'<small>Model reference only · no broker fill</small>'+hoursBadge(d.ibit_hours?.signals?.[i])+'</td></tr>').join('')||empty(6,'No forward entry signals for this model. Warmup and absent signals are not invented trades.');
 $('live-ledger').innerHTML=(d.rows||[]).map(r=>'<tr><td>'+esc(tm(r.time))+'<small>to '+esc(tm(r.end))+'</small></td><td>'+[r.open,r.high,r.low,r.close].map(cash).join(' / ')+'</td><td class="'+(r.observed_minutes<15?'warning':'')+'">'+r.observed_minutes+' / 15</td><td>$'+cash(r.l1_price)+' / $'+cash(r.l2_price)+'<small>L1 known '+esc(tm(r.l1_known_at))+'</small></td><td>$'+cash(r.stop)+' / '+pct(r.remaining)+(r.position_id?' · #'+r.position_id:'')+'</td><td>'+r.events.map(e=>esc(names[e.type]||e.type)+'<small>'+esc(tm(e.time_utc))+(e.price!=null?' @ $'+cash(e.price):'')+'</small>').join('')+'</td></tr>').join('')||empty(6,'No observed completed 15-minute records for this selection yet.');
 $('live-events').innerHTML=(d.events||[]).map((e,i)=>'<tr><td>'+esc(names[e.type]||e.type)+(e.trade_id?' · #'+e.trade_id:'')+'</td><td>'+esc(tm(e.reference_time))+'</td><td>'+esc(tm(e.detected_at))+'<small>'+secs(e.detection_delay_seconds)+' from reference time</small></td><td>$'+cash(e.price)+'<small>'+(e.fraction!=null?pct(e.fraction):'')+'</small></td><td class="ibit-hours-cell">'+esc(e.reason||'Frozen-rule model event')+'<small>No broker fill; detection time is not backdated</small>'+hoursBadge(d.ibit_hours?.events?.[i])+'</td></tr>').join('')||empty(5,'No forward events for this model yet.');
}
async function refresh(){
 if(inflight){queued=true;return;}inflight=true;const id=++serial,model=$('model').value,day=$('live-day').value;
 try{const q=new URLSearchParams({model});if(day)q.set('day',day);
 const r=await fetch('/api/btc-live?'+q,{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'Live comparison unavailable');
 if(id===serial&&$('model').value===model&&$('live-day').value===day){render(d);$('live-error').hidden=true;}
 else queued=true;}
 catch(e){invalidateHours();$('live-error').textContent=e.message;$('live-error').hidden=false;}
 finally{inflight=false;if(queued){queued=false;void refresh();}}
}
async function control(operation){
 try{const r=await fetch('/api/btc-live',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation})});const d=await r.json();if(!r.ok)throw Error(d.error||'Control unavailable');await refresh();}
 catch(e){$('live-error').textContent=e.message;$('live-error').hidden=false;}
}
$('start').onclick=()=>control('start');$('pause').onclick=()=>control('pause');$('model').onchange=refresh;$('live-day').onchange=refresh;$('latest').onclick=()=>{$('live-day').value='';refresh();};
refresh();setInterval(refresh,5000);
})();
