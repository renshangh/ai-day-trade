// Exercise the actual view functions with archived research, without market/bar mocks.
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..');
const latest=path.join(root,'trading_records/btc_structure/latest_run.json');
const available=fs.existsSync(latest);
function review(run){return JSON.parse(execFileSync('python3',['-c',
 `import json;from trading_desk.btc_lab import Lab;from trading_desk.btc_data import STORE,read;print(json.dumps(Lab().detail(${run?JSON.stringify(run):'read(STORE/"latest_run.json")["run_id"]'},'2026-10-12')))`],{cwd:root,maxBuffer:30*1024*1024}));}
function view(data){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',innerHTML:'',textContent:'',querySelector:selector=>get(id+selector)});return nodes.get(id);};
 const context=vm.createContext({document:{getElementById:get,querySelectorAll:()=>[]},Intl,Date,URLSearchParams});
 const source=fs.readFileSync(path.join(root,'trading_desk/btc_lab.js'),'utf8').replace('function fixed38ReviewPanel()', 'globalThis.studyPanel=currentStudyPanel;function fixed38ReviewPanel()');
 vm.runInContext(source.slice(0,source.indexOf("$('run').onclick="))+`globalThis.render={set:(d,s)=>{detail=d;selectedSignal=s;},entryAudit,lossReviewPanel,largeLossReviewPanel,b1ReviewPanel,performanceReviewPanel,pullbackReviewPanel,earlyFailureReviewPanel,fixed38ReviewPanel,metrics,trade,signals,signalDetails,ledger,chart,downloads};})();`,context);
 context.render.set(data);get('signal-route').value='all';get('signal-status').value='all';
 return {api:{...context.render,currentStudyPanel:context.studyPanel},get};
}
test('new monthly view handles B1 with no HL and renders leg P/L and structure raises',{skip:!available&&'Requires preserved real research archive'},()=>{
 const data=review('20261109T030906Z-30-ab'),v=view(data),b1=data.signals.find(s=>s.route==='B1');
 assert.ok(b1);v.api.set(data,b1.id);v.api.metrics(data.run);v.api.signalDetails();
 assert.match(v.get('signal-detail').innerHTML,/B1/);
 v.get('trade').value=String(b1.trade_id);v.api.trade();
 assert.match(v.get('trade-detail').innerHTML,/初始保护/);
 assert.match(v.get('trade-detail').innerHTML,/106\.17/);
 const structural=data.trades.find(p=>p.structure_history?.length);
 assert.ok(structural);v.get('trade').value=String(structural.id);v.api.trade();
 assert.match(v.get('trade-detail').innerHTML,/15分钟结构参考/);
 v.get('signal-route').value='B';v.api.signals();v.api.ledger();v.api.chart();v.api.downloads();
 assert.match(v.get('exports').innerHTML,/PROTECTION.csv/);
 assert.match(v.get('comparison').innerHTML,/旧版 A\/B/);
 assert.match(v.get('metrics').innerHTML,/1,253\.88/);
 assert.doesNotMatch(v.get('signals').querySelector('tbody').innerHTML,/没有符合/);
});
test('corrected run shows all original and remaining losing trades with a separate history warning',{skip:!available&&'Requires preserved real research archive'},()=>{
 const data=review('20261109T034016Z-30-ab'),v=view(data);
 v.api.entryAudit();v.api.metrics(data.run);v.api.lossReviewPanel();
 assert.equal(v.get('entry-audit').innerHTML,'');
 assert.match(v.get('metrics').innerHTML,/2,214\.63/);
 assert.match(v.get('comparison').innerHTML,/修复前/);
 assert.match(v.get('loss-review').innerHTML,/原27笔/);
 assert.equal(data.loss_review.rows.length,27);assert.equal(data.loss_review.remaining_losses.length,19);
 const old=review('20261109T030906Z-30-ab'),previous=view(old);
 previous.api.entryAudit();assert.match(previous.get('entry-audit').innerHTML,/历史记录含无效入场/);
 previous.get('trade').value='2';previous.api.trade();assert.match(previous.get('trade-detail').innerHTML,/此入场无效/);
});
test('prior monthly run remains readable with its own results',{skip:!available&&'Requires preserved real research archive'},()=>{
 const data=review('20261109T002127Z-30-ab'),v=view(data);
 v.api.metrics(data.run);assert.match(v.get('metrics').innerHTML,/3,691\.76/);
 assert.equal(v.get('comparison').innerHTML,'');
});
test('failed-rebound view shows all five controls and the full-sample effects',{skip:!available&&'Requires preserved real research archive'},()=>{
 const data=review('20261109T041525Z-30-ab'),v=view(data);
 v.api.metrics(data.run);v.api.largeLossReviewPanel();v.api.downloads();
 assert.match(v.get('metrics').innerHTML,/3,516\.46/);
 assert.equal(data.large_loss_review.cases.length,5);
 assert.match(v.get('large-loss-review').innerHTML,/八分钟|尚未来得及确认/);
 assert.match(v.get('large-loss-review').innerHTML,/完整序列中全部受影响交易/);
 assert.match(v.get('large-loss-review').innerHTML,/732\.67/);
 assert.match(v.get('exports').innerHTML,/E1_E2_SEQUENTIAL_30D.xlsx/);
 assert.doesNotMatch(v.get('exports').innerHTML,/LARGE_LOSS_REVIEW.csv/);
 assert.equal(data.large_loss_review.sequence_effects.length,8);
});

test('independent B1 audit exposes blocked signals, same-source comparison and release downloads',{skip:!available&&'Requires preserved research archive'},()=>{
 const data=review('20261109T122648Z-30-ab'),v=view(data);
 v.api.metrics(data.run);v.api.b1ReviewPanel();
 assert.match(v.get('metrics').innerHTML,/2,805\.01/);
 assert.match(v.get('comparison').innerHTML,/Release 0\.1/);
 assert.match(v.get('b1-confirmation-review').innerHTML,/26个越价信号/);
 assert.match(v.get('b1-confirmation-review').innerHTML,/09:53/);
 const blocked=data.signals.find(s=>s.b1_confirmation&&!s.b1_confirmation.passed);
 v.api.set(data,blocked.id);v.api.signalDetails();
 assert.match(v.get('signal-detail').innerHTML,/未过，不能入场/);
 assert.match(v.get('signal-detail').innerHTML,/不等于实际成交/);
 v.get('signal-status').value='b1waiting';v.api.signals();
 assert.match(v.get('signal-count').textContent,/当前显示 26/);
 const frozen=review('20261109T041525Z-30-ab'),old=view(frozen);
 old.get('runs').value=frozen.run.run_id;old.api.metrics(frozen.run);old.api.downloads();
 assert.match(old.get('scope').textContent,/Release 0\.1 · 冻结/);
 assert.match(old.get('exports').innerHTML,/E1_E2_SEQUENTIAL_30D.xlsx/);
 assert.doesNotMatch(old.get('exports').innerHTML,/BTC_STRUCTURE_RELEASE_0.1.zip/);
});

test('release 0.1 performance investigation keeps rejected improvements separate',{skip:!available&&'Requires preserved archive'},()=>{
 const data=review('20261109T041525Z-30-ab'),v=view(data);v.api.performanceReviewPanel();
 assert.equal(data.performance_review.trade_count,38);
 assert.equal(data.performance_review.losses_below_1r.length,18);
 assert.match(v.get('performance-review').innerHTML,/18笔未观察到1R/);
 assert.match(v.get('performance-review').innerHTML,/325\.53/);
 assert.match(v.get('performance-review').innerHTML,/不是新月度策略收益/);
 const experimental=view(review('20261109T122648Z-30-ab'));experimental.api.performanceReviewPanel();
 assert.equal(experimental.get('performance-review').innerHTML,'');
});

test('three-case causal review marks post-exit bars and distinguishes held HL from failure',{skip:!available&&'Requires preserved archive'},()=>{
 const data=review('20261109T041525Z-30-ab'),v=view(data);v.api.pullbackReviewPanel();
 const html=v.get('pullback-review').innerHTML;
 assert.match(html,/#5、#32与#30/);
 assert.match(html,/退出后才完整，仅行情对照/);
 assert.match(html,/78,026\.42/);
 assert.match(html,/较高高点＋较高低点/);
 assert.match(html,/原退出与盈亏/);
 assert.match(html,/103\.53/);assert.match(html,/1,350\.96/);
 assert.equal(data.pullback_review.cases.reduce((sum,c)=>sum+c.bars.length,0),73);
 const exp=view(review('20261109T122648Z-30-ab'));exp.api.pullbackReviewPanel();
 assert.equal(exp.get('pullback-review').innerHTML,'');
});

test('two early-exit alternatives show causal prices and unchanged profitable control',{skip:!available&&'Requires preserved archive'},()=>{
 const data=review('20261109T041525Z-30-ab'),v=view(data);v.api.earlyFailureReviewPanel();
 const html=v.get('early-failure-review').innerHTML;
 assert.match(html,/76,079\.93/);assert.match(html,/75,961\.01/);
 assert.match(html,/-211\.35/);assert.match(html,/-330\.24/);
 assert.match(html,/521\.32/);assert.match(html,/402\.42/);
 assert.match(html,/1,454\.49/);assert.match(html,/未触发，保留原25%／75%/);
 assert.match(html,/E1触发后仅为独立E2／原路径对照/);
 assert.match(html,/不能把两种100%退出相加/);
 const exp=view(review('20261109T122648Z-30-ab'));exp.api.earlyFailureReviewPanel();
 assert.equal(exp.get('early-failure-review').innerHTML,'');
});

test('all38 fixed-entry comparison keeps profitable controls and data-gap caveat',{skip:!available&&'Requires preserved archive'},()=>{
 const data=review('20261109T041525Z-30-ab'),v=view(data);v.api.fixed38ReviewPanel();
 const html=v.get('early-failure-fixed38').innerHTML;
 assert.match(html,/4,159\.67/);assert.match(html,/4,195\.15/);
 assert.match(html,/643\.21/);assert.match(html,/678\.69/);
 assert.match(html,/585\.90/);assert.match(html,/402\.42/);
 assert.match(html,/全部38笔/);assert.match(html,/原19笔盈利交易/);
 assert.match(html,/#12原持有后段缺7分钟/);
 assert.equal(data.early_failure_fixed38.rows.length,38);
 const exp=view(review('20261109T122648Z-30-ab'));exp.api.fixed38ReviewPanel();
 assert.equal(exp.get('early-failure-fixed38').innerHTML,'');
});

test('current sequential study separates gap groups and shows no replacement buys',{skip:!available&&'Requires preserved archive'},()=>{
 const data=review(),v=view(data);v.api.currentStudyPanel();v.api.downloads();
 const html=v.get('current-study').innerHTML;
 for(const number of ['3,516.46','4,159.67','4,195.15','2,751.29','2,998.96','3,034.44','765.17','1,160.71'])assert.ok(html.includes(number),number);
 assert.match(html,/新增 0 笔/);assert.match(html,/释放分钟/);assert.match(html,/分组样本会变化/);
 assert.match(html,/521.32/);assert.match(html,/276.27/);assert.match(html,/原净盈亏/);
 assert.equal(data.comparison,null);
 assert.match(v.get('exports').innerHTML,/E1_E2_SEQUENTIAL_30D.xlsx/);
 assert.doesNotMatch(v.get('exports').innerHTML,/E1_E2_FIXED38.xlsx|RESEARCH.xlsx|LARGE_LOSS_REVIEW.csv/);
 const id=data.current_study.run_ids.E1,e1=review(id);
 e1.trades=JSON.parse(fs.readFileSync(path.join(root,'trading_records/btc_structure/runs',id,'result.json'),'utf8')).trades;
 const w=view(e1);
 w.get('trade').value='32';w.api.trade();
 assert.match(w.get('trade-detail').innerHTML,/E1/);assert.match(w.get('trade-detail').innerHTML,/76,079.93/);
 assert.match(w.get('trade-detail').innerHTML,/12:15/);
});
