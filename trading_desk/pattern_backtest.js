'use strict';
const $=id=>document.getElementById(id),esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cash=x=>typeof x==='number'&&Number.isFinite(x)?'$'+x.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'—';
const price=x=>typeof x==='number'&&Number.isFinite(x)?'$'+x.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:4}):'—';
const when=x=>x?new Date(x).toLocaleString('en-US',{timeZone:'America/New_York',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZoneName:'short'}):'—';
const row=xs=>'<tr>'+xs.map(x=>'<td>'+x+'</td>').join('')+'</tr>',ep=t=>when(new Date(t*1000).toISOString());
let request=0;
function link(symbol,file){return `<a href="/api/pattern-backtest/export?symbol=${encodeURIComponent(symbol)}&file=${encodeURIComponent(file)}">${esc(file)}</a>`;}
function draw(d){
 if(!d.available){$('period').textContent='Saved historical study is not ready.';return;}
 $('error').textContent='';$('period').textContent=`${when(d.study.start)} → ${when(d.study.end)} (exclusive) · 30 calendar days · warmup from ${when(d.study.warmup_start)}`;
 $('policy').textContent=JSON.stringify(d.study.policy,null,2);
 $('summary').innerHTML=d.summaries.map(x=>{const s=x.summary,c=x.coverage;
  return row([`${esc(x.symbol)}<small>${esc(c.price_basis)}</small>`,s?`${s.trades} · ${s.closed} / ${s.open} · ${s.wins}/${s.losses}`:'Unavailable',s?cash(s.realized_net):'—',s?cash(s.unrealized_net):'—',s?`${cash(s.normalized_10000_realized)} / ${cash(s.normalized_10000_unrealized)}`:'—',c.test_expected?`${c.test_observed.toLocaleString()} / ${c.test_expected.toLocaleString()}<small>${c.test_missing} missing minutes</small>`:esc(c.reason),s?s.actual_missing_exposed:'—',`<button class="symbol-review" data-symbol="${esc(x.symbol)}">Review</button>`]);}).join('');
 $('combined-downloads').innerHTML=['SUMMARY.csv','TRADES.csv','EXITS.csv','STUDY.json','LIBRARY.json'].map(f=>link('all',f)).join(' · ');
 $('symbol').innerHTML=d.study.symbols.map(s=>`<option${s===d.symbol?' selected':''}>${esc(s)}</option>`).join('');
 const summary=d.summaries.find(x=>x.symbol===d.symbol)?.summary;
 const coverage=d.summaries.find(x=>x.symbol===d.symbol)?.coverage;
 $('counts').textContent=d.unavailable_reason||`${d.symbol}: ${d.trades.length} trades · ${summary?.pattern_checks??0} pattern checks · ${summary?.pattern_accepted??0} accepted. ${JSON.stringify(summary?.rejected_reasons||{})}. Source signal diagnostics: ${JSON.stringify(d.signal_counts)}. Price basis: ${coverage?.price_basis}. ${coverage?.adjustment_note||''}`;
 $('trades').innerHTML=d.trades.map(p=>row([`#${p.id} · ${esc(p.entry_rule)}<small>${esc(p.pattern_match?.nearest_positive?.example_id)}</small>`,`${when(p.entry_time)}<small>${price(p.entry)}</small>`,`${price(p.initial_stop)}<small>${when(p.entry_time)}</small>`,price(p.t1),p.exit_time?when(p.exit_time):`OPEN · ${when(p.mark_time)}<small>mark ${price(p.mark_price)}</small>`,`${cash(p.realized_leg_net)} / ${cash(p.unrealized_net_reference)}`,`${cash(p.normalized_10000_realized_net)} / ${cash(p.normalized_10000_unrealized_net)}`,`<button class="trade-review" data-id="${p.id}">Review</button>`])).join('')||row(['No trades qualified under the unchanged draft rules','','','','','','','']);
 $('downloads').innerHTML=d.unavailable_reason?'':['TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv','PATTERN_DECISIONS.csv','result.json'].map(f=>link(d.symbol,f)).join(' · ');
 const p=d.selected,s=d.entry_evidence;
 $('selected').textContent=p?`${d.symbol} #${p.id}: ${p.status} · entry ${when(p.entry_time)} ${price(p.entry)} · current/final hard stop ${price(p.stop)} · ${p.actual_missing_minutes_while_held} missing required minutes while held`:'No selected trade.';
 $('entry').innerHTML=p?`<p>D / L1: ${price(p.references.l1.price)} at ${when(p.references.l1.time)}; confirmed ${when(p.references.l1.known_at)}. B1 requires no L2.</p><p>Previous full candle: ${when(s.previous_bar_time)}; trigger ${price(p.references.trigger)}. Entry reference ${when(p.entry_time)}; assumed available after ${when(s.interval_end)}. Initial stop ${price(p.initial_stop)}; planned 25% target ${price(p.t1)}.</p>`:'';
 $('legs').innerHTML=p?p.legs.map(l=>row([when(l.time_utc),`${esc(l.reason)} · ${(l.fraction*100).toFixed(0)}%`,price(l.price),`${cash(l.gross)} / ${cash(l.cost)} / ${cash(l.net)}`,cash(l.normalized_10000_net)])).join('')||row(['No exits yet','','','','']):'';
 $('protection').textContent=p?JSON.stringify({initial_stop:{effective_at:p.entry_time,price:p.initial_stop},hard_stop_raises:p.stop_history,structure:p.structure_history,failed_rebounds:p.failed_rebound_history},null,2):'';
 $('ledger').innerHTML=d.rows.map(b=>row([`${ep(b.t)} → ${when(b.end)}`,`${price(b.open)} / ${price(b.high)} / ${price(b.low)} / ${price(b.close)}`,`${b.observed_minutes}/15`,p&&b.position_id===p.id?`${price(b.stop)} / ${b.remaining*100}% remaining`:'No selected position',b.events.map(e=>`${esc(e.type)} ${when(e.time_utc)} ${price(e.price)}`).join('<br>')])).join('');
 $('decisions').innerHTML=d.decisions.map(x=>row([when(x.time_utc),`${esc(x.route)} / ${price(x.reference)}`,x.match?`${esc(x.match.nearest_positive.example_id)} / ${esc(x.match.nearest_negative.example_id)}`:'Not evaluated',x.match?x.match.margin.toFixed(4):'—',x.accepted?`Trade #${x.trade_id}`:esc(x.reason)])).join('')||row(['No would-open pattern decisions; see source-signal diagnostics above','','','','']);
 for(const b of document.querySelectorAll('.symbol-review'))b.addEventListener('click',()=>load(b.dataset.symbol));
 for(const b of document.querySelectorAll('.trade-review'))b.addEventListener('click',()=>load(d.symbol,b.dataset.id));
}
async function load(symbol,trade){const id=++request;try{const qs=new URLSearchParams();if(symbol)qs.set('symbol',symbol);if(trade)qs.set('trade_id',trade);const r=await fetch('/api/pattern-backtest?'+qs);const d=await r.json();if(id!==request)return;if(!r.ok)throw new Error(d.error||'Saved study unavailable');draw(d);}catch(e){if(id===request)$('error').textContent=e.message;}}
$('symbol').addEventListener('change',()=>load($('symbol').value));load();
