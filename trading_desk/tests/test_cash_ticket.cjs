const test = require('node:test');
const assert = require('node:assert/strict');
const {toCents, calculate, sellQuantity, buildReview, washKey} = require('../cash_ticket.js');
test('exact cents and whole shares, never round over budget', () => {
  assert.equal(toCents('57.50'),5750);
  assert.equal(toCents('53.60'),5360);
  for (const value of ['', '-1', 'NaN','1.001']) assert.equal(toCents(value),null);
  assert.equal(calculate(557360,100,5750).quantity,96);
  assert.equal(calculate(1760109,100,5750).quantity,306);
  assert.equal(calculate(10000,25,1800).quantity,1);
  assert.equal(calculate(3628,100,5750).quantity,0);
  for (const p of [25,50,75,100]) for (const cash of [0,1,99,10001,557360]) {
    const r = calculate(cash,p,5750);
    assert.ok(r.cost <= r.budget && r.remaining >= 0);
    assert.equal(r.cost,r.quantity*5750);
  }
});
test('zero price, unsupported allocations and unsafe amounts rejected', () => {
  assert.throws(()=>calculate(10000,100,0));
  assert.throws(()=>calculate(10000,30,100));
  assert.throws(()=>calculate(Number.MAX_SAFE_INTEGER+1,100,100));
});

// Synthetic account fixtures, not market observations. Exercise the incomplete
// and expired ticket states that previously erased all rows and disabled Copy.
const now = Date.parse('2026-11-11T10:00:00Z');
function ticket(extra = {}) {
  const input = {now, snapshot:{as_of:new Date(now).toISOString(), accounts:[
    {account:'2840',verified_cash_cents:10000,cash_ceiling_cents:10000,error:null},
    {account:'3652',verified_cash_cents:null,cash_ceiling_cents:20000,error:null}
  ]}, selected:['2840','3652'], symbol:'TEST', price:'18.00', percentage:50, ...extra};
  if (!Object.hasOwn(extra, 'washReview')) input.washReview = {key:washKey(input.side || 'BUY', input.symbol,input.price,input.selected), result:{
    ok:true,possible:false,protected_account:'3652', side:input.side || 'BUY', symbol:input.symbol,
    limit_price:input.price,as_of:new Date(now).toISOString(),message:'No same-symbol conflict found.'
  }};
  return input;
}
test('missing price explains the blocker and retains each selected account', () => {
  const r = buildReview(ticket({price:''}));
  assert.equal(r.rows.length,2);
  assert.deepEqual(r.rows.map(row=>row.account),['2840','3652']);
  assert.match(r.missing.join(' '),/positive limit price/);
  assert.equal(r.canCopy,false);
  assert.equal(r.rows[0].quantity,undefined);
});
test('one unverified account cannot hide another account’s sizes or block review copy', () => {
  const r = buildReview(ticket());
  assert.equal(r.rows[0].quantity,2);
  assert.match(r.rows[1].reason,/Enter just-verified net cash/);
  assert.equal(r.canCopy,true);
  assert.match(r.text,/BUY 2 shares of TEST at \$18.00 LIMIT DAY, NORMAL session, account \*\*\*2840/);
  assert.doesNotMatch(r.text,/BLOCKED|SKIP|3652/);
  assert.doesNotMatch(r.text,/account \*\*\*3652/);
  assert.equal(r.text,'BUY 2 shares of TEST at $18.00 LIMIT DAY, NORMAL session, account ***2840.');
});
test('changing percentages reprices immediately and zero affordable shares is explicit', () => {
  assert.equal(buildReview(ticket({percentage:100})).rows[0].quantity,5);
  assert.equal(buildReview(ticket({percentage:25})).rows[0].quantity,1);
  const r = buildReview(ticket({price:'101'}));
  assert.equal(r.rows[0].quantity,0);
  assert.match(r.rows[0].reason,/Skip/);
  assert.equal(r.canCopy,false); // No leg to copy when every account is blocked/zero.
  assert.equal(r.text,'');
});
test('expired snapshot preserves rows but never calculates or copies stale amounts', () => {
  const r = buildReview(ticket({now:now+31000}));
  assert.equal(r.rows.length,2);
  assert.ok(r.rows.every(row=>row.quantity==null));
  assert.equal(r.canCopy,false);
  assert.equal(r.text,'');
  assert.match(r.missing.join(' '),/Refresh & calculate/);
});
test('draft cash needs a fresh explicit attestation and stays capped after refresh', () => {
  const manualCash = {'3652':'180.00'};
  let r = buildReview(ticket({manualCash}));
  assert.match(r.rows[1].reason,/Recheck entered net cash/);
  r = buildReview(ticket({manualCash,confirmations:{'3652':{value:'180.00',at:now}}}));
  assert.equal(r.rows[1].quantity,5);
  r = buildReview(ticket({manualCash,confirmations:{'3652':{value:'180.00',at:now-31000}}}));
  assert.equal(r.rows[1].quantity,undefined);
  r = buildReview(ticket({manualCash:{'3652':'200.01'},confirmations:{'3652':{value:'200.01',at:now}}}));
  assert.match(r.rows[1].reason,/exceeds/);
  assert.equal(r.rows[1].quantity,undefined);
});
test('bad inputs and no selections provide actionable feedback without throwing', () => {
  assert.match(buildReview(ticket({selected:[]})).missing.join(' '),/Use checkbox/);
  assert.match(buildReview(ticket({symbol:''})).missing.join(' '),/stock symbol/);
  const r = buildReview(ticket({percentage:30}));
  assert.equal(r.canCopy,false);
  assert.equal(r.rows[0].quantity,undefined);
  assert.match(r.missing.join(' '),/25%, 50%, 75% or 100%/);
});

function sellTicket(extra = {}) {
  return ticket({side:'SELL', symbol:'AXTI', price:'43.00', percentage:100, selected:['1638'],
    snapshot:{as_of:new Date(now).toISOString(), accounts:[{
      account:'1638', verified_cash_cents:null, cash_ceiling_cents:77, error:'Buy cash unavailable',
      holdings_error:null, holdings:{AXTI:{long_quantity:'100',short_quantity:'0',sell_reserved_quantity:'0',available_to_sell_quantity:'100'}}
    }]}, ...extra});
}
test('SELL drafts close verified holdings without requiring buy cash', () => {
  const r=buildReview(sellTicket());
  assert.equal(r.rows[0].quantity,100);
  assert.equal(r.rows[0].cost,430000);
  assert.match(r.text,/SELL 100 shares of AXTI at \$43.00 LIMIT DAY, NORMAL session, account \*\*\*1638/);
  assert.equal(r.text,'SELL 100 shares of AXTI at $43.00 LIMIT DAY, NORMAL session, account ***1638.');
  assert.doesNotMatch(r.text,/BUY |net cash/);
  assert.match(buildReview(sellTicket({duration:'GTC'})).text,/LIMIT GTC/);
  assert.equal(buildReview(sellTicket({duration:'EXTO'})).canCopy,false);
});
test('SELL percentage floors fractional shares after reservations, never oversells', () => {
  assert.equal(sellQuantity('125',50),62);
  assert.equal(sellQuantity('99.99999999',100),99);
  assert.equal(sellQuantity('0.99999999',100),0);
  assert.equal(sellQuantity('-1',100),null);
  assert.equal(sellQuantity(null,100),null);
  const input=sellTicket();
  Object.assign(input.snapshot.accounts[0].holdings.AXTI, {sell_reserved_quantity:'40',available_to_sell_quantity:'60'});
  const r=buildReview(input);
  assert.equal(r.rows[0].quantity,60);
  assert.equal(r.rows[0].reserved,'40');
  assert.match(r.text,/SELL 60 shares/);
});
test('SELL missing, stale, short or unknown holdings never creates a leg', () => {
  const input=sellTicket();
  assert.equal(buildReview({...input,now:now+31000}).canCopy,false);
  assert.equal(buildReview({...input,symbol:'OTHER'}).canCopy,false);
  input.snapshot.accounts[0].holdings.AXTI.available_to_sell_quantity=null;
  assert.equal(buildReview(input).rows[0].quantity,undefined);
  input.snapshot.accounts[0].holdings_error='Order read failed';
  assert.equal(buildReview(input).canCopy,false);
  input.snapshot.accounts[0].holdings_error=undefined;
  assert.equal(buildReview(input).canCopy,false);
});
test('BUY copy stays blocked when the only selected account lacks verified cash', () => {
  const r=buildReview(ticket({selected:['3652']}));
  assert.equal(r.canCopy,false);
  assert.equal(r.text,'');
  assert.match(r.rows[0].reason,/Enter just-verified net cash/);
});

test('copy contains only eligible order lines across five selected accounts', () => {
  const accounts = [['0071','96'],['1638','125'],['2840',null],['3652','306'],['6434',null]].map(([account,qty])=>({
    account,holdings_error:null,holdings:qty ? {HUT:{long_quantity:qty,short_quantity:'0',sell_reserved_quantity:'0',available_to_sell_quantity:qty}} : {}
  }));
  const r=buildReview(ticket({side:'SELL',symbol:'HUT',price:'63.00',percentage:50,
    selected:accounts.map(a=>a.account),snapshot:{as_of:new Date(now).toISOString(),accounts}}));
  assert.equal(r.rows.length,5); // Account blockers remain visible on the page.
  assert.equal(r.text,[
    'SELL 48 shares of HUT at $63.00 LIMIT DAY, NORMAL session, account ***0071.',
    'SELL 62 shares of HUT at $63.00 LIMIT DAY, NORMAL session, account ***1638.',
    'SELL 153 shares of HUT at $63.00 LIMIT DAY, NORMAL session, account ***3652.'
  ].join('\n'));
  const buy=buildReview(ticket({snapshot:{as_of:new Date(now).toISOString(),accounts:[
    {account:'2840',verified_cash_cents:10000,cash_ceiling_cents:10000,error:null},
    {account:'3652',verified_cash_cents:0,cash_ceiling_cents:0,error:null}
  ]}}));
  assert.equal(buy.rows[1].quantity,0);
  assert.doesNotMatch(buy.text,/3652|SKIP|BLOCKED|Snapshot|Basis/);
});

test('every BUY requires a fresh 3652 scan even when 3652 is not selected', () => {
  for (const washReview of [null, {key:'BUY:OTHER:1800',result:{ok:true,possible:false}}]) {
    const r=buildReview(ticket({selected:['2840'],washReview}));
    assert.equal(r.rows[0].quantity,2); // Sizing stays visible; affected leg cannot be copied.
    assert.equal(r.rows[0].washBlocked,true);
    assert.equal(r.canCopy,false);
    assert.equal(r.text,'');
  }
  assert.equal(buildReview(ticket({selected:['2840']})).canCopy,true);
});

test('possible, unknown, failed, mismatched and expired scans block affected BUY drafts', () => {
  for (const changes of [{possible:true},{possible:null},{possible:undefined},{ok:false},
    {protected_account:'2840'},{side:'SELL'},{symbol:'OTHER'},{limit_price:'19.00'},
    {as_of:new Date(now-31000).toISOString()},{as_of:new Date(now+1000).toISOString()}]) {
    const input=ticket();
    Object.assign(input.washReview.result,changes);
    const r=buildReview(input);
    assert.equal(r.canCopy,false,JSON.stringify(changes));
    assert.equal(r.rows[0].washBlocked,true);
  }
});

test('SELL requires review only for 3652 and never blocks unrelated account sells', () => {
  const accounts=['3652','1638','2840'].map(account=>({account,holdings_error:null,
    holdings:{TEST:{long_quantity:'100',sell_reserved_quantity:'0',available_to_sell_quantity:'100'}}}));
  for (const scan of [null,{ok:false},{ok:true,possible:true},{ok:true,possible:null}]) {
    const input=ticket({side:'SELL',selected:accounts.map(a=>a.account),
      snapshot:{as_of:new Date(now).toISOString(),accounts},washReview:null});
    input.washReview={key:'SELL:TEST:1800',result:scan};
    const r=buildReview(input);
    assert.equal(r.rows[0].washBlocked,true);
    assert.ok(r.rows.slice(1).every(row=>!row.washBlocked));
    assert.doesNotMatch(r.text,/3652/);
    assert.match(r.text,/1638/);
    assert.match(r.text,/2840/);
    assert.equal(r.canCopy,true);
  }
  assert.equal(washKey('SELL','TEST','18.00',['1638','2840']),'');
  assert.match(buildReview(sellTicket({washReview:null})).rows[0].reason,/wash-sale check not required/);
});

test('changing side, symbol or limit requires a new scan; allocation does not', () => {
  const input=ticket({selected:['2840']});
  assert.equal(buildReview({...input,price:'19.00'}).canCopy,false);
  assert.equal(buildReview({...input,symbol:'OTHER'}).canCopy,false);
  assert.equal(buildReview({...input,percentage:100}).canCopy,true);
  assert.equal(washKey('SELL','TEST','18.00',['3652']),'SELL:TEST:1800');
});
