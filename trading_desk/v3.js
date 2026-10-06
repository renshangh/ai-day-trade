'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const deskLogic = globalThis.TradingDeskV3Logic;
const scoreFields = [['AI Economy','aiEconomy'],['Market Risk','marketRisk'],['Opportunity','opportunityScore'],['Altcoin Health','altcoinHealth'],['AI Infrastructure','aiInfrastructure']];
const economyFactors = ['AI infrastructure','Enterprise AI','AI agent adoption','AI crypto','Real-world assets','Market liquidity'];
const healthFactors = [['BTC dominance',20],['ETH/BTC',20],['Altcoin season',15],['Stablecoin liquidity',10],['ETF flows',10],['Funding',10],['Open interest',5],['Market breadth',10]];
const key = 'ai-trading-desk-v3';
const legacyKey = 'ai-trading-desk-preview-v3';
let onchainReview = null;
let records = {reports:[], thesisReviews:{}, opportunities:[], decisions:[], healthReviews:[], observations:[]};
let serverRevision = null;
let syncInFlight = false;
let syncQueued = false;
try {
 const data = JSON.parse(localStorage.getItem(key) || localStorage.getItem(legacyKey));
 if (data && typeof data === 'object') {
  for (const kind of ['reports','opportunities','decisions','healthReviews','observations']) if (Array.isArray(data[kind])) records[kind] = data[kind];
  if (data.thesisReviews && typeof data.thesisReviews === 'object' && !Array.isArray(data.thesisReviews)) records.thesisReviews = data.thesisReviews;
 }
} catch { /* Corrupt browser data leaves a fresh, empty desk. */ }
function save(){
 localStorage.setItem(key, JSON.stringify(records));
 localStorage.setItem(`${key}-unsynced`, '1');
 void persist();
}
function syncStatus(message){$('sync-status').textContent=message;}
async function persist(){
 if(serverRevision===null)return;
 if(syncInFlight){syncQueued=true;return;}
 syncInFlight=true;
 const snapshot=JSON.parse(JSON.stringify(records));
 try {
  const response=await fetch('/api/v3/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expectedRevision:serverRevision,data:snapshot})});
  const result=await response.json();
  if(!response.ok)throw new Error(result.error || `Save failed (${response.status})`);
  serverRevision=result.revision;
  if(!syncQueued){localStorage.removeItem(`${key}-unsynced`);syncStatus(`Saved to local desk file · revision ${serverRevision}`);}
 } catch(error){
  if(String(error.message).includes('changed in another session'))serverRevision=null;
  syncStatus(`Browser recovery copy saved. Local desk sync failed: ${error.message}`);
 } finally {
  syncInFlight=false;
  if(syncQueued && serverRevision!==null){syncQueued=false;void persist();}
 }
}
function hasRecords(data){return ['reports','opportunities','decisions','healthReviews','observations'].some(field=>data[field]?.length) || Object.values(data.thesisReviews || {}).some(rows=>rows.length);}
async function hydrate(){
 try {
  const response=await fetch('/api/v3/state');
  if(!response.ok)throw new Error(`HTTP ${response.status}`);
  const payload=await response.json();
  if(!payload.data || !Number.isInteger(payload.revision))throw new Error('Invalid desk file response');
  serverRevision=payload.revision;
  const unsynced=localStorage.getItem(`${key}-unsynced`)==='1';
  if(unsynced && JSON.stringify(records)!==JSON.stringify(payload.data)){
   serverRevision=null;
   syncStatus('Unsynced browser edits differ from the local desk file. Export a backup before resolving the conflict.');
   return;
  }
  if(payload.revision===0 && hasRecords(records)){void persist();return;}
  records=payload.data;
  localStorage.setItem(key,JSON.stringify(records));
  localStorage.removeItem(`${key}-unsynced`);
  renderReport();renderCoin();renderResearch();renderTheses();renderRecords();onchainReview?.refresh();
  syncStatus(`Loaded local desk file · revision ${serverRevision}`);
 } catch(error){syncStatus(`Local desk file unavailable (${error.message}). Entries remain in this browser.`);}
}
function safeUrl(url){ try { const parsed = new URL(url); return ['http:','https:'].includes(parsed.protocol) ? parsed.href : ''; } catch { return ''; } }
function sourceLink(url){ const safe = safeUrl(url); return safe ? `<a class="text-link" href="${esc(safe)}" target="_blank" rel="noopener noreferrer">Source ↗</a>` : ''; }
function displayScore(value){return /^(100|[1-9]?\d)$/.test(String(value ?? '')) ? String(value) : '—';}
async function renderLivePulse(){
 const [boardResult,cycleResult]=await Promise.allSettled([
  fetch('/api/board').then(response=>response.ok?response.json():Promise.reject(new Error(`HTTP ${response.status}`))),
  fetch('/api/cycle').then(response=>response.ok?response.json():Promise.reject(new Error(`HTTP ${response.status}`))),
 ]);
 const board=boardResult.status==='fulfilled'?boardResult.value:null;
 const hottest=board?.lookbacks?.['1']?.hottest;
 const cycle=cycleResult.status==='fulfilled'?cycleResult.value:null;
 const latest=cycle?.latest;
 const boardCard=hottest && Number.isFinite(hottest.mean_return_pct)
  ? `<article class="panel"><span class="eyebrow">MARKET BOARD · ${esc(board.as_of_session || 'date unavailable')}</span><h3>Leading 1-day group</h3><p><b>${esc(hottest.group)}</b> · ${hottest.mean_return_pct.toFixed(2)}% mean return · ${Number.isFinite(hottest.breadth_pct)?hottest.breadth_pct.toFixed(0)+'% breadth':'breadth unavailable'}</p><p class="muted">${esc(board.feed || 'feed unavailable')}${board.stale?' · cached/stale':''}</p><a class="text-link" href="/board?view=momentum">Inspect board ↗</a></article>`
  : '<article class="panel"><h3>Leading group</h3><p class="muted">Live board reading unavailable.</p></article>';
 const cycleCard=latest
  ? `<article class="panel"><span class="eyebrow">RECORDED CYCLE · ${esc(latest.review_date)}</span><h3>AI data center cycle</h3><p><b>${esc(latest.status)}</b> · ${esc(latest.total)}/${esc(cycle.max_score || cycle.score_max || '—')} recorded points</p><a class="text-link" href="/board?view=cycle">Inspect cycle ↗</a></article>`
  : '<article class="panel"><h3>AI data center cycle</h3><p class="muted">No cycle reading recorded.</p></article>';
 $('live-pulse').innerHTML=boardCard+cycleCard;
}
void renderLivePulse();
function renderReport(){
 const reports = [...records.reports].sort((a,b)=>String(b.date).localeCompare(String(a.date)));
 const latest = reports[0];
 const health=[...records.healthReviews].sort((a,b)=>String(b.date).localeCompare(String(a.date)))[0];
 const healthValue=deskLogic.healthScore(health?.items);
 $('report-stamp').textContent = latest ? `Latest manual report · ${latest.date}` : 'No report has been published yet';
 $('scorecard').innerHTML = scoreFields.map(([name,field])=>{const value=field==='altcoinHealth' && healthValue!==null ? healthValue : latest?.[field];return `<div class="score"><div class="name">${name} Score</div><div class="value">${displayScore(value)}</div><small>${value !== '' && value != null ? field==='altcoinHealth' && healthValue!==null ? `Sourced assessment · ${esc(health.date)}` : 'Manual assessment' : 'Awaiting verified inputs'}</small></div>`;}).join('');
 $('economy-inputs').innerHTML = economyFactors.map((name,i)=>`<div class="factor"><span>${name} ${latest?.factors?.[i]?.source ? sourceLink(latest.factors[i].source) : ''}</span><span>${displayScore(latest?.factors?.[i]?.score)}</span></div>`).join('');
 const changes = deskLogic.latestChanges(reports);
 $('changes').innerHTML = changes.length ? changes.map(change=>`<li><span class="change-direction">${esc(change.direction)}</span> ${esc(change.text)} ${sourceLink(change.source)}</li>`).join('') : '<li>No verified changes yet</li>';
 $('decision-lens').innerHTML = `<b>Opportunity</b><p>${esc(latest?.opportunity || 'Awaiting a sourced report.')}</p><b>Risk</b><p>${esc(latest?.risk || 'Awaiting a sourced report.')}</p><b>Action items</b><p>${esc(latest?.actions || 'No action items recorded.')}</p>`;
 $('report-history').innerHTML = reports.length ? reports.map(report=>`<article class="record"><b>${esc(report.date)}</b><span class="muted"> · ${esc(report.method || 'Method not entered')}</span></article>`).join('') : '<div class="empty">No report snapshots yet.</div>';
}
const changeFields = Array.from({length:5},(_,i)=>`<div class="change-entry"><label>Change ${i+1}<input name="change${i}Text" maxlength="180" placeholder="What changed?"></label><label>Direction<select name="change${i}Direction"><option>↑ Positive</option><option>↓ Negative</option><option>↔ Mixed</option></select></label><label>Source URL<input name="change${i}Source" type="url" placeholder="https://..."></label></div>`).join('');
$('change-fields').innerHTML = changeFields;
$('factor-fields').innerHTML = economyFactors.map((name,i)=>`<div class="factor-entry"><label>${name} score<input name="factor${i}Score" type="number" min="0" max="100" placeholder="0–100"></label><label>Source URL<input name="factor${i}Source" type="url" placeholder="https://..."></label></div>`).join('');
$('report-form').elements.date.value = new Date().toISOString().slice(0,10);
$('report-form').addEventListener('submit',event=>{
 event.preventDefault();
 const form=event.currentTarget, data=Object.fromEntries(new FormData(form));
 const changes=[];
 for(let i=0;i<5;i++){
  const change=(data[`change${i}Text`] || '').trim(), source=(data[`change${i}Source`] || '').trim();
  if(change && !safeUrl(source)){form.elements[`change${i}Source`].setCustomValidity('A source URL is required for each development.');form.reportValidity();return;}
  form.elements[`change${i}Source`].setCustomValidity('');
  if(change) changes.push({text:change,source,direction:data[`change${i}Direction`]});
  delete data[`change${i}Text`]; delete data[`change${i}Source`]; delete data[`change${i}Direction`];
 }
 if(changes.length && !records.reports.length){form.elements.change0Text.setCustomValidity('Save a baseline report first, then add developments to the next report.');form.reportValidity();return;}
 const factors=[];
 for(let i=0;i<economyFactors.length;i++){
  const score=data[`factor${i}Score`], source=data[`factor${i}Source`].trim();
  if(score !== '' && !safeUrl(source)){form.elements[`factor${i}Source`].setCustomValidity('A source URL is required for each scored input.');form.reportValidity();return;}
  if(score === '' && source){form.elements[`factor${i}Score`].setCustomValidity('Enter a score for this source.');form.reportValidity();return;}
  factors.push({score,source}); delete data[`factor${i}Score`]; delete data[`factor${i}Source`];
 }
 if(factors.some(f=>f.score !== '') && factors.some(f=>f.score === '')){form.elements.factor0Score.setCustomValidity('Enter all six factor scores or leave all six blank.');form.reportValidity();return;}
 const composite=deskLogic.economyScore(factors);
 data.aiEconomy=composite===null?'':String(composite);
 if(scoreFields.some(([,field])=>!['aiEconomy','altcoinHealth'].includes(field) && data[field] !== '') && !data.method.trim()){form.elements.method.setCustomValidity('Explain the source or method for manually entered scores.');form.reportValidity();return;}
 form.elements.method.setCustomValidity('');
 if(records.reports.some(report=>report.date===data.date)){form.elements.date.setCustomValidity('A report already exists for this date.');form.reportValidity();return;}
 data.changes=changes; data.factors=factors; records.reports.push(data); save(); form.reset(); form.elements.date.value=new Date().toISOString().slice(0,10); renderReport();
});
$('report-form').addEventListener('input',event=>{if(event.target.setCustomValidity)event.target.setCustomValidity('');});
renderReport();
const desk = [
 ['Executive Summary','Market posture, confidence, top developments, opportunities, and risks.','#brief','Read CIO Brief'],
 ['Macro Economy','Fed, yields, dollar, inflation, jobs, commodities, and liquidity.','#brief','Record macro assessment'],
 ['AI Infrastructure','Semiconductors, networking, orders, supply chain, and CapEx.','/board?view=sector','Open sector scorecard'],
 ['Data Center Build-out','Campuses, power, cooling, fiber, and construction.','/board?view=cycle','Open cycle dashboard'],
 ['Enterprise AI','Model releases, agent deployments, MCP, and adoption.','/board?view=enterprise-ai','Open Enterprise AI'],
 ['Onchain Finance Buildout','Digital money, onchain markets, TradFi bridges, infrastructure rails, and agentic finance.','#coins','Open Onchain Finance Buildout'],
 ['AI Stock Watchlist','Price action, catalysts, earnings, and relative strength.','/board?view=momentum','Open stock board'],
 ['Trading Opportunities','Setups, catalysts, risk, and decision criteria.','#pipeline','Open pipeline'],
 ['Risk Dashboard','Macro, concentration, liquidity, leverage, and thesis risk.','/board?view=review','Open daily review'],
 ['HCA Technology Watch','Physical AI, robotics, world models, and manufacturing AI.','#research','Open research queue']
];
$('desk-grid').innerHTML = desk.map(([name,description,href,label],i) => `<div class="desk-item"><b>${String(i+1).padStart(2,'0')} · ${name}</b><p>${description}</p><a class="text-link" href="${href}">${label} ↗</a></div>`).join('');
onchainReview = globalThis.CryptoFinanceInfra.mount($('crypto-infra-map'), {
 getObservations: () => records.observations,
 onSave: entry => { records.observations.push(entry); save(); }
});
const coinPanels = [
 {name:'Altcoin Health Monitor',body:`<p>Eight proposed indicators; no market state is assigned until verified observations are available.</p><div class="pill-list">${['BTC dominance · 20%','ETH/BTC · 20%','Altcoin season · 15%','Stablecoin liquidity · 10%','ETF flows · 10%','Funding · 10%','Open interest · 5%','Market breadth · 10%'].map(x=>`<span class="pill">${x}</span>`).join('')}</div><p class="muted">Each indicator: pending · overall status: unscored.</p>`},
 {name:'AI Coin Dashboard',body:''},
 {name:'Agent Economy',body:`<p>Track actual deployments and economic activity, with dated sources and adoption metrics when available.</p><div class="pill-list">${['Agent commerce','Payments','Identity','MCP adoption','Enterprise deployments','Robotics','Marketplaces'].map(x=>`<span class="pill">${x}</span>`).join('')}</div><p class="muted">Use the observations below to record sourced developments.</p>`},
 {name:'AI × Blockchain',body:`<p>Research map for where blockchains may provide verifiable value to AI systems.</p><div class="pill-list">${['Verifiable AI','Decentralized compute','Decentralized inference','Agent wallets','On-chain reputation','Trusted execution','Tokenized AI services'].map(x=>`<span class="pill">${x}</span>`).join('')}</div><p class="muted">Record adoption and revenue claims with their sources below.</p>`},
 {name:'RWA Dashboard',body:`<p>Watchlist: ONDO, BUIDL, Franklin, Superstate, Ethena, and Centrifuge.</p><div class="pill-list">${['TVL','Treasury tokenization','Institutional adoption','Partnerships','Governance','Large-wallet activity'].map(x=>`<span class="pill">${x}</span>`).join('')}</div><p class="muted">Current TVL and flows are unavailable until recorded with a source. ONDO spot price can be loaded from the configured crypto feed below.</p>`},
 {name:'Early Signals',body:`<p>Capture dated signals before they become consensus: launches, usage, revenue, financing, partnerships, and regulatory developments.</p><p class="muted">Add dated signals with a source below.</p>`}
];
const cryptoUniverse = [
 ['TAO','Infrastructure'],['AKT','Infrastructure'],['RENDER','Infrastructure'],
 ['FET','Agent platforms'],['NEARUSD','Agent infrastructure'],['ONDOUSD','RWA'],['HYPEUSD','Markets']
];
const cryptoQuotes = new Map();
let activeCoin = 0;
function observationPanel(theme){
 const notes=records.observations.filter(note=>note.theme===theme).sort((a,b)=>String(b.date).localeCompare(String(a.date)));
 const list=notes.length ? notes.map(note=>`<article class="review-entry"><b>${esc(note.date)} · ${esc(note.title)}</b><p>${esc(note.detail || '')}</p>${sourceLink(note.source)}</article>`).join('') : '<p class="muted">No sourced observations recorded.</p>';
 return `<div class="observations"><h3>Sourced observations</h3>${list}<details><summary>Add an observation</summary><form class="entry-form observation-form"><input type="hidden" name="theme" value="${esc(theme)}"><label>Date<input name="date" type="date" required value="${new Date().toISOString().slice(0,10)}"></label><label>Development or metric<input name="title" maxlength="160" required></label><label class="full">What it means<textarea name="detail" maxlength="500"></textarea></label><label class="full">Source URL<input name="source" type="url" required placeholder="https://..."></label><button>Save observation</button></form></details></div>`;
}
function renderResearch(){ $('research-notes').innerHTML=observationPanel('Research Lab'); }
function healthPanel(){
 const latest=[...records.healthReviews].sort((a,b)=>String(b.date).localeCompare(String(a.date)))[0];
 const score=deskLogic.healthScore(latest?.items);
 const state=score===null?'Unscored':score>=70?'Healthy':score<=30?'Weak':'Mixed';
 const summary=latest ? `<p><b>${state} · ${score ?? '—'}/100</b> <span class="muted">assessed ${esc(latest.date)}</span></p><div class="pill-list">${healthFactors.map(([name,weight],i)=>`<span class="pill">${esc(name)} ${weight}% · ${esc(latest.items[i]?.state || 'Missing')} ${sourceLink(latest.items[i]?.source)}</span>`).join('')}</div>` : '<p class="muted">No sourced assessment yet.</p>';
 const fields=healthFactors.map(([name,weight],i)=>`<div class="factor-entry"><label>${esc(name)} · ${weight}%<select name="health${i}State" required><option value="">Choose state</option><option>Healthy</option><option>Mixed</option><option>Weak</option></select></label><label>Source URL<input name="health${i}Source" type="url" required placeholder="https://..."></label></div>`).join('');
 return `<p>Score each indicator from sourced observations. Healthy = 100, Mixed = 50, Weak = 0; weighted total determines the score.</p>${summary}<details><summary>Record an assessment</summary><form id="health-form" class="entry-form"><label>Date<input name="date" type="date" required value="${new Date().toISOString().slice(0,10)}"></label><div class="full entry-form">${fields}</div><button>Save health assessment</button></form></details>`;
}
function quoteRow(symbol,theme){
 const item=cryptoQuotes.get(symbol);
 const snapshot=item?.bars ? deskLogic.cryptoSnapshot(item.bars) : null;
 const note=item?.error ? `Unavailable: ${esc(item.error)}` : item?.loading ? 'Loading real bars…' : !item ? 'Load quote' : !snapshot ? 'No usable bars returned' : `${esc(item.feed || 'Feed unavailable')} · ${snapshot.date}`;
 return `<tr><th>${esc(symbol)}<small>${esc(theme)}</small></th><td>${snapshot ? '$'+snapshot.close.toLocaleString(undefined,{maximumFractionDigits:4}) : '—'}</td><td>${snapshot?.dayPct == null ? '—' : snapshot.dayPct.toFixed(2)+'%'}</td><td>${snapshot?.weekPct == null ? '—' : snapshot.weekPct.toFixed(2)+'%'}</td><td>${snapshot?.volume == null ? '—' : snapshot.volume.toLocaleString(undefined,{maximumFractionDigits:0})}</td><td>${note}</td><td><button type="button" class="quote-load" data-crypto="${esc(symbol)}" ${item?.loading?'disabled':''}>${item?'Refresh':'Load'}</button></td></tr>`;
}
function coinQuoteTable(universe){return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Asset / theme</th><th>Last close</th><th>1 bar</th><th>7 bars</th><th>Volume</th><th>Feed / as of</th><th></th></tr></thead><tbody>${universe.map(([symbol,theme])=>quoteRow(symbol,theme)).join('')}</tbody></table></div><p class="footnote">Changes compare actual returned daily closes. “—” means the feed did not provide enough usable data. Relative strength, news, and institutional activity are not connected yet.</p>`;}
function renderCoin(){
 $('coin-tabs').innerHTML = coinPanels.map((p,i)=>`<button role="tab" type="button" data-index="${i}" aria-selected="${i===activeCoin}">${p.name}</button>`).join('');
 const panel=coinPanels[activeCoin];
 const base=activeCoin===0 ? healthPanel() : activeCoin===1 ? coinQuoteTable(cryptoUniverse) : activeCoin===4 ? panel.body+coinQuoteTable([['ONDOUSD','RWA']]) : panel.body;
 const body=activeCoin===0 ? base : base+observationPanel(panel.name);
 $('coin-panel').innerHTML=`<div class="coin-content"><h3>${panel.name}</h3>${body}</div>`;
}
$('coin-tabs').addEventListener('click',event=>{const button=event.target.closest('button[data-index]');if(button){activeCoin=Number(button.dataset.index);renderCoin();}});
$('coin-panel').addEventListener('click',async event=>{
 const button=event.target.closest('button[data-crypto]'); if(!button)return;
 const symbol=button.dataset.crypto;
 cryptoQuotes.set(symbol,{loading:true}); renderCoin();
 try {
  const response=await fetch(`/api/crypto?symbol=${encodeURIComponent(symbol)}`);
  const payload=await response.json();
  if(!response.ok || payload.error) throw new Error(payload.error || `HTTP ${response.status}`);
  cryptoQuotes.set(symbol,payload);
 } catch(error) {cryptoQuotes.set(symbol,{error:error.message || 'Quote unavailable'});}
 renderCoin();
});
$('coin-panel').addEventListener('submit',event=>{
 const form=event.target.closest('#health-form'); if(!form)return;
 event.preventDefault(); const data=Object.fromEntries(new FormData(form));
 const items=healthFactors.map((_,i)=>({state:data[`health${i}State`],source:data[`health${i}Source`]}));
 const invalid=items.findIndex(item=>!deskLogic.validSource(item.source));
 if(invalid>=0){form.elements[`health${invalid}Source`].setCustomValidity('Use an http or https source URL.');form.reportValidity();return;}
 if(deskLogic.healthScore(items)===null){form.reportValidity();return;}
 records.healthReviews.push({date:data.date,items}); save(); renderCoin(); renderReport();
});
$('coin-panel').addEventListener('input',event=>{if(event.target.setCustomValidity)event.target.setCustomValidity('');});
renderCoin();
document.addEventListener('submit',event=>{
 const form=event.target.closest('.observation-form'); if(!form)return;
 event.preventDefault(); const data=Object.fromEntries(new FormData(form));
 if(!safeUrl(data.source)){form.elements.source.setCustomValidity('Use an http or https source URL.');form.reportValidity();return;}
 records.observations.push(data); save(); renderCoin(); renderResearch();
});
document.addEventListener('input',event=>{if(event.target.matches('.observation-form [name="source"]'))event.target.setCustomValidity('');});
renderResearch();
const theses = [
 ['AI Infrastructure Supercycle','Sustained hyperscaler investment supports semiconductors, networking, power equipment, and construction.','CapEx · GPU shipments · optical demand · power orders · utility interconnections'],
 ['Enterprise Agent Revolution','AI agents become standard enterprise tools across models, orchestration, security, and workflow automation.','Deployments · paid usage · retention · workflow outcomes'],
 ['Physical AI','Robotics, vision AI, world models, and digital twins move from pilots into production.','Production deployments · unit economics · safety · adoption'],
 ['AI Power Infrastructure','AI data-center growth drives grid modernization, transformers, switchgear, and backup power demand.','Grid upgrades · lead times · orders · interconnection queues'],
 ['RWA Tokenization','Tokenized financial assets gain sustained institutional usage and durable on-chain value.','TVL quality · settlement usage · issuer adoption · regulation']
];
$('thesis-select').innerHTML=theses.map(([name])=>`<option>${esc(name)}</option>`).join('');
$('thesis-form').elements.date.value=new Date().toISOString().slice(0,10);
function renderTheses(){
 $('thesis-list').innerHTML=theses.map(([name,statement,watch])=>{
  const reviews=Array.isArray(records.thesisReviews[name])?[...records.thesisReviews[name]].sort((a,b)=>String(b.date).localeCompare(String(a.date))):[];
  const latest=reviews[0];
  return `<article class="record"><h3>${esc(name)}</h3><p>${esc(statement)}</p><dl>${field('Confidence / trend',latest?`${displayScore(latest.confidence)} / ${latest.trend}`:'Unrated · awaiting review')}${field('Watch',watch)}${field('Supporting evidence',latest?.supporting || 'None recorded')}${field('Contradicting evidence',latest?.contradicting || 'None recorded')}</dl><details><summary>Review history (${reviews.length})</summary>${reviews.length?reviews.map(review=>`<div class="review-entry"><b>${esc(review.date)}</b> · ${displayScore(review.confidence)} / ${esc(review.trend)} · ${sourceLink(review.source)}<p><b>For:</b> ${esc(review.supporting || 'None')}</p><p><b>Against:</b> ${esc(review.contradicting || 'None')}</p></div>`).join(''):'<p class="muted">No reviews yet.</p>'}</details></article>`;
 }).join('');
}
$('thesis-form').addEventListener('submit',event=>{
 event.preventDefault(); const form=event.currentTarget, data=Object.fromEntries(new FormData(form));
 if(!data.supporting.trim() && !data.contradicting.trim()){form.elements.supporting.setCustomValidity('Record at least one supporting or contradicting observation.');form.reportValidity();return;}
 form.elements.supporting.setCustomValidity('');
 if(!safeUrl(data.source)){form.elements.source.setCustomValidity('Use an http or https source URL.');form.reportValidity();return;}
 form.elements.source.setCustomValidity('');
 const name=data.thesis; delete data.thesis;
 if(!Array.isArray(records.thesisReviews[name]))records.thesisReviews[name]=[];
 records.thesisReviews[name].push(data); save(); form.reset(); form.elements.date.value=new Date().toISOString().slice(0,10); renderTheses();
});
$('thesis-form').addEventListener('input',event=>{if(event.target.setCustomValidity)event.target.setCustomValidity('');});
renderTheses();
function field(label,value){return `<div><dt>${label}</dt><dd>${esc(value || '—')}</dd></div>`;}
function renderRecords(){
 $('opportunity-list').innerHTML=records.opportunities.length?records.opportunities.map((r,i)=>`<article class="record"><h3>${esc(r.name)} <em>${esc(r.stage)}</em></h3><dl>${field('Catalyst',r.catalyst)}${field('Risks',r.risks)}${field('Increase confidence',r.confirm)}${field('Invalidate thesis',r.invalidate)}</dl><label class="inline-edit">Stage <select class="stage-edit" data-index="${i}">${['Research','Watching','Ready for review','Closed'].map(stage=>`<option ${stage===r.stage?'selected':''}>${stage}</option>`).join('')}</select></label><p><button class="remove" data-kind="opportunities" data-index="${i}">Remove</button></p></article>`).join(''):'<div class="empty">No opportunities recorded yet.</div>';
 $('decision-list').innerHTML=records.decisions.length?records.decisions.map((r,i)=>`<article class="record"><h3>${esc(r.decision)}</h3><dl>${field('Recorded',r.recorded)}${field('Rationale',r.rationale)}${field('Evidence',r.evidence)}${field('Review date',r.review)}${field('Outcome',r.outcome)}</dl><form class="outcome-edit inline-edit" data-index="${i}"><label>Update outcome<input name="outcome" maxlength="240" value="${esc(r.outcome || '')}" placeholder="What happened by the review date?"></label><button>Save outcome</button></form><p><button class="remove" data-kind="decisions" data-index="${i}">Remove</button></p></article>`).join(''):'<div class="empty">No decisions recorded yet.</div>';
}
for(const [id,kind] of [['opportunity-form','opportunities'],['decision-form','decisions']]) $(id).addEventListener('submit',event=>{event.preventDefault();const form=event.currentTarget;const data=Object.fromEntries(new FormData(form));if(kind==='decisions')data.recorded=new Date().toISOString().slice(0,10);records[kind].unshift(data);save();form.reset();renderRecords();});
document.addEventListener('click',event=>{const button=event.target.closest('.remove');if(!button)return;const kind=button.dataset.kind;records[kind].splice(Number(button.dataset.index),1);save();renderRecords();});
document.addEventListener('change',event=>{if(!event.target.matches('.stage-edit'))return;records.opportunities[Number(event.target.dataset.index)].stage=event.target.value;save();renderRecords();});
document.addEventListener('submit',event=>{const form=event.target.closest('.outcome-edit');if(!form)return;event.preventDefault();records.decisions[Number(form.dataset.index)].outcome=form.elements.outcome.value.trim();save();renderRecords();});
renderRecords();
$('export-data').addEventListener('click',()=>{
 const blob=new Blob([JSON.stringify({format:'ai-trading-desk-v3',exportedAt:new Date().toISOString(),...records},null,2)],{type:'application/json'});
 const link=document.createElement('a'); link.href=URL.createObjectURL(blob); link.download='ai-trading-desk-v3.json'; link.click();
 setTimeout(()=>URL.revokeObjectURL(link.href),1000);
});
void hydrate();
