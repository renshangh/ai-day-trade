'use strict';
// Shared by the desk and sector board. Crypto links represent associated tokens,
// not company equity. Unlisted entities must never get invented ticker links.
(function (root) {
  const layers = [
  [
    "Custody and wallet controls",
    [
      [
        "Coinbase Prime",
        "https://finance.yahoo.com/quote/COIN/",
        "COIN",
        "stock"
      ],
      [
        "BNY",
        "https://finance.yahoo.com/quote/BK/",
        "BK",
        "stock"
      ],
      [
        "Anchorage Digital",
        null,
        "No public ticker",
        "unlisted"
      ],
      [
        "Fireblocks",
        null,
        "No public ticker",
        "unlisted"
      ]
    ]
  ],
  [
    "Money issuance and movement",
    [
      [
        "Circle",
        "https://finance.yahoo.com/quote/CRCL/",
        "CRCL",
        "stock"
      ],
      [
        "Tether",
        "https://www.coingecko.com/en/coins/tether",
        "USDT",
        "crypto"
      ],
      [
        "Paxos",
        "https://www.coingecko.com/en/coins/pax-dollar",
        "USDP",
        "crypto"
      ],
      [
        "Stripe/Bridge",
        null,
        "No public ticker",
        "unlisted"
      ],
      [
        "Ripple",
        "https://www.coingecko.com/en/coins/ripple",
        "XRP",
        "crypto"
      ],
      [
        "JPMorgan Kinexys",
        "https://finance.yahoo.com/quote/JPM/",
        "JPM",
        "stock"
      ]
    ]
  ],
  [
    "Tokenization and asset administration",
    [
      [
        "Ondo",
        "https://www.coingecko.com/en/coins/ondo",
        "ONDO",
        "crypto"
      ],
      [
        "Securitize",
        "https://finance.yahoo.com/quote/SECZ/",
        "SECZ",
        "stock"
      ],
      [
        "Superstate",
        null,
        "No public ticker",
        "unlisted"
      ],
      [
        "WisdomTree",
        "https://finance.yahoo.com/quote/WT/",
        "WT",
        "stock"
      ],
      [
        "Franklin Templeton",
        "https://finance.yahoo.com/quote/BEN/",
        "BEN",
        "stock"
      ],
      [
        "DTCC",
        null,
        "No public ticker",
        "unlisted"
      ]
    ]
  ],
  [
    "Trading and lending",
    [
      [
        "Coinbase",
        "https://finance.yahoo.com/quote/COIN/",
        "COIN",
        "stock"
      ],
      [
        "Uniswap/UniswapX",
        "https://www.coingecko.com/en/coins/uniswap",
        "UNI",
        "crypto"
      ],
      [
        "Aave",
        "https://www.coingecko.com/en/coins/aave",
        "AAVE",
        "crypto"
      ]
    ]
  ],
  [
    "Institutional settlement and collateral",
    [
      [
        "Broadridge",
        "https://finance.yahoo.com/quote/BR/",
        "BR",
        "stock"
      ],
      [
        "DTCC",
        null,
        "No public ticker",
        "unlisted"
      ],
      [
        "JPMorgan Kinexys",
        "https://finance.yahoo.com/quote/JPM/",
        "JPM",
        "stock"
      ],
      [
        "Canton",
        "https://www.coingecko.com/en/coins/canton",
        "CCCAUSD",
        "crypto"
      ]
    ]
  ],
  [
    "Blockchain settlement networks",
    [
      [
        "Ethereum/L2s",
        "https://www.coingecko.com/en/coins/ethereum",
        "ETH",
        "crypto"
      ],
      [
        "Solana",
        "https://www.coingecko.com/en/coins/solana",
        "SOL",
        "crypto"
      ],
      [
        "Avalanche",
        "https://www.coingecko.com/en/coins/avalanche-2",
        "AVAX",
        "crypto"
      ],
      [
        "Stellar",
        "https://www.coingecko.com/en/coins/stellar",
        "XLM",
        "crypto"
      ],
      [
        "XRP Ledger",
        "https://www.coingecko.com/en/coins/ripple",
        "XRP",
        "crypto"
      ],
      [
        "NEAR",
        "https://www.coingecko.com/en/coins/near",
        "NEAR",
        "crypto"
      ],
      [
        "Cardano",
        "https://www.coingecko.com/en/coins/cardano",
        "ADA",
        "crypto"
      ]
    ]
  ],
  [
    "Data and cross-chain connectivity",
    [
      [
        "Chainlink",
        "https://www.coingecko.com/en/coins/chainlink",
        "LINK",
        "crypto"
      ],
      [
        "Circle CCTP",
        "https://finance.yahoo.com/quote/CRCL/",
        "CRCL",
        "stock"
      ]
    ]
  ],
  [
    "Agent commerce",
    [
      [
        "Coinbase x402/Bazaar",
        "https://finance.yahoo.com/quote/COIN/",
        "COIN",
        "stock"
      ],
      [
        "NEAR AI",
        "https://www.coingecko.com/en/coins/near",
        "NEAR",
        "crypto"
      ],
      [
        "Olas",
        "https://www.coingecko.com/en/coins/autonolas",
        "OLAS",
        "crypto"
      ],
      [
        "Virtuals",
        "https://www.coingecko.com/en/coins/virtual-protocol",
        "VIRTUAL",
        "crypto"
      ],
      [
        "Fetch.ai",
        "https://www.coingecko.com/en/coins/fetch-ai",
        "FET",
        "crypto"
      ]
    ]
  ]
];
  const escape = value => String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[ch]));
  function chartHref(symbol, kind) {
    return `/board?view=ai-crypto&symbol=${encodeURIComponent(symbol)}&asset=${kind}#detail-card`;
  }
  function marketLink(name, url, ticker, kind) {
    if (!url) return `<span class="crypto-infra-unlisted">${escape(name)} <small>(${escape(ticker)})</small></span>`;
    return `<a class="onchain-symbol" href="${chartHref(ticker, kind)}" data-chart-symbol="${escape(ticker)}" data-chart-asset="${kind}" title="Show ${escape(ticker)} chart">${escape(name)}${name === ticker ? "" : ` <small>(${escape(ticker)})</small>`}</a> <a class="onchain-market" href="${escape(url)}" target="_blank" rel="noopener noreferrer" aria-label="${escape(name)} market page" title="${kind === 'stock' ? 'Stock quote' : 'Associated token; not company equity'}">↗</a>`;
  }
  function render() {
    return `<div class="crypto-infra-wrap"><table class="crypto-infra-table"><thead><tr><th scope="col">Infrastructure layer</th><th scope="col">Companies and platforms</th></tr></thead><tbody>${layers.map(([layer, entries]) => `<tr><th scope="row">${escape(layer)}</th><td>${entries.map(entry => marketLink(...entry)).join('<span class="crypto-infra-separator">, </span>')}</td></tr>`).join('')}</tbody></table></div>`;
  }
  const theme = 'Onchain Finance Buildout';
  const reviewLayers = [
    {name:'Digital Money', watch:'CRCL / USDC, USDT, PYUSD, bank tokens', metrics:['USDC supply','Stablecoin transaction volume','USDC market share'], question:'Is digital money growing, and who earns the economics?'},
    {name:'Onchain Markets', watch:'COIN / Base, HOOD, Ondo, Securitize, Kraken / xStocks', metrics:['Tokenized asset value','Tokenized market volume'], question:'Are tokenized stocks, bonds, funds and RWAs gaining actual usage?'},
    {name:'TradFi Bridge', watch:'Citi, JPM, BNY, DTCC, ICE / NYSE, Nasdaq', metrics:['Live institutional deployments','Settlement volume'], question:'Which partnerships, custody, settlement or regulatory developments changed access?'},
    {name:'Infrastructure Rails', watch:'Ethereum, Base, Solana, Arbitrum, Chainlink, Canton', metrics:['Settlement volume','Network fees'], question:'Where are assets and settlement moving, and which rails capture fees?'},
    {name:'Agentic Finance', watch:'x402, agent wallets, machine-to-machine payments', metrics:['Paid agent transactions','Active paying agents'], question:'Is there evidence of repeat paid usage beyond announcements?'}
  ];
  const stock = (name, symbol) => [name, `https://finance.yahoo.com/quote/${symbol}/`, symbol, 'stock'];
  const crypto = (name, symbol, id) => [name, `https://www.coingecko.com/en/coins/${id}`, symbol, 'crypto'];
  const watchEntries = [
    [stock('Circle','CRCL'), crypto('USDC','USDC','usd-coin'), crypto('Tether','USDT','tether'), stock('PayPal','PYPL'), crypto('PYUSD','PYUSD','paypal-usd')],
    [stock('Coinbase / Base','COIN'), stock('Robinhood','HOOD'), crypto('Ondo','ONDO','ondo'), stock('Securitize','SECZ')],
    [stock('Citi','C'), stock('JPMorgan','JPM'), stock('BNY','BK'), stock('ICE / NYSE','ICE'), stock('Nasdaq','NDAQ')],
    [crypto('Ethereum','ETH','ethereum'), stock('Base / Coinbase','COIN'), crypto('Solana','SOL','solana'), crypto('Arbitrum','ARB','arbitrum'), crypto('Chainlink','LINK','chainlink'), crypto('Canton','CCCAUSD','canton')],
    [stock('x402 / Coinbase','COIN')]
  ];
  const chartAssets = new Map([...layers.flatMap(([,entries])=>entries), ...watchEntries.flat()].filter(entry=>entry[1]).map(entry=>[entry[2], entry[3]]));
  function assetKind(symbol) { return chartAssets.get(symbol); }
  function marketUrl(symbol) { return [...layers.flatMap(([,entries])=>entries), ...watchEntries.flat()].find(entry=>entry[2] === symbol && entry[1])?.[1]; }
  function today() {
    const parts = new Intl.DateTimeFormat('en-US', {timeZone:'America/New_York', year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const part = name => parts.find(p => p.type === name).value;
    return `${part('year')}-${part('month')}-${part('day')}`;
  }
  function previousDay(date) {
    const day = new Date(`${date}T12:00:00Z`);
    day.setUTCDate(day.getUTCDate() - 1);
    return day.toISOString().slice(0,10);
  }
  function validSource(source) {
    try { return ['https:','http:'].includes(new URL(source).protocol); } catch { return false; }
  }
  function validateEntry(entry) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(entry.date || '') || !Number.isFinite(Date.parse(`${entry.date}T12:00:00Z`)) || new Date(`${entry.date}T12:00:00Z`).toISOString().slice(0,10) !== entry.date) return 'Choose a valid review date.';
    if (!reviewLayers.some(layer => layer.name === entry.layer)) return 'Choose a review layer.';
    if (!entry.title?.trim() || !entry.detail?.trim() || !entry.impact?.trim()) return 'Record the development, evidence, and portfolio implications.';
    if (!validSource(entry.source)) return 'Use an http or https source URL.';
    if (!['Announcement','Pilot','Live usage','Regulatory development'].includes(entry.evidence)) return 'Choose the evidence type.';
    if (entry.value !== '' && entry.value != null && (!Number.isFinite(Number(entry.value)) || Number(entry.value) < 0 || !entry.metric?.trim() || !entry.unit?.trim())) return 'A metric needs a non-negative value, name and unit.';
    return null;
  }
  // Only compare matching, sourced observations on consecutive calendar dates.
  // A gap is not yesterday; missing values never become zero or carry forward.
  function metricDelta(entry, observations) {
    if (entry.value === '' || entry.value == null || !Number.isFinite(Number(entry.value)) || !entry.metric || !entry.unit || !validSource(entry.source)) return null;
    const matches = observations.filter(row => row.theme === theme && row.date === previousDay(entry.date) && row.layer === entry.layer && row.metric === entry.metric && row.unit === entry.unit && row.value !== '' && row.value != null && Number.isFinite(Number(row.value)) && validSource(row.source));
    if (matches.length !== 1) return null;
    const prior = Number(matches[0].value), change = Number(entry.value) - prior;
    return {change, percent:prior === 0 ? null : change / prior * 100, prior:matches[0]};
  }
  function renderEntry(entry, observations) {
    const delta = metricDelta(entry, observations);
    const value = entry.value !== '' && entry.value != null && Number.isFinite(Number(entry.value)) ? `${escape(entry.metric)}: ${escape(entry.value)} ${escape(entry.unit)}` : 'Metric unavailable';
    const comparison = delta ? `${delta.change > 0 ? '+' : ''}${Number(delta.change.toPrecision(6))} ${escape(entry.unit)}${delta.percent == null ? ' · percentage unavailable (zero baseline)' : ` (${delta.percent > 0 ? '+' : ''}${delta.percent.toFixed(2)}%)`} since yesterday · <a href="${escape(delta.prior.source)}" target="_blank" rel="noopener noreferrer">Yesterday’s source</a>` : 'Day-over-day comparison unavailable: needs one matching sourced metric yesterday.';
    return `<article class="onchain-entry"><h4>${escape(entry.title)}</h4><p><small>${escape(entry.date)} · ${escape(entry.evidence || 'Evidence type unspecified')}</small></p><p>${escape(entry.detail || '')}</p><p><b>${value}</b><br><small>${comparison}</small></p><p><b>COIN / CRCL and winners / losers:</b> ${escape(entry.impact || 'No implications recorded.')}</p>${validSource(entry.source) ? `<a href="${escape(entry.source)}" target="_blank" rel="noopener noreferrer">Evidence source ↗</a>` : '<span>Source unavailable</span>'}</article>`;
  }
  function renderReview(observations = [], date = today(), editable = false) {
    const rows = observations.filter(row => row.theme === theme && row.date === date);
    return `<div class="onchain-review"><h3>What changed since yesterday?</h3><p>How quickly is the financial system actually moving onchain, and who is capturing the economics?</p><div class="onchain-anchors"><b>Anchor securities:</b> ${marketLink(...stock('COIN','COIN'))} · ${marketLink(...stock('CRCL','CRCL'))}<span>Review growth, competition, revenue capture and risks.</span></div><label class="onchain-date">Review date (Eastern time)<input class="onchain-date-input" type="date" value="${escape(date)}" required></label><p class="onchain-status" role="status">${rows.length ? `${rows.length} sourced entries for ${escape(date)}` : `No sourced review recorded for ${escape(date)}. Missing data does not mean no change.`}</p><div class="onchain-grid">${reviewLayers.map((layer, i) => `<article class="onchain-layer"><h3>${escape(layer.name)}</h3><p class="onchain-watch">${escape(layer.watch)}</p><p class="onchain-tickers">${watchEntries[i].map(entry=>marketLink(...entry)).join(" · ")}</p><p>${escape(layer.question)}</p><p><small>Track: ${escape(layer.metrics.join(' · '))}</small></p>${rows.filter(row => row.layer === layer.name).map(row => renderEntry(row, observations)).join('') || '<p class="onchain-empty">Not reviewed for this date.</p>'}</article>`).join('')}</div>${editable ? `<details class="onchain-editor"><summary>Record a sourced daily entry</summary><p>Enter comparable metrics in consistent units and from the same scope / method. Announcements and pilots are separate from live usage. Add a separate entry for each metric.</p><form class="onchain-form"><label>Date<input name="date" type="date" required value="${escape(date)}"></label><label>Layer<select name="layer">${reviewLayers.map(layer=>`<option>${escape(layer.name)}</option>`).join('')}</select></label><label>Evidence type<select name="evidence">${['Announcement','Pilot','Live usage','Regulatory development'].map(kind=>`<option>${kind}</option>`).join('')}</select></label><label>What changed?<input name="title" required maxlength="160"></label><label>Evidence / adoption / regulatory details<textarea name="detail" required maxlength="1500"></textarea></label><label>COIN / CRCL implications; who gains or loses?<textarea name="impact" required maxlength="1000"></textarea></label><label>Metric name (optional)<input name="metric" list="onchain-metrics" maxlength="100"><datalist id="onchain-metrics">${[...new Set(reviewLayers.flatMap(layer=>layer.metrics))].map(metric=>`<option value="${escape(metric)}"></option>`).join('')}</datalist></label><label>Observed value (optional)<input name="value" type="number" min="0" step="any"></label><label>Unit / scope (e.g. USD, USDC supply)<input name="unit" maxlength="100"></label><label>Source URL<input name="source" type="url" required maxlength="2000"></label><button type="submit">Save daily entry</button></form></details>` : '<p><a href="/#coins">Record daily evidence on the main desk ↗</a></p>'}<details class="onchain-legacy"><summary>Full infrastructure reference map · eight original layers</summary>${render()}</details></div>`;
  }
  function mount(container, {getObservations = () => [], onSave = null, onSelect = null} = {}) {
    let date = today();
    const refresh = () => { container.innerHTML = renderReview(getObservations(), date, !!onSave); };
    container.addEventListener('change', event => {
      if (event.target.matches('.onchain-date-input') && event.target.value) {date = event.target.value; refresh();}
    });
    container.addEventListener('submit', event => {
      if (!event.target.matches('.onchain-form')) return;
      event.preventDefault();
      const entry = {theme, ...Object.fromEntries(new FormData(event.target))};
      const error = validateEntry(entry);
      if (error) { container.querySelector('.onchain-status').textContent = error; return; }
      onSave(entry); date = entry.date; refresh();
    });
    container.addEventListener('click', event => {
      const link = event.target.closest('[data-chart-symbol]');
      if (!link || !onSelect || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button) return;
      event.preventDefault();
      onSelect(link.dataset.chartSymbol, link.dataset.chartAsset);
    });
    refresh();
    return {refresh};
  }
  root.CryptoFinanceInfra = { layers, render, chartHref, assetKind, marketUrl, watchEntries, theme, reviewLayers, today, validateEntry, metricDelta, renderReview, mount };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.CryptoFinanceInfra;
})(globalThis);
