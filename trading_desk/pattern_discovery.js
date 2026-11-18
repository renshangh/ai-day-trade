'use strict';
const $=id=>document.getElementById(id);
const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=x=>typeof x==='number'&&Number.isFinite(x)?'$'+x.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'—';
const when=x=>x?new Date(x).toLocaleString('en-US',{timeZone:'America/New_York',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZoneName:'short'}):'—';
const cell=x=>'<td>'+x+'</td>',row=xs=>'<tr>'+xs.map(cell).join('')+'</tr>';
const epoch=t=>new Date(t*1000).toISOString();
function evidence(e){const s=e.setup,b=s.stabilization_bar;
 return `<details><summary>B1 · entry evidence</summary><p>Impulse: ${when(epoch(s.impulse.t))} → ${when(epoch(s.impulse.t+900))}</p><p>L1 / extended D: ${money(e.references.l1.price)} at ${when(e.references.l1.time)}; known ${when(e.references.l1.known_at)}. L2 is not required for B1.</p><p>Completed reference: ${when(epoch(b.t))} → ${when(epoch(b.t+900))}; high ${money(b.high)}, close ${money(b.close)}. Trigger ${money(e.references.trigger)}.</p><p>Modeled exits: ${e.outcome.legs.map(l=>`${l.fraction*100}% at ${when(l.time_utc)}, ${money(l.price)}, net ${money(l.net)} (${esc(l.reason)})`).join('; ')}</p><pre>${esc(JSON.stringify({features:e.features,references:e.references,setup:e.setup},null,2))}</pre></details>`;
}
let pending=false,editing=false,libraryKey=null,universeScreen=null;
function renderUniverse(){
 const u=universeScreen;if(!u)return;
 const filter=$('universe-filter').value||'selected';
 const rows=u.rows.filter(x=>filter==='all'||filter==='qualified'&&x.qualifies||filter==='selected'&&(x.selected||['SPY','QQQ'].includes(x.symbol)));
 const billion=x=>'$'+(x/1e9).toFixed(2)+'B',million=x=>(x/1e6).toFixed(1)+'M';
 $('universe-summary').textContent=`Completed session ${u.session} · ${u.universe_size} names screened · ${u.qualified} qualified · ${u.omitted.length} unavailable. Both 5/20-session averages require ≥$500M/day and ≥5M shares/day; positive beta ≥1.25; ATR14 ≥3% of close. Consolidated SIP daily data; no IEX liquidity estimates.`;
 $('universe').innerHTML=rows.map(x=>row([`${esc(x.symbol)} · ${esc(x.kind)}${x.leverage_daily?'<small class="bad">'+esc(x.leverage_daily)+'× DAILY leveraged target</small>':''}`,x.beta63.toFixed(2),`${money(x.atr14)} / ${x.atr_pct.toFixed(2)}%`,`${billion(x.avg_dollar_volume_5)} / ${billion(x.avg_dollar_volume_20)}`,`${million(x.avg_shares_5)} / ${million(x.avg_shares_20)}`,x.selected?'Selected for paper scan':x.qualifies?'Qualified / reserve':esc(x.reasons.join('; '))])).join('');
}
function render(s){
 const lib=s.library,c=s.config||{};
 $('health').textContent=`${s.status} · worker ${s.worker_fresh?'responding':'not fresh/not started'} · last update ${when(s.updated_at)} · activation ${when(s.activation)} · local paper only`;
 $('error').textContent=s.error?.error||'';
 if(!editing){$('watchlist').value=(c.watchlist||[]).join(', ');$('enabled').checked=!!c.enabled;}
 universeScreen=s.universe_screen||null;renderUniverse();
 const key=lib?`${lib.version}:${lib.source_sha256}`:null;
 if(lib&&key!==libraryKey){
  libraryKey=key;
  $('definition').innerHTML=Object.entries(lib.definition).map(([k,v])=>`<p><strong>${esc(k)}</strong>: ${esc(v)}</p>`).join('');
  $('selection').textContent=`${lib.examples.length} ranked winners · ${lib.examples.filter(e=>e.matching_enabled!==false).length} enabled for matching · ${lib.counterexamples.length} losing lookalikes · training ends ${when(lib.training_end)}. ${lib.selection_bias}`;
  $('examples').innerHTML=lib.examples.map(e=>row([`${esc(e.example_id)} / #${e.source_trade_id}${e.quality_flag?'<small class="bad">Data gap: conditional P/L; matching disabled</small>':''}`,when(e.entry_time),`${money(e.entry)} / ${money(e.references.l1?.price)} / ${money(e.initial_stop)}`,money(e.target),when(e.outcome.exit_time),`${money(e.outcome.net)} / ${e.outcome.net_r.toFixed(2)}R`,evidence(e)])).join('');
  $('features').innerHTML='<pre>'+esc(JSON.stringify({features:lib.features,counterexamples:lib.counterexamples.map(e=>({id:e.example_id,source_trade:e.source_trade_id,entry:e.entry_time,features:e.features,outcome:e.outcome.net}))},null,2))+'</pre>';
 }
 const symbols=s.symbols||[];
 $('coverage').innerHTML=symbols.map(x=>{const p=x.open_position;return row([`${esc(x.symbol)}<small>${esc(x.source)}</small>`,`${esc(x.status)}<small>${when(x.last_bar)} · ${x.observed_minutes??0} real minutes</small>${x.error?'<span class="bad">'+esc(x.error)+'</span>':''}`,p?`#${p.id} · ${p.remaining*100}% remaining`:'None',p?`${money(p.entry)} / ${money(p.stop)} / ${money(p.t1)}`:'—',p?money(p.unrealized_net_reference):'—',money(x.realized_net)]);}).join('')||row(['Waiting for first scan','','','','','']);
 const decisions=symbols.flatMap(x=>(x.decisions||[]).map(d=>({...d,symbol:x.symbol}))).sort((a,b)=>b.time_utc.localeCompare(a.time_utc));
 $('decisions').innerHTML=decisions.map(d=>row([`${esc(d.symbol)}<small>${when(d.time_utc)}</small>`,`${when(d.available_after)}<small>${when(d.detected_at)} · ${Number(d.delay_seconds).toFixed(0)}s delay</small>`,d.match?`${esc(d.match.nearest_positive.example_id)} / ${esc(d.match.nearest_negative.example_id)}`:'No match evaluated',d.match?d.match.margin.toFixed(4):'—',`${money(d.reference)} / ${money(d.initial_stop)} / ${money(d.target)}`,d.accepted?`Local paper #${d.trade_id}`:`Skipped: ${esc(d.reason)}`])).join('')||row(['No forward qualifying crossings yet','','','','','']);
 $('trades').innerHTML=symbols.flatMap(x=>[...(x.closed_trades||[]),...(x.open_position?[x.open_position]:[])].flatMap(p=>(p.legs||[]).map(l=>row([`${esc(x.symbol)} / #${p.id}`,`${when(p.entry_time)}<small>${money(p.entry)}</small>`,`${when(l.time_utc)}<small>${esc(l.reason)} · ${l.fraction*100}%</small>`,money(l.price),money(l.net),p.net===null||p.net===undefined?'Still open':money(p.net)])))).join('')||row(['No model exits yet','','','','','']);
}
async function refresh(){if(pending)return;pending=true;try{const r=await fetch('/api/pattern-discovery');const s=await r.json();if(!r.ok)throw new Error(s.error||'Local data unavailable');render(s);}catch(e){$('error').textContent=e.message;}finally{pending=false;}}
$('watchlist').addEventListener('input',()=>editing=true);$('enabled').addEventListener('change',()=>editing=true);
$('universe-filter').addEventListener('change',renderUniverse);
$('config-form').addEventListener('submit',async e=>{e.preventDefault();$('saved').textContent='Saving…';try{const r=await fetch('/api/pattern-discovery',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({watchlist:$('watchlist').value.split(/[\s,]+/).filter(Boolean),enabled:$('enabled').checked})});const x=await r.json();if(!r.ok)throw new Error(x.error);editing=false;$('saved').textContent='Saved for the next cycle';await refresh();}catch(e){$('saved').textContent=e.message;}});
$('refresh').addEventListener('click',refresh);refresh();setInterval(refresh,30000);
