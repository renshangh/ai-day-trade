'use strict';
globalThis.RangeDiscovery = (() => {
  const mounted = new WeakMap();
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const price = value => Number.isFinite(value) ? '$' + value.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:value < 10 ? 4 : 2}) : 'Unavailable';
  const dollars = value => Number.isFinite(value) ? '$' + new Intl.NumberFormat('en-US', {notation:'compact', maximumFractionDigits:1}).format(value) : 'Unavailable';
  const stamp = value => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Unavailable';
  function matches(row, threshold=15) {
    return Number.isFinite(row?.range_ratio) && Number.isInteger(row?.rounded_ratio)
      && row.rounded_ratio >= threshold;
  }
  function volumePasses(row) {
    // Recheck the observations rather than trusting a saved pass/fail badge.
    if (!Number.isFinite(row?.volume_usd)) return false;
    if (row.asset==='crypto') return row.volume_usd>=1_000_000;
    if (row.stock_mode==='two_year' && !(Number.isFinite(row.volume_usd_5) && row.volume_usd_5>=100_000_000 && Number.isFinite(row.volume_shares_5) && row.volume_shares_5>=2_000_000)) return false;
    return row.asset==='stock' && row.volume_usd>=100_000_000 &&
      Number.isFinite(row.volume_shares) && row.volume_shares>=2_000_000;
  }
  function isLong(row) { return row?.asset==='stock' && row.stock_mode==='two_year'; }
  function baseQuality(row) {
    if (row?.qualification_version!==7 || row.quality_pass!==true || !Number.isInteger(row.completed_cycles)) return false;
    if (isLong(row)) return row.lookback_days===730 && row.annual_cycles?.length===2 && row.annual_cycles.every(n=>n>=1) &&
      row.quarter_containment?.length===8 && row.quarter_containment.every(n=>n>=.5) && row.containment>=.8 && row.stability<=.6 &&
      row.last_close>=row.support && row.last_close<=row.resistance;
    return row.recent_range_pass===true && row.completed_cycles>=1;
  }
  function qualityPasses(row) { return baseQuality(row) && row.completed_cycles>=(isLong(row)?3:2); }
  function qualifies(row, threshold=15) {
    return matches(row, threshold) && volumePasses(row) && qualityPasses(row);
  }
  function needsReview(row, threshold=15) {
    return row?.asset==='stock' && !isLong(row) && matches(row,threshold) && volumePasses(row) && baseQuality(row) && row.completed_cycles===1;
  }
  function historyChart(row) {
    const points=row.daily_closes;
    if(!Array.isArray(points) || points.length<2 || !points.every(p=>Array.isArray(p) && Number.isFinite(Date.parse(p[0])) && Number.isFinite(p[1]) && p[1]>0)) return '';
    const stamps=points.map(p=>Date.parse(p[0])), prices=points.map(p=>p[1]);
    const low=Math.min(...prices,row.support), high=Math.max(...prices,row.resistance), pad=(high-low)*.1;
    const bottom=low-pad, top=high+pad, y=p=>(top-p)/(top-bottom)*230;
    const x=t=>(t-stamps[0])/(stamps.at(-1)-stamps[0])*900;
    const path=points.map((p,i)=>(i?'L':'M')+x(stamps[i]).toFixed(2)+','+y(p[1]).toFixed(2)).join(' ');
    return `<figure class="rd-history"><figcaption><strong><a href="/board?view=range-discovery&symbol=${encodeURIComponent(row.symbol)}&asset=${row.asset}#detail-card" data-rd-symbol="${esc(row.symbol)}" data-rd-asset="${row.asset}">${esc(row.symbol)} · View detailed chart ↓</a></strong> · Support ${price(row.support)} · Resistance ${price(row.resistance)} · Last close ${price(row.last_close)}</figcaption>
      <div class="rd-price-plot"><div class="rd-price-axis"><span>${price(top)}</span><span>Price (USD)</span><span>${price(bottom)}</span></div>
      <svg viewBox="0 0 900 230" preserveAspectRatio="none" role="img" aria-label="${esc(row.symbol)} actual daily closing prices, measured support and resistance">
      <rect x="0" y="${y(row.resistance)}" width="900" height="${y(row.support)-y(row.resistance)}" class="rd-range-band"/>
      <path d="M0 ${y(row.support)}H900 M0 ${y(row.resistance)}H900" class="rd-range-lines"/>
      <path d="${path}" class="rd-close-line"/></svg></div>
      <div class="rd-date-axis"><span>${esc(points[0][0])}</span><span>Date · daily closes · adjusted prices</span><span>${esc(points.at(-1)[0])}</span></div></figure>`;
  }
  function mount(container, options={}) {
    if (!container) return;
    if (mounted.has(container)) {
      const existing=mounted.get(container);existing.options={...existing.options,...options};return existing;
    }
    const controller={options};
    let selectedKey='', selectionId='';
    const keyOf=row=>row.asset+':'+row.symbol;
    function choose(row, scroll=true) {
      if(!row)return;
      selectedKey=keyOf(row);
      selectionId=(data?.started_at||'')+':'+selectedKey;
      controller.options.onSelect?.(row,{scroll,scanStartedAt:data?.started_at});
    }
    function chooseDefault() {
      if(data?.status!=='complete' || !controller.options.onSelect)return;
      const visible=(data.rows||[]).filter(r=>(market==='both' || r.asset===(market==='stocks'?'stock':'crypto')) &&
        (r.asset==='crypto' || (r.stock_mode||'45_day')===stockMode));
      const initial=controller.options.initialSymbol;
      const initialAsset=controller.options.initialAsset;
      const wanted=visible.find(r=>keyOf(r)===selectedKey) || (!selectedKey && visible.find(r=>r.symbol===initial && (!initialAsset || r.asset===initialAsset))) ||
        visible.filter(r=>qualifies(r,threshold)).sort((a,b)=>(b.ranking_score||0)-(a.ranking_score||0))[0] || visible.find(r=>needsReview(r,threshold));
      if(wanted && selectionId!==(data.started_at||'')+':'+keyOf(wanted)){choose(wanted,false);draw();}
    }
    let data=null, error='', submitting=false, timer=null;
    let market='both', threshold=15, stockMode='45_day', selectionTouched=false;
    container.classList.add('range-discovery');
    function draw() {
      const running = submitting || data?.status === 'running';
      const long=stockMode==='two_year';
      const all = (data?.rows || []).filter(r => matches(r, threshold) &&
        (market === 'both' || r.asset === (market === 'stocks' ? 'stock' : 'crypto')) &&
        (r.asset==='crypto' || (r.stock_mode||'45_day')===stockMode));
      const rows = all.filter(r => qualifies(r, threshold)).sort((a,b)=>(b.ranking_score||0)-(a.ranking_score||0));
      const review = all.filter(r=>needsReview(r,threshold)).sort((a,b)=>(b.ranking_score||0)-(a.ranking_score||0));
      const rejected = all.filter(r => !qualifies(r, threshold) && !needsReview(r,threshold));
      const scope = data ? `${data.checked} / ${data.total} checked` : 'No discovery loaded';
      const status = data?.status === 'running' ? 'Scanning fresh market observations…' :
        data?.status === 'complete' ? 'Scan complete' : data?.status === 'failed' ? 'Scan unavailable' : 'Ready when you are';
      container.innerHTML = `
        <div class="rd-intro"><div><span class="rd-eyebrow">14-DAY CRYPTO · ${long?'2-YEAR':'45-DAY'} STOCKS</span>
          <h3>Find a repeatable trading range</h3><p>Require repeated swings inside a stable box, sufficient volume and a wide enough range.</p></div>
          <span class="rd-mode">Research only</span></div>
        <p class="rd-method">Current crypto focus: <strong>NEAR · DOT</strong>. Discovery does not change the paper-trading watchlist.</p>
        <form data-rd-form class="rd-toolbar">
          <label>Markets<select data-rd-market ${running?'disabled':''}><option value="both">Stocks + crypto</option><option value="crypto">Crypto / Coinbase</option><option value="stocks">Stocks</option></select></label>
          <label>Stock range<select data-rd-stock-mode ${running?'disabled':''}><option value="45_day">45 days · recent ranges</option><option value="two_year">2 years · long-term boxes</option></select></label>
          <label>Rounded minimum<input data-rd-threshold type="number" min="1" max="100" step="1" value="${threshold}" ${running?'disabled':''}> <span>%</span></label>
          <button class="primary" type="submit" ${running?'disabled':''}>${running?'Discovering…':'Discover candidates'}</button>
        </form>
        <p class="rd-method">Range ratio = (resistance − support) ÷ support × 100. Round up, then require ≥ ${threshold}%. For example, 14.56% → 15% passes the width filter only.</p>
        <div class="rd-summary"><div><b>${rows.length}</b><span>qualified range candidates</span></div><div><b>${review.length}</b><span>stocks needing review</span></div><div><b>${rejected.length}</b><span>disqualified wide moves</span></div><div><b>${esc(scope)}</b><span>${esc(status)}</span></div></div>
        <p class="rd-status" role="status" aria-live="polite">${esc(error || status)}${data?.started_at?' · Started '+esc(stamp(data.started_at)):''}${data?.completed_at?' · Completed '+esc(stamp(data.completed_at)):''}</p>
        <p class="rd-method"><strong>Stocks:</strong> ${long?'730 calendar days of daily prices. Require at least 3 full swings, at least 1 in each year, boundary movement ≤60%, 80% overall containment, 50% containment in every quarter, and the latest close inside. A full swing within the latest 126 sessions improves ranking. Both 5- and 20-session averages must reach $100M and 2M shares.':'Two full swings qualify; exactly one full swing goes to Needs review. Boundary movement ≤60%, liquidity, containment and latest close inside the box remain required. Recent full swings improve ranking; start-to-end movement above 40% and unusually wide ranges are cautions.'} A fresh bounce is required before entry.</p>
        <p class="rd-method"><strong>Crypto unchanged:</strong> two full swings, start-to-end movement ≤40%, boundary movement ≤60%, and one full swing within the latest 7 days, with at least 80% of recent closes inside the box.</p>
        <p class="rd-method">Required dollar volume: crypto ≥ $1M / 24h; stocks ≥ $100M and 2M shares / session. Dollar volume estimates sum each completed candle’s price × traded units.</p>
        <div class="rd-table-wrap"><table data-rd-candidates aria-label="Qualified range trade discovery candidates"><thead><tr><th>Candidate</th><th>Support</th><th>Resistance</th><th>Range ratio</th><th>Volume estimate</th><th>Range checks</th><th>Data through</th></tr></thead>
          <tbody>${rows.map(row=>{
            const crypto=row.asset==='crypto';
            const liquid=volumePasses(row);
            const url='/board?view=range-discovery&symbol='+encodeURIComponent(row.symbol)+'&asset='+row.asset+'#detail-card';
            const paper=crypto ? row.paper_supported===false?'Not on Alpaca paper':row.paper_supported===true?'Alpaca paper supported':'Paper availability unverified' : 'Earnings / news review required';
            return `<tr><th><a href="${url}" data-rd-symbol="${esc(row.symbol)}" data-rd-asset="${row.asset}" ${selectedKey===keyOf(row)?'aria-current="true"':''}>${esc(row.symbol)}</a><small>${esc(row.source)} · ${esc(row.interval)}</small><small>${esc(paper)}</small></th>
              <td>${price(row.support)}</td><td>${price(row.resistance)}</td>
              <td><strong>${row.range_ratio.toFixed(2)}%</strong><small>rounded up: ${row.rounded_ratio}%</small></td>
              <td><span class="rd-badge ${liquid?'rd-pass':'rd-warn'}">${liquid?'Volume passes':'Low volume'}</span><small>${dollars(row.volume_usd)} / ${crypto?'24h':isLong(row)?'session (20-day avg)':'session'}</small>${isLong(row)?'<small>5-day avg: '+dollars(row.volume_usd_5)+' / session</small>':''}${Number.isFinite(row.volume_shares)?'<small>'+new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:1}).format(row.volume_shares)+' shares / session</small>':''}</td>
              <td><span class="rd-badge rd-pass">Range checks pass</span><small>${row.completed_cycles} completed full swings</small>${isLong(row)?'<small>Annual halves: '+esc(row.annual_cycles.join(' / '))+' · Latest 126 sessions: '+row.recent_six_month_cycles+' full swings</small>':''}<small>${esc([...(row.warnings || []),...(row.advisories || [])].join('; ') || 'Fresh spread, depth and event review still required')}</small></td>
              <td>${esc(stamp(row.last_bar_at))}</td></tr>`;
          }).join('') || `<tr><td colspan="7" class="rd-empty">${running?'Checking the discovery pool. Qualified ranges will appear as symbols finish.':data?.status==='idle'||!data?'Choose your markets and select Discover candidates.':'No candidates pass all width, volume and repeated-swing checks. Disqualified moves are listed below.'}</td></tr>`}</tbody></table></div>
        ${long?'':`<section data-rd-review><h4>Needs review — one completed stock swing (${review.length})</h4>
          <p>These stocks pass the mandatory range and liquidity checks but have only one completed full swing. They are excluded from qualified candidates and are not entry signals.</p>
          <div class="rd-table-wrap"><table data-rd-review-table aria-label="One-swing stocks needing review"><thead><tr><th>Stock</th><th>Support / resistance</th><th>Range ratio</th><th>Recent session volume</th><th>Review notes</th></tr></thead><tbody>${review.map(row=>`<tr><th><a href="/board?view=range-discovery&symbol=${encodeURIComponent(row.symbol)}&asset=stock#detail-card" data-rd-symbol="${esc(row.symbol)}" data-rd-asset="stock">${esc(row.symbol)}</a><small>Rank score ${esc(row.ranking_score)} · not a return forecast</small></th><td>${price(row.support)}–${price(row.resistance)}<small>Last close ${price(row.last_close)}</small></td><td>${row.range_ratio.toFixed(2)}%</td><td>${dollars(row.volume_usd)} / session<small>${esc(new Intl.NumberFormat('en-US',{notation:'compact'}).format(row.volume_shares))} shares</small></td><td>1 completed full swing; ${row.recent_completed_cycles} recent swings.<small>${esc((row.advisories||[]).join('; '))}</small></td></tr>`).join('') || '<tr><td colspan="5">No one-swing stocks pass the other mandatory checks.</td></tr>'}</tbody></table></div>
        </section>`}
        ${long?`<details class="rd-details" data-rd-long-charts open><summary>Review two-year price charts (${rows.filter(isLong).length})</summary><p>Actual adjusted daily closes. Shaded bands mark measured support and resistance; temporary breaks remain visible.</p>${rows.filter(isLong).map(historyChart).join('') || '<p>No qualified long-term ranges to chart yet.</p>'}</details>`:''}
        <details class="rd-details" data-rd-rejected><summary>Disqualified moves — not candidates (${rejected.length})</summary>
          <p>These moves pass the width filter but fail other required checks. They are excluded from discovery candidates.</p>
          <div class="rd-table-wrap"><table data-rd-disqualified aria-label="Disqualified price moves"><thead><tr><th>Symbol</th><th>Measured boundaries</th><th>Range ratio</th><th>Completed full swings</th><th>Checks and disqualification</th></tr></thead><tbody>${rejected.map(row=>{
            const reasons=[...(row.warnings||[])];
            if (!volumePasses(row)) reasons.push('Insufficient or unavailable dollar volume');
            if (row.qualification_version!==7) reasons.push('Re-scan required to verify longer windows and recent swings');
            if (row.qualification_version===7 && row.completed_cycles<(isLong(row)?3:row.asset==='stock'?1:2)) reasons.push(`${row.completed_cycles} full swings observed; require at least ${isLong(row)?3:row.asset==='stock'?1:2}`);
            return `<tr><th><a href="/board?view=range-discovery&symbol=${encodeURIComponent(row.symbol)}&asset=${row.asset}#detail-card" data-rd-symbol="${esc(row.symbol)}" data-rd-asset="${row.asset}">${esc(row.symbol)}</a><small>${esc(row.source)}</small></th><td>${price(row.support)}–${price(row.resistance)}<small>Last completed close: ${price(row.last_close)}</small></td><td>${row.range_ratio.toFixed(2)}%</td><td>${Number.isInteger(row.completed_cycles)?row.completed_cycles:'Unverified'}</td><td>${esc([...new Set(reasons)].join('; ') || 'Range-quality evidence unavailable')}<small>${Number.isFinite(row.stability)?'Boundary movement: '+(100*row.stability).toFixed(1)+'% (maximum 60%). ':''}${Number.isFinite(row.drift)?'Start-to-end movement: '+(100*row.drift).toFixed(1)+(row.asset==='stock'?'% (ranking factor). ':'% (maximum 40%). '):''}${Number.isInteger(row.recent_completed_cycles)?'Recent 7 days: '+row.recent_completed_cycles+' full swings; '+(100*row.recent_containment).toFixed(1)+'% of closes inside.':''}</small></td></tr>`;
          }).join('') || '<tr><td colspan="5">No disqualified wide moves in this scan.</td></tr>'}</tbody></table></div></details>
        <details class="rd-details"><summary>Scan coverage and unavailable data (${data?.omitted?.length || 0})</summary>
          <p>${data?.crypto_pool?.length || 23} reviewed Coinbase USD coins and ${data?.stock_pool?.length || 52} reviewed stocks. This is a bounded research pool, not the whole market. Current matches use the filters above; scanned markets: ${esc(data?.market || 'not scanned')}.</p>
          <p>Crypto pool: ${esc((data?.crypto_pool || []).join(', ') || 'Available after loading scan coverage')}.</p><p>Stock pool: ${esc((data?.stock_pool || []).join(', ') || 'Available after loading scan coverage')}.</p>
          ${(data?.omitted || []).map(r=>`<p>${esc(r.symbol)} · ${esc(r.reason)}</p>`).join('') || '<p>No unavailable observations reported.</p>'}</details>
        <p class="rd-footnote">14 calendar days for crypto; ${long?'730 days / daily consolidated SIP prices for stocks, split/dividend adjusted. Complete daily history is mandatory; missing or delisted histories are omitted.':'45 calendar days / 30-minute Schwab prices for stocks. Both markets require 80% recent containment.'} A recent full swing is required for crypto and improves stock ranking. Crypto uses completed 4-hour Coinbase candles; ${long?'stocks use completed daily consolidated SIP candles':'stocks use completed 30-minute regular-session Schwab candles'} and a verified session calendar. Volume is a venue-specific estimate: crypto requires $1M / 24h; stocks require 2M shares and $100M per session. A discovery match is not an entry signal. Fees, spreads, depth, events and breakout risk still need review. No orders are placed.</p>`;
      container.querySelector('[data-rd-market]').value=market;
      container.querySelector('[data-rd-stock-mode]').value=stockMode;
    }
    function validate(payload) {
      if (!payload || !['idle','running','complete','failed'].includes(payload.status) || !Array.isArray(payload.rows)) throw new Error('Discovery response unavailable');
      if (!payload.rows.every(r=>r && /^[A-Z0-9.]{1,12}$/.test(r.symbol) && ['crypto','stock'].includes(r.asset)
        && Number.isFinite(r.support) && r.support>0 && Number.isFinite(r.resistance) && r.resistance>r.support
        && Number.isFinite(r.range_ratio) && Number.isInteger(r.rounded_ratio) && Number.isFinite(Date.parse(r.last_bar_at)))) throw new Error('Invalid discovery observations');
      return payload;
    }
    async function read() {
      try {
        const response=await fetch('/api/range-discovery', {signal:AbortSignal.timeout(15000)});
        if (!response.ok) throw new Error('Could not load discovery status');
        data=validate(await response.json());
        if(!selectionTouched && ['45_day','two_year'].includes(data.stock_mode)) stockMode=data.stock_mode;
        error='';draw();chooseDefault();
        if (data.status==='running') timer=setTimeout(read, 2000);
      } catch (e) {error='Discovery connection unavailable. Previously loaded results retain their original dates. Retrying connection…';draw();timer=setTimeout(read, 5000);}
    }
    async function start() {
      if (submitting || data?.status==='running') return;
      clearTimeout(timer);submitting=true;error='';draw();
      try {
        const response=await fetch('/api/range-discovery', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({market,threshold,stock_mode:stockMode}),signal:AbortSignal.timeout(15000)});
        if (!response.ok) throw new Error('Could not start discovery');
        data=validate(await response.json());submitting=false;draw();chooseDefault();
        if (data.status==='running') timer=setTimeout(read, 1000);
      } catch (e) {submitting=false;error=e.message;draw();}
    }
    container.addEventListener('click',event=>{
      const anchor=event.target.closest?.('[data-rd-symbol]');
      if(!anchor || !controller.options.onSelect || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)return;
      const row=(data?.rows||[]).find(r=>r.symbol===anchor.getAttribute('data-rd-symbol') && r.asset===anchor.getAttribute('data-rd-asset'));
      if(!row)return;
      event.preventDefault();choose(row,true);draw();
    });
    container.addEventListener('submit' , event=>{if(event.target.matches('[data-rd-form]')){event.preventDefault();start();}});
    container.addEventListener('change', event=>{
      if (event.target.matches('[data-rd-stock-mode]')) {stockMode=event.target.value;selectionTouched=true;}
      if (event.target.matches('[data-rd-market]')) market=event.target.value;
      if (event.target.matches('[data-rd-threshold]')) threshold=Math.max(1,Math.min(100,Math.ceil(Number(event.target.value)||15)));
      draw();chooseDefault();
    });
    Object.assign(controller,{read,start});mounted.set(container,controller);draw();read();return controller;
  }
  if (typeof document!=='undefined') document.addEventListener('DOMContentLoaded',()=>mount(document.getElementById('range-discovery-home')));
  return {mount,matches,volumePasses,qualityPasses,qualifies,needsReview,historyChart};
})();
if (typeof module!=='undefined') module.exports=globalThis.RangeDiscovery;
