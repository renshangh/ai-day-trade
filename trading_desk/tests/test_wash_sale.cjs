const fs = require('fs');
const vm = require('vm');
const test = require('node:test');
const assert = require('node:assert/strict');

const source = fs.readFileSync(new URL('../app.js', `file://${__filename}`), 'utf8');
const start = source.indexOf('function renderWashSaleAlert(');
const end = source.indexOf('\nfunction renderSchwabTrade(', start);
const context = {
  esc: value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
  fmtPx: value => Number.isFinite(value) ? `$${value.toFixed(2)}` : '—',
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);

test('warning renders matched account trade and advisory scope', () => {
  const html = context.renderWashSaleAlert({wash_sale: {
    ok: true, level: 'warning', message: 'Possible wash sale', symbol: 'LITE',
    matched_trades: [{trade_date: '2026-10-01', account: '***3652', side: 'SELL', quantity: 5, symbol: 'LITE', price: 100}],
  }});
  assert.match(html, /Wash-sale review required/);
  assert.match(html, /\*\*\*3652/);
  assert.match(html, /other brokers/);
});

test('unavailable scan never renders as safe', () => {
  const html = context.renderWashSaleAlert({wash_sale: {ok: false, message: 'history unavailable'}});
  assert.match(html, /Wash-sale check unavailable/);
  assert.match(html, /history unavailable/);
});
