/* Saved research only. Never starts workers or calls any order endpoint. */
(()=>{
'use strict';
const $=id=>document.getElementById(id),esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=x=>Number.isFinite(x)?x.toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}):'—';
const price=x=>Number.isFinite(x)?'$'+x.toLocaleString('en-US',{maximumFractionDigits:6}):'—';
const stamp=x=>x?new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZoneName:'short'}).format(new Date(x)):'—';
let current=null;
const exportURL=(file,symbol='all',model='E1',sequence='steeper')=>'/api/followthrough/export?'+new URLSearchParams({file,symbol,model,sequence});
const links=(files,symbol='all',model='E1',sequence='steeper')=>files.map(f=>`<a href="${exportURL(f,symbol,model,sequence)}">${esc(f)}</a>`).join(' · ');
function legs(p){return (p||[]).map(l=>`${stamp(l.time_utc)} · ${price(l.price)} · ${(l.fraction*100).toFixed(0)}% · ${money(l.net)} · ${esc(l.reason)}`).join('<br>')||'No realized leg';}
function inspect(id){const p=current.trades.find(x=>x.trade_id===id);if(!p)return;
 $('follow-detail').innerHTML=`<h3>${esc(current.symbol)} ${esc(current.model)} #${id} · ${esc(current.policy)}</h3><p>Entry ${stamp(p.entry_time)} at ${price(p.entry)} · original stop ${price(p.initial_stop)} · 25% target ${price(p.target_25)}</p><p><b>Original:</b> ${legs(p.original_legs)}</p><p><b>Research:</b> ${legs(p.legs)}</p><p>${p.signal?'Confirmed '+stamp(p.signal.confirmed_at)+' · reference '+price(p.signal.exit_reference)+' · earliest modeled boundary; actual receipt/fill unverified.':'No strictly earlier eligible failure. Original exit retained.'}</p><details open><summary>Known evidence and checks</summary><pre>${esc(JSON.stringify({signal:p.signal,notes:p.notes,references:p.references},null,2))}</pre></details>`;
}
function render(d){current=d;
 if(!d.available){$('follow-status').textContent='Saved research unavailable; no substituted observations.';return;}
 $('follow-status').textContent=`Historical only · ${stamp(d.study.start)} → ${stamp(d.study.end)} (exclusive) · ${d.policy} · ${d.group} · no live changes`;
 $('follow-cases').innerHTML=d.cases.map(c=>{const p=c.original;const out=k=>{const r=c.exits[k];const l=r.legs.at(-1);return `${stamp(r.exit_time)} · ${price(l?.price)}<br>${money(r.net)} / 1 ${esc(c.asset.split('/')[0])}<br>${r.triggered?'Earlier research reference':'Original exit retained'}`;};return `<tr><td>${esc(c.asset)} #${c.trade_id}<br>${stamp(p.entry_time)} · ${price(p.entry)}<br>Trigger ${price(p.references.trigger)}</td><td>Net drop ${c.shock.net_drop_atr.toFixed(2)} ATR<br>Old low excursion ${c.shock.excursion_atr.toFixed(2)} ATR<br>Not a ≥3 ATR net shock; no automatic A buy</td><td>${stamp(p.exit_time)} · ${price(p.legs.at(-1)?.price)}<br>${money(p.legs.reduce((s,l)=>s+l.net,0))} / 1 ${esc(c.asset.split('/')[0])}</td><td>${out('F1')}</td><td>${out('F2')}</td></tr>`;}).join('');
 $('follow-summary').innerHTML=d.summaries.map(b=>{const s=b.exit;return `<tr><td>${esc(b.symbol)} ${esc(b.model)} · ${s.trades}</td><td>${money(s.normalized_10000_original)} → ${money(s.normalized_10000_overlay)}<br>Δ ${money(s.normalized_10000_overlay-s.normalized_10000_original)}</td><td>${s.earlier}</td><td>${s.loser_improved} / ${s.loser_worsened}</td><td>${s.winners_cut} / ${s.winners_flipped_to_loss}</td></tr>`;}).join('');
 const rows=d.trades.filter(p=>!$('follow-changed').checked||p.triggered);
 $('follow-counts').textContent=`${rows.length} displayed / ${d.trades.length} original trades in selected partition. Winner harm and unchanged controls are retained for review.`;
 $('follow-trades').innerHTML=rows.map(p=>`<tr><td>#${p.trade_id} ${esc(p.route)}<br>${stamp(p.entry_time)} · ${price(p.entry)}</td><td>${stamp(p.original_exit)}<br>${money(p.original_net)}</td><td>${stamp(p.exit_time)}<br>${money(p.net)}</td><td>${money(p.delta)}<br>${p.winner_flipped_to_loss?'WINNER → LOSS':p.winner_cut?'Winner cut':p.loser_improved?'Loss reduced':p.loser_worsened?'Loss worsened':p.triggered?'Earlier exit':'Unchanged'}</td><td><button class="follow-inspect" data-id="${p.trade_id}">Inspect #${p.trade_id}</button></td></tr>`).join('')||'<tr><td colspan="5">No matching trades; no prices invented.</td></tr>';
 $('follow-detail').textContent='Select Inspect for signal confirmation, execution reference, original legs and research legs.';
 $('shock-summary').innerHTML=d.summaries.map(b=>{const a=b.shock_original,n=b.shock_steeper;return `<tr><td>${esc(b.symbol)} ${esc(b.model)}</td><td>${a.trades} → ${n.trades}</td><td>${money(a.normalized_10000_realized)} → ${money(n.normalized_10000_realized)}<br>Δ ${money(n.normalized_10000_realized-a.normalized_10000_realized)}</td><td>${b.shock_dd_original.toFixed(2)} → ${b.shock_dd_steeper.toFixed(2)}</td><td>${b.old_episodes} → ${b.new_episodes}<br>All study episodes</td></tr>`;}).join('');
 const trade=p=>p?`#${p.id} ${esc(p.entry_rule)} · ${price(p.entry)}<br>Stop ${price(p.initial_stop)} · T1 ${price(p.t1)}<br>${legs(p.legs)}`:'No trade';
 $('shock-changes').innerHTML=d.shock_changes.map(c=>`<tr><td>${stamp(c.time)}<br>${esc(c.status)}</td><td>${trade(c.original)}</td><td>${trade(c.steeper)}</td><td>${money(c.delta_normalized_10000)}</td></tr>`).join('')||'<tr><td colspan="4">No matching shock trades in this partition.</td></tr>';
 $('follow-protocol').textContent=JSON.stringify({exits:d.study.exit_protocol,shock:d.study.shock_protocol,controls:d.study.controls_reproduced});
 $('follow-downloads').innerHTML=links(['STUDY.json','EXIT_SUMMARY.csv','EXIT_TRADES.csv','SHOCK_CHANGES.csv','BTC_USD_0445.json','SOL_USD_0445.json'])+'<br>Selected book: '+links(['EXITS.json','SHOCK_CHANGES.json'],d.symbol,d.model)+'<br>Steeper sequence: '+links(['TRADES.csv','EXITS.csv','PROTECTION.csv','SIGNALS.csv','LEDGER.csv','result.json'],d.symbol,d.model);
}
let request=0;
async function load(){const n=++request;try{const [symbol,model]=$('follow-book').value.split('|'),q=new URLSearchParams({symbol,model,policy:$('follow-policy').value,group:$('follow-group').value});const r=await fetch('/api/followthrough?'+q,{cache:'no-store'});if(!r.ok)throw Error('Saved research could not be read');const d=await r.json();if(n!==request)return;$('follow-error').hidden=true;render(d);}catch(e){if(n!==request)return;$('follow-error').hidden=false;$('follow-error').textContent=e.message;}}
$('follow-book').onchange=load;$('follow-policy').onchange=load;$('follow-group').onchange=load;
$('follow-changed').onchange=()=>current&&render(current);
$('follow-trades').onclick=e=>{const button=e.target.closest('.follow-inspect');if(button)inspect(Number(button.dataset.id));};
load();
})();
