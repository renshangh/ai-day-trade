(()=>{
'use strict';
const $=id=>document.getElementById(id),esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cash=x=>x==null?'—':'$'+Number(x).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const time=x=>x?new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZoneName:'short'}).format(new Date(x)):'Open';
const clock=t=>time(new Date(t*1000).toISOString()),empty=(n,t)=>'<tr><td colspan="'+n+'">'+esc(t)+'</td></tr>';
let current=null,generation=0;
function summary(s){
 const names={all:'All observations',no_flagged_gap:'No flagged gap',gap_or_partial_context:'Gap / partial context'};
 $('summary').innerHTML=Object.entries(s.summaries).flatMap(([model,pair])=>Object.entries(names).map(([group,label])=>{const a=pair.control[group],b=pair.variant[group];return '<tr><td>'+esc(model+' · '+label)+'</td><td>'+a.entries+' · '+a.wins+'/'+a.losses+'</td><td>'+cash(a.net)+'</td><td>'+b.entries+' · '+b.wins+'/'+b.losses+'</td><td>'+cash(b.net)+'</td><td>'+cash(b.net-a.net)+'</td><td>'+a.max_drawdown_r.toFixed(2)+' → '+b.max_drawdown_r.toFixed(2)+'</td><td>'+cash(a.max_closed_trade_drawdown_usd)+' → '+cash(b.max_closed_trade_drawdown_usd)+'</td><td>'+cash(a.cost)+' → '+cash(b.cost)+'</td></tr>';})).join('');
 const negative=Object.values(s.summaries).every(p=>p.variant.all.net<0);
 $('verdict').textContent=negative?'All filtered variants still lose money. The parent-only change improves these saved comparisons, but remains research only.':'Research comparison only; no live strategy change or validated return claim.';
}
function chart(){
 if(!current)return;const rows=current.rows,p=current.selected;if(!rows.length){$('chart').textContent='No observed bars for this trade.';return;}
 const W=Math.max(260,Math.floor($('chart').clientWidth)),H=370+Math.max(0,p.legs.length-1)*55,L=W<500?60:78,R=W<500?22:38,T=25+(p.legs.length+1)*45,B=55;
 const start=rows[0].t,end=rows.at(-1).t+1800;const values=rows.flatMap(r=>[r.low,r.high]).concat([p.entry,...p.legs.map(l=>l.price)]);
 const low=Math.min(...values),high=Math.max(...values),pad=(high-low||1)*.16,min=low-pad,max=high+pad;
 const x=t=>L+(t-start)/(end-start)*(W-L-R),y=v=>T+(max-v)/(max-min)*(H-T-B),ts=v=>Date.parse(v)/1000;
 let s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Trade '+p.id+' actual 15-minute bars, entry and all recorded exits">';
 for(let i=0;i<4;i++){const price=min+(max-min)*i/3;s+='<line class="grid" x1="'+L+'" x2="'+(W-R)+'" y1="'+y(price)+'" y2="'+y(price)+'"/><text class="axis" x="'+(L-7)+'" y="'+(y(price)+4)+'" text-anchor="end" font-size="12">'+Math.round(price).toLocaleString('en-US')+'</text>';}
 const events=[{t:ts(p.entry_time),price:p.entry,label:'ENTRY',color:'#60a5fa'},...p.legs.map(l=>({t:ts(l.time_utc),price:l.price,label:'EXIT '+Math.round(l.fraction*100)+'%',color:'#f87171'}))];
 for(const e of events){const t=Math.floor(e.t/900)*900;s+='<rect x="'+x(t)+'" y="'+T+'" width="'+Math.max(1,x(t+900)-x(t))+'" height="'+(H-T-B)+'" fill="'+e.color+'" opacity=".08"/>';}
 const width=Math.max(.6,Math.min(4,(x(start+900)-x(start))*.35));
 for(const r of rows){const mid=x(r.t+450),color=r.close>=r.open?'#46bd8a':'#e87575';s+='<g><title>'+esc(clock(r.t)+' → '+clock(r.t+900)+' · O/H/L/C '+[r.open,r.high,r.low,r.close].map(cash).join(' / ')+' · '+r.observed_minutes+'/15 actual minutes')+'</title><line x1="'+mid+'" x2="'+mid+'" y1="'+y(r.high)+'" y2="'+y(r.low)+'" stroke="'+color+'" stroke-width=".8"/><rect x="'+(mid-width/2)+'" y="'+Math.min(y(r.open),y(r.close))+'" width="'+width+'" height="'+Math.max(.7,Math.abs(y(r.open)-y(r.close)))+'" fill="'+color+'"/></g>';}
 events.forEach((e,i)=>{const pos=x(e.t),py=y(e.price);const tx=Math.max(L+50,Math.min(W-R-52,pos+(i===0?-35:35))),ty=20+i*45;
  s+='<line x1="'+tx+'" y1="'+(ty+34)+'" x2="'+pos+'" y2="'+py+'" stroke="'+e.color+'" stroke-width="1.4"/><text x="'+tx+'" y="'+ty+'" text-anchor="middle" fill="'+e.color+'" font-size="12"><tspan x="'+tx+'">'+esc(e.label)+'</tspan><tspan x="'+tx+'" dy="15">'+esc(time(new Date(e.t*1000).toISOString()))+'</tspan><tspan x="'+tx+'" dy="15">'+cash(e.price)+'</tspan></text>';
  s+=i===0?'<path d="M '+pos+' '+(py-5)+' l 5 5 -5 5 -5 -5 Z" fill="'+e.color+'"/>':'<path d="M '+(pos-5)+' '+(py-5)+' l 10 0 -5 9 Z" fill="'+e.color+'"/>';
 });
 const count=W<500?3:5;for(let i=0;i<count;i++){const t=start+(end-start)*i/(count-1),pos=x(t);s+='<text class="axis" x="'+pos+'" y="'+(H-30)+'" text-anchor="'+(i===0?'start':i===count-1?'end':'middle')+'" font-size="11">'+esc(clock(t))+'</text>';}
 s+='<text class="axis" x="'+(W/2)+'" y="'+(H-5)+'" text-anchor="middle" font-size="12">15-minute intervals · New York time</text></svg>';$('chart').innerHTML=s;
}
function draw(d){
 current=d;summary(d.study);$('source').textContent='Same window '+time(d.study.start)+' → '+time(d.study.end)+' (exclusive). Source SHA256 '+d.study.source_minute_sha256+'.';
 const counts={};d.changes.forEach(r=>counts[r.status]=(counts[r.status]||0)+1);
 $('sequence-note').textContent=d.trades.length+' trades · '+(counts.unchanged||0)+' matched entries/exits · '+(counts.added||0)+' added · '+(counts.removed||0)+' removed · '+(counts.changed||0)+' changed same-entry trades. Rejected C entries can change later A/B/C opportunities. Entry matching uses time and route; risk/exit formulas are unchanged.';
 $('trades').innerHTML=d.trades.map(p=>'<tr><td>#'+p.id+' · '+esc(p.entry_rule)+'</td><td>'+esc(time(p.entry_time))+'<small>'+cash(p.entry)+'</small></td><td>'+cash(p.initial_stop)+' / '+cash(p.t1)+'</td><td>'+esc(time(p.exit_time))+'<small>'+(p.legs.length?cash(p.legs.at(-1).price):'No exit recorded')+'</small></td><td>'+cash(p.net)+'</td><td>'+(p.gap_exposed||p.context_partial?'Flagged gap/context':'No flagged gap')+'</td><td><button class="review-button" data-id="'+p.id+'">Review</button></td></tr>').join('');
 $('trades').querySelectorAll('button').forEach(b=>b.onclick=()=>load(b.dataset.id));
 $('changes').innerHTML=d.changes.filter(c=>c.status!=='unchanged').map(c=>'<tr><td>'+esc(c.status)+'</td><td>'+(c.original?'#'+c.original.id+' · '+esc(c.original.entry_rule):'—')+'</td><td>'+(c.p1?'#'+c.p1.id+' · '+esc(c.p1.entry_rule):'—')+'</td><td>'+esc(time((c.original||c.p1).entry_time))+'</td><td>'+cash(c.original?.net)+'</td><td>'+cash(c.p1?.net)+'</td><td>'+cash(c.delta)+'</td></tr>').join('')||empty(7,'No sequence changes.');
 $('trade').innerHTML=d.trades.map(p=>'<option value="'+p.id+'">#'+p.id+' · '+esc(time(p.entry_time))+' · '+esc(p.entry_rule)+' · '+cash(p.net)+'</option>').join('');$('trade').value=d.selected.id;
 const p=d.selected;$('selected').textContent=d.model+' / '+d.sequence+' · #'+p.id+' · entry '+time(p.entry_time)+' '+cash(p.entry)+' · initial stop '+cash(p.initial_stop)+' · T1 '+cash(p.t1)+' · net '+cash(p.net)+(p.legs.length?' · all recorded exits marked below':' · still open; no exit marker exists');
 $('legs').innerHTML=p.legs.map(l=>'<tr><td>'+esc(l.reason)+' · '+Math.round(l.fraction*100)+'%</td><td>'+esc(time(l.time_utc))+'</td><td>'+cash(l.price)+'</td><td>'+cash(l.gross)+'</td><td>'+cash(l.cost)+'</td><td>'+cash(l.net)+'</td></tr>').join('')||empty(6,'Still open: no model exit has occurred.');
 const context=p.continuation;
 $('audit').innerHTML=context?'<p>Parent D '+cash(context.parent.price)+' · '+esc(clock(context.parent.time))+' · confirmed '+esc(clock(context.parent.known_at))+'</p><p>Rebound '+cash(context.rebound.price)+' · '+esc(clock(context.rebound.time))+'</p><p>Fresh HL '+cash(context.hl.price)+' · '+esc(clock(context.hl.time))+' · confirmed '+esc(clock(context.hl.known_at))+'</p><p>Initial stop uses the larger parent D minus 0.25 entry ATR. Nearer HL breaks are diagnostics, not new exit rules.</p>':'<p>This is an existing A/B route. Its original definition is unchanged.</p>';

 $('ledger').innerHTML=d.rows.map(r=>'<tr><td>'+esc(time(r.time))+' → '+esc(time(r.end))+'</td><td>'+[r.open,r.high,r.low,r.close].map(cash).join(' / ')+'<small>'+r.observed_minutes+'/15 observed minutes</small></td><td>'+cash(r.l1_price)+' / '+cash(r.l2_price)+'</td><td>'+(r.position_id===p.id?cash(r.stop)+' / '+Math.round((r.remaining||0)*100)+'%':'No selected position')+'</td><td>'+r.events.map(e=>esc(e.type)+' '+esc(time(e.time_utc))+(e.price?' '+cash(e.price):'')).join('<br>')+'</td></tr>').join('');
 const checks=d.parent_decisions;
 $('decision-note').textContent=checks.length+' C checks · '+checks.filter(a=>a.blocked).length+' blocked · '+checks.filter(a=>a.uncertainty.length).length+' uncertain and retained. Control mode records would-block evidence without rejecting.';
 $('parent-decisions').innerHTML=checks.map(a=>'<tr><td>'+esc(time(a.time_utc))+'<small>'+cash(a.entry_reference)+'</small></td><td>'+esc(a.blocked?'Blocked — no fill':a.filter_enabled?'Retained':'Control — audit only')+'<small>'+(a.trade_id?'Trade #'+a.trade_id:'No trade')+'</small></td><td>'+cash(a.context.parent.price)+' / '+cash(a.context.hl.price)+'</td><td>'+(a.failed_parent_chain?esc(time(a.failed_parent_chain.break_time))+'<small>L '+cash(a.failed_parent_chain.pullback.price)+' · LH '+cash(a.failed_parent_chain.lower_high.price)+'</small>':'None recorded')+'</td><td>'+esc(a.uncertainty.join('; ')||'Clear under locked protocol')+'</td><td>'+esc(a.trigger_flag_ignored?'Present; not used':'Absent')+'</td></tr>').join('')||empty(6,'No would-open C checks.');
 $('rules').innerHTML=Object.entries(d.study.policy).map(([k,v])=>'<p><b>'+esc(k)+'</b>: '+esc(v)+'</p>').join('');
 const q=new URLSearchParams({model:d.model,sequence:d.sequence});$('downloads').innerHTML=['TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv','PARENT_DECISIONS.csv','CHANGES.csv','result.json'].map(file=>'<a href="/api/btc-parent-filter/export?'+q+'&file='+file+'">'+file+'</a>').join('');chart();
}
async function load(id){const token=++generation,q=new URLSearchParams({model:$('model').value,sequence:$('sequence').value});if(id)q.set('trade_id',id);try{const r=await fetch('/api/btc-parent-filter?'+q,{cache:'no-store'}),d=await r.json();if(!r.ok)throw Error(d.error||'Comparison unavailable');if(token!==generation)return;if(!d.available)throw Error('Parent-only study is not complete yet.');draw(d);$('error').hidden=true;}catch(e){if(token!==generation)return;$('error').textContent=e.message;$('error').hidden=false;}}
let resize;new ResizeObserver(()=>{clearTimeout(resize);resize=setTimeout(chart,60);}).observe($('chart'));
$('model').onchange=()=>load();$('sequence').onchange=()=>load();$('trade').onchange=()=>load($('trade').value);load();
})();
