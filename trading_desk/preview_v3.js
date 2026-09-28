'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const scores = ['AI Economy','Market Risk','Opportunity','Altcoin Health','AI Infrastructure'];
$('scorecard').innerHTML = scores.map(name => `<div class="score"><div class="name">${name} Score</div><div class="value">—</div><small>Awaiting verified inputs</small></div>`).join('');
$('economy-inputs').innerHTML = ['AI infrastructure','Enterprise AI','AI agent adoption','AI crypto','Real-world assets','Market liquidity'].map(name => `<div class="factor"><span>${name}</span><span>—</span></div>`).join('');
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
$('thesis-list').innerHTML=theses.map(([name,statement,watch])=>`<article class="record"><h3>${name}</h3><p>${statement}</p><dl><div><dt>Confidence / trend</dt><dd>Unrated · awaiting review</dd></div><div><dt>Watch</dt><dd>${watch}</dd></div><div><dt>Supporting evidence</dt><dd>None recorded</dd></div><div><dt>Contradicting evidence</dt><dd>None recorded</dd></div><div><dt>Review history</dt><dd>No reviews yet</dd></div></dl></article>`).join('');
const key = 'ai-trading-desk-preview-v3';
let records;
try { const data=JSON.parse(localStorage.getItem(key)); records={opportunities:Array.isArray(data?.opportunities)?data.opportunities:[],decisions:Array.isArray(data?.decisions)?data.decisions:[]}; } catch {records={opportunities:[],decisions:[]};}
function save(){localStorage.setItem(key,JSON.stringify(records));}
function field(label,value){return `<div><dt>${label}</dt><dd>${esc(value || '—')}</dd></div>`;}
function renderRecords(){
 $('opportunity-list').innerHTML=records.opportunities.length?records.opportunities.map((r,i)=>`<article class="record"><h3>${esc(r.name)} <em>${esc(r.stage)}</em></h3><dl>${field('Catalyst',r.catalyst)}${field('Risks',r.risks)}${field('Increase confidence',r.confirm)}${field('Invalidate thesis',r.invalidate)}</dl><p><button class="remove" data-kind="opportunities" data-index="${i}">Remove</button></p></article>`).join(''):'<div class="empty">No opportunities recorded yet.</div>';
 $('decision-list').innerHTML=records.decisions.length?records.decisions.map((r,i)=>`<article class="record"><h3>${esc(r.decision)}</h3><dl>${field('Recorded',r.recorded)}${field('Rationale',r.rationale)}${field('Evidence',r.evidence)}${field('Review date',r.review)}${field('Outcome',r.outcome)}</dl><p><button class="remove" data-kind="decisions" data-index="${i}">Remove</button></p></article>`).join(''):'<div class="empty">No decisions recorded yet.</div>';
}
for(const [id,kind] of [['opportunity-form','opportunities'],['decision-form','decisions']]) $(id).addEventListener('submit',event=>{event.preventDefault();const form=event.currentTarget;const data=Object.fromEntries(new FormData(form));if(kind==='decisions')data.recorded=new Date().toISOString().slice(0,10);records[kind].unshift(data);save();form.reset();renderRecords();});
document.addEventListener('click',event=>{const button=event.target.closest('.remove');if(!button)return;const kind=button.dataset.kind;records[kind].splice(Number(button.dataset.index),1);save();renderRecords();});
renderRecords();
