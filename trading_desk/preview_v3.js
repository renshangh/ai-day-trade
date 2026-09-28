'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const previewLogic = globalThis.PreviewV3Logic;
const scoreFields = [['AI Economy','aiEconomy'],['Market Risk','marketRisk'],['Opportunity','opportunityScore'],['Altcoin Health','altcoinHealth'],['AI Infrastructure','aiInfrastructure']];
const economyFactors = ['AI infrastructure','Enterprise AI','AI agent adoption','AI crypto','Real-world assets','Market liquidity'];
const key = 'ai-trading-desk-preview-v3';
let records = {reports:[], thesisReviews:{}, opportunities:[], decisions:[]};
try {
 const data = JSON.parse(localStorage.getItem(key));
 if (data && typeof data === 'object') {
  for (const kind of ['reports','opportunities','decisions']) if (Array.isArray(data[kind])) records[kind] = data[kind];
  if (data.thesisReviews && typeof data.thesisReviews === 'object' && !Array.isArray(data.thesisReviews)) records.thesisReviews = data.thesisReviews;
 }
} catch { /* Corrupt browser data leaves a fresh, empty preview. */ }
function save(){ localStorage.setItem(key, JSON.stringify(records)); }
function safeUrl(url){ try { const parsed = new URL(url); return ['http:','https:'].includes(parsed.protocol) ? parsed.href : ''; } catch { return ''; } }
function sourceLink(url){ const safe = safeUrl(url); return safe ? `<a class="text-link" href="${esc(safe)}" target="_blank" rel="noopener noreferrer">Source ↗</a>` : ''; }
function displayScore(value){return /^(100|[1-9]?\d)$/.test(String(value ?? '')) ? String(value) : '—';}
function renderReport(){
 const reports = [...records.reports].sort((a,b)=>String(b.date).localeCompare(String(a.date)));
 const latest = reports[0];
 $('report-stamp').textContent = latest ? `Latest manual report · ${latest.date}` : 'No report has been published for this preview';
 $('scorecard').innerHTML = scoreFields.map(([name,field])=>`<div class="score"><div class="name">${name} Score</div><div class="value">${displayScore(latest?.[field])}</div><small>${latest?.[field] !== '' && latest?.[field] != null ? 'Manual preview assessment' : 'Awaiting verified inputs'}</small></div>`).join('');
 $('economy-inputs').innerHTML = economyFactors.map((name,i)=>`<div class="factor"><span>${name} ${latest?.factors?.[i]?.source ? sourceLink(latest.factors[i].source) : ''}</span><span>${displayScore(latest?.factors?.[i]?.score)}</span></div>`).join('');
 const changes = previewLogic.latestChanges(reports);
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
 const composite=previewLogic.economyScore(factors);
 data.aiEconomy=composite===null?'':String(composite);
 if(scoreFields.some(([,field])=>field !== 'aiEconomy' && data[field] !== '') && !data.method.trim()){form.elements.method.setCustomValidity('Explain the source or method for manually entered scores.');form.reportValidity();return;}
 form.elements.method.setCustomValidity('');
 if(records.reports.some(report=>report.date===data.date)){form.elements.date.setCustomValidity('A report already exists for this date.');form.reportValidity();return;}
 data.changes=changes; data.factors=factors; records.reports.push(data); save(); form.reset(); form.elements.date.value=new Date().toISOString().slice(0,10); renderReport();
});
$('report-form').addEventListener('input',event=>{if(event.target.setCustomValidity)event.target.setCustomValidity('');});
renderReport();
const desk = [
 ['Executive Summary','Market posture, confidence, top developments, opportunities, and risks.'],
 ['Macro Economy','Fed, yields, dollar, inflation, jobs, commodities, and liquidity.'],
 ['AI Infrastructure','Semiconductors, networking, orders, supply chain, and CapEx.'],
 ['Data Center Build-out','Campuses, power, cooling, fiber, and construction.'],
 ['Enterprise AI','Model releases, agent deployments, MCP, and adoption.'],
 ['AI Coins & Agent Economy','Altcoin health, tokens, agents, blockchain, RWA, and early signals.'],
 ['AI Stock Watchlist','Price action, catalysts, earnings, and relative strength.'],
 ['Trading Opportunities','Setups, catalysts, risk, and decision criteria.'],
 ['Risk Dashboard','Macro, concentration, liquidity, leverage, and thesis risk.'],
 ['HCA Technology Watch','Physical AI, robotics, world models, and manufacturing AI.']
];
$('desk-grid').innerHTML = desk.map(([name,description],i) => `<div class="desk-item"><b>${String(i+1).padStart(2,'0')} · ${name}</b><p>${description}</p></div>`).join('');
const coinPanels = [
 {name:'Altcoin Health Monitor',body:`<p>Eight proposed indicators; no market state is assigned until verified observations are available.</p><div class="pill-list">${['BTC dominance · 20%','ETH/BTC · 20%','Altcoin season · 15%','Stablecoin liquidity · 10%','ETF flows · 10%','Funding · 10%','Open interest · 5%','Market breadth · 10%'].map(x=>`<span class="pill">${x}</span>`).join('')}</div><p class="muted">Each indicator: pending · overall status: unscored.</p>`},
 {name:'AI Coin Dashboard',body:`<p>Research universe only. Price, volume, relative strength, trend, news, and institutional activity are awaiting a verified feed.</p><table class="data-table"><thead><tr><th>Theme</th><th>Watchlist</th><th>Market data</th></tr></thead><tbody><tr><td>Infrastructure</td><td>TAO · AKT · RENDER · AIOZ</td><td>Unavailable</td></tr><tr><td>Agent platforms</td><td>VIRTUAL · FET/ASI · OLAS</td><td>Unavailable</td></tr><tr><td>Data</td><td>LINK · GRT</td><td>Unavailable</td></tr></tbody></table>`},
 {name:'Agent Economy',body:`<p>Track actual deployments and economic activity, with dated sources and adoption metrics when available.</p><div class="pill-list">${['Agent commerce','Payments','Identity','MCP adoption','Enterprise deployments','Robotics','Marketplaces'].map(x=>`<span class="pill">${x}</span>`).join('')}</div><p class="muted">No verified observations recorded.</p>`},
 {name:'AI × Blockchain',body:`<p>Research map for where blockchains may provide verifiable value to AI systems.</p><div class="pill-list">${['Verifiable AI','Decentralized compute','Decentralized inference','Agent wallets','On-chain reputation','Trusted execution','Tokenized AI services'].map(x=>`<span class="pill">${x}</span>`).join('')}</div><p class="muted">No adoption or revenue claims recorded.</p>`},
 {name:'RWA Dashboard',body:`<p>Watchlist: ONDO, BUIDL, Franklin, Superstate, Ethena, and Centrifuge.</p><div class="pill-list">${['TVL','Treasury tokenization','Institutional adoption','Partnerships','Governance','Large-wallet activity'].map(x=>`<span class="pill">${x}</span>`).join('')}</div><p class="muted">Current TVL and flows are unavailable.</p>`},
 {name:'Early Signals',body:`<p>Capture dated signals before they become consensus: launches, usage, revenue, financing, partnerships, and regulatory developments.</p><p class="muted">No sourced signals entered yet.</p>`}
];
let activeCoin = 0;
function renderCoin(){ $('coin-tabs').innerHTML = coinPanels.map((p,i)=>`<button role="tab" type="button" data-index="${i}" aria-selected="${i===activeCoin}">${p.name}</button>`).join(''); $('coin-panel').innerHTML=`<div class="coin-content"><h3>${coinPanels[activeCoin].name} <em>[PREVIEW]</em></h3>${coinPanels[activeCoin].body}</div>`; }
$('coin-tabs').addEventListener('click',event=>{const button=event.target.closest('button[data-index]');if(button){activeCoin=Number(button.dataset.index);renderCoin();}}); renderCoin();
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
 const blob=new Blob([JSON.stringify({format:'ai-trading-desk-preview-v3',exportedAt:new Date().toISOString(),...records},null,2)],{type:'application/json'});
 const link=document.createElement('a'); link.href=URL.createObjectURL(blob); link.download='ai-trading-desk-preview-v3.json'; link.click();
 setTimeout(()=>URL.revokeObjectURL(link.href),1000);
});
