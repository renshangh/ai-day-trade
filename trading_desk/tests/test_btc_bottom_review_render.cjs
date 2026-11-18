const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process');
const root=path.resolve(__dirname,'../..');
function actual(now='2026-11-15T14:35:00Z'){
const code=`import json,tempfile
from pathlib import Path
from trading_desk.tests.test_btc_bottom_review import fixture
from trading_desk.btc_bottom_review import snapshot
from trading_desk.ibit_hours import epoch
with tempfile.TemporaryDirectory() as name:
 root=Path(name);state,_=fixture(root)
 print(json.dumps(snapshot(state,now=epoch('${now}'),root=root,calendar_root=root/'calendar')))`;
return JSON.parse(cp.execFileSync('python3',['-c',code],{cwd:root,maxBuffer:1024*1024}));
}
function render(data){const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',innerHTML:'',hidden:false,disabled:false});return nodes.get(id);};let source=fs.readFileSync(path.join(root,'trading_desk/btc_bottom_review.js'),'utf8');source=source.slice(0,source.indexOf('let busy=false;'))+'globalThis.draw=render;})();';const ctx=vm.createContext({document:{getElementById:get},Intl,Date});vm.runInContext(source,ctx);ctx.draw(data);return get;}
test('dated invalidation and conditional stop never appear as an active model entry',()=>{const get=render(actual());assert.match(get('bottom-review-content').innerHTML,/Invalidated; entry never triggered/);assert.match(get('bottom-review-content').innerHTML,/66,160/);assert.match(get('bottom-review-content').innerHTML,/65,880/);assert.match(get('bottom-review-content').innerHTML,/Not formed in this future sequence/);assert.match(get('bottom-review-content').innerHTML,/not a model rule/);});
test('zero recorded actions and older context stay explicitly separate',()=>{const get=render(actual());assert.match(get('bottom-review-counts').textContent,/0\.1: 0 entries \/ 0 exit legs/);assert.match(get('bottom-review-actions').innerHTML,/No recorded model entries or exits/);assert.match(get('bottom-review-older').innerHTML,/#20/);assert.match(get('bottom-review-older').innerHTML,/55\.65/);assert.match(get('bottom-review-older').innerHTML,/306\.76/);assert.match(get('bottom-review-older').innerHTML,/Before window; historical only/);});
test('all real actions within a historical 12h window retain model and availability labels',()=>{const get=render(actual('2026-11-15T00:40:00Z'));assert.match(get('bottom-review-counts').textContent,/2 entries \/ 2 exit legs/);assert.match(get('bottom-review-actions').innerHTML,/0\.1 \/ E1 \/ E2/);assert.match(get('bottom-review-actions').innerHTML,/Available/);assert.match(get('bottom-review-actions').innerHTML,/closed/);});
test('audit or quote failure never substitutes zero trades or an old current price',()=>{const d=actual();d.quote=null;d.history.status='unavailable';d.history.error='Unavailable';d.history.counts=null;const get=render(d);assert.match(get('bottom-review-counts').textContent,/no zero-trade conclusion/);assert.match(get('bottom-review-actions').innerHTML,/Records unavailable/);assert.doesNotMatch(get('bottom-review-actions').innerHTML,/No recorded model entries/);assert.match(get('bottom-review-quote').textContent,/Fresh BTC quote unavailable/);});
test('review refresh is manual GET-only and introduces no trading or recurring monitor',()=>{const source=fs.readFileSync(path.join(root,'trading_desk/btc_bottom_review.js'),'utf8');assert.match(source,/fetch\('\/api\/btc-bottom-review'/);assert.doesNotMatch(source,/method:.*POST|\/api\/schwab|setInterval|setTimeout|PLACE BUY|PLACE SELL/);const html=fs.readFileSync(path.join(root,'trading_desk/btc_live.html'),'utf8');assert.match(html,/Refresh review data/);assert.match(html,/BEFORE this window/);});
