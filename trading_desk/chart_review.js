/* Dated discretionary research. Loading this view never refreshes accounts or sends orders. */
(() => {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = value => Number.isFinite(value) ? '$' + value.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2}) : 'Unavailable';
  const number = value => Number.isFinite(value) ? value.toFixed(2) : 'Unavailable';
  const time = value => {
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? 'Time unavailable' : date.toLocaleString('en-US', {timeZone:'America/New_York', month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit'}) + ' ET';
  };
  const safeURL = value => {
    if (typeof value !== 'string') return '';
    if (value.startsWith('/chart-review-assets/') && !value.includes('..')) return value;
    try { const url = new URL(value); return url.protocol === 'https:' ? url.href : ''; } catch { return ''; }
  };
  const link = (label, url) => safeURL(url) ? `<a href="${escape(safeURL(url))}" target="_blank" rel="noopener">${escape(label)} ↗</a>` : escape(label);
  function chart(item) {
    const url = safeURL(item.url);
    return url ? `<figure class="chart-review-figure"><a href="${escape(url)}" target="_blank" rel="noopener"><img loading="lazy" src="${escape(url)}" alt="${escape(item.title)}"></a><figcaption>${escape(item.state)} · captured ${escape(item.captured)} · ${link('Open full-size chart', url)}</figcaption></figure>` : '';
  }
  function comparison(asset) {
    const review = asset.comparison;
    if (!review) return '';
    const find = url => (asset.charts || []).find(item => item.url === url);
    const panel = (url, label) => {
      const item = find(url);
      return `<section><h4>${escape(label)}</h4>${item ? chart(item) : '<p class="chart-review-meta">Saved capture unavailable; no substitute drawing.</p>'}</section>`;
    };
    return `<section class="chart-review-comparison" aria-label="${escape(asset.symbol)} original and updated charts"><div class="chart-review-pair">${panel(review.original_url,review.original_label || 'Original drawing')}${panel(review.updated_url,review.updated_label || 'Updated drawing')}</div><div class="chart-review-verdict"><h4>Which count fits better?</h4><p><strong>${escape(review.verdict)}</strong></p><p><strong>What changed:</strong> ${escape(review.changes)}</p><p><strong>Why:</strong> ${escape(review.reason)}</p><p><strong>Evidence:</strong> ${escape(review.evidence)}</p><p><strong>Next test:</strong> ${escape(review.confirmation)}</p><p class="chart-review-meta">${escape(review.limits)}</p></div></section>`;
  }
  function futures(asset) {
    const future = asset.futures;
    if (!future) return '';
    const quote = future.quote || {};
    const capture = (asset.charts || []).find(item => item.url === future.chart_url);
    return `<section class="chart-review-futures" aria-label="${escape(future.symbol)} futures evidence"><h4>${escape(future.symbol)} · separate futures evidence</h4><p class="chart-review-price">${Number.isFinite(quote.price) ? quote.price.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) + ' points' : 'Quote unavailable'}</p><p class="chart-review-meta">${escape(quote.source)} · ${escape(quote.session)} · source timestamp ${escape(time(quote.time))}. ${escape(quote.delay)}.</p><p>${escape(future.summary)}</p><p class="chart-review-meta">${escape(future.baseline)} ${escape(future.source_note)}</p><table class="chart-review-table"><thead><tr><th>Futures points</th><th>Observed reference / review test</th></tr></thead><tbody>${(future.points || []).map(([level,note])=>`<tr><th>${escape(level)}</th><td>${escape(note)}</td></tr>`).join('')}</tbody></table>${capture ? chart(capture) : '<p class="chart-review-meta">Futures capture unavailable.</p>'}<p class="chart-review-meta">${escape(future.chart_note)}</p></section>`;
  }
  function sessionPlan(plan) {
    if (!plan || !Array.isArray(plan.holdings)) return '';
    const today = new Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    const historical = today > plan.date;
    return `<section class="chart-review-intro chart-review-plan" id="next-session-plan" aria-label="Next-session trading plan"><span class="chart-review-kicker">${historical ? 'HISTORICAL PLAN — REFRESH REQUIRED' : 'NEXT-SESSION PLAN'} · ${escape(plan.date)}</span><h2>${escape(plan.title)}</h2><p><strong>${escape(plan.stance)}</strong></p><p class="chart-review-meta">Evidence ${escape(time(plan.observed_at))} · ${escape(plan.evidence_note)}</p><div class="chart-review-plan-grid">${plan.holdings.map(item=>{const q=item.quote||{};return `<article class="chart-review-plan-card"><h3>${escape(item.symbol)}</h3><p class="chart-review-price">${money(q.price)}</p><p class="chart-review-meta">${escape(q.source)} · ${escape(q.session)} · ${escape(time(q.time))}. ${escape(q.delay)}.</p><p><strong>Hold:</strong> ${escape(item.hold)}</p><p><strong>Sell / trim — first:</strong> ${escape(item.sell_first)}</p><p><strong>Sell / trim — next:</strong> ${escape(item.sell_next)}</p><p><strong>Warning:</strong> ${escape(item.warning)}</p><p><strong>Bottom hypothesis invalid below:</strong> ${escape(item.invalidation)}</p><p class="chart-review-meta">${escape(item.count_note)}</p></article>`;}).join('')}</div><h3>Market confirmation levels</h3><div class="chart-review-plan-grid">${(plan.confirmation||[]).map(item=>`<article class="chart-review-plan-card"><h4>${escape(item.symbol)}</h4><p>${escape(item.snapshot)}</p><p><strong>Hold / reclaim:</strong> ${escape(item.support)}</p><p><strong>Confirmation:</strong> ${escape(item.upside)}</p><p><strong>Failure:</strong> ${escape(item.failure)}</p><p class="chart-review-meta">${escape(item.note)}</p></article>`).join('')}</div><h3>How to use the plan</h3><ol>${(plan.execution||[]).map(item=>`<li>${escape(item)}</li>`).join('')}</ol><p><strong>${escape(plan.event?.title)}</strong> · ${escape(time(plan.event?.time))} · ${link('Official calendar',plan.event?.source)}</p><p class="chart-review-meta">${escape(plan.limits)}</p></section>`;
  }
  function intradayChart(bars, interval, references, formatPrice, symbol) {
    if (!Number.isFinite(interval) || interval <= 0) return '';
    const usable = bars.filter(bar => Array.isArray(bar) && bar.length === 5
      && bar.every(Number.isFinite) && bar[2] >= Math.max(bar[1], bar[4])
      && bar[3] <= Math.min(bar[1], bar[4]));
    if (usable.length < 2) return '';

    const observedLow = Math.min(...usable.map(bar => bar[3]));
    const observedHigh = Math.max(...usable.map(bar => bar[2]));
    const pad = Math.max((observedHigh - observedLow) * 0.13, observedHigh * 0.0001);
    const levels = references.filter(level => Number.isFinite(level.value)
      && level.value >= observedLow - pad && level.value <= observedHigh + pad);
    const low = Math.min(observedLow, ...levels.map(level => level.value)) - pad;
    const high = Math.max(observedHigh, ...levels.map(level => level.value)) + pad;
    const left = 76, right = 738, top = 15, bottom = 195;
    const start = usable[0][0] - interval / 2;
    const end = usable.at(-1)[0] + interval / 2;
    const x = timestamp => left + (timestamp - start) / (end - start) * (right - left);
    const y = price => bottom - (price - low) / (high - low) * (bottom - top);
    const width = Math.min(10, Math.max(2, (x(start + interval) - left) * 0.68));
    const axisPrice = value => value.toLocaleString('en-US', {maximumFractionDigits: 2});
    const yAxis = Array.from({length: 5}, (_, index) => {
      const price = low + (high - low) * index / 4;
      const position = y(price).toFixed(1);
      return `<line class="wave-grid-line" x1="${left}" x2="${right}" y1="${position}" y2="${position}"/><text x="${left - 9}" y="${position}" text-anchor="end" dy=".33em">${escape(axisPrice(price))}</text>`;
    }).join('');
    const labelTime = timestamp => new Date(timestamp * 1000).toLocaleTimeString('en-US', {
      timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit'
    });
    const xAxis = [0, 1, 2].map(index => {
      const tick = Math.round((usable.length - 1) * index / 2);
      return `<text x="${x(usable[tick][0]).toFixed(1)}" y="215" text-anchor="${['start','middle','end'][index]}">${escape(labelTime(usable[tick][0]))}</text>`;
    }).join('');
    const guides = levels.map(({value, label}) => {
      const position = y(value).toFixed(1);
      return `<line class="wave-threshold" x1="${left}" x2="${right}" y1="${position}" y2="${position}"><title>${escape(label)} · ${escape(formatPrice(value))}</title></line>`;
    }).join('');
    const candles = usable.map(([timestamp, open, highPrice, lowPrice, close]) => {
      const cx = x(timestamp);
      const direction = close >= open ? 'wave-up' : 'wave-down';
      const bodyTop = Math.min(y(open), y(close));
      return `<g class="${direction}"><line x1="${cx.toFixed(1)}" x2="${cx.toFixed(1)}" y1="${y(highPrice).toFixed(1)}" y2="${y(lowPrice).toFixed(1)}"/><rect x="${(cx - width / 2).toFixed(1)}" y="${bodyTop.toFixed(1)}" width="${width.toFixed(1)}" height="${Math.max(1, Math.abs(y(close) - y(open))).toFixed(1)}"><title>${escape(labelTime(timestamp))} ET · open ${escape(formatPrice(open))} · high ${escape(formatPrice(highPrice))} · low ${escape(formatPrice(lowPrice))} · close ${escape(formatPrice(close))}</title></rect></g>`;
    }).join('');
    const legend = levels.map(({value, label}) => `${escape(label)} ${escape(formatPrice(value))}`).join(' · ');
    return `<figure class="wave-candle-figure"><svg class="wave-candle-chart" viewBox="0 0 768 228" role="img" aria-label="${escape(symbol)} observed intraday candles, Eastern time">${yAxis}${xAxis}${guides}${candles}</svg>${legend ? `<figcaption>Dashed lines · ${legend}</figcaption>` : ''}</figure>`;
  }

  function intradayReview(asset, update, price) {
    const row = update?.assets?.[asset.symbol];
    if (!row || !Array.isArray(row.bars) || !row.review) return '';
    const chart = intradayChart(row.bars, row.interval_seconds, row.references || [], price, asset.symbol);
    if (!chart) return '';
    const change = Number.isFinite(row.change_pct)
      ? ` · ${row.change_pct >= 0 ? '+' : ''}${row.change_pct.toFixed(2)}% vs ${asset.symbol === 'BTC' ? 'midnight ET' : 'prior session close'}`
      : '';
    const gaps = row.missing_inside > 0 ? ` · ${row.missing_inside} missing candles` : '';
    return `<section class="wave-intraday" aria-label="${escape(asset.symbol)} intraday Elliott Wave update">
      <h4>Intraday update · ${escape(update.date)}</h4>
      <p class="chart-review-price">${price(row.last)}<small>${escape(change)}</small></p>
      <p class="chart-review-meta">${escape(row.source)} · ${escape(row.session)} · through ${escape(time(row.as_of))}. ${escape(row.delay)}${escape(gaps)}.</p>
      ${chart}
      <p>${escape(row.review.observation)}</p>
      <div class="wave-paths">
        <p><strong>Recovery path</strong>${escape(row.review.recovery)}</p>
        <p><strong>Extension or invalidation</strong>${escape(row.review.extension)}</p>
      </div>
      <p class="chart-review-meta">Scenario review with ${escape(update.model)}. The drawings below retain their original evidence dates.</p>
    </section>`;
  }

  function card(asset, full, update) {
    const quote = asset.quote || {};
    const price = value => asset.unit === 'points' ? (Number.isFinite(value) ? value.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' points' : 'Unavailable') : money(value);
    const daily = asset.daily;
    const current = asset.charts?.[0];
    const change = Number.isFinite(asset.change_pct) ? ` · ${asset.change_pct >= 0 ? '+' : ''}${asset.change_pct.toFixed(2)}% ${escape(asset.change_baseline || 'vs previous regular close')}` : '';
    // Compared captures stay visible together; history excludes those same URLs.
    const shown = new Set(asset.comparison ? [asset.comparison.original_url, asset.comparison.updated_url] : [current?.url]);
    if (asset.futures?.chart_url) shown.add(asset.futures.chart_url);
    const history = (asset.charts || []).filter(item => !shown.has(item.url));
    const dailyText = daily ? `<p class="chart-review-meta">Completed ${escape(daily.date)}: close ${money(daily.close)} · range ${money(daily.low)}–${money(daily.high)} · volume ${Number(daily.volume).toLocaleString()} (${number(daily.volume_ratio)}× prior 20 sessions). SMA20 / 50 / 200: ${money(daily.sma20)} / ${money(daily.sma50)} / ${money(daily.sma200)}. 5 / 21 sessions: ${number(daily.five_session_pct)}% / ${number(daily.twentyone_session_pct)}%.</p>` : '';
    const levels = `<table class="chart-review-table"><thead><tr><th>Level</th><th>Review test</th></tr></thead><tbody>${(asset.levels || []).map(([level, test])=>`<tr><th>${escape(level)}</th><td>${escape(test)}</td></tr>`).join('')}</tbody></table>`;
    const conditions = `<p><strong>Confirmation:</strong> ${escape(asset.confirmation)}</p><p><strong>Invalidation / warning:</strong> ${escape(asset.invalidation)}</p>`;
    const otherCharts = history.length
      ? `<details><summary>${history.length} other ${escape(asset.symbol)} drawing captures</summary>${history.map(chart).join('')}</details>`
      : '';
    return `<article class="chart-review-asset ${asset.comparison ? 'chart-review-compared' : ''}" id="chart-${escape(asset.symbol)}"><div class="chart-review-heading"><h3>${escape(asset.symbol)}</h3><span class="chart-review-status">${escape(asset.status)}</span></div>${intradayReview(asset, update, price)}<p class="chart-review-price">${price(quote.price)}<small>${change}</small></p><p class="chart-review-meta">${escape(quote.source)} · ${escape(quote.session)} · source timestamp ${escape(time(quote.time))}. ${escape(quote.delay)}.</p><p>${escape(asset.summary)}</p>${asset.benchmark_note ? `<p>${escape(asset.benchmark_note)}</p>` : ''}${asset.comparison ? comparison(asset) : current ? chart(current) : '<p class="chart-review-meta">Saved chart unavailable; no drawing has been invented.</p>'}${futures(asset)}${full ? dailyText : ''}${levels}${conditions}${full ? `<p><strong>Company / market evidence:</strong> ${escape(asset.fundamentals)}</p><p>${(asset.sources || []).map(([label,url])=>link(label,url)).join(' · ')}</p><p class="chart-review-meta">${escape(asset.chart_note)}</p>` : ''}${otherCharts}${full ? '' : `<p><a href="/chart-review#chart-${escape(asset.symbol)}">Read full ${escape(asset.symbol)} analysis ↗</a></p>`}</article>`;
  }
  function render(data, full) {
    const assetLinks = data.assets.map(asset => `<a href="#chart-${escape(asset.symbol)}">${escape(asset.symbol)}</a>`).join('');
    const navigation = `<div class="chart-review-intro chart-review-scenarios">
      <h2>Elliott Wave scenarios</h2>
      <p class="chart-review-meta">${data.intraday_update ? `Intraday update ${escape(data.intraday_update.date)} · Baseline drawings ${escape(data.date)}.` : `Saved ${escape(data.date)} chart review.`} Select a ticker for its working count, alternate paths, and confirmation and invalidation levels.</p>
      <nav class="chart-review-navigation" aria-label="Elliott Wave scenarios">${assetLinks}${full ? '' : '<a href="/chart-review">Full gallery ↗</a>'}</nav>
    </div>`;
    const stale = new Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date()) !== data.date;
    return `${navigation}<div class="chart-review-intro"><span class="chart-review-kicker">DAILY REVIEW · ${escape(data.date)} · ${stale ? 'HISTORICAL SNAPSHOT — REFRESH REQUIRED' : 'DATED MARKET SNAPSHOT'}</span><h2>Watch first. Review the evidence.</h2><p><strong>${escape(data.owner_decision)}</strong></p><p>${escape(data.market)}</p><p class="chart-review-meta">Completed-session snapshot ${escape(time(data.market_observed_at))}. ${escape(data.data_note)}</p>${data.comparison_review_at ? `<p><strong>Original versus updated review · ${escape(time(data.comparison_review_at))}</strong><br>${escape(data.comparison_note)}</p>` : ''}<div class="chart-review-events">${(data.events || []).map(([label,date,url])=>`<p><strong>${escape(label)}</strong> · ${escape(date)} · ${link('Issuer evidence',url)}</p>`).join('')}</div>${full ? '<p><a href="/board?view=review">Back to Daily Review ↗</a> · <a href="/">AI Trading Desk v3 ↗</a></p>' : `<p><a href="/chart-review">Open all ${(data.assets || []).reduce((total, asset) => total + (asset.charts || []).length, 0)} saved drawings and full analysis ↗</a></p>`}</div>${sessionPlan(data.next_session_plan)}<div class="chart-review-grid ${full?'chart-review-full':''}">${(data.assets || []).map(asset=>card(asset,full,data.intraday_update)).join('')}</div>${full ? `<section class="chart-review-intro"><h2>Daily review checklist</h2><ol>${(data.daily_checklist||[]).map(item=>`<li>${escape(item)}</li>`).join('')}</ol><p class="chart-review-meta">Research references only. No approved stops, account sizes, broker orders or guaranteed future prices are created by this page. Earlier chart captures remain dated history.</p></section>` : ''}`;
  }
  const targets = Array.from(document.querySelectorAll('[data-chart-review]'));
  if (!targets.length) return;
  fetch('/chart_review.json', {cache:'no-store'}).then(response=>{
    if (!response.ok) throw new Error('Saved review unavailable');
    return response.json();
  }).then(data=>{
    if (!Array.isArray(data.assets) || !data.date) throw new Error('Invalid saved review');
    for (const target of targets) target.innerHTML = render(data, target.dataset.chartReview === 'full');
    // Ticker anchors do not exist until the saved manifest finishes loading.
    const anchor = location.hash.slice(1);
    if (anchor.startsWith('chart-')) document.getElementById(anchor)?.scrollIntoView();
  }).catch(()=>{for(const target of targets) target.textContent='Saved chart review unavailable. No previous prices or scenarios have been substituted.';});
})();
