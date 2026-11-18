const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {execFileSync}=require('node:child_process'),root=path.resolve(__dirname,'../..');
const library=JSON.parse(execFileSync('python3',['-c',"import json;from trading_desk.pattern_library import create_library;print(json.dumps(create_library()))"],{cwd:root}));
function view(){const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',checked:false,textContent:'',innerHTML:'',addEventListener:()=>{}});return nodes.get(id);};
const ctx=vm.createContext({document:{getElementById:get},Date,Number});
let src=fs.readFileSync(path.join(root,'trading_desk/pattern_discovery.js'),'utf8');src=src.slice(0,src.indexOf("$('watchlist').addEventListener"));vm.runInContext(src+'\nglobalThis.draw=render;',ctx);
ctx.draw({status:'not started',library,config:{watchlist:['BTC/USD','SPY'],enabled:true},symbols:[]});return Object.assign(get,{draw:ctx.draw});}
test('shows all ten actual reference trades with separate outcomes and no invented forward fills',()=>{const get=view();assert.equal((get('examples').innerHTML.match(/<tr>/g)||[]).length,10);assert.match(get('selection').textContent,/17 losing lookalikes/);assert.match(get('decisions').innerHTML,/No forward qualifying/);assert.match(get('trades').innerHTML,/No model exits/);assert.equal(get('watchlist').value,'BTC/USD, SPY');assert.match(get('definition').innerHTML,/research drafts/);});
test('no account or order controls are offered',()=>{const html=fs.readFileSync(path.join(root,'trading_desk/pattern_discovery.html'),'utf8');assert.match(html,/no Alpaca paper-account orders/);assert.match(html,/1 comparison unit/);assert.match(html,/library radius/);assert.doesNotMatch(html,/<button[^>]*>[^<]*(?:buy|sell|place order)/i);});
test('real universe screen exposes beta, normalized ATR, consolidated liquidity and leverage',()=>{
 const file=path.join(root,'trading_records/pattern_discovery/UNIVERSE_SCREEN.json');if(!fs.existsSync(file))return;
 const universe=JSON.parse(fs.readFileSync(file,'utf8')),get=view();get.draw({status:'running',library,config:{},symbols:[],universe_screen:universe});
 assert.match(get('universe-summary').textContent,/309 names screened/);assert.match(get('universe').innerHTML,/DAILY leveraged target/);
 assert.equal((get('universe').innerHTML.match(/<tr>/g)||[]).length,14);
 assert.match(get('universe').innerHTML,/CIFR/);assert.match(get('universe').innerHTML,/Beta below 1.25/);
 get('universe-filter').value='qualified';get.draw({status:'running',library,config:{},symbols:[],universe_screen:universe});
 assert.equal((get('universe').innerHTML.match(/<tr>/g)||[]).length,universe.qualified);
});
