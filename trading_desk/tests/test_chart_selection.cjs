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
