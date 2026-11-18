const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..');
const data=JSON.parse(execFileSync('python3',['-c',"import json;from trading_desk.btc_p1_view import P1_VIEW;print(json.dumps(P1_VIEW.snapshot('0.1','frozen',23)))"],{cwd:root}));
function draw(width){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',hidden:false,textContent:'',innerHTML:'',clientWidth:width,querySelectorAll:()=>[]});return nodes.get(id);};
 let source=fs.readFileSync(path.join(root,'trading_desk/btc_p1.js'),'utf8');
 source=source.slice(0,source.indexOf('let resize;'))+'globalThis.render=draw;})();';
 const ctx=vm.createContext({document:{getElementById:get},Intl,Date,URLSearchParams});
 vm.runInContext(source,ctx);ctx.render(data);return get;
}
test('actual entry and full exit are both labelled in the selected chart',()=>{
 const get=draw(640);assert.match(get('chart').innerHTML,/ENTRY/);assert.match(get('chart').innerHTML,/EXIT 100%/);
 assert.match(get('chart').innerHTML,/77,030\.52/);assert.match(get('legs').innerHTML,/failed_rebound_exit_remaining/);
 assert.match(get('selected').textContent,/all recorded exits marked/);
});
test('chart uses container width and tables retain all original trades',()=>{
 const get=draw(320);assert.match(get('chart').innerHTML,/viewBox="0 0 320 370"/);
 assert.equal((get('trades').innerHTML.match(/class="review-button"/g)||[]).length,38);
 assert.match(get('changes').innerHTML,/removed/);assert.match(get('early-case').innerHTML,/03:17/);
});
test('P1 chart overrides inherited 720px minimum that clipped the right edge',()=>{
 const css=fs.readFileSync(path.join(root,'trading_desk/btc_p1.css'),'utf8');
 assert.match(css,/#chart svg\{[^}]*min-width:0/);
 assert.match(css,/#source\{overflow-wrap:anywhere\}/);
});
