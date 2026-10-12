/* Sourced RWA market screen on the sector board. */
'use strict';
globalThis.RwaMarket = (() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const usd = value => Number.isFinite(value) ? new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',notation:'compact',maximumFractionDigits:2}).format(value) : '—';
  const controllers = new WeakMap();
  function mount(container, force=false, onSelect=null) {
    if (!container) return;
    if (controllers.has(container)) { if (force) controllers.get(container)(); return; }
    let data=null, order='balanced', loading=false;
    function draw() {
      const coins=[...(data?.coins || [])];
      if (order==='cap') coins.sort((a,b)=>b.market_cap-a.market_cap);
      if (order==='volume') coins.sort((a,b)=>b.volume_24h-a.volume_24h);
      container.innerHTML=`<div class="rwa-toolbar"><label>Sort leaders <select data-rwa-sort><option value="balanced">Market cap + volume</option><option value="cap">Market cap</option><option value="volume">24h volume</option></select></label><button type="button" data-rwa-refresh ${loading?'disabled':''}>${loading?'Refreshing…':'Refresh market data'}</button></div>
        <p>Up to 10 from a reviewed RWA and tokenization pool, requiring a verified Coinbase USD or USDC market in normal trading, at least $100M circulating market cap and $10M reported 24-hour trading volume. Default order adds market-cap and volume ranks with equal weight; lower is better. Ranks are within the qualifying pool.</p>
        <p role="status">${data?.stale ? escape(data.warning) : loading ? 'Loading reported market data…' : 'Latest successful market snapshot.'} ${data?.fetched_at ? 'Retrieved '+escape(new Date(data.fetched_at).toLocaleString())+'.' : ''} ${data?.coinbase_checked_at ? 'Coinbase markets verified '+escape(new Date(data.coinbase_checked_at).toLocaleString())+'.' : ''}</p>
        <div class="table-wrap"><table class="data-table rev-tbl"><thead><tr><th>Coin</th><th>RWA / tokenization role</th><th>Market cap (USD)</th><th>24h volume (USD)</th><th>Cap / volume rank</th><th>Coinbase market</th><th>Source updated</th></tr></thead><tbody>${coins.map(c=>`<tr><th><a href="/board?view=rwa&amp;symbol=${encodeURIComponent(c.symbol)}&amp;asset=crypto#detail-card" data-rwa-coin="${escape(c.symbol)}" title="Show ${escape(c.symbol)} chart below">${escape(c.symbol)}</a><small>${escape(c.name)}</small></th><td>${escape(c.role)}</td><td>${usd(c.market_cap)}</td><td>${usd(c.volume_24h)}</td><td>${escape(c.cap_rank)} / ${escape(c.volume_rank)}</td><td>${escape(c.coinbase_product)}</td><td>${escape(new Date(c.updated_at).toLocaleString())}</td></tr>`).join('') || '<tr><td colspan="7">Market observations unavailable.</td></tr>'}</tbody></table></div>
        <p class="footnote">${data?.eligible_count ?? '—'} tokens passed the screen. <a href="https://www.coingecko.com/en/categories/real-world-assets-rwa" target="_blank" rel="noopener noreferrer">Source: CoinGecko RWA category</a>. Market cap means circulating token value, not FDV or tokenized assets under management. Volume is reported across markets in dollars, not venue candle volume or guaranteed executable liquidity. Infrastructure and governance tokens do not confer ownership of the assets they support. Gold-backed tokens represent a different exposure. Restricted funds, stablecoins and tokenized stock wrappers are outside this pool. Coinbase verification checks public Exchange markets; availability for your account or region may differ. Charts use Kraken candles.</p>`;
      container.querySelector('[data-rwa-sort]').value=order;
    }
    async function refresh(force=false) {
      if (loading) return;
      loading=true; draw();
      try {
        const response=await fetch('/api/rwa-market'+(force?'?force=1':''), {signal:AbortSignal.timeout(30000)});
        if (!response.ok) throw new Error('Market refresh unavailable');
        const payload=await response.json();
        if (!Array.isArray(payload?.coins) || !payload.coins.every(c=>
          c && typeof c.id==='string' && typeof c.symbol==='string' && typeof c.name==='string' &&
          typeof c.url==='string' && c.url.startsWith('https://www.coingecko.com/en/coins/') &&
          Number.isFinite(c.market_cap) && c.market_cap>0 && Number.isFinite(c.volume_24h) && c.volume_24h>0 &&
          Number.isFinite(Date.parse(c.updated_at)) &&
          typeof c.coinbase_product==='string' && [c.symbol+'-USD',c.symbol+'-USDC'].includes(c.coinbase_product) &&
          Number.isFinite(Date.parse(payload.coinbase_checked_at)))) throw new Error('Invalid market response');
        data=payload;
      } catch (error) {
        // Without a valid verification response, do not display unverified tokens.
        data={...(data || {}), coins:[], eligible_count:0, coinbase_checked_at:null, stale:true, warning:'Market or Coinbase verification unavailable. The token list is withheld until verification succeeds.'};
      } finally {loading=false;draw();}
    }
    container.addEventListener('change', event=>{if(event.target.matches('[data-rwa-sort]')){order=event.target.value;draw();}});
    container.addEventListener('click', event=>{
      const coin=event.target.closest('[data-rwa-coin]');
      if (coin) {
        if (onSelect && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && (event.button==null || event.button===0)) {
          event.preventDefault();onSelect(coin.dataset.rwaCoin);
        }
        return;
      }
      if(event.target.closest('[data-rwa-refresh]'))refresh(true);
    });
    controllers.set(container,()=>refresh(true));refresh();
  }
  return {mount};
})();
