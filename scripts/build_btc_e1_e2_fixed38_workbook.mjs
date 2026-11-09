import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const root=process.cwd(),store=path.join(root,'trading_records/btc_structure');
const r=JSON.parse(await fs.readFile(path.join(store,'investigations/RELEASE_0_1_E1_E2_FIXED38.json'),'utf8'));
const out=path.join(root,'outputs/btc_e1_e2_release01_fixed38_20261109');
await fs.mkdir(out,{recursive:true});
try{await fs.symlink('/Users/danielshan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',path.join(out,'node_modules'),'dir');}catch(e){if(e.code!=='EEXIST')throw e;}
const require=createRequire(path.join(out,'package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const wb=Workbook.create(),main=wb.worksheets.add('38笔对照'),legs=wb.worksheets.add('退出腿与来源');
const usd='$#,##0.00;($#,##0.00);"—"';
const ny=v=>v?new Date(new Intl.DateTimeFormat('sv-SE',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(v)).replace(' ','T')+'Z'):null;
const zone=v=>new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',timeZoneName:'short'}).formatToParts(new Date(v)).find(p=>p.type==='timeZoneName').value;
const col=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
function base(s,range){s.showGridLines=false;const x=s.getRange(range);x.format.font={name:'Arial',size:11,color:'#172B4D'};x.format.columnWidth=18;x.format.rowHeight=24;x.format.verticalAlignment='center';}
function head(s,range){const x=s.getRange(range);x.format.fill='#243B53';x.format.font={name:'Arial',size:11,color:'#FFFFFF',bold:true};x.format.wrapText=true;x.format.rowHeight=44;x.format.horizontalAlignment='center';}
function date(s,range){s.getRange(range).setNumberFormat('mm/dd/yy hh:mm');s.getRange(range).format.columnWidth=23;}
const reasonNames={target_25:'首次25%止盈',stop:'原硬止损',failed_rebound_exit_remaining:'原失败反弹退出',structure_exit_remaining:'原结构退出',turning_exit_remaining:'原冲高失败退出',giveback_exit_remaining:'原浮盈保护退出',wick_exit_all:'原长上影退出',unpromoted_E1_CONTINUOUS_WEAKNESS:'E1候选余仓退出',unpromoted_E2_RECLAIM_FAILURE_FOLLOWTHROUGH:'E2候选余仓退出'};
const rawLegs=[];
for(const x of r.rows)for(const plan of ['0.1','E1','E2']){
  const list=plan==='0.1'?x.baseline_legs:x.alternatives[plan].legs;
  for(const [i,l] of (list||[]).entries())rawLegs.push({trade:x.trade_id,plan,ordinal:i+1,entry:x.entry,...l});
}
const le=rawLegs.length+5;
base(legs,'A1:Q'+Math.max(le,24));legs.tabColor='#C8B9A6';
legs.getRange('A2').values=[['原退出及独立候选的逐腿计算']];
legs.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#172B4D'};
legs.getRange('A5:L5').values=[['原交易#','方案','腿序号','退出时间 纽约','初始仓位比例','退出参考价 USD','原入场价 USD','毛盈亏 USD','摩擦成本 USD','净盈亏 USD','退出依据','退出 UTC']];
head(legs,'A5:L5');
legs.getRange('A6:L'+le).values=rawLegs.map(l=>[l.trade,l.plan,l.ordinal,ny(l.time_utc),l.fraction,l.price,l.entry,null,null,null,reasonNames[l.reason]||l.reason,new Date(l.time_utc)]);
legs.tables.add('A5:L'+le,true,'ExitLegCalculations');
date(legs,'D6:D'+le);date(legs,'L6:L'+le);legs.getRange('E6:E'+le).setNumberFormat('0%');legs.getRange('F6:J'+le).setNumberFormat(usd);legs.getRange('K5:K'+le).format.columnWidth=28;
for(let row=6;row<=le;row++)legs.getRange('H'+row+':J'+row).formulas=[['=(F'+row+'-G'+row+')*E'+row,'=(F'+row+'+G'+row+')*E'+row+'*$N$6/10000','=H'+row+'-I'+row]];
legs.getRange('N5:P5').values=[['单边摩擦 bps','固定值说明','来源与适用范围']];head(legs,'N5:P5');
legs.getRange('N6:P6').values=[[2,'每笔初始1 BTC','ETF零佣金加价差滑点，非实盘成交']];
legs.getRange('N6').format.font={name:'Arial',size:11,color:'#0000FF'};
legs.getRange('N8:P15').values=[
 ['研究范围','固定原38笔入场','独立退出对照，未重跑整月策略'],
 ['原记录',r.source_run,'冻结Release 0.1'],
 ['分钟来源','Alpaca BTC/USD','0.1冻结MINUTES.jsonl.gz'],
 ['分钟输入SHA256',r.source_minute_sha256,'与原0.1逐字节核验一致'],
 ['E1','连续两次降高降低','完整收盘失守原突破，红线、≤前收、非内包'],
 ['E2','收复失败后跟随确认','先有E1背景，完整收复、失守、下一根继续降高降低'],
 ['时间','纽约展示，UTC另列','完整K线结束才确认，随后实际分钟首价估算退出'],
 ['缺口','不补值、不可回填','缺少执行首价时估值留空']
 ];
legs.getRange('N5:N15').format.columnWidth=22;legs.getRange('O5:O15').format.columnWidth=38;legs.getRange('P5:P15').format.columnWidth=58;legs.getRange('N8:P15').format.wrapText=true;legs.getRange('N8:P15').format.rowHeight=44;
legs.freezePanes.freezeRows(5);legs.freezePanes.freezeColumns(2);

const headers=['原交易#','入场路线','原入场 纽约','原入场 USD','原最终退出 纽约','原最终退出价 USD','原整笔净盈亏 USD','E1状态','E1确认 纽约','E1退出 纽约','E1退出价 USD','E1整笔净盈亏 USD','E1净差 USD','E2状态','E2确认 纽约','E2退出 纽约','E2退出价 USD','E2整笔净盈亏 USD','E2净差 USD','原盈利被E1减利','原盈利被E2减利','原持有数据质量','切片缺失分钟','E1提前分钟','E2提前分钟','原入场 UTC','原退出 UTC','E1确认 UTC','E1退出 UTC','E2确认 UTC','E2退出 UTC','原初始止损 USD','初始止损生效 纽约','原D USD','入场时区','入场前上下文'];
const end=15+r.rows.length,last=col(headers.length);
base(main,'A1:'+last+end);main.tabColor='#243B53';
main.getRange('A2').values=[['E1 / E2：全部38笔固定原入场退出对照']];
main.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#172B4D'};
main.getRange('B5:E5').values=[['指标','0.1原退出','E1','E2']];head(main,'B5:E5');
main.getRange('B6:B12').values=[['固定入场净额 USD'],['相对0.1净差 USD'],['提前退出笔数'],['原盈利被减利笔数'],['盈利笔数'],['亏损笔数'],['无持有缺口净差']];
main.getRange('B5:B12').format.columnWidth=23;main.getRange('C5:E12').format.columnWidth=23;
main.getRange('G5').values=[['固定原入场，仅比较退出；合计不代表新的整月策略收益。']];
main.getRange('G7').values=[['E1 / E2保持原定义；每笔初始1 BTC。原0.1及原工作簿不变。']];
main.getRange('G9').values=[['#12原持有后段缺7分钟，发生在两种候选退出之后；差额为条件估算。']];
main.getRange('G11').values=[['全部19笔原盈利交易均保留；无持有缺口子集36笔，列出单独净差。']];
main.getRange('A15:'+last+'15').values=[headers];head(main,'A15:'+last+'15');
main.getRange('A16:'+last+end).values=r.rows.map(x=>{
 const a=x.alternatives.E1,b=x.alternatives.E2;
 return [x.trade_id,x.entry_rule,ny(x.entry_time),x.entry,ny(x.baseline_exit),x.baseline_exit_price,null,a.triggered?'提前':'保留原退出',a.triggered?ny(a.signal.confirmed_at):null,ny(a.exit_time),a.exit_price,null,null,b.triggered?'提前':'保留原退出',b.triggered?ny(b.signal.confirmed_at):null,ny(b.exit_time),b.exit_price,null,null,null,null,x.gap_exposed?'原持有含缺口':'无已标记持有缺口',x.slice_missing_minutes,a.minutes_earlier,b.minutes_earlier,new Date(x.entry_time),new Date(x.baseline_exit),a.triggered?new Date(a.signal.confirmed_at):null,a.exit_time?new Date(a.exit_time):null,b.triggered?new Date(b.signal.confirmed_at):null,b.exit_time?new Date(b.exit_time):null,x.initial_stop,ny(x.entry_time),x.original_d.price,zone(x.entry_time),x.context_partial?'不完整':'无已标记缺口'];
});
main.tables.add('A15:'+last+end,true,'All38ExitComparisons');
for(let row=16;row<=end;row++){
 for(const [dest,plan] of [['G','0.1'],['L','E1'],['R','E2']]){
  const matches="'退出腿与来源'!$A$6:$A$"+le+',A'+row+','+"'退出腿与来源'!$B$6:$B$"+le+',"'+plan+'"';
  main.getRange(dest+row).formulas=[['=IF(COUNTIFS('+matches+')>0,SUMIFS('+"'退出腿与来源'!$J$6:$J$"+le+','+matches+'),"缺少估价")']];
 }
 main.getRange('M'+row).formulas=[['=IF(AND(ISNUMBER(G'+row+'),ISNUMBER(L'+row+')),L'+row+'-G'+row+',"")']];
 main.getRange('S'+row).formulas=[['=IF(AND(ISNUMBER(G'+row+'),ISNUMBER(R'+row+')),R'+row+'-G'+row+',"")']];
 main.getRange('T'+row+':U'+row).formulas=[['=IF(AND(G'+row+'>0,ISNUMBER(M'+row+'),M'+row+'<0),"是","否")','=IF(AND(G'+row+'>0,ISNUMBER(S'+row+'),S'+row+'<0),"是","否")']];
}
for(const c of ['C','E','I','J','O','P','Z','AA','AB','AC','AD','AE','AG'])date(main,c+'16:'+c+end);
for(const c of ['D','F','G','K','L','M','Q','R','S','AF','AH'])main.getRange(c+'16:'+c+end).setNumberFormat(usd);
main.getRange('A15:A'+end).format.columnWidth=10;main.getRange('B15:B'+end).format.columnWidth=14;
for(const c of ['V','AJ'])main.getRange(c+'15:'+c+end).format.columnWidth=24;
for(const c of ['G','L','R'])main.getRange(c+'16:'+c+end).conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{font:{color:'#B42318'}}});
main.getRange('C6:E7').setNumberFormat(usd);main.getRange('C12:E12').setNumberFormat(usd);
for(const [column,netColumn,statusColumn,hurtColumn,deltaColumn] of [['C','G',null,null,null],['D','L','H','T','M'],['E','R','N','U','S']]){
 main.getRange(column+'6').formulas=[['=IF(COUNT('+netColumn+'16:'+netColumn+end+')=38,SUM('+netColumn+'16:'+netColumn+end+'),"部分估值缺失")']];
 main.getRange(column+'7').formulas=[[column==='C'?'=0':'='+column+'6-$C$6']];
 main.getRange(column+'8').formulas=[[statusColumn?'=COUNTIF('+statusColumn+'16:'+statusColumn+end+',"提前")':'=0']];
 main.getRange(column+'9').formulas=[[hurtColumn?'=COUNTIF('+hurtColumn+'16:'+hurtColumn+end+',"是")':'=0']];
 main.getRange(column+'10').formulas=[['=COUNTIF('+netColumn+'16:'+netColumn+end+',">0")']];
 main.getRange(column+'11').formulas=[['=COUNTIF('+netColumn+'16:'+netColumn+end+',"<0")']];
 main.getRange(column+'12').formulas=[[deltaColumn?'=SUMIFS('+deltaColumn+'16:'+deltaColumn+end+',$V$16:$V$'+end+',"无已标记持有缺口")':'=0']];
}
main.freezePanes.freezeRows(15);main.freezePanes.freezeColumns(2);
await wb.recalculate();
for(let i=0;i<rawLegs.length;i++){
 const got=legs.getRange('J'+(i+6)).values[0][0];
 if(Math.abs(got-rawLegs[i].net)>1e-8)throw Error('Leg mismatch '+i);
}
for(let i=0;i<r.rows.length;i++){
 const x=r.rows[i],row=i+16;
 for(const [column,want] of [['G',x.baseline_net],['L',x.alternatives.E1.net],['M',x.alternatives.E1.net_change],['R',x.alternatives.E2.net],['S',x.alternatives.E2.net_change]]){
  const got=main.getRange(column+row).values[0][0];if(Math.abs(got-want)>1e-8)throw Error('Trade mismatch '+x.trade_id+' '+column);
 }
}
const checks=main.getRange('C6:E12').values;
if(Math.abs(checks[0][0]-r.baseline.net)>1e-8||Math.abs(checks[0][1]-r.summary.E1.fixed_entry_net)>1e-8||Math.abs(checks[0][2]-r.summary.E2.fixed_entry_net)>1e-8)throw Error('Summary mismatch');
// Check formula sensitivity without altering the delivered fixed assumptions.
const original=checks[0][0];legs.getRange('N6').values=[[3]];await wb.recalculate();
if(main.getRange('C6').values[0][0]>=original)throw Error('Cost sensitivity failed');
legs.getRange('N6').values=[[2]];await wb.recalculate();
if(Math.abs(main.getRange('C6').values[0][0]-original)>1e-8)throw Error('Cost restore failed');
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'Final formula scan'});
await fs.writeFile(path.join(out,'FORMULA_SCAN.json'),scan.ndjson);
await fs.writeFile(path.join(out,'VERIFICATION.json'),JSON.stringify({summary:checks,trades:38,legs:rawLegs.length,all_rows_reconciled:true},null,2));
for(const [sheetName,range,label] of [['38笔对照','A1:O12','总览'],['38笔对照','A15:G20','原退出'],['38笔对照','H15:S20','E1_E2退出'],['38笔对照','T15:AJ20','质量与时间'],['退出腿与来源','A1:L11','退出腿'],['退出腿与来源','N5:P15','来源']]){
 const preview=await wb.render({sheetName,range,scale:1});await fs.writeFile(path.join(out,label+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb),target=path.join(out,'E1_E2_FIXED38.xlsx');await xlsx.save(target);
await fs.copyFile(target,path.join(store,'investigations/E1_E2_FIXED38.xlsx'));
console.log(JSON.stringify({file:target,trade_count:38,legs:rawLegs.length,summary:checks}));
