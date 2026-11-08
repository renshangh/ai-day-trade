import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const root=process.cwd();
const output=path.join(root,'outputs/btc_structure_2026_11_08');
await fs.mkdir(output,{recursive:true});
const dependencies=path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
try {await fs.symlink(dependencies,path.join(output,'node_modules'),'dir');} catch(e) {if(e.code!=='EEXIST') throw e;}
const require=createRequire(path.join(output,'package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const reportDir=path.join(root,'reports/btc_structure_2026_11_08');
const report=JSON.parse(await fs.readFile(path.join(reportDir,'RETEST.json'),'utf8'));
const current=JSON.parse(await fs.readFile(path.join(reportDir,'CURRENT_SNAPSHOT.json'),'utf8'));
const base=report.runs[1];
const sourceStart=Date.parse(report.warmup_start_utc)/1000;
const sourceEnd=Date.parse(report.end_utc)/1000;
const raw=new Map();
for(const request of report.provenance.requests){
  for(const r of JSON.parse(await fs.readFile(path.join(reportDir,'raw',request.file),'utf8'))){
    if(r[0]>=sourceStart&&r[0]<sourceEnd)raw.set(r[0],r);
  }
}
const observations=[...raw.values()].sort((a,b)=>a[0]-b[0]);
const wb=Workbook.create();
const summary=wb.worksheets.add('总览');
const candidates=wb.worksheets.add('突破候选');
const today=wb.worksheets.add('本次逐K审查');
const params=wb.worksheets.add('参数');
const data=wb.worksheets.add('原始15分钟');
const color={ink:'#172B4D',header:'#243B53',rule:'#D9E2EC',input:'#FFF4CC',amber:'#FFF1D6'};
function formatSheet(sheet,lastCol,lastRow){
  sheet.showGridLines=false;
  const area=sheet.getRange(`A1:${lastCol}${lastRow}`);
  area.format.font={name:'Arial',size:11,color:color.ink};
  area.format.rowHeight=22;
  area.format.verticalAlignment='center';
  area.format.columnWidth=16;
}
function title(sheet,text){sheet.getRange('A2').values=[[text]];sheet.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:color.ink};}
function header(sheet,range){const r=sheet.getRange(range);r.format.fill=color.header;r.format.font={name:'Arial',size:11,bold:true,color:'#FFFFFF'};r.format.rowHeight=30;r.format.horizontalAlignment='center';}
function table(sheet,range,name){sheet.tables.add(range,true,name);}
const fmt='$#,##0.00;($#,##0.00);"—"';
const ratio='0.00"x";(0.00"x");"—"';

formatSheet(params,'D',31);title(params,'V1.1 初次测试参数');
params.getRange('A4:C4').values=[['参数','数值','说明']];header(params,'A4:C4');
params.getRange('A5:C20').values=[
 ['最低净收益风险倍数',2,'可调整，候选比例与筛选随之重算'],
 ['基准单边摩擦 bps',2,'可调整；包含假设价差和滑点，不是现货费率'],
 ['零摩擦对照 bps',0,'乐观上界；不代表真实零成本'],
 ['压力单边摩擦 bps',5,'假设值；不是实时成交成本'],
 ['止损缓冲 / ATR',0.25,'下列结构参数是本次快照；更改后需重新运行复测'],
 ['目标缓冲 / ATR',0.10,'T1为最近已知阻力减去该缓冲'],
 ['更高低点最小差 / ATR',0.10,'L2须高于前个已确认摆动低点L1'],
 ['允许追价 / ATR',0.10,'次根开盘仍须满足入场价上限与2R'],
 ['信号有效期 / 根',8,'确认K线后最多等待8根15分钟K线'],
 ['摆动点左右确认 / 根',1,'严格低于/高于左右各一根；右侧完成后才可用'],
 ['ATR周期 / 根',14,'简单平均真实波幅；非Wilder平滑'],
 ['阻力回看 / 根',672,'7天内全部已确认15分钟摆动高点，未人工分级'],
 ['T1卖出初始持仓比例',0.5,'后续退出剩余全部，非剩余仓位再减半'],
 ['长上影 / 全振幅',0.5,'阻力失败的研究阈值；本轮无交易可验证退出'],
 ['佣金假设',0,'按用户ETF零佣金；本轮只测BTC全天结构'],
 ['真实订单数量',0,'只读研究，没有预览或下单']
];
params.getRange('A5:A20').format.columnWidth=31;
params.getRange('B5:B20').format.columnWidth=14;
params.getRange('C5:C20').format.columnWidth=81;
params.getRange('B5:B8').format.fill=color.input;
params.getRange('B5:B8').format.font.color='#0000FF';
params.getRange('B9:B12').setNumberFormat('0.00');
params.getRange('B17:B18').setNumberFormat('0%');
params.getRange('A23:C28').values=[
 ['规则边界','本次不加1小时趋势硬过滤，只保留15分钟已确认阻力。',null],
 ['限制','阻力重要性未分类；每个小高点都计入可能过严。',null],
 ['执行模型','触发后仅看次根开盘是否在限价内；其余放弃，不追价。',null],
 ['同根双触及','先止损；限价要求严格越价；成交时刻未知。',null],
 ['退出验证','0笔交易，因此胜率、利润和分批退出效果均不可评估。',null],
 ['表格更新','修改成本/2R可重算筛选；结构及原始行情不是自动更新。',null]
];params.getRange('B23:B28').format.columnWidth=30;

const n=base.candidates.length;
formatSheet(candidates,'Q',n+7);title(candidates,'30天局部突破候选');
candidates.getRange('A4').values=[['确认时间以纽约时区显示；UTC用于DST重叠时段核对。无真实或模拟成交。']];
const headings=['确认时间 纽约','确认时间 UTC','信号收盘参考','结构止损','第一目标 T1','第二目标 T2','基准净RR','零摩擦RR','压力净RR','价格筛选','已完成K线高点','L1低点','L2低点','信号ATR','最近阻力','确认K线开始UTC','原研究结论'];
candidates.getRange('A6:Q6').values=[headings];header(candidates,'A6:Q6');
const chineseDecision=d=>d.startsWith('rejected: net')?'放弃：净RR不足':d;
// Excel dates have no timezone. A stores NY wall time; B preserves true UTC.
// Do not feed offset ISO strings to automatic coercion, which converts to UTC.
const cRows=base.candidates.map(c=>[new Date(c.confirmed_ny.slice(0,19)+'Z'),new Date(c.confirmed_utc),c.close_reference,c.stop,c.t1,c.t2,null,null,null,null,c.trigger,c.l1,c.l2,c.atr,c.resistance,new Date(c.confirmation_bar_utc),chineseDecision(c.decision)]);
candidates.getRange(`A7:Q${n+6}`).values=cRows;
for(let row=7;row<=n+6;row++){
  const e=`C${row}`,s=`D${row}`,t=`E${row}`;
  const rr=(cell)=>`(${t}-${e}-'参数'!${cell}/10000*(${e}+${t}))/(${e}-${s}+'参数'!${cell}/10000*(${e}+${s}))`;
  candidates.getRange(`G${row}:J${row}`).formulas=[['='+rr('$B$6'),'='+rr('$B$7'),'='+rr('$B$8'),`=IF(G${row}>='参数'!$B$5,"通过价格筛选；结构和成交需另查","放弃：净RR不足")`]];
}
candidates.getRange(`A7:B${n+6}`).setNumberFormat('mm/dd/yy hh:mm');
candidates.getRange(`P7:P${n+6}`).setNumberFormat('mm/dd/yy hh:mm');
candidates.getRange(`C7:F${n+6}`).setNumberFormat(fmt);
candidates.getRange(`K7:O${n+6}`).setNumberFormat(fmt);
candidates.getRange(`G7:I${n+6}`).setNumberFormat(ratio);
candidates.getRange(`G7:G${n+6}`).conditionalFormats.add('cellIs',{operator:'lessThan',formula:"'参数'!$B$5",format:{fill:color.amber}});
candidates.getRange(`A1:B${n+6}`).format.columnWidth=27;
candidates.getRange(`J1:J${n+6}`).format.columnWidth=35;
candidates.getRange(`P1:P${n+6}`).format.columnWidth=24;
candidates.getRange(`Q1:Q${n+6}`).format.columnWidth=26;
candidates.freezePanes.freezeRows(6);candidates.freezePanes.freezeColumns(2);
table(candidates,`A6:Q${n+6}`,'BtcCandidates');

const ledger=new Map(base.ledger.map(x=>[Date.parse(x.start_utc)/1000,x]));
const ny=new Intl.DateTimeFormat('sv-SE',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
formatSheet(data,'K',observations.length+6);title(data,'Coinbase BTCUSD 原始15分钟');
data.getRange('A4').values=[['Source: Coinbase Exchange BTC-USD candles; '+report.source]];
data.getRange('A6:K6').values=[['起始时间 UTC','起始时间 纽约','开盘','最高','最低','收盘','成交量 BTC','30天测试期','完成时ATR','逐K研究状态','收盘确认时间UTC']];header(data,'A6:K6');
const dRows=observations.map(([t,l,h,o,c,v])=>{const a=ledger.get(t);return [new Date(t*1000),'NY '+(a?a.start_ny:ny.format(new Date(t*1000)).replace(' ','T')+':00-04:00'),o,h,l,c,v,a?'测试':'预热',a?.atr??null,a?chineseDecision(a.decision):'预热；不计入30天结果',new Date((t+900)*1000)];});
data.getRange(`A7:K${dRows.length+6}`).values=dRows;
data.getRange(`A7:A${dRows.length+6}`).setNumberFormat('mm/dd/yy hh:mm');
data.getRange(`K7:K${dRows.length+6}`).setNumberFormat('mm/dd/yy hh:mm');
data.getRange(`C7:F${dRows.length+6}`).setNumberFormat(fmt);
data.getRange(`I7:I${dRows.length+6}`).setNumberFormat(fmt);
data.getRange(`G7:G${dRows.length+6}`).setNumberFormat('#,##0.0000');
data.getRange(`A1:B${dRows.length+6}`).format.columnWidth=27;
data.getRange(`B1:B${dRows.length+6}`).format.columnWidth=37;
data.getRange(`J1:J${dRows.length+6}`).format.columnWidth=44;
data.getRange(`K1:K${dRows.length+6}`).format.columnWidth=25;
data.freezePanes.freezeRows(6);data.freezePanes.freezeColumns(2);table(data,`A6:K${dRows.length+6}`,'BtcRawBars');

const ts=[...observations,...current.bars.map(b=>[b.t,b.low,b.high,b.open,b.close,b.volume])].filter(r=>r[0]>=Date.parse('2026-11-08T13:00:00Z')/1000);
formatSheet(today,'K',39);title(today,'11月8日逐K审查（截至11:15 EST）');
today.getRange('A4').values=[['Chrome刷新约11:25 EST；11:15–11:30尚未完成。30天复测区间仍固定截至11:00。']];
today.getRange('A6:K6').values=[['15分钟时段 EST','最早确认时间','开盘','最高','最低','收盘参考','前根已知高点','低点下限参考','练习目标','乐观RR上界','判定']];header(today,'A6:K6');
const reasons=['无回踩确认；阻力处不追','退回76000以下；08:30可确认长上影','下跌延续，无触发','新低，不是更高低点','越过局部高点，但结构与RR不足','无触发；低点仅高1.48','局部突破；RR不足','连续走高，无独立回踩，不追','仅回调，没有收盘突破','盘中越高但收盘未确认','突破候选，但RR不足','收盘未越过前根高点','盘中越过75980.47，收盘失守；不买'];
const lowBounds={4:75778.04,6:75779.52,10:75891.5,11:75891.5,12:75891.5};
const todayRows=ts.map((r,i)=>{
 const [t,l,h,o,c]=r;
 const a=ny.format(new Date(t*1000)).slice(-5),b=ny.format(new Date((t+900)*1000)).slice(-5);
 const previous=raw.get(t-900);
 return [a+'–'+b,b+'后',o,h,l,c,previous?.[2]??null,lowBounds[i]??null,75990,null,reasons[i]??'尚未分类'];
});
today.getRange(`A7:K${todayRows.length+6}`).values=todayRows;
for(let r=7;r<todayRows.length+7;r++) today.getRange(`J${r}`).formulas=[[`=IF(H${r}="","n.a.",(I${r}-F${r})/(F${r}-H${r}))`]];
today.getRange(`C7:I${todayRows.length+6}`).setNumberFormat(fmt);
today.getRange(`J7:J${todayRows.length+6}`).setNumberFormat(ratio);
today.getRange('A1:B29').format.columnWidth=20;today.getRange('K1:K29').format.columnWidth=43;
today.getRange('A22').values=[['H列仅为零缓冲计算的低点下限，不是可下单止损；真实保护须在结构低点下方。']];
today.getRange('A24').values=[['08:30长上影退出：只对已持仓情景；不假定卖在76,094.99，也没有任何成交。']];
today.getRange('A26').values=[['11:25结论：未通过买入条件。T1 75,990是先前练习参考，不是自动更新的目标。']];
today.getRange('A28:C28').values=[['价位核算（非订单）','价格','条件']];header(today,'A28:C28');
today.getRange('A29:C33').values=[
 ['10:15回调低点',75891.50,'10:30后已知的低点；不是已确认的新入场'],
 ['11:15时 ATR(14)',current.last_atr,'14根完整真实波幅的简单平均'],
 ['止损示例',null,'低点减0.25 ATR；不作为真实订单'],
 ['第一目标示例',75990,'旧练习阻力76000前；仅供核算'],
 ['按11:15收盘净RR',null,'不足2R，放弃。剩余50%没有预设可信的新目标']
];
today.getRange('B31').formulas=[["=B29-B30*'参数'!B9"]];
today.getRange('B33').formulas=[["=(B32-F19-'参数'!B6/10000*(F19+B32))/(F19-B31+'参数'!B6/10000*(F19+B31))"]];
today.getRange('B29:B32').setNumberFormat(fmt);today.getRange('B33').setNumberFormat(ratio);
today.getRange('C29:C33').format.columnWidth=19;
today.getRange('A35').values=[['新L2候选75,918.51：需等11:30完成后再看右侧是否守住；尚不是已确认止损结构。']];
today.getRange('A37').values=[['若11:30才确认止跌K，后续收盘突破最早11:45评估；届时仍须按实际报价、最近阻力重算2R。']];
today.freezePanes.freezeRows(6);table(today,`A6:K${todayRows.length+6}`,'BtcCurrentReview');

formatSheet(summary,'H',37);title(summary,'BTC 15分钟规则复测');summary.tabColor='#243B53';params.tabColor='#627D98';
summary.getRange('A4:D4').values=[['测试开始 UTC',new Date(report.start_utc),'测试结束 UTC',new Date(report.end_utc)]];
summary.getRange('B4').setNumberFormat('mm/dd/yy hh:mm');summary.getRange('D4').setNumberFormat('mm/dd/yy hh:mm');
summary.getRange('A6').values=[['仓库：https://github.com/renshangh/ai-day-trade']];
summary.getRange('A8:C8').values=[['数据与候选','数量 / 结果','说明']];header(summary,'A8:C8');
summary.getRange('A9:C15').values=[
 ['应有完整K线',report.expected_test_bars,'30天，全天，每日96根'],
 ['实际完整K线',null,'缺失不补造；另有672根预热'],
 ['突破候选',null,'完成更高低点和收盘突破的价格候选'],
 ['基准成本下通过2R',null,'2bps每边是研究假设，不是实测价差'],
 ['原研究模拟入场',0,'原始2bps实验：全部放弃，未建仓'],
 ['胜率 / 交易收益','不适用','0笔交易，不能评价策略盈利或卖出效果'],
 ['当前买点','不合格','11:15收盘突破失败；11:25刷新检查']
];
summary.getRange('B10').formulas=[[`=COUNTIFS('原始15分钟'!H7:H${dRows.length+6},"测试")`]];
summary.getRange('B11').formulas=[[`=COUNTA('突破候选'!A7:A${n+6})`]];
summary.getRange('B12').formulas=[[`=COUNTIFS('突破候选'!G7:G${n+6},">="&'参数'!$B$5)`]];
summary.getRange('A18:D18').values=[['成本对照（每边）','通过价格筛选','最大净RR','不代表ETF收益']];header(summary,'A18:D18');
for(const [row,p,g] of [[19,7,'H'],[20,6,'G'],[21,8,'I']]){
 summary.getRange(`A${row}:D${row}`).formulas=[[`='参数'!B${p}`,`=COUNTIFS('突破候选'!${g}7:${g}${n+6},">="&'参数'!$B$5)`,`=MAX('突破候选'!${g}7:${g}${n+6})`,'="BTC全天结构筛选"']];
}
summary.getRange('A19:A21').setNumberFormat('0.0" bps"');summary.getRange('C19:C21').setNumberFormat(ratio);
summary.getRange('A24').values=[['限制：本轮把近7天所有已确认小高点都当阻力，可能过严；并未完成手册全部主观判断。']];
summary.getRange('A26').values=[['不要把0次入场解释为胜率0%或策略无效。退出、成交滑点及ETF映射尚未得到交易样本验证。']];
summary.getRange('A28').values=[['黄色单元格可调整成本与2R门槛；结构参数与行情快照须重新运行研究后更新。']];
summary.getRange('A30').values=[['当前没有真实订单。下一步先人工审查阻力重要性，再另记规则版本做前瞻验证。']];
summary.getRange('A1:A37').format.columnWidth=28;summary.getRange('B1:B37').format.columnWidth=27;
summary.getRange('C1:C37').format.columnWidth=55;summary.getRange('D1:D37').format.columnWidth=27;
summary.getRange('E1:H37').format.columnWidth=10;

// Check an editable cost driver and restore it before the final recalculation.
const originalRR=candidates.getRange('G7').values[0][0];
params.getRange('B6').values=[[3]];
const changedRR=candidates.getRange('G7').values[0][0];
if(!(changedRR<originalRR))throw new Error('Cost driver did not recalculate candidate RR');
params.getRange('B6').values=[[2]];
wb.recalculate();
for(let i=0;i<n;i++){
 const calculated=candidates.getRange(`G${i+7}`).values[0][0];
 if(Math.abs(calculated-base.candidates[i].reward_risk)>1e-9)throw new Error('Spreadsheet/Python RR disagreement');
}
console.log('Summary controls',JSON.stringify(summary.getRange('B10:B12').values));
if(summary.getRange('B10').values[0][0]!==2880||summary.getRange('B11').values[0][0]!==114||summary.getRange('B12').values[0][0]!==0)throw new Error('Summary reconciliation failed');
console.log((await wb.inspect({kind:'table',range:'总览!A8:D21',include:'values,formulas',tableMaxRows:14,tableMaxCols:4})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:40},summary:'Final formula error scan'})).ndjson);
const renders=[['总览','A1:H31','SUMMARY'],['突破候选','A1:J13','CANDIDATES'],['本次逐K审查','A1:K38','CURRENT'],['参数','A1:C28','PARAMETERS'],['原始15分钟','A1:I13','DATA']];
for(const [sheetName,range,name] of renders){
 const image=await wb.render({sheetName,range,scale:1.25,format:'png'});
 await fs.writeFile(path.join(output,name+'.png'),new Uint8Array(await image.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
const destination=path.join(output,'BTC_30_DAY_RETEST.xlsx');
await xlsx.save(destination);
await fs.copyFile(destination,path.join(reportDir,'BTC_30_DAY_RETEST.xlsx'));
console.log('Saved '+destination);
