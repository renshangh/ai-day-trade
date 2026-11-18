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
  function card(asset, full) {
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
    return `<article class="chart-review-asset ${asset.comparison ? 'chart-review-compared' : ''}" id="chart-${escape(asset.symbol)}"><div class="chart-review-heading"><h3>${escape(asset.symbol)}</h3><span class="chart-review-status">${escape(asset.status)}</span></div><p class="chart-review-price">${price(quote.price)}<small>${change}</small></p><p class="chart-review-meta">${escape(quote.source)} · ${escape(quote.session)} · source timestamp ${escape(time(quote.time))}. ${escape(quote.delay)}.</p><p>${escape(asset.summary)}</p>${asset.benchmark_note ? `<p>${escape(asset.benchmark_note)}</p>` : ''}${asset.comparison ? comparison(asset) : current ? chart(current) : '<p class="chart-review-meta">Saved chart unavailable; no drawing has been invented.</p>'}${futures(asset)}${full ? dailyText + levels + `<p><strong>Confirmation:</strong> ${escape(asset.confirmation)}</p><p><strong>Invalidation / warning:</strong> ${escape(asset.invalidation)}</p><p><strong>Company / market evidence:</strong> ${escape(asset.fundamentals)}</p><p>${(asset.sources || []).map(([label,url])=>link(label,url)).join(' · ')}</p><p class="chart-review-meta">${escape(asset.chart_note)}</p>${history.length ? `<details><summary>${history.length} other ${escape(asset.symbol)} drawing captures</summary>${history.map(chart).join('')}</details>` : ''}` : `<p>${escape(asset.levels?.slice(0, 3).map(([level,test])=>level + ': ' + test).join(' '))}</p><p><a href="/chart-review#chart-${escape(asset.symbol)}">Read full ${escape(asset.symbol)} analysis and drawings ↗</a></p>`}</article>`;
  }
  function render(data, full) {
    const navigation = `<nav class="chart-review-navigation" aria-label="Daily chart comparisons">${(data.assets || []).map(asset=>`<a href="#chart-${escape(asset.symbol)}">${escape(asset.symbol)}</a>`).join(' · ')}</nav>`;
    const stale = new Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date()) !== data.date;
    return `${sessionPlan(data.next_session_plan)}<div class="chart-review-intro"><span class="chart-review-kicker">DAILY REVIEW · ${escape(data.date)} · ${stale ? 'HISTORICAL SNAPSHOT — REFRESH REQUIRED' : 'DATED MARKET SNAPSHOT'}</span><h2>Watch first. Review the evidence.</h2><p><strong>${escape(data.owner_decision)}</strong></p><p>${escape(data.market)}</p><p class="chart-review-meta">Completed-session snapshot ${escape(time(data.market_observed_at))}. ${escape(data.data_note)}</p>${data.comparison_review_at ? `<p><strong>Original versus updated review · ${escape(time(data.comparison_review_at))}</strong><br>${escape(data.comparison_note)}</p>` : ''}${navigation}<div class="chart-review-events">${(data.events || []).map(([label,date,url])=>`<p><strong>${escape(label)}</strong> · ${escape(date)} · ${link('Issuer evidence',url)}</p>`).join('')}</div>${full ? '<p><a href="/board?view=review">Back to Daily Review ↗</a> · <a href="/">AI Trading Desk v3 ↗</a></p>' : `<p><a href="/chart-review">Open all ${(data.assets || []).reduce((total, asset) => total + (asset.charts || []).length, 0)} saved drawings and full analysis ↗</a></p>`}</div><div class="chart-review-grid ${full?'chart-review-full':''}">${(data.assets || []).map(asset=>card(asset,full)).join('')}</div>${full ? `<section class="chart-review-intro"><h2>Daily review checklist</h2><ol>${(data.daily_checklist||[]).map(item=>`<li>${escape(item)}</li>`).join('')}</ol><p class="chart-review-meta">Research references only. No approved stops, account sizes, broker orders or guaranteed future prices are created by this page. Earlier chart captures remain dated history.</p></section>` : ''}`;
  }
  const targets = Array.from(document.querySelectorAll('[data-chart-review]'));
  if (!targets.length) return;
  fetch('/chart_review.json', {cache:'no-store'}).then(response=>{
    if (!response.ok) throw new Error('Saved review unavailable');
    return response.json();
  }).then(data=>{
    if (!Array.isArray(data.assets) || !data.date) throw new Error('Invalid saved review');
    for (const target of targets) target.innerHTML = render(data, target.dataset.chartReview === 'full');
  }).catch(()=>{for(const target of targets) target.textContent='Saved chart review unavailable. No previous prices or scenarios have been substituted.';});
})();
