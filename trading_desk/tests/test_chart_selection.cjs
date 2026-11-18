const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../app.js'),'utf8');

test('expired Schwab authentication clears previously loaded holdings',async()=>{
  const state={schwabPositions:{ok:true,positions:[{symbol:'OLD'}]}};
  let rendered=false;
  const context=vm.createContext({state,
    fetch:async()=>({json:async()=>({ok:false,error:'OAuth expired'})}),
    fetchSchwabPositions:async()=>{throw Error('must not read without authentication');},
    renderSchwabStatus:()=>{rendered=true;}});
  vm.runInContext(source.slice(source.indexOf('async function fetchSchwabStatus('),
    source.indexOf('async function fetchSchwabPositions(')),context);
  await context.fetchSchwabStatus();
  assert.equal(state.schwabPositions,null);
  assert.equal(rendered,true);
});

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

test('crypto research resolves provider pages and USD aliases for the selected token',()=>{
  const context=vm.createContext({});
  vm.runInContext(source.slice(source.indexOf('const CRYPTO_RESEARCH_SLUGS'),source.indexOf('function renderDetail(')),context);
  const links=context.cryptoResearchLinks('LINK');
  assert.equal(links[0].url,'https://www.coingecko.com/en/coins/chainlink');
  assert.equal(links[1].url,'https://coinmarketcap.com/currencies/chainlink/');
  assert.equal(context.cryptoResearchLinks('ONDOUSD')[0].url,'https://www.coingecko.com/en/coins/ondo');
  assert.equal(context.cryptoResearchLinks('SYRUP')[1].url,'https://coinmarketcap.com/currencies/maple-finance/');
  assert.equal(context.cryptoResearchLinks('CCCAUSD')[1].url,'https://coinmarketcap.com/currencies/canton-network/');
  assert.equal(context.cryptoResearchLinks('COIN').length,0);
});

test('switching crypto research replaces links and stock-only facts',()=>{
  const elements=new Map();
  const $=id=>{if(!elements.has(id))elements.set(id,{replaceChildren(){this.cleared=true;}});return elements.get(id);};
  const context=vm.createContext({$});
  vm.runInContext(source.slice(source.indexOf('const CRYPTO_RESEARCH_SLUGS'),source.indexOf('function renderDetail(')),context);
  context.renderCryptoResearch('LINK');
  assert.match($('c-links').innerHTML,/CoinGecko/);
  assert.match($('c-links').innerHTML,/CoinMarketCap/);
  assert.match($('c-links').innerHTML,/target="_blank" rel="noopener noreferrer"/);
  context.renderCryptoResearch('QNT');
  assert.equal($('c-title').textContent,'Crypto research — QNT');
  assert.doesNotMatch($('c-links').innerHTML,/chainlink/);
  assert.match($('c-links').innerHTML,/quant-network/);
  assert.match($('c-links').innerHTML,/currencies\/quant\//);
  for(const id of ['c-stats','c-facts','c-news'])assert.ok($(id).cleared,id);
});

test('discovery candles use their entire measured interval instead of a generic calendar slice',()=>{
 const context=vm.createContext({});
 vm.runInContext(source.slice(source.indexOf('function chartStartIndex('),source.indexOf('function visibleSlice(')),context);
 assert.equal(context.chartStartIndex({discovery:{interval:'4h'},asset_type:'crypto',bars:[]},{key:'3M',bars:63}),0);
});

test('a slower stock snapshot response cannot overwrite a later selected crypto snapshot',async()=>{
 const calls=[],pending=[];
 const state={selectionSeq:0,stock:null};
 const element={classList:{add(){},remove(){}},scrollIntoView(){},textContent:''};
 const context=vm.createContext({state,URLSearchParams,$:()=>element,
  clearSelectedChart:s=>{state.stock=null;state.symbol=s;},renderDetail:()=>calls.push(state.symbol),fetchDetail:()=>{},
  fetch:url=>new Promise(resolve=>pending.push({url,resolve}))});
 vm.runInContext(source.slice(source.indexOf('function rangeDiscoveryOptions('),source.indexOf('function selectOnchainSymbol(')),context);
 const first=context.selectDiscoverySymbol({symbol:'SWKS',asset:'stock'},{scroll:false,scanStartedAt:'snapshot'});
 const second=context.selectDiscoverySymbol({symbol:'NEAR',asset:'crypto'},{scroll:false,scanStartedAt:'snapshot'});
 const observations=JSON.parse(fs.readFileSync(require('node:path').join(__dirname,'../../reports/range_trading/NEAR_DOT_REFRESH.json'),'utf8'));
 const realBar=observations.products['NEAR-USD'].candles[0];
 pending[1].resolve({ok:true,json:async()=>({symbol:'NEAR',asset_type:'crypto',bars:[realBar]})});await second;
 const stockBar=JSON.parse(fs.readFileSync(require('node:path').join(__dirname,'../../reports/range_trading/TWO_YEAR_DAILY_SOURCE_2026_10_17.json'),'utf8')).products.SWKS[0];
 pending[0].resolve({ok:true,json:async()=>({symbol:'SWKS',asset_type:'stock',bars:[stockBar]})});await first;
 assert.equal(state.symbol,'NEAR');assert.equal(state.stock.symbol,'NEAR');assert.deepEqual(calls,['NEAR']);
 assert.match(pending[1].url,/asset=crypto/);assert.match(pending[1].url,/scan=snapshot/);
});
