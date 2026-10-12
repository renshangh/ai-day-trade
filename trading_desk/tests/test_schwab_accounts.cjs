const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app.js'), 'utf8');
const context = vm.createContext({
  esc: v => String(v), fmtMoney0: v => v == null ? '—' : `$${v}`,
  fmtPx: v => v == null ? '—' : String(v), fmtPct: v => v == null ? '—' : `${v.toFixed(2)}%`, signClass: () => '',
});
vm.runInContext(source.slice(source.indexOf('function schwabAccountName('), source.indexOf('function renderSchwabTrade(')), context);
const position = (account, quantity, average_price) => ({account, symbol: 'TEST', quantity,
  average_price, short_quantity: 0, market_value: quantity * 20, open_profit_loss: quantity * (20-average_price), current_day_profit_loss: 0});
const book = {combined: true, as_of: 'combined-time', accounts: [
  {label: '***3652', balances: {liquidation_value: 1000, cash_balance: 0}, as_of: 'individual-time'},
  {label: '***6434', balances: {liquidation_value: 4000, cash_balance: 100}, as_of: 'ira-time'},
], positions: [{symbol: 'TEST', quantity: 40, average_price: 12.5, account_positions: [position('***3652',10,5), position('***6434',30,15)]}]};
test('shared tickers retain separate costs, quantities, account weights and timestamps', () => {
  const accounts = context.schwabAccountViews(book);
  assert.equal(accounts[0].positions[0].quantity, 10);
  assert.equal(accounts[1].positions[0].average_price, 15);
  const individual = context.schwabHoldingMetrics(accounts[0].positions[0], 1000);
  const ira = context.schwabHoldingMetrics(accounts[1].positions[0], 4000);
  assert.equal(individual.cost, 50); assert.equal(ira.cost, 450);
  assert.equal(individual.weight, 20); assert.equal(ira.weight, 15);
  assert.equal(individual.profitPct, 300); assert.equal(ira.mark, 20);
  const html = context.renderSchwabAccounts(book);
  assert.match(html, /IRA · \*\*\*6434/); assert.match(html, /Individual · \*\*\*3652/);
  assert.match(html, /individual-time/); assert.match(html, /ira-time/);
  assert.match(html, /registration confirmation pending/);
});
test('missing or zero basis and missing equity stay unavailable', () => {
  for (const avg of [null, 0]) {
    const metrics = context.schwabHoldingMetrics(position('***3652', 10, avg), null);
    assert.equal(metrics.cost, null); assert.equal(metrics.profitPct, null); assert.equal(metrics.weight, null);
  }
  assert.equal(context.schwabHoldingMetrics({...position('***3652',10,5),short_quantity:1},1000).cost,null);
});
test('empty accounts stay visible; hidden holdings still contribute to totals', () => {
  const p = structuredClone(book);
  p.accounts.push({label:'***9999', balances:{}});
  p.positions.push({symbol:'SNDL', account_positions:[{...position('***3652',5,1),symbol:'SNDL'}]});
  p.positions[0].account_positions[1].current_day_profit_loss = null;
  const html = context.renderSchwabAccounts(p);
  assert.match(html, /Holdings value<\/dt><dd>\$300/);
  assert.doesNotMatch(html, /<th scope="row">SNDL/);
  assert.match(html, /Day P\/L<\/dt><dd>—/);
  assert.match(html, /No displayed holdings in this account/);
});
test('single-account response remains scoped and preview requires labeled account choice', () => {
  const accounts=context.schwabAccountViews({account:'***3652',as_of:'single',positions:[position('***3652',10,5)]});
  assert.equal(accounts.length,1); assert.equal(accounts[0].as_of,'single');
  assert.match(source, /select name="account_last4" required/);
  assert.match(source, /Choose an account/);
});
