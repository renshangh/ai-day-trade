const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {execFileSync}=require('node:child_process'),root=path.resolve(__dirname,'../..');
const data=JSON.parse(execFileSync('python3',['-c',"import json;from trading_desk.btc_parent_hl_view import CONTINUATION_VIEW;print(json.dumps(CONTINUATION_VIEW.snapshot()))"],{cwd:root}));
function render(width){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',hidden:false,textContent:'',innerHTML:'',clientWidth:width,querySelectorAll:()=>[]});return nodes.get(id);};
 let source=fs.readFileSync(path.join(root,'trading_desk/btc_parent_hl.js'),'utf8');
 source=source.slice(0,source.indexOf('let resize;'))+'globalThis.render=draw;})();';
 const ctx=vm.createContext({document:{getElementById:get},Intl,Date,URLSearchParams});
 vm.runInContext(source,ctx);ctx.render(data);return get;
}
test('C chart shows recorded entry and exit with parent evidence',()=>{
 const get=render(640);
 assert.match(get('chart').innerHTML,/ENTRY/);assert.match(get('chart').innerHTML,/EXIT 100%/);
 assert.match(get('audit').innerHTML,/Parent D/);assert.match(get('audit').innerHTML,/Fresh HL/);
 assert.match(get('early-case').innerHTML,/03:17/);assert.match(get('early-case').innerHTML,/03:18/);
 assert.match(get('early-case').innerHTML,/held_position/);
 assert.equal((get('trades').innerHTML.match(/class="review-button"/g)||[]).length,143);
});
test('negative results, all gap groups, full sequence and responsive chart remain visible',()=>{
 const get=render(320);
 assert.match(get('chart').innerHTML,/viewBox="0 0 320 370"/);
 assert.match(get('summary').innerHTML,/8,575\.17/);
 assert.equal((get('summary').innerHTML.match(/<tr>/g)||[]).length,9);
 assert.match(get('downloads').innerHTML,/PROTECTION\.csv/);
 const css=fs.readFileSync(path.join(root,'trading_desk/btc_parent_hl.css'),'utf8');
 assert.match(css,/#chart svg\{[^}]*min-width:0/);
 assert.match(fs.readFileSync(path.join(root,'trading_desk/btc_parent_hl.html'),'utf8'),/lost money in all three/);
});
