import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const root=process.cwd(),store=path.join(root,'trading_records/btc_structure');
const active=JSON.parse(await fs.readFile(path.join(store,'studies/ACTIVE.json'),'utf8'));
const folder=path.join(store,'studies',active.study_id);
const study=JSON.parse(await fs.readFile(path.join(folder,'STUDY.json'),'utf8'));
const out=path.join(root,'outputs/btc_e1_e2_sequential_'+active.study_id);
await fs.mkdir(out,{recursive:true});
try{await fs.symlink('/Users/danielshan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',path.join(out,'node_modules'),'dir');}catch(e){if(e.code!=='EEXIST')throw e;}
const require=createRequire(path.join(out,'package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const models=['0.1','E1','E2'],data={};
for(const m of models)data[m]=JSON.parse(await fs.readFile(path.join(store,'runs',study.run_ids[m],'WORKBOOK_DATA.json'),'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('本轮比较'),trades=wb.worksheets.add('全部交易'),legs=wb.worksheets.add('退出腿与来源'),changes=wb.worksheets.add('顺序变化'),timeline=wb.worksheets.add('逐根15分钟');
const usd='$#,##0.00;($#,##0.00);"—"';
const nydtf=new Intl.DateTimeFormat('sv-SE',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
const ny=v=>v?new Date(nydtf.format(new Date(v)).replace(' ','T')+'Z'):null;
const zoned=v=>v?new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZoneName:'short'}).format(new Date(v)):'';
const col=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
function base(s,last,end){s.showGridLines=false;s.tabColor='#C8B9A6';const x=s.getRange('A1:'+last+end);x.format.font={name:'Arial',size:11,color:'#172B4D'};x.format.columnWidth=19;x.format.rowHeight=25;x.format.verticalAlignment='center';}
function title(s,text){s.getRange('A2:L2').merge();s.getRange('A2').values=[[text]];s.getRange('A2').format.font={name:'Arial',size:17,bold:true,color:'#172B4D'};s.getRange('A2:L2').format.rowHeight=33;}
function head(s,range){const x=s.getRange(range);x.format.fill='#243B53';x.format.font={name:'Arial',size:11,bold:true,color:'#FFFFFF'};x.format.rowHeight=48;x.format.wrapText=true;}
function dates(s,c,a,b){s.getRange(c+a+':'+c+b).setNumberFormat('mm/dd/yy hh:mm');s.getRange(c+a+':'+c+b).format.columnWidth=23;}
const reason={target_25:'首次25%止盈',stop:'硬止损',failed_rebound_exit_remaining:'失败反弹退出',structure_exit_remaining:'结构转弱退出',giveback_exit_remaining:'浮盈回吐退出',turning_exit_remaining:'冲高转弱退出',wick_exit_all:'长上影退出',e1_exit_remaining:'E1连续转弱退出',e2_exit_remaining:'E2收复失败退出'};
const allTrades=[],allLegs=[];
for(const model of models)for(const p of data[model].result.trades){
 allTrades.push({model,p});
 for(const [i,l] of p.legs.entries())allLegs.push({model,p,l,ordinal:i+1});
}
const te=6+allTrades.length,le=6+allLegs.length;
base(legs,'Q',Math.max(le,25));title(legs,'逐腿盈亏计算｜每笔初始1 BTC，固定每边2 bps');
legs.getRange('A6:L6').values=[['方案','交易#','腿序号','执行纽约时间','初始仓位比例','退出参考价 USD','入场参考价 USD','毛盈亏 USD','摩擦成本 USD','净盈亏 USD','退出依据','执行 UTC']];
head(legs,'A6:L6');
legs.getRange('A7:L'+le).values=allLegs.map(({model,p,l,ordinal})=>[model,p.id,ordinal,ny(l.time_utc),l.fraction,l.price,p.entry,null,null,null,reason[l.reason]||l.reason,l.time_utc]);
for(let r=7;r<=le;r++)legs.getRange('H'+r+':J'+r).formulas=[['=(F'+r+'-G'+r+')*E'+r,'=(F'+r+'+G'+r+')*E'+r+'*$N$6/10000','=H'+r+'-I'+r]];
legs.getRange('N5:P5').values=[['单边摩擦 bps','执行模型','来源 / 边界']];head(legs,'N5:P5');
legs.getRange('N6:P6').values=[[2,'初始1 BTC；ETF零佣金','仍计价差与滑点，非ETF真实成交']];
legs.getRange('N6').format.font={name:'Arial',size:11,color:'#0000FF'};
legs.getRange('N8:P18').values=[
 ['行情来源','Alpaca BTC/USD真实1m','0.1冻结数据；未调用交易API'],
 ['冻结SHA256',study.source_minute_sha256,'与0.1分钟流核验一致'],
 ['UTC测试窗口',study.start,study.end+'（不含）'],
 ['纽约测试窗口',zoned(study.start),zoned(study.end)+'（不含）'],
 ['实际 / 应有分钟',study.source_quality.observed_minutes,study.source_quality.expected_minutes],
 ['缺失分钟',study.source_quality.missing_minutes,'不补值、不插值、不推定缺口内成交'],
 ['E1','两次连续降高降低（3根完整15m）','失守原触发价；红线、≤前收、非内包'],
 ['E2','E1背景→完整收复→失守','紧邻下一完整K线降高降低，方向条件同E1'],
 ['E1/E2执行','完整15m结束确认','仅下一实际观测1m开盘；缺首价不回填'],
 ['缺口分组','持有期缺口 OR 入场窗口不完整','无缺口组是补集；各序列重新标记'],
 ['来源路径','trading_records/btc_structure/studies/'+study.study_id+'/STUDY.json','结果与逐根来源为各run的WORKBOOK_DATA.json']
 ];
legs.getRange('N5:N18').format.columnWidth=24;legs.getRange('O5:O18').format.columnWidth=46;legs.getRange('P5:P18').format.columnWidth=60;legs.getRange('N8:P18').format.wrapText=true;legs.getRange('N8:P18').format.rowHeight=55;
dates(legs,'D',7,le);legs.getRange('E7:E'+le).setNumberFormat('0%');legs.getRange('F7:J'+le).setNumberFormat(usd);legs.getRange('K6:K'+le).format.columnWidth=28;legs.getRange('L6:L'+le).format.columnWidth=30;
legs.getRange('L7:L'+le).setNumberFormat('yyyy-mm-dd hh:mm" UTC"');legs.getRange('O10').setNumberFormat('yyyy-mm-dd hh:mm" UTC"');
legs.tables.add('A6:L'+le,true,'SequentialExitLegs');legs.freezePanes.freezeRows(6);legs.freezePanes.freezeColumns(2);

const th=['方案','交易#','入场路线','入场纽约时间','入场价 USD','初始止损 USD','止损生效纽约','D/L1价格 USD','D/L1发生纽约','D/L1确认纽约','L2价格 USD','L2发生纽约','L2确认纽约','首次25%时间 纽约','首次25%价格 USD','首次25%净 USD','余仓退出比例','余仓退出时间 纽约','余仓退出价格 USD','余仓净 USD','整笔净 USD','原0.1净 USD','净差 USD','净R','初始净风险 USD','最终保护止损 USD','状态','缺口分组','持有期缺口','入场窗口不完整','E确认纽约','余仓退出依据','入场UTC','最终退出UTC','E确认UTC'];
base(trades,col(th.length),te);trades.tabColor='#526D82';title(trades,'全部交易｜0.1 / E1 / E2 完整顺序，逐腿可追溯');
trades.getRange('A4').values=[['未触及T1的亏损按100%退出；B1没有L2时留空。参考价来自真实分钟，非逐笔实盘成交。纽约日期另列UTC，覆盖夏令时切换。']];
trades.getRange('A6:'+col(th.length)+'6').values=[th];head(trades,'A6:'+col(th.length)+'6');
trades.getRange('A7:'+col(th.length)+te).values=allTrades.map(({model,p})=>{
 const t1=p.legs.find(l=>l.reason==='target_25'),rem=p.legs.filter(l=>l.reason!=='target_25'),last=rem.at(-1),refs=p.references,e=p.case_exit_evidence?.find(x=>/^e[12]_exit/.test(x.reason)),before=data['0.1'].result.trades.find(q=>q.entry_time===p.entry_time&&q.entry_rule===p.entry_rule);
 if(rem.length!==1)throw Error('Unexpected remainder aggregation: '+model+' '+p.id);
 return [model,p.id,p.entry_rule,ny(p.entry_time),p.entry,p.initial_stop,ny(p.entry_time),refs.l1?.price??null,ny(refs.l1?.time),ny(refs.l1?.known_at),refs.l2?.price??null,ny(refs.l2?.time),ny(refs.l2?.known_at),ny(t1?.time_utc),t1?.price??null,null,last.fraction,ny(last.time_utc),last.price,null,null,before?.net??null,null,null,p.initial_risk,p.stop,p.status,(p.gap_exposed||p.context_partial)?'含缺口 / 上下文不完整':'无已标记缺口',p.gap_exposed?'是':'否',p.context_partial?'是':'否',ny(e?.confirmed_at),reason[last.reason]||last.reason,p.entry_time,p.exit_time,e?.confirmed_at??null];
});
for(let r=7;r<=te;r++){
 const match="'退出腿与来源'!$A$7:$A$"+le+',A'+r+','+"'退出腿与来源'!$B$7:$B$"+le+',B'+r;
 trades.getRange('P'+r).formulas=[['=IF(ISNUMBER(O'+r+'),SUMIFS('+"'退出腿与来源'!$J$7:$J$"+le+','+match+','+"'退出腿与来源'!$K$7:$K$"+le+',"首次25%止盈"),"")']];
 trades.getRange('T'+r+':U'+r).formulas=[['=SUMIFS('+"'退出腿与来源'!$J$7:$J$"+le+','+match+')-IF(ISNUMBER(P'+r+'),P'+r+',0)','=SUMIFS('+"'退出腿与来源'!$J$7:$J$"+le+','+match+')']];
 trades.getRange('W'+r+':X'+r).formulas=[['=U'+r+'-V'+r,'=U'+r+'/Y'+r]];
}
trades.tables.add('A6:'+col(th.length)+te,true,'SequentialTrades');
for(const c of ['D','G','I','J','L','M','N','R','AE'])dates(trades,c,7,te);
for(const c of ['E','F','H','K','O','P','S','T','U','V','W','Y','Z'])trades.getRange(c+'7:'+c+te).setNumberFormat(usd);
trades.getRange('Q7:Q'+te).setNumberFormat('0%');trades.getRange('X7:X'+te).setNumberFormat('0.0000');
trades.getRange('AB6:AB'+te).format.columnWidth=31;trades.getRange('AF6:AF'+te).format.columnWidth=28;trades.getRange('AG6:AI'+te).format.columnWidth=30;
trades.getRange('AG7:AI'+te).setNumberFormat('yyyy-mm-dd hh:mm" UTC"');
trades.getRange('U7:W'+te).conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{font:{color:'#B42318'}}});
trades.freezePanes.freezeRows(6);trades.freezePanes.freezeColumns(3);

base(summary,'L',29);summary.tabColor='#243B53';title(summary,'30天完整顺序重跑｜保留0.1，E1与E2分别独立执行');
summary.getRange('A4').values=[['同一冻结分钟流、原入场/风险/止盈参数不变；不是固定入场归因。每笔初始1 BTC；零佣金 + 每边2 bps。']];
summary.getRange('A6:L6').values=[['方案','分组','入场笔数','盈利笔数','亏损笔数','已平仓净 USD','净R','最大回撤 R','持有缺口笔数','未平仓笔数','提前退出次数','较0.1全部净差']];
head(summary,'A6:L6');const groups=[['all','全部'],['no_flagged_gap','无已标记缺口'],['gap_or_partial_context','含缺口 / 上下文不完整']];
let sr=7;
for(const model of models)for(const [g,label] of groups){
 const st=study.summaries[model][g],r=sr++;
 summary.getRange('A'+r+':L'+r).values=[[model,label,null,null,null,null,null,st.max_drawdown_r,st.holding_gap,st.open,g==='all'?(study.changes[model]?.early_exit_count??0):null,null]];
 const match="'全部交易'!$A$7:$A$"+te+',A'+r+(g==='all'?'':','+"'全部交易'!$AB$7:$AB$"+te+',B'+r);
 summary.getRange('C'+r+':G'+r).formulas=[['=COUNTIFS('+match+')','=COUNTIFS('+match+','+"'全部交易'!$U$7:$U$"+te+',">0")','=COUNTIFS('+match+','+"'全部交易'!$U$7:$U$"+te+',"<=0")','=SUMIFS('+"'全部交易'!$U$7:$U$"+te+','+match+')','=SUMIFS('+"'全部交易'!$X$7:$X$"+te+','+match+')']];
 if(g==='all')summary.getRange('L'+r).formulas=[['=F'+r+'-$F$7']];
}
summary.getRange('F7:F15').setNumberFormat(usd);summary.getRange('L7:L15').setNumberFormat(usd);summary.getRange('G7:H15').setNumberFormat('0.0000');summary.getRange('B6:B15').format.columnWidth=31;summary.getRange('F6:F15').format.columnWidth=24;summary.getRange('L6:L15').format.columnWidth=25;
summary.getRange('A18').values=[['完整顺序结论：E1/E2各38笔；新增买点0，未再采取的原入场0；均为19胜19负，原盈利交易未被减利。']];
summary.getRange('A20').values=[['提前释放的5个空仓窗口均无新越价信号；所以本次完整顺序净额恰与固定入场研究一致，并非跳过顺序重跑。']];
summary.getRange('A22').values=[['分组注意：#12提前退出避开后段观测缺口，0.1无缺口36笔变成E1/E2各37笔；分组净额差不能当固定样本改善。']];
summary.getRange('A24').values=[['含缺口结果单列，未补齐558个缺失分钟；无已标记缺口不保证所有更早阻力背景完整。全部为样本内模型研究。']];
summary.getRange('A26').values=[['当前表仅保留本轮三条序列；旧研究从页面和本表移除，原文件与0.1冻结档案保留，不改变正式0.1。']];
summary.freezePanes.freezeRows(6);summary.freezePanes.freezeColumns(2);

const altered=models.slice(1).flatMap(m=>study.changes[m].changed_same_entry.map(x=>({model:m,...x})));
const ce=6+altered.length;base(changes,'L',25);title(changes,'提前离场后的完整顺序变化｜没有新增或丢失买点');
changes.getRange('A6:L6').values=[['方案','原# / 新#','原退出 纽约','新退出 纽约','原净 USD','新净 USD','净差 USD','释放分钟','新越价信号','合格候选','原缺口标记','新缺口标记']];head(changes,'A6:L6');
changes.getRange('A7:L'+ce).values=altered.map(x=>{const w=study.changes[x.model].freed_windows.find(v=>v.new_trade_id===x.new_trade_id);return [x.model,x.baseline_trade_id+' / '+x.new_trade_id,ny(x.baseline_exit),ny(x.new_exit),x.baseline_net,x.new_net,null,w.minutes,w.crossed_signal_count,w.qualified_signal_count,x.baseline_gap?'是':'否',x.new_gap?'是':'否'];});
for(let r=7;r<=ce;r++)changes.getRange('G'+r).formulas=[['=F'+r+'-E'+r]];
changes.tables.add('A6:L'+ce,true,'SequenceChanges');dates(changes,'C',7,ce);dates(changes,'D',7,ce);changes.getRange('E7:G'+ce).setNumberFormat(usd);
changes.getRange('A15').values=[['逐一核对提前退出至原退出的空仓窗口：新增买点0；原38笔时间、路线、入场价、初始止损与T1均一致。']];
changes.getRange('A17').values=[['E1/E2各有56条越价信号，与0.1清单一致。旧入场结构仍在每次入场后消费，不因提前退出而重新使用。']];
changes.getRange('A19').values=[['E1：#11、#12、#32减亏；E2：#12、#32减亏。两者是互斥方案，不能把减亏额相加。']];
changes.freezePanes.freezeRows(6);changes.freezePanes.freezeColumns(2);

const chrono=[];
for(const m of models)for(const b of data[m].ledger)chrono.push([m,ny(b.time),ny(b.end),b.open,b.high,b.low,b.close,b.observed_minutes,b.l1_price??null,ny(b.l1_time),ny(b.l1_known_at),b.l2_price??null,ny(b.l2_time),b.stop??null,b.remaining,b.position_id??null,b.events.map(e=>zoned(e.time_utc)+' '+e.type+(e.price!=null?' @ '+e.price:'')+(e.stop!=null?' stop '+e.stop:'')+(e.reason?' '+e.reason:'')).join(' | '),b.time]);
const che=6+chrono.length;base(timeline,'R',che);title(timeline,'逐根15分钟｜实际观测聚合，不补缺口');
timeline.getRange('A4').values=[['L1/L2为该时点扫描状态，不能替换已持仓的父D；每笔入场采用的D/L2见“全部交易”。覆盖<15分钟的K线仅保留实际观测。']];
timeline.getRange('A6:R6').values=[['方案','K线起点 纽约','K线结束 纽约','开 USD','高 USD','低 USD','收 USD','观测分钟 /15','扫描L1 USD','L1发生纽约','L1确认纽约','扫描L2 USD','L2发生纽约','持仓保护止损 USD','剩余初始比例','持仓交易#','实际事件 / 时间 / 参考价','K线起点UTC']];head(timeline,'A6:R6');
timeline.getRange('A7:R'+che).values=chrono;timeline.tables.add('A6:R'+che,true,'Chronological15m');
for(const c of ['B','C','J','K','M'])dates(timeline,c,7,che);
for(const c of ['D','E','F','G','I','L','N'])timeline.getRange(c+'7:'+c+che).setNumberFormat(usd);
timeline.getRange('O7:O'+che).setNumberFormat('0%');timeline.getRange('Q6:Q'+che).format.columnWidth=95;timeline.getRange('R6:R'+che).format.columnWidth=30;timeline.freezePanes.freezeRows(6);timeline.freezePanes.freezeColumns(3);
timeline.getRange('R7:R'+che).setNumberFormat('yyyy-mm-dd hh:mm" UTC"');
for(const [s,rows,last] of [[summary,[4,18,20,22,24,26],'L'],[trades,[4],'L'],[changes,[15,17,19],'L'],[timeline,[4],'R']]){
 for(const row of rows){const range=s.getRange('A'+row+':'+last+row);range.merge();range.format.wrapText=true;range.format.rowHeight=42;}
}
await wb.recalculate();
for(let i=0;i<allLegs.length;i++)if(Math.abs(legs.getRange('J'+(i+7)).values[0][0]-allLegs[i].l.net)>1e-8)throw Error('Leg reconciliation '+i);
for(let i=0;i<allTrades.length;i++)if(Math.abs(trades.getRange('U'+(i+7)).values[0][0]-allTrades[i].p.net)>1e-8)throw Error('Trade reconciliation '+i);
const check=summary.getRange('A7:L15').values;
for(let i=0;i<check.length;i++){const model=models[Math.floor(i/3)],g=groups[i%3][0],want=study.summaries[model][g];if(Math.abs(check[i][5]-want.net)>1e-8||check[i][2]!==want.entries||Math.abs(check[i][6]-want.net_r)>1e-8)throw Error('Group reconciliation '+model+' '+g);}
const before=summary.getRange('F7').values[0][0];legs.getRange('N6').values=[[3]];await wb.recalculate();if(summary.getRange('F7').values[0][0]>=before)throw Error('Cost sensitivity');legs.getRange('N6').values=[[2]];await wb.recalculate();if(Math.abs(summary.getRange('F7').values[0][0]-before)>1e-8)throw Error('Cost restore');
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},summary:'Final formula errors'});
await fs.writeFile(path.join(out,'FORMULA_SCAN.json'),scan.ndjson);
await fs.writeFile(path.join(out,'VERIFICATION.json'),JSON.stringify({study:study.study_id,trades:allTrades.length,legs:allLegs.length,bars:chrono.length,summary:check,reconciled:true,cost_sensitivity_passed:true},null,2));
for(const [sheetName,range,label] of [['本轮比较','A1:L26','总览'],['全部交易','A6:J12','入场保护'],['全部交易','N6:AF12','退出盈亏'],['全部交易','AG6:AI12','UTC时间'],['退出腿与来源','A1:L12','逐腿计算'],['退出腿与来源','N5:P18','来源'],['顺序变化','A1:L19','顺序'],['逐根15分钟','A1:R5','逐根标题'],['逐根15分钟','A6:I12','逐根'],['逐根15分钟','J6:R12','逐根参考']]){
 const img=await wb.render({sheetName,range,scale:1});await fs.writeFile(path.join(out,label+'.png'),new Uint8Array(await img.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb),target=path.join(out,'E1_E2_SEQUENTIAL_30D.xlsx');await xlsx.save(target);
await fs.copyFile(target,path.join(folder,'E1_E2_SEQUENTIAL_30D.xlsx'));
console.log(JSON.stringify({file:target,trades:allTrades.length,legs:allLegs.length,bars:chrono.length,summary:check}));
