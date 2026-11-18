/* Read-only BUY/SELL drafts. Never calls a broker preview or order endpoint. */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const dollars = n => n == null ? 'Unavailable' : '$' + (n / 100).toFixed(2);
  // Exact integer cents, including common JSON floating-point account artifacts.
  function toCents(s) {
    if (!/^\d+(?:\.\d{1,2})?$/.test(String(s))) return null;
    const [whole, frac = ''] = String(s).split('.');
    const n = Number(whole) * 100 + Number(frac.padEnd(2, '0'));
    return Number.isSafeInteger(n) ? n : null;
  }
  function calculate(cash, percentage, price) {
    if (![cash, price].every(Number.isSafeInteger) || cash < 0 || price <= 0 || ![25,50,75,100].includes(percentage)) throw Error('Invalid sizing inputs');
    // BigInt prevents multiplication/rounding from buying one extra share.
    const budget = Number(BigInt(cash) * BigInt(percentage) / 100n);
    const quantity = Math.floor(budget / price), cost = quantity * price;
    return {budget, quantity, cost, remaining: cash - cost};
  }
  function sellQuantity(available, percentage) {
    const value = String(available ?? '');
    if (!/^\d+(?:\.\d{1,20})?$/.test(value) || ![25,50,75,100].includes(percentage)) return null;
    const [whole, fraction = ''] = value.split('.');
    const scale = 10n ** BigInt(fraction.length);
    const result = Number((BigInt(whole) * scale + BigInt(fraction || '0')) * BigInt(percentage) / (100n * scale));
    return Number.isSafeInteger(result) ? result : null;
  }
  function washKey(side, symbol, price, selected) {
    const ticker = String(symbol).trim().toUpperCase(), limit = toCents(price);
    if (!selected.length || !['BUY','SELL'].includes(side) || !/^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker) || !limit) return '';
    return side === 'BUY' || selected.includes('3652') ? `${side}:${ticker}:${limit}` : '';
  }
  function buildReview({snapshot, selected, symbol, price, percentage, side = 'BUY', duration = 'DAY', manualCash = {}, confirmations = {}, washReview = null, now = Date.now()}) {
    const age = snapshot ? (now - Date.parse(snapshot.as_of)) / 1000 : Infinity;
    const fresh = age >= 0 && age <= 30;
    const limit = toCents(price), ticker = String(symbol).trim().toUpperCase(), missing = [];
    if (!snapshot) missing.push('Refresh accounts in step 1.');
    if (!selected.length) missing.push('Select at least one account using the Use checkbox in step 1.');
    if (!/^[A-Z][A-Z0-9./-]{0,11}$/.test(ticker)) missing.push('Enter a stock symbol.');
    if (!limit) missing.push('Enter a positive limit price, with at most two decimals.');
    if (![25,50,75,100].includes(percentage)) missing.push('Choose 25%, 50%, 75% or 100%.');
    if (!['BUY','SELL'].includes(side)) missing.push('Choose BUY or SELL.');
    if (!['DAY','GTC'].includes(duration)) missing.push('Choose DAY or GTC.');
    if (snapshot && !fresh) missing.push('Account snapshot expired. Click Refresh & calculate below.');
    const rows = selected.map(account => {
      const a = snapshot?.accounts.find(a => a.account === account);
      let reason = '', cash = null;
      if (!a) reason = 'Account unavailable; refresh accounts.';
      else if (!fresh) reason = 'Expired account snapshot: click Refresh & calculate.';
      else if (side === 'SELL') {
        if (a.holdings_error !== null) return {account, reason:a.holdings_error || 'Holdings coverage unavailable; refresh accounts.'};
        const h = a.holdings?.[ticker];
        if (!h) return {account, reason:'No verified long holding for this symbol.'};
        const quantity = sellQuantity(h.available_to_sell_quantity, percentage);
        const base = {account, held:h.long_quantity, reserved:h.sell_reserved_quantity, available:h.available_to_sell_quantity};
        if (h.available_to_sell_quantity == null) return {...base, reason:'Sellable long shares unavailable; check short positions and commitments.'};
        if (quantity == null || !limit) return {...base, reason:'Enter a limit price and choose a percentage to calculate shares.'};
        const cost = quantity * limit;
        if (!Number.isSafeInteger(cost)) return {...base, reason:'Order value exceeds supported sizing range.'};
        return {...base, quantity, cost, reason:quantity === 0 ? 'Skip: no whole uncommitted shares at this percentage.' : 'Draft · holdings verified · wash-sale check not required outside ***3652 · lot review pending'};
      }
      else if (a.error) reason = a.error;
      else {
        cash = a.verified_cash_cents ?? toCents(manualCash[account] ?? '');
        const confirmation = confirmations[account];
        if (cash == null) reason = 'Enter just-verified net cash for this account in step 1.';
        else if (a.cash_ceiling_cents == null || cash > a.cash_ceiling_cents) reason = 'Entered cash exceeds the current cash ceiling or commitment coverage is unavailable.';
        else if (a.verified_cash_cents == null && (!confirmation || confirmation.value !== manualCash[account] || now - confirmation.at < 0 || now - confirmation.at > 30000)) reason = 'Recheck entered net cash, then click Refresh & calculate to confirm it.';
      }
      if (reason) return {account, reason};
      if (!limit || ![25,50,75,100].includes(percentage)) return {account, cash, reason:'Enter a limit price and choose a percentage to calculate shares.'};
      const result = calculate(cash, percentage, limit);
      return {account, cash, ...result, reason:result.quantity === 0 ? 'Skip: cash budget cannot buy one whole share.' : 'Draft · cash verified'};
    });
    const key = washKey(side, ticker, price, selected);
    const scan = washReview?.key === key ? washReview.result : null;
    const scanAge = scan ? (now - Date.parse(scan.as_of)) / 1000 : Infinity;
    const scanFresh = scanAge >= 0 && scanAge <= 30;
    const scanUsable = scan?.ok === true && scan.protected_account === '3652' &&
      scan.side === side && scan.symbol === ticker && toCents(scan.limit_price) === limit && scanFresh;
    const washMessage = !key ? 'Wash-sale checks apply to all BUY drafts and only SELL drafts in ***3652.' :
      !scan ? '3652 wash-sale check pending.' : !scan.ok ? '3652 wash-sale check unavailable. Refresh & calculate to retry.' :
      !scanUsable ? '3652 wash-sale check expired or mismatched. Refresh & calculate.' : scan.message;
    rows.forEach(row => {
      if (!(row.quantity > 0) || !(side === 'BUY' || (side === 'SELL' && row.account === '3652'))) return;
      row.washBlocked = !scanUsable || scan.possible !== false;
      row.reason = row.washBlocked ? `Blocked · ${washMessage}` : `Draft · 3652 same-symbol scan checked · ${side === 'BUY' ? 'cash verified' : 'holdings verified'} · tax-lot review before execution`;
    });
    // Copy exact legs only when at least one account can support a nonzero
    // draft. Blocked/zero rows remain visible, never become order quantities.
    const canCopy = fresh && missing.length === 0 && rows.some(r => r.quantity > 0 && !r.washBlocked);
    const text = canCopy ? rows.filter(r => r.quantity > 0 && !r.washBlocked).map(r =>
      `${side} ${r.quantity} shares of ${ticker} at $${(limit/100).toFixed(2)} LIMIT ${duration}, NORMAL session, account ***${r.account}.`).join('\n') : '';
    return {fresh, missing, rows, canCopy, text, washKey:key, washMessage};
  }
  if (typeof module !== 'undefined') module.exports = {toCents, calculate, sellQuantity, buildReview, washKey};
  if (typeof document === 'undefined') return;
  let snapshot = null, percentage = null, text = '', refreshing = false;
  let confirmations = {};
  let washReview = null, washAttempt = '', washTimer = null;
  function syncWashCheck(key, selected) {
    if (key === washAttempt) return;
    washAttempt = key; washReview = null;
    clearTimeout(washTimer);
    if (!key) return;
    const [side, symbol, limit] = key.split(':');
    // Debounce input edits; stale responses cannot approve a changed ticket.
    const attempt = {};
    syncWashCheck.attempt = attempt;
    washTimer = setTimeout(async () => {
      let result;
      try {
        const params = new URLSearchParams({side, symbol, price:(Number(limit)/100).toFixed(2), accounts:selected.join(',')});
        const response = await fetch(`/api/schwab/cash-wash-check?${params}`, {cache:'no-store'});
        result = await response.json();
        if (!response.ok) result = {ok:false};
      } catch { result = {ok:false}; }
      if (washAttempt !== key || syncWashCheck.attempt !== attempt) return;
      washReview = {key, result}; render();
    }, 300);
  }
  const names = {'0071':'SEP', '3652':'Individual', '6434':'Individual 401(k)', '2840':'Roth IRA', '1638':'Rollover IRA'};
  function fresh() {
    const age = snapshot ? (Date.now() - Date.parse(snapshot.as_of)) / 1000 : Infinity;
    return age >= 0 && age <= 30;
  }
  function render() {
    const selected = [...document.querySelectorAll('.use-account:checked')].map(e => e.dataset.account);
    const manualCash = Object.fromEntries([...document.querySelectorAll('[data-cash-account]')].map(e => [e.dataset.cashAccount, e.value]));
    const side = $('side').value, selling = side === 'SELL';
    const review = buildReview({snapshot, selected, symbol:$('symbol').value, price:$('price').value, percentage, side, duration:$('duration').value, manualCash, confirmations, washReview});
    document.body.dataset.side = side;
    $('percentage-basis').textContent = selling ? 'Percentage of available long shares in each account' : 'Percentage of each account’s verified net cash';
    $('funding-help').textContent = selling ? 'SELL uses current long holdings less open sell commitments. No cash entry is needed. Percentages apply to the remaining shares, rounded down. This ticket cannot open a short position.' : 'BUY needs verified spendable cash. Enter net cash just checked in Schwab when the API supplies only a cash-balance ceiling.';
    const ticker = $('symbol').value.trim().toUpperCase();
    document.querySelectorAll('[data-holding-account]').forEach(cell => {
      const a = snapshot?.accounts.find(a => a.account === cell.dataset.holdingAccount), h = a?.holdings?.[ticker];
      cell.textContent = a?.holdings_error || (h ? `${h.long_quantity} held · ${h.sell_reserved_quantity} reserved · ${h.available_to_sell_quantity ?? 'unavailable'} available` : 'No verified holding for symbol');
    });
    if (snapshot) {
      const age = Math.max(0, Math.floor((Date.now() - Date.parse(snapshot.as_of)) / 1000));
      $('status').textContent = `Schwab read ${new Date(snapshot.as_of).toLocaleTimeString('en-US', {timeZone:'America/New_York'})} ET · ${age}s old · refresh took ${snapshot.elapsed_seconds}s${review.fresh ? '' : ' · EXPIRED — refresh required'}`;
      $('status').className = review.fresh ? 'good' : 'warning';
    }
    const blocked = review.rows.filter(r => r.quantity == null || r.washBlocked).length;
    $('wash-status').textContent = review.washMessage;
    $('wash-status').className = review.rows.some(r => r.washBlocked) ? 'warning' : 'muted';
    $('sizing-status').textContent = review.missing.length ? review.missing.join(' ') : `${side} draft · ${percentage}% per account · ${blocked ? blocked + ' account(s) blocked; see Status below' : 'whole shares, rounded down'} · no orders sent`;
    $('sizing-status').className = review.missing.length || blocked ? 'warning' : 'good';
    $('result-head').innerHTML = (selling ? ['Account','Held','Open sell reserve','Available','SELL shares','Est. proceeds','Status / next step'] : ['Account','Net cash','Budget','BUY shares','Est. cost','Cash left','Status / next step']).map(label=>`<th>${label}</th>`).join('');
    $('result').innerHTML = review.rows.length ? review.rows.map(r => `<tr><td>***${esc(r.account)}</td>${selling ? `<td>${esc(r.held ?? '—')}</td><td>${esc(r.reserved ?? '—')}</td><td>${esc(r.available ?? '—')}</td><td>${r.quantity ?? '—'}</td><td>${dollars(r.cost)}</td>` : `<td>${dollars(r.cash)}</td><td>${dollars(r.budget)}</td><td>${r.quantity ?? '—'}</td><td>${dollars(r.cost)}</td><td>${dollars(r.remaining)}</td>`}<td class="${r.quantity == null || r.washBlocked ? 'warning' : ''}">${esc(r.reason)}</td></tr>`).join('') : '<tr><td colspan="7">Select accounts with the Use checkboxes in step 1. They will appear here.</td></tr>';
    text = refreshing ? '' : review.text;
    $('copy').disabled = !text;
    $('copy-help').textContent = text ? 'Copies only eligible BUY/SELL lines. Blocked and skipped accounts appear only in the table above. Copying does not send orders.' : review.missing.join(' ') || 'No order draft available: resolve the account status above, or change the percentage/price.';
    $('order-draft').value = text;
    $('calculate').disabled = refreshing;
    if (!text) { $('copy-text').hidden = true; $('copy-text').value = ''; }
    syncWashCheck(snapshot && review.fresh ? review.washKey : '', selected);
  }
  async function refreshCash(reconfirm) {
    if (refreshing) return;
    // Preserve only this open ticket's explicit selections, never cash attestations.
    const selected = new Set([...document.querySelectorAll('.use-account:checked')].map(e => e.dataset.account));
    const drafts = Object.fromEntries([...document.querySelectorAll('[data-cash-account]')].map(e => [e.dataset.cashAccount, e.value]));
    const attestedAt = Date.now();
    confirmations = {}; refreshing = true;
    snapshot = null; render(); $('copied').textContent = '';
    $('accounts').innerHTML = '<tr><td colspan="7">Refreshing linked accounts together…</td></tr>';
    $('refresh').disabled = true; $('status').textContent = 'Reading current cash, holdings and open order commitments…';
    try {
      const response = await fetch('/api/schwab/cash-snapshot?force=1', {cache:'no-store'});
      const result = await response.json();
      if (!response.ok || !result.ok) throw Error(result.error || 'Cash refresh unavailable.');
      snapshot = result;
      $('accounts').innerHTML = result.accounts.map(a => `<tr><td><input type="checkbox" aria-label="Select account ${esc(a.account)}" class="use-account" data-account="${esc(a.account)}" ${selected.has(a.account) ? 'checked' : ''}></td><td>***${esc(a.account)}<br>${esc(names[a.account] || '')}</td><td class="buy-only">${dollars(a.cash_balance_cents)}</td><td class="buy-only">${dollars(a.buy_commitments_cents)}</td><td class="buy-only">${a.verified_cash_cents == null ? `<label>Confirm net cash $<input type="number" min="0" step="0.01" id="cash-${esc(a.account)}" data-cash-account="${esc(a.account)}" aria-label="Verified net cash account ${esc(a.account)}" placeholder="Enter verified cash" value="${esc(drafts[a.account] ?? '')}" ${a.error || a.cash_ceiling_cents == null ? 'disabled' : ''}></label><small>Ceiling ${dollars(a.cash_ceiling_cents)}</small>` : `<span class="good">${dollars(a.verified_cash_cents)}</span>`}</td><td class="sell-only" data-holding-account="${esc(a.account)}"></td><td><span class="buy-only">${esc(a.error || a.cash_source)}</span><span class="sell-only">Schwab long holdings less open sell orders. ${a.account === '3652' ? '3652 wash-sale check required.' : 'No wash-sale check required.'}</span></td></tr>`).join('');
      // Only the explicit Refresh & calculate action renews an attestation.
      // Values survive an ordinary refresh as drafts, never as verified cash.
      if (reconfirm && Date.now() - attestedAt <= 30000) for (const id of selected) {
        if (drafts[id] != null && drafts[id] !== '') confirmations[id] = {value:drafts[id], at:attestedAt};
      }
    } catch (e) { $('status').textContent = e.message; $('status').className = 'warning'; $('accounts').innerHTML = '<tr><td colspan="7">Unavailable. No old balances or holdings reused.</td></tr>'; }
    finally { refreshing = false; $('refresh').disabled = false; render(); }
  }
  $('refresh').addEventListener('click', () => refreshCash(false));
  $('calculate').addEventListener('click', () => refreshCash(true));
  document.addEventListener('input', e => {
    if (e.target.dataset.cashAccount) confirmations[e.target.dataset.cashAccount] = {value:e.target.value, at:Date.now()};
    $('copied').textContent = ''; render();
  });
  document.addEventListener('change', () => { $('copied').textContent = ''; render(); });
  $('percentages').addEventListener('click', e => {
    if (!e.target.dataset.percent) return;
    $('copied').textContent = '';
    percentage = Number(e.target.dataset.percent);
    document.querySelectorAll('[data-percent]').forEach(b => { const active = Number(b.dataset.percent) === percentage; b.classList.toggle('selected', active); b.setAttribute('aria-pressed', String(active)); }); render();
  });
  $('copy').addEventListener('click', async () => {
    render(); // Recheck freshness/attestations at click time, not the last timer tick.
    if (!fresh() || !text) { render(); return; }
    try { await navigator.clipboard.writeText(text); $('copied').textContent = 'Copied order draft. No orders sent.'; }
    catch { $('copy-text').value = text; $('copy-text').hidden = false; $('copy-text').focus(); $('copy-text').select(); $('copied').textContent = 'Automatic clipboard access is unavailable. Copy the selected review text below.'; }
  });
  render();
  setInterval(render, 1000);
})();
