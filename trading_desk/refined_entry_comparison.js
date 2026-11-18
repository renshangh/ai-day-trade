(()=>{'use strict';
const $=id=>document.getElementById(id),esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const price=x=>x==null?'—':Number(x).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:6});
const money=x=>x==null?'—':Number(x).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const tm=x=>x?new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZoneName:'short'}).format(new Date(x)):'—';
let latest=null,serial=0;
function exportLink(symbol,model,sequence,file){return '<a href="/api/refined-entry/export?'+new URLSearchParams({symbol,model,sequence,file})+'">'+esc(file)+'</a>';}
function trade(p){if(!p)return 'No trade in this sequence / partition';return '#'+p.id+' · <b>'+esc(p.entry_rule)+'</b> @ $'+price(p.entry)+'<small>stop $'+price(p.initial_stop)+' · T1 $'+price(p.t1)+'</small><small>'+p.legs.map(l=>esc(tm(l.time_utc))+' · '+(l.fraction*100).toFixed(0)+'% @ $'+price(l.price)+' · '+esc(l.reason)).join('<br>')+'</small><small>realized $'+price(p.realized_leg_net)+' · '+esc(p.status)+(p.remaining?' · open mark $'+price(p.unrealized_net_reference):'')+'</small>';}
function render(d){latest=d;if(!d.available){$('refined-status').textContent='Saved comparison is not available yet. Opening this page never starts a replay.';return;}
const st=d.study;
$('refined-status').textContent='Historical only · '+tm(st.start)+' to '+tm(st.end)+' (end exclusive). All four original controls reproduced. Frozen 0.2 and both live workers unchanged.';
$('refined-summary').innerHTML=d.summaries.map(b=>'<tr><td>'+esc(b.symbol+' · '+b.model)+'</td><td>'+b.original.trades+' → '+b.refined.trades+'<small>closed '+b.original.closed+' → '+b.refined.closed+' · open '+b.original.open+' → '+b.refined.open+'</small></td><td>$'+price(b.original.realized_net)+' → $'+price(b.refined.realized_net)+'<small>Δ $'+price(b.delta_realized)+'</small></td><td>$'+money(b.original.normalized_10000_realized)+' → $'+money(b.refined.normalized_10000_realized)+'<small>Δ $'+money(b.delta_normalized_10000)+'</small></td><td>$'+money(b.original.normalized_10000_unrealized)+' → $'+money(b.refined.normalized_10000_unrealized)+'</td><td>'+Number(b.original_max_dd_r).toFixed(2)+' → '+Number(b.refined_max_dd_r).toFixed(2)+'</td></tr>').join('');
const book=d.summaries.find(b=>b.symbol===d.symbol&&b.model===d.model),c=book.all_group_change_counts;
$('refined-counts').textContent='All-data changes for selected book: '+Object.entries(c).map(([k,v])=>k.replaceAll('_',' ')+' '+v).join(' · ')+'. Selected source: '+d.coverage.missing_test_minutes+' absent minutes / '+d.coverage.expected_test_minutes+' expected. Data-exposure partitions do not fill gaps.';
$('refined-policy').textContent=st.protocol.B1+' '+st.protocol.B2+' '+st.protocol.shock+' '+st.protocol.lifecycle+' '+st.protocol.unchanged+' '+st.costs+'. '+st.sizing+'. Full sequential replay; same-entry matches are by time, not trade ID; later replacement buys remain visible. This is the same development month, not unseen validation.';
const rows=d.changes.filter(c=>!$('refined-changed-only').checked||c.status!=='unchanged');
$('refined-changes').innerHTML=rows.map(c=>'<tr><td>'+esc(tm(c.time))+'<small>'+esc(c.status.replaceAll('_',' '))+'</small>'+(c.group_note?'<small>'+esc(c.group_note)+'</small>':'')+'</td><td>'+trade(c.original)+'</td><td>'+trade(c.refined)+'</td><td>$'+price(c.delta_realized)+'<small>$10k entry Δ $'+money(c.delta_normalized_10000)+'</small></td><td><button class="refined-inspect" data-index="'+c.index+'">Inspect</button></td></tr>').join('')||'<tr><td colspan="5">No matching changes in this partition.</td></tr>';
$('refined-downloads').innerHTML=['SUMMARY.csv','CHANGES.csv','TRADES.csv','EXITS.csv','STUDY.json'].map(n=>exportLink('all','all','all',n)).join(' · ');
const selected=rows[0];if(selected)inspect(selected.index);else $('refined-detail').textContent='No selected trade.';
}
function inspect(index){if(!latest)return;const c=latest.changes.find(x=>x.index===index);if(!c)return;
const a=c.original,b=c.refined,details=p=>p?'<p><b>D / L2:</b> $'+price(p.references?.l1?.price)+' / $'+price(p.references?.l2?.price)+'<small>D '+esc(tm(p.references?.l1?.time))+'; known '+esc(tm(p.references?.l1?.known_at))+'</small></p>'+trade(p):'<p>No trade on this side.</p>';
$('refined-detail').innerHTML='<h3>'+esc(tm(c.time)+' · '+c.status)+'</h3><div class="refined-detail-grid"><div><h4>Original</h4>'+details(a)+'</div><div><h4>Refined</h4>'+details(b)+'</div></div><details><summary>Refined state at the original entry minute</summary><pre>'+esc(JSON.stringify(c.original_entry_review,null,2))+'</pre></details><p>'+['original','refined'].map(seq=>esc(seq)+': '+['TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv','result.json'].map(n=>exportLink(latest.symbol,latest.model,seq,n)).join(' · ')).join('<br>')+'</p>';
}
async function load(){const version=++serial,[symbol,model]=$('refined-book').value.split('|'),group=$('refined-group').value;
try{const r=await fetch('/api/refined-entry?'+new URLSearchParams({symbol,model,group}),{cache:'no-store'}),d=await r.json();if(!r.ok)throw Error(d.error||'Saved comparison unavailable');if(version===serial){render(d);$('refined-error').hidden=true;}}catch(e){if(version===serial){$('refined-error').textContent=e.message;$('refined-error').hidden=false;}}}
$('refined-book').onchange=load;$('refined-group').onchange=load;$('refined-changed-only').onchange=()=>{if(latest)render(latest);};
$('refined-changes').onclick=e=>{const b=e.target.closest('.refined-inspect');if(b)inspect(Number(b.dataset.index));};load();
})();
