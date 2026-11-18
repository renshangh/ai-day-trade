const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {execFileSync}=require('node:child_process'),root=path.resolve(__dirname,'../..');
const data=JSON.parse(execFileSync('python3',['-c',"import json;from trading_desk.btc_parent_filter_view import PARENT_FILTER_VIEW;print(json.dumps(PARENT_FILTER_VIEW.snapshot()))"],{cwd:root}));
function render(width){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',hidden:false,textContent:'',innerHTML:'',clientWidth:width,querySelectorAll:()=>[]});return nodes.get(id);};
 let source=fs.readFileSync(path.join(root,'trading_desk/btc_parent_filter.js'),'utf8');
 source=source.slice(0,source.indexOf('let resize;'))+'globalThis.render=draw;})();';
 const ctx=vm.createContext({document:{getElementById:get},Intl,Date,URLSearchParams});
 vm.runInContext(source,ctx);ctx.render(data);return get;
}
test('full sequential chart includes entry and every actual exit within available width',()=>{
 const get=render(320);assert.match(get('chart').innerHTML,/viewBox="0 0 320 /);
 assert.match(get('chart').innerHTML,/ENTRY/);
 for(const leg of data.selected.legs)assert.ok(get('chart').innerHTML.includes('EXIT '+Math.round(leg.fraction*100)+'%'));
 assert.equal((get('trades').innerHTML.match(/class="review-button"/g)||[]).length,data.trades.length);
 assert.match(get('changes').innerHTML,/added/);
});
test('still-negative verdict, separate gap groups and ignored trigger evidence are visible',()=>{
 const get=render(640);assert.match(get('verdict').textContent,/still lose money/);
 assert.equal((get('summary').innerHTML.match(/<tr>/g)||[]).length,9);
 assert.match(get('parent-decisions').innerHTML,/Blocked — no fill/);
 assert.match(get('parent-decisions').innerHTML,/Present; not used/);
 assert.match(get('downloads').innerHTML,/CHANGES\.csv/);
 assert.match(get('downloads').innerHTML,/PARENT_DECISIONS\.csv/);
});
