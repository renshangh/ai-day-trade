import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const root=process.cwd();
const previewB1Only=process.argv.includes('--preview-b1-only');
const store=path.join(root,'trading_records/btc_structure');
const {run_id}=JSON.parse(await fs.readFile(path.join(store,'latest_run.json'),'utf8'));
const output=path.join(root,'outputs','btc_30d_'+run_id);
await fs.mkdir(output,{recursive:true});
const deps='/Users/danielshan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
try{await fs.symlink(deps,path.join(output,'node_modules'),'dir');}catch(e){if(e.code!=='EEXIST')throw e;}
const require=createRequire(path.join(output,'package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const folder=path.join(store,'runs',run_id);
const {result:r,ledger}=JSON.parse(await fs.readFile(path.join(folder,'WORKBOOK_DATA.json'),'utf8'));
const comparison=JSON.parse(await fs.readFile(path.join(folder,'COMPARISON.json'),'utf8'));
let lossReview=null;try{lossReview=JSON.parse(await fs.readFile(path.join(folder,'LOSS_REVIEW.json'),'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
let largeReview=null;try{largeReview=JSON.parse(await fs.readFile(path.join(folder,'LARGE_LOSS_REVIEW.json'),'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
let b1Review=null;try{b1Review=JSON.parse(await fs.readFile(path.join(folder,'B1_CONFIRMATION_REVIEW.json'),'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
const wb=Workbook.create();
const sheets=Object.fromEntries(['总览','模拟交易','退出与止损','保护变更','全部信号','15分钟审查','参数与来源'].map(n=>[n,wb.worksheets.add(n)]));
const summary=sheets['总览'],signals=sheets['全部信号'],trades=sheets['模拟交易'],exits=sheets['退出与止损'],bars=sheets['15分钟审查'],params=sheets['参数与来源'],protection=sheets['保护变更'];
const lossSheet=lossReview?wb.worksheets.add('亏损逐笔复核'):null;
const b1Sheet=b1Review?wb.worksheets.add('B1独立确认复核'):null;
const largeSheet=largeReview?wb.worksheets.add('大额亏损逐笔修复'):null;
const ny=v=>v?new Date(new Intl.DateTimeFormat('sv-SE',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(v)).replace(' ','T')+'Z'):null;
const utc=v=>v?new Date(v):null;
const iso=p=>p?new Date(p.time*1000).toISOString():null;
const number='$'+'#,##0.00;($#,##0.00);"—"',rr='0.000"R";(0.000"R");"—"';
const decisions={entry:'已模拟入场',risk_rejected:'风险未过',structure_rejected:'结构价格未过',held_position:'合格但已有持仓',exit_minute_no_reentry:'退出分钟不重入'};
const reasons={stop:'止损退出余仓',target_25:'第一目标25%',target_remaining:'历史第二目标余仓',wick_exit_all:'末分钟长上影退出余仓',stop_entry_minute_ambiguous:'入场分钟歧义止损',giveback_exit_remaining:'1R后回吐50%退出余仓',turning_exit_remaining:'末分钟冲高失败退出余仓',structure_exit_remaining:'已确认15分钟结构破位',failed_rebound_exit_remaining:'失败反弹LH确认后破低退出'};
const col=n=>{let s='';for(;n>0;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
function table(sheet,title,headers,rows,name){
  sheet.showGridLines=false;const end=rows.length+5,last=col(headers.length);
  const all=sheet.getRange(`A1:${last}${Math.max(end,8)}`);
  all.format.font={name:'Arial',size:11,color:'#172B4D'};all.format.rowHeight=23;all.format.columnWidth=19;all.format.verticalAlignment='center';
  sheet.getRange('A2').values=[[title]];sheet.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#172B4D'};
  sheet.getRange(`A5:${last}5`).values=[headers];header(sheet,`A5:${last}5`);
  if(rows.length){sheet.getRange(`A6:${last}${end}`).values=rows;sheet.tables.add(`A5:${last}${end}`,true,name);}
  sheet.freezePanes.freezeRows(5);sheet.freezePanes.freezeColumns(2);
  return end;
}
function header(sheet,range){const x=sheet.getRange(range);x.format.fill='#243B53';x.format.font={name:'Arial',size:11,bold:true,color:'#FFFFFF'};x.format.wrapText=true;x.format.horizontalAlignment='center';x.format.rowHeight=38;}
function width(sheet,range,n){sheet.getRange(range).format.columnWidth=n;}
function dates(sheet,range){sheet.getRange(range).setNumberFormat('mm/dd/yy hh:mm');width(sheet,range,22);}

// The constants are fixed replay assumptions, not a promise that editing Excel reruns the engine.
table(params,'参数与真实来源',['参数','固定值','含义'],[
 ['单边摩擦 bps',2,'BTC信号，ETF零佣金假设，仍计价差滑点'],
 ['硬门槛净RR（须大于）',0,'目标扣成本后须有正空间；2R只作提示'],
 ['初始止损缓冲 ATR',.25,'较大D下方，未改为内部浅HL'],
 ['HL容差 ATR',.10,'高于较大D'],['追价上限 ATR',.10,'相对突破线'],
 ['突破增量 USD',.01,'前一根完整15分钟最高价上方'],
 ['B急跌 / 事前ATR',2,r.b1_independent_hold?'B1等独立完整守D后突破；B2反弹回踩HL突破':'历史B1急跌后首次止跌突破；B2反弹回踩HL突破'],
 ['第一目标仓位比例',.25,'保留原25% / 75%'],
 ['上影 / 全振幅',.5,'非绿、不高于前根收盘、非内包；无整数关口限制'],['末分钟窗口 秒',60,'只用已知前14分钟及末分钟开盘'],
 ['整数关口门槛',null,'已停用；中点下穿仅预警，另保留批准的冲高失败退出'],
 ['15分钟转折左右确认',1,'嵌套计数范围，不以内部HL替代父D；机械分级可能较人工更细'],
 ['ATR周期',14,'完整15分钟TR简单平均；原缺口处理保留'],
 ['2R参考线（仅提示）',2,'不阻止盈利空间为正的候选'],
 ],'FixedParameters');
width(params,'A1:A45',32);width(params,'B1:B45',23);width(params,'C1:C45',110);
params.getRange('B8:B10').setNumberFormat('0.00');params.getRange('B13').setNumberFormat('0%');
params.getRange('A22:C32').values=[
 ['来源','Alpaca US BTC/USD','https://data.alpaca.markets/v1beta3/crypto/us/bars'],
 ['研究记录',run_id,r.strategy_version],
 ['区间起点 纽约',ny(r.start),'纽约时间含夏令时；各信号保留UTC，避免重复01:00歧义'],
 ['区间终点 纽约（不含）',ny(r.end),'30×24小时；先用7天真实行情预热'],
 ['实际 / 预期分钟',r.test_data_quality.observed_minutes,`${r.test_data_quality.expected_minutes}；缺失${r.test_data_quality.missing_minutes}，不补值`],
 ['分钟输入SHA256',null,r.source_minute_sha256],
 ['止损 / 退出实现',null,r.draft_parameters.failed_rebound_exit?'原V5保护＋独立H-L-LH后破低退出；硬止损不变':'V5：原硬保护＋15分钟结构＋1R后50%回吐＋末分钟冲高失败＋上影'],
 ['收益单位',null,'每初始1 BTC条件模型；不是ETF实际成交或账户收益'],
 ['资格和成交',null,'没有正净空间、缺少目标或被占仓的信号不计交易盈亏'],
 ['表格更新',null,'固定研究快照；修改表格不等同于重新识别结构或重放成交'],
 ['来源记录',null,'零量来源可能是报价中间价；分钟触发不能确定具体秒或实际成交价'],
 ];dates(params,'B24:B25');
params.getRange('A35:C39').values=[
 ['最大浮盈启用价格1R',1,'入场价减原初始止损；卖25%后不重设'],
 ['整笔最大浮盈回吐阈值',.5,'非绿、≤前收盘、非内包时退出实际余仓'],
 ['冲高失败前根振幅回撤',.5,'前根完整阳线；本根创新高后在末分钟跌破其中点'],
 ['固定第二目标',null,'已停用；历史T2仅供追溯，不执行'],
 ['历史结果比较',comparison.baseline.run_id,comparison.change_description_zh||'同一输入快照；入口和退出版本均变化，不是单变量比较'],
];
if(largeReview)params.getRange('A41:C43').values=[
 ['独立失败反弹退出',null,'完整15分钟H-L-LH，LH右邻完成后生效，严格跌破L退出实际余仓；无需新高/1R'],
 ['缺口处理',null,'清除未确认形态；保留此前完整确认参考，仅按后续真实观测触发并标记缺口'],
 ['500美元',500,'仅筛选基准亏损用于审查；不是仓位上限，也不是新增固定止损'],
];

const signalRows=r.signals.map(s=>{const f=s.references;return [s.id,s.route,ny(s.time_utc),s.entry_reference,s.initial_stop,s.t1,null,decisions[s.decision],s.trade_id,
 utc(s.time_utc),utc(s.interval_end),s.structural_price_signal?'通过':'未过',s.risk_passed?'通过':'未过',f.l1.price,ny(f.l1.time),ny(f.l1.known_at),f.l2?.price??null,ny(f.l2?.time),ny(f.l2?.known_at),s.atr,s.t2,
 s.signal_reasons.join('；')||s.risk_reason||s.decision,s.quote_reference?'报价参考':'有源成交量',s.context_partial?'不完整':'无已标记缺口',s.net_reward_risk,null,s.setup_evidence.lows?.length??null];});
const se=table(signals,'全部A/B信号，包括未过2R',['信号ID','入口','触发时间 纽约','参考入场 USD','初始保护 USD','第一目标 USD','公式净RR','处理','交易ID','触发 UTC','分钟结束 UTC','结构价格','目标净空间为正','较大D USD','D时间 纽约','D确认 纽约','HL USD','HL时间 纽约','HL确认 纽约','入场前ATR','第二目标 USD','原因','价格来源','入场上下文','引擎净RR','公式差异','A低点计数'],signalRows,'AllEntrySignals');
dates(signals,`C6:C${se}`);dates(signals,`J6:K${se}`);dates(signals,`O6:P${se}`);dates(signals,`R6:S${se}`);
for(const c of ['D','E','F','N','Q','T','U'])signals.getRange(`${c}6:${c}${se}`).setNumberFormat(number);
for(let row=6;row<=se;row++){
 signals.getRange(`G${row}`).formulas=[[`=IF(ISNUMBER(F${row}),(F${row}-D${row}-(D${row}+F${row})*'参数与来源'!$B$6/10000)/(D${row}-E${row}+(D${row}+E${row})*'参数与来源'!$B$6/10000),"目标缺失")`]];
 signals.getRange(`Z${row}`).formulas=[[`=IF(ISNUMBER(G${row}),G${row}-Y${row},"")`]];
}
signals.getRange(`G6:G${se}`).setNumberFormat(rr);signals.getRange(`Y6:Z${se}`).setNumberFormat('0.000000');width(signals,`H5:H${se}`,24);width(signals,`V5:V${se}`,68);
signals.getRange(`G6:G${se}`).conditionalFormats.add('cellIs',{operator:'lessThan',formula:2,format:{fill:'#FFF1D6',font:{color:'#8A4100'}}});

const legRows=[];
for(const p of r.trades)for(const l of p.legs)legRows.push([p.id,p.entry_rule,reasons[l.reason]||l.reason,ny(l.time_utc),l.fraction,l.price,p.entry,null,null,null,l.net,null,utc(l.time_utc)]);
const le=table(exits,'逐笔退出腿，时间为实际分钟区间起点',['交易ID','入口','退出原因','退出时间 纽约','初始仓位比例','参考退出 USD','入场 USD','毛盈亏 USD','摩擦 USD','净盈亏 USD','引擎净盈亏','公式差异','退出 UTC'],legRows,'ExitLegs');
dates(exits,`D6:D${le}`);dates(exits,`M6:M${le}`);width(exits,`C5:C${le}`,28);exits.getRange(`E6:E${le}`).setNumberFormat('0%');exits.getRange(`F6:L${le}`).setNumberFormat(number);
for(let row=6;row<=le;row++)exits.getRange(`H${row}:J${row}`).formulas=[[`=(F${row}-G${row})*E${row}`,`=(F${row}+G${row})*E${row}*'参数与来源'!$B$6/10000`,`=H${row}-I${row}`]];
for(let row=6;row<=le;row++)exits.getRange(`L${row}`).formulas=[[`=J${row}-K${row}`]];
const stopRows=[];
for(const p of r.trades){
 const add=(kind,t,price,low,lowTime,known)=>stopRows.push([p.id,p.entry_rule,kind,ny(t),price,low,ny(lowTime),ny(known),utc(t)]);
 add('初始硬止损',p.entry_time,p.initial_stop,p.references.l1.price,p.references.l1.time,p.references.l1.known_at);
 for(const h of p.stop_history||[])add('较大波段硬止损上移',h.effective_time,h.price,h.reference_low,h.reference_low_time,h.breakout_time);
 for(const h of p.structure_history||[])add('15分钟结构参考，严格破位退出',iso({time:h.effective_at}),h.price,h.price,iso({time:h.low_time}),iso({time:h.breakout_known_at}));
 for(const h of p.failed_rebound_history||[])add('独立失败反弹退出线，非硬止损上移',iso({time:h.effective_at}),h.price,h.low.price,iso({time:h.low.time}),iso({time:h.lower_high.known_at}));
}
stopRows.sort((a,b)=>a[0]-b[0]||a[8]-b[8]);
const pe=table(protection,'初始保护与独立退出参考，生效前不得回用',['交易ID','入口','保护类型','生效时间 纽约','保护价格 USD','低点参考 USD','低点时间 纽约','确认时间 纽约','生效 UTC'],stopRows,'ProtectionChanges');
dates(protection,`D6:D${pe}`);dates(protection,`G6:I${pe}`);protection.getRange(`E6:F${pe}`).setNumberFormat(number);width(protection,`C1:C${pe}`,38);

const te=table(trades,'逐笔入场、初始止损、25%止盈和余仓退出',['交易ID','入口','信号ID','入场时间 纽约','入场 USD','初始止损 USD','第一目标 USD','历史T2，已停用 USD','初始净风险 USD','状态','退出时间 纽约','已实现净盈亏 USD','净R','持有行情缺口','入场上下文','引擎净R','公式差异','保护上移次数','累计R','历史峰值R','回撤R','初始止损生效 纽约','25%状态','25%退出 纽约','25%退出 USD','25%净盈亏 USD','余仓比例','余仓退出 纽约','余仓退出 USD','余仓净盈亏 USD','余仓退出依据','入场 UTC','25%退出 UTC','余仓退出 UTC','初始价格风险 USD','余仓未实现毛盈亏 USD'],r.trades.map(p=>{
 const first=p.legs.find(l=>l.reason==='target_25'),rest=p.legs.filter(l=>l.reason!=='target_25'),last=rest.at(-1);
 return [p.id,p.entry_rule,p.signal_id,ny(p.entry_time),p.entry,p.initial_stop,p.t1,p.t2,null,p.status==='closed'?'已平仓':'未平仓',ny(p.exit_time),null,null,p.gap_exposed?'有缺口':'无已标记缺口',p.context_partial?'不完整':'无已标记缺口',p.net_r,null,(p.stop_history?.length||0)+(p.structure_history?.length||0),null,null,null,ny(p.entry_time),first?'已触及':'未触及',ny(first?.time_utc),first?.price??null,null,last?rest.reduce((n,l)=>n+l.fraction,0):p.remaining,ny(last?.time_utc),last?.price??null,null,last?(reasons[last.reason]||last.reason):'仍持有',utc(p.entry_time),utc(first?.time_utc),utc(last?.time_utc),p.entry-p.initial_stop,p.unrealized_gross??null];
}),'SimulatedTrades');
dates(trades,`D6:D${te}`);dates(trades,`K6:K${te}`);trades.getRange(`E6:I${te}`).setNumberFormat(number);trades.getRange(`L6:L${te}`).setNumberFormat(number);trades.getRange(`M6:M${te}`).setNumberFormat(rr);trades.getRange(`S6:U${te}`).setNumberFormat(rr);trades.getRange(`P6:Q${te}`).setNumberFormat('0.000000');
for(let row=6;row<=te;row++){
 trades.getRange(`I${row}`).formulas=[[`=E${row}-F${row}+(E${row}+F${row})*'参数与来源'!$B$6/10000`]];
 trades.getRange(`L${row}:M${row}`).formulas=[[`=SUMIFS('退出与止损'!$J$6:$J$${le},'退出与止损'!$A$6:$A$${le},A${row})`,`=IF(J${row}="已平仓",L${row}/I${row},"")`]];
 trades.getRange(`Q${row}`).formulas=[[`=IF(J${row}="已平仓",M${row}-P${row},"")`]];
 trades.getRange(`S${row}:U${row}`).formulas=[[`=SUM($M$6:M${row})`,`=MAX(0,$S$6:S${row})`,`=T${row}-S${row}`]];
 trades.getRange(`Z${row}`).formulas=[[`=IF(W${row}="已触及",SUMIFS('退出与止损'!$J$6:$J$${le},'退出与止损'!$A$6:$A$${le},A${row},'退出与止损'!$C$6:$C$${le},"第一目标25%"),"")`]];
 trades.getRange(`AD${row}`).formulas=[[`=IF(ISNUMBER(AC${row}),L${row}-SUM(Z${row}),"")`]];
}
for(const c of ['V','X','AB','AF','AG','AH'])dates(trades,`${c}6:${c}${te}`);
for(const c of ['Y','Z','AC','AD','AI','AJ'])trades.getRange(`${c}6:${c}${te}`).setNumberFormat(number);
trades.getRange(`AA6:AA${te}`).setNumberFormat('0%');width(trades,`W5:W${te}`,18);width(trades,`AE5:AE${te}`,38);

const be=table(bars,'30天实际观测逐根15分钟审查',['K线开始 纽约','开始 UTC','结束 UTC','开盘 USD','最高 USD','最低 USD','收盘 USD','真实分钟数','A较大D USD','A回踩HL USD','A低点计数','B急跌D USD','B2回踩HL USD','收盘后硬保护 USD','剩余比例','交易ID','本根事件','完整事件记录','15分钟结构参考 USD'],ledger.map(b=>[ny(b.time),utc(b.time),utc(b.end),b.open,b.high,b.low,b.close,b.observed_minutes,b.entry_setups?.A?.d?.price??null,b.entry_setups?.A?.hl?.price??null,b.entry_setups?.A?.lower_low_count??null,b.entry_setups?.B1?.d?.price??b.entry_setups?.B?.d?.price??null,b.entry_setups?.B2?.hl?.price??b.entry_setups?.B?.hl?.price??null,b.stop,b.remaining,b.position_id,b.events.map(e=>[e.type,e.entry_rule,e.signal_id?'信号'+e.signal_id:''].filter(Boolean).join(' ')).join('；'),JSON.stringify(b.events),b.case_structure_reference?.price??null]),'RealFifteenMinuteBars');
dates(bars,`A6:C${be}`);bars.getRange(`D6:G${be}`).setNumberFormat(number);bars.getRange(`I6:J${be}`).setNumberFormat(number);bars.getRange(`L6:N${be}`).setNumberFormat(number);bars.getRange(`O6:O${be}`).setNumberFormat('0%');width(bars,`Q5:Q${be}`,45);width(bars,`R5:R${be}`,85);

summary.showGridLines=false;summary.getRange('A1:H27').format.font={name:'Arial',size:11,color:'#172B4D'};summary.getRange('A1:H27').format.rowHeight=24;summary.getRange('A1:H27').format.columnWidth=19;
summary.getRange('A2').values=[['BTC A/B入口 30天复测']];summary.getRange('A2').format.font={name:'Arial',size:16,bold:true};
summary.getRange('A3').values=[[`${r.start} 至 ${r.end}（UTC，终点不含）`]];
summary.getRange('A5:B5').values=[['指标','结果']];header(summary,'A5:B5');width(summary,'A1:A27',30);
summary.getRange('A6:A16').values=[['全部去重信号'],['合格候选'],['已模拟入场'],['不足2R（有目标）'],['目标缺失'],['结构价格未过'],['已平仓'],['胜率'],['净R合计'],['最大回撤R'],['已实现净USD，每笔1 BTC']];
summary.getRange('B6:B16').formulas=[
 [`=COUNTA('全部信号'!A6:A${se})`],[`=COUNTIFS('全部信号'!L6:L${se},"通过",'全部信号'!M6:M${se},"通过")`],[`=COUNTA('模拟交易'!A6:A${te})`],
 [`=COUNTIFS('全部信号'!L6:L${se},"通过",'全部信号'!G6:G${se},"<2")`],
 [`=COUNTIFS('全部信号'!L6:L${se},"通过",'全部信号'!G6:G${se},"目标缺失")`],
 [`=COUNTIFS('全部信号'!L6:L${se},"未过")`],[`=COUNTIFS('模拟交易'!J6:J${te},"已平仓")`],
 [`=IF(B12>0,COUNTIFS('模拟交易'!M6:M${te},">0")/B12,"")`],
 [`=SUM('模拟交易'!M6:M${te})`],[`=MAX('模拟交易'!U6:U${te})`],[`=SUM('模拟交易'!L6:L${te})`]];
summary.getRange('B13').setNumberFormat('0.0%');summary.getRange('B14:B15').setNumberFormat(rr);summary.getRange('B16').setNumberFormat(number);width(summary,'B1:B27',20);
summary.getRange('D5:H5').values=[['独占入口分组','信号数','模拟交易','已平仓','净R']];header(summary,'D5:H5');
for(const [i,route] of [...new Set(r.signals.map(s=>s.route))].sort().entries()){const row=6+i;summary.getRange(`D${row}`).values=[[route]];summary.getRange(`E${row}:H${row}`).formulas=[[
 `=COUNTIFS('全部信号'!B6:B${se},D${row})`,`=COUNTIFS('模拟交易'!B6:B${te},D${row})`,`=COUNTIFS('模拟交易'!B6:B${te},D${row},'模拟交易'!J6:J${te},"已平仓")`,`=SUMIFS('模拟交易'!M6:M${te},'模拟交易'!B6:B${te},D${row})`]];}
summary.getRange('H6:H10').setNumberFormat(rr);
summary.getRange('D12').values=[['A：四轮独立LL及LH，随后HH、HL、突破。']];summary.getRange('D13').values=[[r.b1_independent_hold?'B1：D后独立完整15分钟守D，再突破。':'B1：连续急跌后首次止跌突破；不虚构HL。']];summary.getRange('D14').values=[['B2：急跌后反弹，形成HL后突破。']];
summary.getRange('A19').values=[['未交易信号不计盈亏。合格但被持仓占用的候选仍保留。']];
summary.getRange('A20').values=[[`测试区间${r.test_data_quality.observed_minutes}个真实分钟；缺失${r.test_data_quality.missing_minutes}分钟，未补值。`]];
summary.getRange('A21').values=[[b1Review?'仅增加B1独立守D确认；全部止损、退出和成本数值不变。':largeReview?'保留入场结构消费，新增已批准的独立失败反弹退出；数值参数未调。':r.consume_entry_history?'入场后消费旧结构，下一完整15分钟开始重建；退出及数值参数未调。':'采用已批准A/B1/B2入口及V5退出；数值参数未调。']];
summary.getRange('A22').values=[['净R为各笔净收益/各自初始净风险之和；与固定1 BTC净USD可能异号。']];
summary.getRange('A23').values=[['2R已降为提示；不足2R但净空间为正的候选可参与模拟。']];
summary.getRange('A24').values=[['这里只研究BTC全天信号，非ETF实际成交收益；没有提交订单。']];
summary.getRange('A26:D26').values=[['历史固定结果对照',comparison.baseline_label||'旧版',comparison.current_label||'本次','差值']];header(summary,'A26:D26');
const old=comparison.baseline;
summary.getRange('A27:D34').values=[
 ['全部信号',old.signals.all,null,null],['入场笔数',old.entries,null,null],['已平仓',old.metrics.closed,null,null],
 ['胜率',old.metrics.win_rate,null,null],['净R',old.metrics.net_r,null,null],['最大回撤R',old.metrics.max_drawdown_r,null,null],
 ['已平仓净USD',old.closed_net,null,null],['期末未平仓笔数',old.open_positions.length,null,null]];
for(const [i,formula] of ['B6','B8','B12','B13','B14','B15','B16',`COUNTA('模拟交易'!A6:A${te})-B12`].entries()){
 const row=27+i;summary.getRange(`C${row}:D${row}`).formulas=[[`=${formula}`,`=C${row}-B${row}`]];
}
summary.getRange('B26:C26').format.wrapText=true;summary.getRange('A26:D26').format.rowHeight=48;
summary.getRange('B30:D30').setNumberFormat('0.0%');summary.getRange('B31:D32').setNumberFormat(rr);summary.getRange('B33:D33').setNumberFormat(number);
summary.getRange('A36').values=[[comparison.change_description_zh||'同一行情SHA256；旧版为旧B入口与旧退出，本次含B1/B2和V5，不能只归因于退出变化。']];
summary.getRange('A37').values=[['旧研究 '+old.run_id+'；当前 '+run_id+'。两套结果均完整保留。']];
summary.getRange('A38').values=[['全部时间以纽约展示，UTC另列；时间是1分钟区间起点，初始保护假设成交后立即生效。']];
summary.getRange('A39').values=[['未触及25%目标先退出者按100%记录；不存在虚构的25%与75%两腿。']];
summary.getRange('A26:H39').format.rowHeight=24;summary.getRange('A26:H39').format.font={name:'Arial',size:11,color:'#172B4D'};header(summary,'A26:D26');

if(lossReview){
 const rows=lossReview.rows.map(x=>[x.old_trade_id,x.route,ny(x.entry_time),x.entry,x.initial_stop,ny(x.origin_time),ny(x.previous_entry),x.static_reused_history?'是':'否',x.cause,x.gross,x.cost,x.net,ny(x.exit_time),reasons[x.exit_reason]||x.exit_reason,x.exit_price,x.new_outcome,x.new_trade_id,x.new_net,x.maximum_observed_favourable_r,x.maximum_observed_adverse_r,x.previous_2h_move,x.initial_risk_atr,Object.values(x.exit_checks).every(Boolean)?'通过':'失败',x.action,x.gap_exposed?'有缺口':'无已标记缺口',utc(x.entry_time),utc(x.exit_time)]);
 const end=table(lossSheet,'原27笔亏损逐笔核验，与修复后顺序结果对照',['原交易#','入口','原入场 纽约','原入场 USD','原初始止损 USD','结构起点 纽约','前笔入场 纽约','静态旧结构复用','诊断','毛盈亏 USD','成本 USD','原净盈亏 USD','原退出 纽约','原退出依据','原退出 USD','修复后顺序结果','新交易#','新净盈亏 USD','已观察最大浮盈R','已观察最大不利R','此前2小时涨跌','原初始风险/ATR','分钟退出条件核验','处置','持有数据质量','原入场 UTC','原退出 UTC'],rows,'OriginalLossReview');
 for(const c of ['C','F','G','M','Z','AA'])dates(lossSheet,`${c}6:${c}${end}`);
 for(const c of ['D','E','J','K','L','O','R'])lossSheet.getRange(`${c}6:${c}${end}`).setNumberFormat(number);
 lossSheet.getRange(`S6:T${end}`).setNumberFormat(rr);lossSheet.getRange(`U6:U${end}`).setNumberFormat('0.00%');lossSheet.getRange(`V6:V${end}`).setNumberFormat('0.00');
 width(lossSheet,`I1:I${end}`,35);width(lossSheet,`N1:N${end}`,31);width(lossSheet,`P1:P${end}`,46);width(lossSheet,`X1:X${end}`,56);
 const first=end+6,last=first+lossReview.remaining_losses.length;
 lossSheet.getRange(`A${end+3}`).values=[['修复后仍亏损的交易：以下编号为新记录，与上表原编号不同。']];
 lossSheet.getRange(`A${first}:M${first}`).values=[['新交易#','入口','入场 纽约','入场 USD','初始止损 USD','退出 纽约','退出 USD','退出依据','毛盈亏 USD','成本 USD','净盈亏 USD','已观察最大浮盈R','结论']];header(lossSheet,`A${first}:M${first}`);
 const remaining=lossReview.remaining_losses.map(x=>[x.old_trade_id,x.route,ny(x.entry_time),x.entry,x.initial_stop,ny(x.exit_time),x.exit_price,reasons[x.exit_reason]||x.exit_reason,x.gross,x.cost,x.net,x.maximum_observed_favourable_r,x.cause]);
 lossSheet.getRange(`A${first+1}:M${last}`).values=remaining;dates(lossSheet,`C${first+1}:C${last}`);dates(lossSheet,`F${first+1}:F${last}`);
 for(const c of ['D','E','G','I','J','K'])lossSheet.getRange(`${c}${first+1}:${c}${last}`).setNumberFormat(number);
 lossSheet.getRange(`L${first+1}:L${last}`).setNumberFormat(rr);lossSheet.getRange(`A${first+1}:M${last}`).format.font={name:'Arial',size:11,color:'#172B4D'};
 lossSheet.getRange(`M${first+1}:M${last}`).format.wrapText=true;lossSheet.getRange(`A${first+1}:M${last}`).format.rowHeight=42;
 summary.getRange('A41').values=[[`原27笔亏损已逐笔核验：${lossReview.reused_static}笔有旧结构复用标记；修复后仍有${lossReview.remaining_losses.length}笔亏损。详见“亏损逐笔复核”。`]];
}
if(largeReview){
 const cases=largeReview.cases,rows=cases.map(c=>{const a=c.before,b=c.after,e=b.case_exit_evidence?.findLast(x=>x.reason==='failed_rebound_exit_remaining'),p=e?.failed_rebound;return [c.old_trade_id,c.entry_rule,ny(a.entry_time),a.entry,a.initial_stop,ny(a.exit_time),a.net,ny(b.exit_time),b.legs.at(-1).price,b.net,null,
 p?.high.price??null,ny(p?iso({time:p.high.time}):null),ny(p?iso({time:p.high.known_at}):null),p?.low.price??null,ny(p?iso({time:p.low.time}):null),ny(p?iso({time:p.low.known_at}):null),p?.lower_high.price??null,ny(p?iso({time:p.lower_high.time}):null),ny(p?iso({time:p.lower_high.known_at}):null),ny(p?iso({time:p.effective_at}):null),c.outcome,c.sequential_trade_id,c.sequential_net,a.gap_exposed?'有缺口，条件估算':'无已标记持有缺口',utc(a.entry_time),utc(b.exit_time)];});
 const end=table(largeSheet,'基准超过$500亏损：固定原入场，只比较退出',['基准交易#','入口','原入场 纽约','原入场 USD','原初始止损 USD','原退出 纽约','原净盈亏 USD','新退出 纽约','新退出 USD','新净盈亏 USD','净盈亏差额 USD','H USD','H发生 纽约','H确认 纽约','L USD','L发生 纽约','L确认 纽约','LH USD','LH发生 纽约','LH确认 纽约','生效 纽约','逐笔结论','新顺序交易#','新顺序净盈亏 USD','数据质量','入场 UTC','新退出 UTC'],rows,'LargeLossFixes');
 for(const c of ['C','F','H','M','N','P','Q','S','T','U','Z','AA'])dates(largeSheet,`${c}6:${c}${end}`);
 for(const c of ['D','E','G','I','J','K','L','O','R','X'])largeSheet.getRange(`${c}6:${c}${end}`).setNumberFormat(number);
 for(let i=6;i<=end;i++)largeSheet.getRange(`K${i}`).formulas=[[`=J${i}-G${i}`]];
 width(largeSheet,`V1:V${end}`,64);width(largeSheet,`Y1:Y${end}`,32);
 largeSheet.getRange('A12').values=[['H、L、LH均完整确认后才生效。#5八分钟止损，无完整新结构；$500不是新损失上限。']];
 largeSheet.getRange('A13').values=[['固定入场的改善与完整顺序复测分开；新退出后的行情只作对照，不计该笔持仓收益。']];
 const start=16,barRows=[];
 const eventNames={...reasons,entry:'入场',failed_rebound_reference:'LH确认，参考生效',failed_rebound_reclaimed:'LH重夺，组合失效',failed_rebound_context_reset:'清理未确认形态',failed_rebound_outside_bar:'外包高低先后未知'};
 for(const c of cases)for(const b of c.rows)barRows.push([c.old_trade_id,ny(b.time),ny(b.observed_end_exclusive||b.end),b.open,b.high,b.low,b.close,b.observed_minutes,b.remaining,
 b.events.filter(e=>/failed_rebound|^entry$|^stop$|^target_25$/.test(e.type)).map(e=>[ny(e.time_utc)?.toISOString().slice(5,16).replace('T',' '),eventNames[e.type]||e.type,e.price==null?'':Number(e.price).toFixed(2)].join(' ')).join('；'),
 b.failed_rebound_state?.reference?.price??null,
 tsJs(c.before.exit_time)>=tsJs(b.time)&&tsJs(c.before.exit_time)<tsJs(b.end)?ny(c.before.exit_time):null]);
 function tsJs(t){return new Date(t).getTime();}
 const last=start+barRows.length;
 largeSheet.getRange(`A${start}:L${start}`).values=[['基准交易#','15分钟开始 纽约','实际观测结束 纽约','开盘 USD','最高 USD','最低 USD','收盘 USD','实际分钟数/15','新方案行末余仓','当时事件','已知退出参考 USD','原退出发生时间']];header(largeSheet,`A${start}:L${start}`);
 largeSheet.getRange(`A${start+1}:L${last}`).values=barRows;
 largeSheet.getRange(`A${start+1}:L${last}`).format.font={name:'Arial',size:11,color:'#172B4D'};largeSheet.getRange(`A${start+1}:L${last}`).format.rowHeight=24;
 dates(largeSheet,`B${start+1}:C${last}`);dates(largeSheet,`L${start+1}:L${last}`);largeSheet.getRange(`D${start+1}:G${last}`).setNumberFormat(number);largeSheet.getRange(`K${start+1}:K${last}`).setNumberFormat(number);largeSheet.getRange(`I${start+1}:I${last}`).setNumberFormat('0%');
 width(largeSheet,`J${start}:J${last}`,38);largeSheet.getRange(`J${start+1}:J${last}`).format.wrapText=true;
 for(let i=0;i<barRows.length;i++)if(barRows[i][9].length>55)largeSheet.getRange(`A${start+i+1}:L${start+i+1}`).format.rowHeight=48;
 summary.getRange('A41').values=[['详见“大额亏损逐笔修复”：四笔减亏，#5不变；#5与#32仍超$500，不强行缩仓抹去损失。']];
}

if(b1Review){
 const rows=b1Review.rows.map(x=>[x.old_trade_id,x.old_route,ny(x.old_entry_time),x.old_entry,x.old_net,x.disposition,x.new_trade_id,x.new_route,x.new_entry,x.new_net,utc(x.old_entry_time)]);
 const end=table(b1Sheet,'Release 0.1全部38笔：新B1月度序列去向',['0.1交易#','原路线','原入场 纽约','原入场 USD','原净盈亏 USD','新序列处理','新交易#','新路线','同时间新入场 USD','新净盈亏 USD','原入场 UTC'],rows,'B1HistoricalComparison');
 dates(b1Sheet,`C6:C${end}`);dates(b1Sheet,`K6:K${end}`);
 for(const c of ['D','E','I','J'])b1Sheet.getRange(`${c}6:${c}${end}`).setNumberFormat(number);
 width(b1Sheet,`F1:F${end}`,68);b1Sheet.getRange(`F6:F${end}`).format.wrapText=true;b1Sheet.getRange(`A6:K${end}`).format.rowHeight=54;
 const start=end+5,last=start+b1Review.accepted_b1.length;
 b1Sheet.getRange(`A${start-2}`).values=[['新B1全部实际入场：D确认以后独立完整守D；未交易不填盈亏。']];
 b1Sheet.getRange(`A${start}:N${start}`).values=[['新交易#','D发生 纽约','D确认 纽约','D USD','独立K线开始 纽约','完整确认 纽约','确认低点 USD','实际分钟数','实际入场 纽约','入场 USD','初始止损 USD','净盈亏 USD','入场 UTC','确认 UTC']];header(b1Sheet,`A${start}:N${start}`);
 b1Sheet.getRange(`A${start+1}:N${last}`).values=b1Review.accepted_b1.map(x=>[x.trade_id,ny(x.d_time),ny(x.d_known_at),x.d_price,ny(x.confirmation.time),ny(x.confirmation.known_at),x.confirmation.low,x.confirmation.observed_minutes,ny(x.entry_time),x.entry,x.initial_stop,x.net,utc(x.entry_time),utc(x.confirmation.known_at)]);
 b1Sheet.getRange(`A${start+1}:N${last}`).format.font={name:'Arial',size:11,color:'#172B4D'};b1Sheet.getRange(`A${start+1}:N${last}`).format.rowHeight=24;
 for(const c of ['B','C','E','F','I','M','N'])dates(b1Sheet,`${c}${start+1}:${c}${last}`);
 for(const c of ['D','G','J','K','L'])b1Sheet.getRange(`${c}${start+1}:${c}${last}`).setNumberFormat(number);
 summary.getRange('A41').values=[[`Release 0.1冻结38笔净+$3,516.46；新B1 ${b1Review.accepted_b1.length}笔均过独立确认，${b1Review.waiting_cross_count}个未通过越价信号保留审查。`]];
 params.getRange('A41:C44').values=[['基准版本','Release 0.1','源代码、真实分钟、38笔及原表格均封存，独立重放一致'],['B1独立守D',1,'D之后至少一根完整15分钟，15个真实分钟，最低不低于同一D'],['B1生效',null,'确认完成后才允许突破最新完整K线高点+$0.01；新D重启等待'],['#5原候选',null,'09:45不入场；09:53原D破位；未交易盈亏留空。后续新D单独评估']];
}

if(b1Review){params.getRange('C22:C44').format.wrapText=true;params.getRange('A22:C44').format.rowHeight=36;params.getRange('A39:C39').format.rowHeight=66;}
await wb.recalculate();
const checks={summary:summary.getRange('B6:B16').values,signalDeltas:signals.getRange(`Z6:Z${se}`).values,tradeDeltas:trades.getRange(`Q6:Q${te}`).values,exitDeltas:exits.getRange(`L6:L${le}`).values};
for(const [i,p] of r.trades.entries()){
 const first=p.legs.find(l=>l.reason==='target_25'),rest=p.legs.filter(l=>l.reason!=='target_25');
 const firstCell=trades.getRange(`Z${i+6}`).values[0][0],restCell=trades.getRange(`AD${i+6}`).values[0][0];
 if(first?Math.abs(firstCell-first.net)>1e-8:(firstCell!==''&&firstCell!==null))throw Error('First-25% leg mismatch '+p.id);
 if(rest.length&&Math.abs(restCell-rest.reduce((n,l)=>n+l.net,0))>1e-8)throw Error('Remainder leg mismatch '+p.id);
}
const [all,qualified,traded,below,missing,structuralFail,closed,win,net,drawdown]=checks.summary.flat();
for(const [a,b,name] of [[all,r.signal_counts.all,'signals'],[qualified,r.signal_counts.risk_passed,'qualified'],[traded,r.trades.length,'trades'],[below,r.signal_counts.below_2r,'below2R'],[missing,r.signal_counts.target_missing,'missing targets'],[closed,r.metrics.closed,'closed'],[win,r.metrics.win_rate,'win rate'],[net,r.metrics.net_r,'net R'],[drawdown,r.metrics.max_drawdown_r,'drawdown']])if(Math.abs(a-b)>1e-8)throw Error(`${name} mismatch ${a} vs ${b}`);
for(const name of ['signalDeltas','tradeDeltas','exitDeltas'])for(const [v] of checks[name])if(typeof v==='number'&&Math.abs(v)>1e-8)throw Error(name+' reconciliation failed');
// Verify cost formulas recalculate, then restore fixed assumptions before export.
const baseNet=summary.getRange('B16').values[0][0];params.getRange('B6').values=[[3]];await wb.recalculate();
if(summary.getRange('B16').values[0][0]>=baseNet)throw Error('Cost sensitivity did not recalculate');
params.getRange('B6').values=[[2]];await wb.recalculate();
if(Math.abs(summary.getRange('B16').values[0][0]-baseNet)>1e-8)throw Error('Cost restore failed');
await fs.writeFile(path.join(output,'VERIFICATION.json'),JSON.stringify({run_id,...checks},null,2));
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NULL!|#NUM!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'Final formula scan'});
await fs.writeFile(path.join(output,'FORMULA_SCAN.json'),errors.ndjson);
for(const [name,range] of [['总览','A1:H39'],['全部信号','A1:H10'],['模拟交易','A1:M10'],['保护变更','A1:I10'],['退出与止损','A1:J10'],['15分钟审查','A1:H10'],['参数与来源','A1:C18']]){
 if(previewB1Only&&name!=='参数与来源')continue;
 const preview=await wb.render({sheetName:name,range,scale:1});await fs.writeFile(path.join(output,name+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
for(const [sheetName,range,label] of [['模拟交易','V5:AJ10','分批明细'],['参数与来源','A22:C39','来源和退出参数']]){
 if(previewB1Only&&sheetName!=='参数与来源')continue;
 const preview=await wb.render({sheetName,range,scale:1});await fs.writeFile(path.join(output,label+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
if(b1Sheet){for(const [range,label] of [['A1:F11','B1旧入场去向'],['A48:N54','B1独立确认新入场']]){if(previewB1Only&&label!=='B1旧入场去向')continue;const preview=await wb.render({sheetName:'B1独立确认复核',range,scale:1});await fs.writeFile(path.join(output,label+'.png'),new Uint8Array(await preview.arrayBuffer()));}}
if(lossSheet){for(const [range,label] of [['A1:L10','亏损逐笔复核'],['A35:M43','修复后亏损']]){const preview=await wb.render({sheetName:'亏损逐笔复核',range,scale:1});await fs.writeFile(path.join(output,label+'.png'),new Uint8Array(await preview.arrayBuffer()));}}
if(largeSheet){for(const [range,label] of [['A1:K13','大额亏损逐笔修复'],['L5:U10','大额亏损结构时点'],['A16:L22','大额亏损逐根对照']]){const preview=await wb.render({sheetName:'大额亏损逐笔修复',range,scale:1});await fs.writeFile(path.join(output,label+'.png'),new Uint8Array(await preview.arrayBuffer()));}}
const xlsx=await SpreadsheetFile.exportXlsx(wb);const target=path.join(output,'BTC_AB_30D.xlsx');await xlsx.save(target);
await fs.copyFile(target,path.join(folder,'RESEARCH.xlsx'));
console.log(JSON.stringify({run_id,file:target,signals:r.signals.length,trades:r.trades.length,net_r:r.metrics.net_r}));
