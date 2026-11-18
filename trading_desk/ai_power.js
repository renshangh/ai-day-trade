'use strict';
// Earnings evidence is dated; market refreshes never silently revise the screen.
(function(root) {
 const theme='AI Power / Neocloud';
 const universe=['CORZ','GLXY','HUT','RIOT'];
 const benchmarks=['SPY','QQQ'];
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const money=x=>Number.isFinite(x)?'$'+x.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'Unavailable';
 const pct=x=>Number.isFinite(x)?`${x>=0?'+':''}${x.toFixed(2)}%`:'Unavailable';
 const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const mean=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
 const url=x=>{try {const u=new URL(x);return ['https:','http:'].includes(u.protocol)?u.href:null;}catch{return null;}};
 const source=(label,href)=>`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;
 const research=[
  {symbol:'CORZ',name:'Core Scientific',role:'AI colocation landlord + remaining mining',date:'2026-11-05',eps:0.47,fact:'Q3 2026 consolidated net income $1,178.1M; diluted EPS +$0.47. Billing capacity reached 485 MW.',view:'A $1,034.4M noncash warrant/CVR gain boosted net income. Operating cash flow and capital spending must be assessed separately.',href:'https://investors.corescientific.com/news-events/press-releases/detail/146/core-scientific-announces-third-quarter-2026-results'},
  {symbol:'GLXY',name:'Galaxy Digital',role:'AI data-center landlord + digital assets and investments',date:'2026-10-27',eps:0.66,fact:'Q3 2026 consolidated net income $322.8M; diluted EPS +$0.66. Helios delivered 133 MW of revenue-generating critical IT capacity.',view:'Treasury and investment results materially supported earnings. Data-center adjusted EBITDA is not free cash flow.',href:'https://galaxydigital.gcs-web.com/news-releases/news-release-details/galaxy-announces-third-quarter-2026-financial-results'},
  {symbol:'HUT',name:'Hut 8',role:'Power / AI infrastructure developer + compute',date:'2026-11-04',eps:0.98,fact:'Q3 2026 consolidated net income $189.5M; $131.1M attributable to Hut 8 shareholders; diluted EPS +$0.98.',view:'Digital-asset gains of $413.8M supported earnings. Restricted project funds are not free corporate cash; future lease capacity is not current rent.',href:'https://www.hut8.com/news-insights/press-releases/hut-8-reports-third-quarter-2026-results'},
  {symbol:'RIOT',name:'Riot Platforms',role:'Powered-land / data-center landlord + mining and engineering',date:'2026-11-04',eps:0.01,fact:'Q3 2026 net income $4.0M; diluted EPS +$0.01. Data-center revenue $18.4M includes tenant fit-out reimbursements.',view:'The 910 IT MW Corsicana lease represents future delivery, not current revenue. Positive EPS does not establish positive operating or free cash flow.',href:'https://www.sec.gov/Archives/edgar/data/1167419/000110465926122417/riot-20260930x10q.htm'}
 ];
 // USD millions; balance-sheet values are September 30, 2026, not live quotes.
 // Restricted proceeds and undrawn facilities must never inflate available cash.
 const debtProfiles=[
  {symbol:'CORZ',operatingCash9m:296.243,cash:803.941,restricted:837.603,debt:4302.175,operating:72.350,interest:54.066,incurredInterest:71.840,floating:0,
   cashLabel:'Cash excluding restricted balances',coverageLabel:'GAAP operating income / gross interest expense',
   maturity:'No scheduled principal through 2028. 2029: $460M converts plus $189.75M secured-note amortization, assuming the first installment date in the filing.',
   note:'$4,385M principal versus $4,302.2M carrying debt. Funded notes have fixed coupons of 0%, 3% and 7.75%; the floating revolver was undrawn. Coverage including capitalized interest is only 1.01×. Construction spending and delivery obligations still require funding.',
   rateNote:'No drawn floating debt at September 30. Future draws and refinancing can raise costs; fixed coupons do not reset when market rates rise.',
   href:'https://www.sec.gov/Archives/edgar/data/1839341/000183934126000030/core-20260930.htm'},
  {symbol:'GLXY',operatingCash9m:null,cash:1324.759,restricted:null,debt:6958.910,operating:null,interest:null,floating:null,
   cashLabel:'Reported cash; availability not fully reconciled',coverageLabel:'Unavailable — full financing-cost scope not reconciled',
   maturity:'$651.8M current cash loans and notes (carrying value, not a contractual maturity schedule). Full maturity and rate split unavailable in the release.',
   note:'Cash debt excludes another $2,343.6M of borrowed digital assets and $2,612.2M collateral payable. Stablecoins and Treasury bills are separate assets, not added to cash here. Investment gains and financing costs within transaction expenses prevent a comparable operating interest-coverage calculation from this release.',
   rateNote:'Floating balances and hedges not reconciled. No zero-exposure assumption. Data-center construction creates further funding needs.',
   href:'https://investor.galaxy.com/news-releases/news-release-details/galaxy-announces-third-quarter-2026-financial-results'},
  {symbol:'HUT',operatingCash9m:-5.031,cash:156.865,restricted:6394.491,debt:7628.225,operating:318.207,operatingGain:413.789,interest:105.512,floating:null,
   cashLabel:'Consolidated cash excluding restricted funds',coverageLabel:'Operating income excluding digital-asset gain / gross interest',
   maturity:'September schedule: $26.41M remaining 2026 (repaid in October), $200M in 2027; project amortization begins in 2028. Major project notes mature in 2042.',
   note:'$6,394.5M restricted cash and short-term investments cannot be treated as free corporate cash. $7,726.4M debt principal is classified non-recourse; project collateral can still be lost. Excluding the $413.8M digital-asset gain turns operating income negative; unadjusted coverage is 3.02×. Consolidated cash includes subsidiaries with minority owners.',
   rateNote:'Major $7.5B project notes have fixed coupons near 6.1%; $200M FalconX loan is fixed at 7%. The variable TZRC note had a rate cap and was repaid in October; a simple September shock is unavailable without cap headroom.',
   href:'https://cdn.kscope.io/62547e628bd95ebf173fc45acc0efe8a.html'},
  {symbol:'RIOT',operatingCash9m:-487.119,cash:669.052,restricted:79.170,debt:656.645,operating:1.224,interest:2.748,floating:75.120,
   cashLabel:'Cash excluding restricted balances',coverageLabel:'GAAP operating income / gross interest expense',
   maturity:'$67.5M current debt carrying value. The $573M facility matures December 31, 2026; $20.85M was drawn. Most other principal is 0.75% convertible notes due 2030.',
   note:'$674.5M debt principal versus $656.6M carrying debt. Operating income does not cover reported gross interest and includes asset valuation effects. The planned Corsicana build requires substantial additional financing; its future borrowing is excluded from current debt.',
   rateNote:'$75.12M drawn floating principal: $34.272M + $20M revolvers and $20.848M project loan. Scenario is gross, before cash-interest offsets, hedges, fees or future balance changes; it is not a forecast.',
   href:'https://www.sec.gov/Archives/edgar/data/1167419/000110465926122417/riot-20260930x10q.htm'}
 ];
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 function debtMetrics(p) {
  const operating=finite(p.operating)&&(!('operatingGain' in p)||finite(p.operatingGain))?p.operating-('operatingGain' in p?p.operatingGain:0):null;
  return {cashDebt:finite(p.cash)&&p.cash>=0&&finite(p.debt)&&p.debt>0?p.cash/p.debt:null,
   coverage:finite(operating)&&finite(p.interest)&&p.interest>0?operating/p.interest:null};
 }
 function rateStress(principal,bps) {
  return finite(principal)&&principal>=0&&finite(bps)&&bps>=0?principal*bps/10000:null;
 }
 const million=x=>finite(x)?`$${x.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1})}M`:'Unavailable';
 const ratio=x=>finite(x)?`${x.toFixed(2)}×`:'Unavailable';
 function renderDebt(bps) {
  return `<section id="power-debt"><h3>Debt & rate resilience</h3><p>How well could these companies withstand funding pressure? September 30, 2026 balances and Q3 results · reviewed November 6. These diagnostics are not a survival percentage or bankruptcy probability.</p><div class="power-table"><table><caption>USD millions · cash excludes separately reported restricted funds</caption><thead><tr><th>Company</th><th>Cash</th><th>Restricted funds</th><th>Debt carrying value</th><th>Cash / debt</th><th>9-month operating cash flow</th><th>Operating interest coverage</th></tr></thead><tbody>${debtProfiles.map(p=>{const m=debtMetrics(p);return `<tr><th>${p.symbol}</th><td>${million(p.cash)}<small>${esc(p.cashLabel)}</small></td><td>${million(p.restricted)}</td><td>${million(p.debt)}</td><td>${ratio(m.cashDebt)}</td><td>${million(p.operatingCash9m)}</td><td>${ratio(m.coverage)}<small>${esc(p.coverageLabel)}</small></td></tr>`;}).join('')}</tbody></table></div><p class="power-note">Cash / debt measures a cash cushion, not ability to repay everything today. Coverage below 1× means the stated operating income is less than gross interest expense; a negative value means operating losses. HUT excludes a disclosed asset gain as a sensitivity, not standardized adjusted earnings. GLXY debt omits separately shown digital-asset financing, so ratios are not directly comparable. Operating cash flow is January–September, before capex, and may include Bitcoin sales or working-capital timing; it is not recurring free cash flow. No cash runway is estimated without a defensible ongoing burn rate. These measures do not include all principal payments, maintenance capex, leases or project completion costs.</p><label>Higher-rate scenario<select data-power-rate>${[100,200,300].map(n=>`<option value="${n}" ${n===bps?'selected':''}>+${n/100} percentage point${n===100?'':'s'}</option>`).join('')}</select></label><p>Additional annual gross interest on verified drawn floating debt, holding balances constant. Fixed-rate debt is exposed when refinanced; undrawn facilities are not cash.</p><div class="power-grid">${debtProfiles.map(p=>`<article class="power-panel"><h4>${p.symbol} · ${million(rateStress(p.floating,bps))} / year</h4><p>${esc(p.rateNote)}</p><p><strong>Repayments:</strong> ${esc(p.maturity)}</p><p>${esc(p.note)}</p>${source('Balance sheet, debt notes & results',p.href)}</article>`).join('')}</div><p class="power-note">Refinancing illustration: each $1B refinanced at this higher rate would add ${million(rateStress(1000,bps))} annually. This is hypothetical, not a company forecast. No automatic safest-company ranking: cash restrictions, asset-price exposure, collateral calls, covenants and committed construction can matter more than a single ratio. Refresh market updates prices only; filing figures require a sourced review.</p></section>`;
 }
 const plans=[];
 function metrics(payload,cutoff,expectedDates=[]) {
  if(!payload || payload.error || payload.stale) return {error:payload?.stale?'Stale source':payload?.error||'No data'};
  const bars=(payload.bars||[]).filter(b=>typeof b.t==='string'&&b.t<cutoff).sort((a,b)=>a.t.localeCompare(b.t));
  if(!bars.length)return {error:'No completed sessions'};
  // Invalid or duplicate observations invalidate the reading; no forward-fill.
  if(new Set(bars.map(b=>b.t)).size!==bars.length || bars.some(b=>!['o','h','l','c','v'].every(k=>typeof b[k]==='number'&&Number.isFinite(b[k]))||b.c<=0||b.l<=0||b.h<b.l||b.v<0))return {error:'Invalid market observations'};
  const tail=bars.at(-1), closes=bars.map(b=>b.c), avg=n=>closes.length>=n?mean(closes.slice(-n)):null;
  const ret=n=>closes.length>n?(tail.c/closes.at(-1-n)-1)*100:null;
  const dates=new Set(bars.map(b=>b.t));
  const missing=expectedDates.slice(-50).filter(d=>!dates.has(d));
  const prev=bars.slice(-10,-5),recent=bars.slice(-5),v20=bars.length>=21?mean(bars.slice(-21,-1).map(b=>b.v)):null;
  return {date:tail.t,close:tail.c,day:ret(1),r5:ret(5),r21:ret(21),sma20:avg(20),sma50:avg(50),sma200:avg(200),low10:bars.length>=10?Math.min(...bars.slice(-10).map(b=>b.l)):null,high20:bars.length>=20?Math.max(...bars.slice(-20).map(b=>b.h)):null,volRatio:v20>0?tail.v/v20:null,risingLows:bars.length>=10?Math.min(...recent.map(b=>b.l))>Math.min(...prev.map(b=>b.l)):null,missing:missing.length,feed:payload.feed||'Unavailable',dates:bars.map(b=>b.t)};
 }
 function assess(payloads,cutoff) {
  const spy=metrics(payloads.SPY,cutoff),qqq=metrics(payloads.QQQ,cutoff);
  const rows=Object.fromEntries([...universe,...benchmarks].map(s=>[s,metrics(payloads[s],cutoff,spy.dates||[])]));
  const valid=universe.filter(s=>!rows[s].error&&rows[s].sma50!==null&&rows[s].r21!==null&&!rows[s].missing&&rows[s].date===spy.date);
  const complete=valid.length===universe.length&&!spy.error&&!qqq.error&&spy.r21!==null&&qqq.r21!==null&&spy.date===qqq.date;
  const average=key=>valid.length?mean(valid.map(s=>rows[s][key])):null;
  const above=valid.filter(s=>rows[s].close>rows[s].sma50).length;
  const gates=[
   {name:'At least 60% of the four-stock watchlist above the 50-day average',pass:complete?above/universe.length>=0.6:null},
   {name:'Five-session equal-weight return beats SPY and QQQ',pass:complete?average('r5')>Math.max(spy.r5,qqq.r5):null},
   {name:'21-session equal-weight return beats SPY and QQQ',pass:complete?average('r21')>Math.max(spy.r21,qqq.r21):null},
   {name:'At least 60% have rising five-session lows',pass:complete?valid.filter(s=>rows[s].risingLows).length/universe.length>=0.6:null}
  ];
  let sustained=false;
  if(complete){
   const prior=assessPrevious(payloads,spy.date);
   sustained=prior;
  }
  const age=spy.date?(Date.parse(cutoff)-Date.parse(spy.date))/86400000:Infinity;
  const fresh=age>=0&&age<=4;
  const confirmed=complete&&fresh&&sustained&&gates.every(g=>g.pass===true);
  return {rows,cutoff,date:spy.date,valid:valid.length,above,gates,sustained,complete,fresh,confirmed,status:!complete||!fresh?'Insufficient fresh evidence':confirmed?'Broad recovery conditions met':'Broad recovery unconfirmed',r5:average('r5'),r21:average('r21')};
 }
 function assessPrevious(payloads,cutoff){
  const spy=metrics(payloads.SPY,cutoff),qqq=metrics(payloads.QQQ,cutoff);
  const rows=universe.map(s=>metrics(payloads[s],cutoff,spy.dates||[]));
  const complete=!spy.error&&!qqq.error&&spy.r21!==null&&qqq.r21!==null&&spy.date===qqq.date&&rows.every(r=>!r.error&&!r.missing&&r.sma50!==null&&r.r21!==null&&r.date===spy.date);
  return complete&&rows.filter(r=>r.close>r.sma50).length/universe.length>=0.6&&mean(rows.map(r=>r.r5))>Math.max(spy.r5,qqq.r5)&&mean(rows.map(r=>r.r21))>Math.max(spy.r21,qqq.r21)&&rows.filter(r=>r.risingLows).length/universe.length>=0.6;
 }
 function sizeTrade({entry,stop,target,risk,budget}) {
  const values=[entry,stop,target,risk,budget];
  if(!values.every(x=>typeof x==='number'&&Number.isFinite(x)&&x>0)||stop>=entry||target<=entry)return {error:'Enter positive prices with stop < entry < target, plus risk and cash limits.'};
  const rr=(target-entry)/(entry-stop);
  if(rr<2)return {error:`Skip: ${rr.toFixed(2)}R is below the 2R minimum.`,rr};
  const shares=Math.floor(Math.min(risk/(entry-stop),budget/entry));
  if(shares<1)return {error:'Cash or risk limit cannot fund one share.'};
  return {shares,notional:shares*entry,loss:shares*(entry-stop),gain:shares*(target-entry),rr};
 }
 function validateEntry(e) {
  return !e||e.theme!==theme||!/^\d{4}-\d{2}-\d{2}$/.test(e.date||'')||!e.title?.trim()||!e.detail?.trim()||!url(e.source)?'Date, evidence, interpretation and a valid source URL are required.':null;
 }
 function renderSignals(a) {
  return `<div class="power-verdict"><span class="power-kicker">COMPLETED-SESSION PRICE COMPARISON</span><h3>${esc(a.status)}</h3><p>Through ${esc(a.date||'unavailable')} · ${a.valid}/${universe.length} usable stocks · ${a.above}/${universe.length} above the 50-day average.</p><p>Equal-weight return: 5 sessions ${pct(a.r5)} / 21 sessions ${pct(a.r21)}.</p></div><ul class="power-gates">${a.gates.map(g=>`<li><b>${g.pass===null?'Unavailable':g.pass?'Met':'Not met'}</b> ${esc(g.name)}</li>`).join('')}<li>Conditions also held on the preceding completed session: ${a.sustained?'Yes':'Not confirmed'}.</li></ul><p class="power-note">Discretionary, unbacktested research criteria. Today’s New York candle is excluded. Missing, stale or misaligned observations cannot confirm recovery. Price strength does not establish earnings quality.</p><div class="power-table"><table><thead><tr><th>Stock / benchmark</th><th>Close</th><th>5 sessions</th><th>21 sessions</th><th>20-day</th><th>50-day</th><th>200-day</th></tr></thead><tbody>${[...universe,...benchmarks].map(s=>{const r=a.rows[s];return `<tr><th><a data-power-symbol="${s}" href="/board?view=ai-power&amp;symbol=${s}#detail-card">${s}</a><small>${esc(r.error||r.date)}${r.missing?' · missing sessions':''}</small></th><td>${money(r.close)}</td><td>${pct(r.r5)}</td><td>${pct(r.r21)}</td><td>${money(r.sma20)}</td><td>${money(r.sma50)}</td><td>${money(r.sma200)}</td></tr>`;}).join('')}</tbody></table></div>`;
 }
 function mount(container,{getObservations=()=>[],onSave=null,onSelect=null}={}) {
  let assessment=null,loading=false,error='',rateBps=200;
  function refresh(){
   const entries=getObservations().filter(e=>e.theme===theme).sort((a,b)=>b.date.localeCompare(a.date));
   container.innerHTML=`<div class="power-desk"><div class="power-toolbar"><p>AI infrastructure · earnings, cash quality and delivery</p><button type="button" data-power-refresh ${loading?'disabled':''}>${loading?'Refreshing…':'Refresh market'}</button></div><p class="power-note">Earnings screen: Q3 2026 releases through November 5, 2026. CORZ, GLXY, HUT and RIOT reported positive GAAP diluted EPS. This is a dated screen, not a claim of recurring profitability or positive free cash flow.</p>${error?`<p role="alert">${esc(error)}</p>`:''}<section id="power-research"><h3>Neocloud & AI infrastructure watchlist</h3><div class="power-grid">${research.map(r=>`<article class="power-panel"><span class="power-kicker">${esc(r.role)} · released ${r.date}</span><h4><a data-power-symbol="${r.symbol}" href="/board?view=ai-power&amp;symbol=${r.symbol}#detail-card">${r.symbol}</a> · ${esc(r.name)}</h4><p>${esc(r.fact)}</p><p><strong>Cash-quality check:</strong> ${esc(r.view)}</p>${source('Company release / filing',r.href)}</article>`).join('')}</div><p>CIFR is outside this positive-diluted-EPS screen: Q3 net income and basic EPS were positive, but diluted EPS was negative. These companies combine landlords, developers, mining and digital assets; they are not interchangeable GPU cloud operators.</p></section>${renderDebt(rateBps)}<section id="power-market"><h3>Price strength & breadth</h3>${assessment?renderSignals(assessment):'<p>Loading completed sessions. Missing data stays unavailable.</p>'}</section><section id="power-plan"><h3>What to verify before investing</h3><ul><li>Separate recurring rent and services from fit-out reimbursements, power pass-throughs and noncash gains.</li><li>Reconcile operating cash flow, Bitcoin sales, customer advances, cash capex, debt service and dilution.</li><li>Distinguish billed IT MW from signed future leases, utility approvals and pipeline. Contracts do not confer permit immunity.</li><li>Compare current valuation and remaining committed funding before ranking opportunities.</li></ul><p class="power-note">No standing entry levels, allocation budgets or account data are attached to this watchlist.</p></section><section id="power-journal"><h3>Sourced research notes</h3>${entries.length?entries.map(e=>`<article class="power-panel"><small>${esc(e.date)}</small><h4>${esc(e.title)}</h4><p>${esc(e.detail)}</p>${url(e.source)?source('Evidence',url(e.source)):''}</article>`).join(''):'<p>No saved notes for this theme. Earlier theme records remain historical.</p>'}</section></div>`;
  }
  async function load(force=false){
   if(loading)return;loading=true;error='';refresh();
   try{
    const payloads={};let cursor=0;const symbols=[...universe,...benchmarks];
    await Promise.all(Array.from({length:4},async()=>{while(cursor<symbols.length){const s=symbols[cursor++];try{const r=await fetch(`/api/stock?symbol=${s}${force?'&force=1':''}`);if(!r.ok)throw new Error('Market data unavailable');payloads[s]=await r.json();}catch(e){payloads[s]={error:e.message};}}}));
    assessment=assess(payloads,today());
   }catch(e){assessment=null;error=e.message;}
   loading=false;refresh();
  }
  container.addEventListener('click',e=>{const a=e.target.closest('[data-power-symbol]');if(a&&onSelect&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey&&e.button===0){e.preventDefault();onSelect(a.dataset.powerSymbol);}if(e.target.closest('[data-power-refresh]'))void load(true);});
  container.addEventListener('change',e=>{if(e.target.matches?.('[data-power-rate]')){const next=Number(e.target.value);if([100,200,300].includes(next)){rateBps=next;refresh();}}});
  refresh();void load();return {refresh,reload:load};
 }
 root.AIPower={theme,universe,benchmarks,plans,research,debtProfiles,debtMetrics,rateStress,metrics,assess,sizeTrade,validateEntry,mount};
 if(typeof module!=='undefined')module.exports=root.AIPower;
})(globalThis);
