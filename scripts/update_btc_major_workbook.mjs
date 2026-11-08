import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {constants} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const root=process.cwd(), reportDir=path.join(root,'reports/btc_structure_2026_11_08');
const out=path.join(root,'outputs/btc_structure_2026_11_08');
const deps=path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
await fs.mkdir(out,{recursive:true});
try{await fs.symlink(deps,path.join(out,'node_modules'),'dir');}catch(e){if(e.code!=='EEXIST')throw e;}
const require=createRequire(path.join(out,'package.json'));
const {FileBlob,Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const filename=path.join(reportDir,'BTC_30_DAY_RETEST.xlsx');
const original=path.join(reportDir,'BTC_30_DAY_RETEST_V1_1.xlsx');
try{await fs.copyFile(filename,original,constants.COPYFILE_EXCL);}catch(e){if(e.code!=='EEXIST')throw e;}
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(original));
const revised=JSON.parse(await fs.readFile(path.join(reportDir,'major_resistance/MAJOR_RETEST.json'),'utf8'));
const old=JSON.parse(await fs.readFile(path.join(reportDir,'RETEST.json'),'utf8'));
const base=revised.runs[1], comparison=base.comparison;
const summary=wb.worksheets.getItem('总览'),cand=wb.worksheets.getItem('突破候选'),params=wb.worksheets.getItem('参数');
const review=wb.worksheets.getItem('本次逐K审查'),data=wb.worksheets.getItem('原始15分钟');
// Preserve unrelated current-chart and source tables exactly, including formulas.
const untouched={reviewValues:JSON.stringify(review.getUsedRange().values),reviewFormulas:JSON.stringify(review.getUsedRange().formulas),dataValues:JSON.stringify(data.getUsedRange().values)};
const trades=wb.worksheets.add('模拟交易');
const fmt='$#,##0.00;($#,##0.00);"—"',rrFmt='0.00"x";(0.00"x");"—"',rFmt='0.00"R";(0.00"R");"—"';
function header(s,a){const r=s.getRange(a);r.format.fill='#243B53';r.format.font={name:'Arial',size:11,bold:true,color:'#FFFFFF'};r.format.horizontalAlignment='center';r.format.rowHeight=30;}
function wall(iso){return new Date(iso.slice(0,19)+'Z');}
function date(t){return new Date(t*1000);}
function title(s,text){s.getRange('A2').values=[[text]];}

title(params,'V1.2 重要波段阻力（固定定义）');
params.getRange('C16').values=[['7天内已确认重要1小时高点；相交区域合并']];
params.getRange('A22:C22').values=[['模拟交易固定单边摩擦 bps',2,'交易明细固定原2bps；编辑上方成本只改变价格筛选']];
params.getRange('A23:C28').clear({applyTo:'contents'});
params.getRange('A24:C31').values=[
 ['波段高点左右确认 / 小时',2,'峰值严格高于左右各2根完整小时K线'],
 ['前后起伏最低 / 小时ATR',1,'前侧上升、后侧回撤分别达到峰值时小时ATR(14)'],
 ['阻力区半宽 / 小时ATR',0.15,'峰值±0.15小时ATR；相交区域合并，按近端下沿定T1'],
 ['小时数据','4根完整15分钟','缺一根不生成小时K；不得提前使用未确认波峰'],
 ['最近区域','包含现价的区域也算','身处区域内不能跳过它选远处目标；缺阻力不交易'],
 ['其他条件','保持V1.1不变','15分钟入场、止损、2R、缓冲、期限及50%退出不变'],
 ['样本性质','同月修订重测','本月已用于修改定义，不是样本外验证'],
 ['真实订单',0,'仅研究，无真实交易或ETF收益']
];
params.getRange('A24:A31').format.columnWidth=31;
params.getRange('B22:B31').format.font={name:'Arial',size:11,color:'#172B4D'};
params.getRange('B22:B31').format.fill='#FFFFFF';
params.getRange('B22:B31').setNumberFormat('General');
params.getRange('B26').setNumberFormat('0.00');
params.getRange('B24:B26').format.columnWidth=30;

title(cand,'同一114个信号：小高点与重要波段对照');
cand.getRange('A4').values=[['G–J为新版价格筛选；R–T保留旧版；通过筛选不等于能开仓，需核对持仓与次根成交。']];
const n=comparison.length,last=n+6;
cand.getRange(`C7:W${last}`).clear({applyTo:'contents'});
cand.getRange('C6:W6').values=[['信号收盘参考','结构止损','新版目标T1','新版目标T2','新版基准净RR','新版零摩擦RR','新版压力净RR','新版价格筛选','确认K线高点','L1低点','L2低点','信号ATR','波段阻力下沿','确认K线开始UTC','固定2bps研究结论','旧版最近小高点','旧版目标T1','旧版基准净RR','波段阻力上沿','区域最晚确认UTC','组成波峰数']];
header(cand,'A6:W6');
const execution=new Map(base.candidates.map(c=>[c.signal_t,c]));
const outcomes=new Map(base.trades.map(t=>[t.signal_time_utc,t]));
for(let i=0;i<n;i++){
 const c=comparison[i],row=i+7,z=c.major_zones[0];
 const x=execution.get(c.signal_t);
 let decision=c.major_pass?(x?.decision.startsWith('entered:')?'模拟入场；见交易明细':'通过；当时已有持仓'):(c.major_t1==null?'放弃：缺已确认波段阻力':'放弃：净RR不足');
 cand.getRange(`C${row}:W${row}`).values=[[c.close_reference,c.stop,c.major_t1,c.major_t2,null,null,null,null,c.trigger,c.l1,c.l2,c.atr,c.major_resistance,new Date(c.confirmation_bar_utc),decision,c.resistance,c.t1,c.reward_risk,z?.upper??null,z?date(Math.max(...z.members.map(p=>p.known_at))):null,z?.members.length??0]];
 if(c.major_t1!=null){
  const formula=p=>`=(E${row}-C${row}-'参数'!${p}/10000*(C${row}+E${row}))/(C${row}-D${row}+'参数'!${p}/10000*(C${row}+D${row}))`;
  cand.getRange(`G${row}:I${row}`).formulas=[[formula('$B$6'),formula('$B$7'),formula('$B$8')]];
 }else cand.getRange(`G${row}:I${row}`).values=[['n.a.','n.a.','n.a.']];
 cand.getRange(`J${row}`).formulas=[[`=IF(E${row}="","放弃：缺已确认波段阻力",IF(G${row}>='参数'!$B$5,"通过价格筛选","放弃：净RR不足"))`]];
}
cand.getRange(`C7:F${last}`).setNumberFormat(fmt);
cand.getRange(`G7:I${last}`).setNumberFormat(rrFmt);
cand.getRange(`K7:O${last}`).setNumberFormat(fmt);
cand.getRange(`R7:S${last}`).setNumberFormat(fmt);
cand.getRange(`T7:T${last}`).setNumberFormat(rrFmt);
cand.getRange(`U7:U${last}`).setNumberFormat(fmt);
cand.getRange(`V7:V${last}`).setNumberFormat('mm/dd/yy hh:mm');
cand.getRange(`W7:W${last}`).setNumberFormat('0');
cand.getRange(`R6:W${last}`).format.font={name:'Arial',size:11,color:'#172B4D'};
cand.getRange(`R6:W${last}`).format.columnWidth=23;header(cand,'R6:W6');
cand.getRange(`J1:J${last}`).format.columnWidth=29;
cand.getRange(`Q1:Q${last}`).format.columnWidth=34;
for(const t of [...cand.tables.items])t.delete();
cand.tables.add(`A6:W${last}`,true,'BtcCandidatesV12');

trades.showGridLines=false;
trades.getRange('A1:N42').format.font={name:'Arial',size:11,color:'#172B4D'};
trades.getRange('A1:N42').format.rowHeight=24;
trades.getRange('A1:N42').format.columnWidth=18;
title(trades,'固定2bps：模拟交易与分批退出');
trades.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#172B4D'};
trades.getRange('A4').values=[['R为每笔初始计划风险；这些是OHLC模型成交，止盈/止损所在15分钟区间不代表准确成交秒数。']];
trades.getRange('A6:L6').values=[['编号','入场确认 纽约','模型入场 纽约','模型买价','初始止损','第一目标','第二目标','退出区间 纽约','最后退出原因','全仓净结果 R','累计 R','已知结果']];header(trades,'A6:L6');
const tLast=6+base.trades.length;
const fillHeader=tLast+6,fillStart=fillHeader+1,fillLast=fillHeader+base.fills.length;
const tradeMap=new Map(base.trades.map(t=>[t.id,t]));
for(let i=0;i<base.trades.length;i++){
 const t=base.trades[i],row=7+i;
 trades.getRange(`A${row}:L${row}`).values=[[t.id,wall(t.signal_time_ny),wall(t.entry_time_ny),t.entry,t.initial_stop,t.t1,t.t2,wall(t.exit_time_ny),t.net_r>0&&t.exit_reason==='stop'?'分批止盈后移动保护退出':t.exit_reason==='stop'?'止损退出':t.exit_reason,null,null,t.net_r>0?'盈利':'亏损']];
 trades.getRange(`J${row}:K${row}`).formulas=[[`=SUMIFS(K${fillStart}:K${fillLast},A${fillStart}:A${fillLast},A${row})`,`=SUM(J$7:J${row})`]];
}
trades.getRange(`A${fillHeader}:K${fillHeader}`).values=[['交易编号','退出区间开始UTC','退出区间开始纽约','时间口径','原因','初始仓位比例','模型卖价','原模型买价','初始风险 $/BTC','本次净值差 $/BTC','本次贡献 R']];header(trades,`A${fillHeader}:K${fillHeader}`);
for(let i=0;i<base.fills.length;i++){
 const f=base.fills[i],row=fillStart+i,t=tradeMap.get(f.trade_id);
 trades.getRange(`A${row}:K${row}`).values=[[f.trade_id,new Date(f.time_utc),wall(f.time_ny),f.time_basis.includes('interval')?'该15分钟内；准确时刻未知':'下一根开盘',f.reason,f.fraction_initial,f.model_price,t.entry,t.initial_risk,null,null]];
 trades.getRange(`J${row}:K${row}`).formulas=[[`=F${row}*(G${row}-H${row}-'参数'!$B$22/10000*(G${row}+H${row}))`,`=J${row}/I${row}`]];
}
trades.getRange(`B7:C${tLast}`).setNumberFormat('mm/dd/yy hh:mm');trades.getRange(`H7:H${tLast}`).setNumberFormat('mm/dd/yy hh:mm');
trades.getRange(`D7:G${tLast}`).setNumberFormat(fmt);trades.getRange(`J7:K${tLast}`).setNumberFormat(rFmt);
trades.getRange(`B${fillStart}:C${fillLast}`).setNumberFormat('mm/dd/yy hh:mm');
trades.getRange(`F${fillStart}:F${fillLast}`).setNumberFormat('0%');trades.getRange(`G${fillStart}:J${fillLast}`).setNumberFormat(fmt);trades.getRange(`K${fillStart}:K${fillLast}`).setNumberFormat(rFmt);
trades.getRange('A1:A42').format.columnWidth=9;trades.getRange('B1:C42').format.columnWidth=25;
trades.getRange('H1:H42').format.columnWidth=25;trades.getRange('I1:I42').format.columnWidth=37;
trades.getRange('L1:L42').format.columnWidth=18;trades.getRange(`D${fillHeader}:D${fillLast}`).format.columnWidth=25;
trades.tables.add(`A6:L${tLast}`,true,'BtcModelTrades');trades.tables.add(`A${fillHeader}:K${fillLast}`,true,'BtcModelExitLegs');
trades.freezePanes.freezeRows(6);trades.freezePanes.freezeColumns(1);

title(summary,'BTC复测：重要波段阻力 vs 小高点');
summary.getRange('A8:D31').clear({applyTo:'contents'});
summary.getRange('A8:D8').values=[['同批候选对照','V1.1 小高点','V1.2 重要波段','说明']];header(summary,'A8:D8');
summary.getRange('A9:D15').values=[
 ['完整测试K线',2880,2880,'相同30天区间和源数据；另有672根预热'],
 ['同批突破候选',114,114,'持仓是否占用不影响这一独立价格筛选对照'],
 ['固定2bps通过2R',0,base.summary.same_signal_passes,'新版14个；其中4个出现时仍在持仓'],
 ['固定2bps模型入场',0,base.summary.model_entries,'同时只持有一笔，未开重复仓位'],
 ['已平仓交易',0,base.summary.closed_trades,'全为OHLC模型结果，没有真实下单'],
 ['盈利 / 亏损','不适用',`${base.summary.winners} / ${base.summary.closed_trades-base.summary.winners}`,'胜率及盈亏请结合小样本与建模假设'],
 ['净结果 R','不适用',null,'每笔1R固定为初始计划风险；不是账户收益率']
];
summary.getRange('C15').formulas=[[`=SUM('模拟交易'!J7:J${tLast})`]];summary.getRange('C15').setNumberFormat(rFmt);
summary.getRange('A18:D18').values=[['成本对照 / 每边','同114信号通过2R','模型入场 / 平仓','模型净结果 R']];header(summary,'A18:D18');
for(let i=0;i<3;i++){
 const run=revised.runs[i],row=19+i;
 summary.getRange(`A${row}:D${row}`).values=[[run.config.one_way_friction_bps,run.summary.same_signal_passes,`${run.summary.model_entries} / ${run.summary.closed_trades}`,run.summary.net_closed_r]];
}
summary.getRange('A19:A21').setNumberFormat('0.0" bps"');summary.getRange('D19:D21').setNumberFormat(rFmt);
summary.getRange('A24').values=[['结论：小高点定义确实过严；改为重要波段后有买点，但本月固定2bps模型仍亏损约6.72R。']];
summary.getRange('A26').values=[['注意：本月用于发现问题并修订定义，仍是样本内研究。尚未证明此方法有盈利优势。']];
summary.getRange('A28').values=[['黄色成本/2R输入只重算候选筛选；固定模拟交易不随之重跑。旧R1/T1/RR保留在候选R–T列。']];
summary.getRange('A30').values=[['本次逐K审查仍保留11月8日11:25历史快照；这里没有刷新当前报价，也没有真实订单。']];
summary.getRange('A32:C32').values=[['固定2bps模拟胜率',null,'收盘标记最大回撤 R']];
summary.getRange('B32').formulas=[[`=COUNTIFS('模拟交易'!J7:J${tLast},">0")/COUNTA('模拟交易'!A7:A${tLast})`]];summary.getRange('B32').setNumberFormat('0.0%');
summary.getRange('D32').values=[[base.summary.max_drawdown_r]];summary.getRange('D32').setNumberFormat(rFmt);
summary.getRange('A34').values=[['重要波段：已完成1小时高点，左右各2小时确认，前后起伏≥1小时ATR，相交区域合并。']];
summary.getRange('A36').values=[['来源与研究说明：https://github.com/renshangh/ai-day-trade/blob/main/docs/BTC_STRUCTURE_RETEST.md']];
summary.getRange('A1:A37').format.columnWidth=28;summary.getRange('B1:B37').format.columnWidth=26;
summary.getRange('C1:C37').format.columnWidth=33;summary.getRange('D1:D37').format.columnWidth=53;

const expected=comparison.filter(c=>c.major_pass).length;
const before=cand.getRange('G7').values[0][0];params.getRange('B6').values=[[3]];
if(typeof before==='number'&&!(cand.getRange('G7').values[0][0]<before))throw new Error('Cost edit did not recalculate');
params.getRange('B6').values=[[2]];
wb.recalculate();
for(let i=0;i<n;i++){
 const c=comparison[i],v=cand.getRange(`G${i+7}`).values[0][0];
 if(c.major_reward_risk!=null&&Math.abs(v-c.major_reward_risk)>1e-9)throw new Error('Revised RR mismatch');
}
for(let i=0;i<base.trades.length;i++){
 if(Math.abs(trades.getRange(`J${i+7}`).values[0][0]-base.trades[i].net_r)>1e-9)throw new Error('Trade legs do not reconcile');
}
if(Math.abs(summary.getRange('C15').values[0][0]-base.summary.net_closed_r)>1e-9)throw new Error('Net R mismatch');
if(untouched.reviewValues!==JSON.stringify(review.getUsedRange().values)||untouched.reviewFormulas!==JSON.stringify(review.getUsedRange().formulas)||untouched.dataValues!==JSON.stringify(data.getUsedRange().values))throw new Error('Unrelated historical review or original data changed');
console.log('Reconciled',expected,'same-signal passes;',base.trades.length,'closed model trades; net R',summary.getRange('C15').values[0][0]);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'Revised formula error scan'})).ndjson);
for(const [sheetName,range,name] of [['总览','A1:H37','MAJOR_SUMMARY'],['突破候选','A1:J14','MAJOR_CANDIDATES'],['参数','A20:C31','MAJOR_PARAMETERS'],['模拟交易','A1:L18','MAJOR_TRADES'],['模拟交易',`A${fillHeader}:K${fillLast}`,'MAJOR_LEGS']]){
 const preview=await wb.render({sheetName,range,scale:1.25,format:'png'});
 await fs.writeFile(path.join(out,name+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
const result=await SpreadsheetFile.exportXlsx(wb);
await result.save(path.join(out,'BTC_30_DAY_RETEST.xlsx'));
await fs.copyFile(path.join(out,'BTC_30_DAY_RETEST.xlsx'),filename);
console.log('Updated '+filename);
