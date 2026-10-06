const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../app.js'),'utf8');

test('switching symbols clears candles, feed, tooltip and stock-only facts',()=>{
  const state={stock:{symbol:'COIN'},symbol:'COIN',hover:12};
  const elements=new Map();
  const $=id=>{
    if(!elements.has(id)) elements.set(id,{textContent:'old',width:100,height:100,
      replaceChildren(){this.cleared=true;},classList:{remove(){}},
      getContext(){return {clearRect(){elements.get(id).cleared=true;}};}});
    return elements.get(id);
  };
  const context=vm.createContext({state,$});
  vm.runInContext(source.slice(source.indexOf('function clearSelectedChart('),source.indexOf('function selectOnchainSymbol(')),context);
  context.clearSelectedChart('CCCAUSD');
  assert.equal(state.stock,null);
  assert.equal(state.symbol,'CCCAUSD');
  assert.equal($('d-feed').textContent,'');
  assert.equal($('c-facts-hint').textContent,'');
  for(const id of ['chart','table-view','c-facts','c-news','c-links']) assert.ok($(id).cleared,id);
});

test('stock and crypto selection dispatch independently and reveal the lower chart',()=>{
  const calls=[];
  const context=vm.createContext({fetchStock:(s,f)=>calls.push(['stock',s,f]),fetchCrypto:(s,f)=>calls.push(['crypto',s,f]),$:(id)=>({scrollIntoView:()=>calls.push(['scroll',id])})});
  vm.runInContext(source.slice(source.indexOf('function selectOnchainSymbol('),source.indexOf('let onchainBoardReview')),context);
  context.selectOnchainSymbol('COIN','stock');
  context.selectOnchainSymbol('CCCAUSD','crypto');
  assert.deepEqual(calls,[['stock','COIN',false],['scroll','detail-card'],['crypto','CCCAUSD',false],['scroll','detail-card']]);
});


test('crypto ranges use calendar months with gaps and month-end clamping; stock ranges keep sessions',()=>{
  const context=vm.createContext({});
  vm.runInContext(source.slice(source.indexOf('function chartStartIndex('),source.indexOf('function visibleSlice(')),context);
  const bars=['2025-08-30','2025-08-31','2025-12-01','2026-02-28','2026-03-01','2026-05-31','2026-08-31'].map(t=>({t}));
  const crypto={bars,asset_type:'crypto'};
  assert.equal(context.chartStartIndex(crypto,{key:'6M',bars:126}),3);
  assert.equal(context.chartStartIndex(crypto,{key:'3M',bars:63}),5);
  assert.equal(context.chartStartIndex(crypto,{key:'1Y',bars:252}),1);
  assert.equal(context.chartStartIndex(crypto,{key:'2Y',bars:Infinity}),0);
  assert.equal(context.chartStartIndex({bars},{key:'3M',bars:3}),4);
  assert.equal(context.chartStartIndex({bars},{key:'2Y',bars:Infinity}),0);
});
