const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..');
const data=JSON.parse(execFileSync('python3',['-c',"import json;from trading_desk.btc_live import Controller;print(json.dumps(Controller().status()))"],{cwd:root}));
function render(d){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{value:id==='model'?'0.1':'',dataset:{},innerHTML:'',textContent:'',hidden:false});return nodes.get(id);};
 let source=fs.readFileSync(path.join(root,'trading_desk/btc_live.js'),'utf8');
 source=source.slice(0,source.indexOf("$('start').onclick="))+'globalThis.draw=render;})();';
 const ctx=vm.createContext({document:{getElementById:get},Intl,Date,URLSearchParams});
 vm.runInContext(source,ctx);ctx.draw(d);
 return get;
}
test('empty comparison renders no fabricated trades and explicit broker boundary',()=>{
 const get=render({...data,models:[],signals:[],events:[],rows:[],quote:null,quote_fresh:false,health:'paused'});
 assert.match(get('model-cards').innerHTML,/actual warmup/);
 assert.match(get('live-signals').innerHTML,/not invented trades/);
 assert.match(get('live-metrics').innerHTML,/Disabled/);
 assert.match(get('quote-status').textContent,/No fresh|unavailable/i);
});
test('archived real entry carries reference and delayed detection labels',()=>{
 const run=JSON.parse(fs.readFileSync(path.join(root,'trading_records/btc_structure/runs/20261109T041525Z-30-ab/result.json'),'utf8'));
 const signal={...run.signals[0],detected_at:run.signals[0].interval_end,detection_delay_seconds:60};
 const get=render({...data,models:[],signals:[signal],events:[],rows:[],quote_fresh:false});
 assert.match(get('live-signals').innerHTML,/82,571.35/);
 assert.match(get('live-signals').innerHTML,/no broker fill/);
 assert.match(get('live-signals').innerHTML,/60s/);
});

test('switching models during a request discards the old response and refreshes immediately',async()=>{
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{value:id==='model'?'0.1':'',dataset:{},innerHTML:'',textContent:'',hidden:false});return nodes.get(id);};
 const pending=[];
 let source=fs.readFileSync(path.join(root,'trading_desk/btc_live.js'),'utf8');
 source=source.slice(0,source.indexOf("$('start').onclick="))+'globalThis.pull=refresh;})();';
 const ctx=vm.createContext({document:{getElementById:get},Intl,Date,URLSearchParams,
  fetch:url=>new Promise(resolve=>pending.push({url,resolve}))});
 vm.runInContext(source,ctx);
 const first=ctx.pull();
 get('model').value='E2';await ctx.pull();
 pending[0].resolve({ok:true,json:async()=>({...data,selected_model:'0.1'})});
 await first;
 assert.equal(get('model-cards').innerHTML,'');
 assert.equal(pending.length,2);assert.match(pending[1].url,/model=E2/);
 pending[1].resolve({ok:true,json:async()=>({...data,selected_model:'E2',cost_note:'E2 response'})});
 await new Promise(resolve=>setImmediate(resolve));
 assert.match(get('live-cost').textContent,/E2 response/);
});
