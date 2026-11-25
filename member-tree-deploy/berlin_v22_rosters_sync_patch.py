"""Sync V22's two review lists to independent Berlin test, without any ledger writes.

Executed AFTER berlin_flatline_list_patch.py, replacing only that browser-only helper.
No changes to account import, daily ledger, historical snapshots or backend.
"""
from pathlib import Path
jp=Path("member-tree/static/app.js")
hp=Path("member-tree/static/index.html")
j=jp.read_text(encoding="utf-8")
h=hp.read_text(encoding="utf-8")
start=j.find("// Berlin 躺平名单：")
end=j.find("function berlinHistoryDateShift(value,days){",start)
assert start!=-1 and end>start, "Original Berlin history/flatline injection is absent"
assert j.count("function berlinFlatlineRows(){")==1
script=r'''
// Berlin synchronized V22 review rosters: read-only, no HTTP mutations.
let berlinFlatlineUI=null,berlinLoanUI=null;
let berlinFlatSort='days',berlinFlatDesc=true,berlinFlatPage=0;
let berlinLoanSort='ratio',berlinLoanDesc=true,berlinLoanPage=0;
const BERLIN_REVIEW_PAGE=100;
const BERLIN_SAN_ROOTS=new Set(['SAN1','SAN2','SAN5','SAN6','SAN8']);
function berlinReviewAccount(s){
 return String(s||'').trim().toUpperCase().replace(/^SAN0+([1-9]\d*)$/,'SAN$1');
}
function berlinReviewValidDate(s){
 const day=String(s||'').slice(0,10);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(day))return false;
 const d=new Date(day+'T00:00:00Z');
 return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===day;
}
function berlinReviewCutoff(day){
 if(!berlinReviewValidDate(day))return '';
 const date=new Date(day+'T00:00:00Z');
 const y=date.getUTCFullYear(),m=date.getUTCMonth(),d=date.getUTCDate();
 const end=new Date(Date.UTC(y,m-2,0)).getUTCDate();
 return new Date(Date.UTC(y,m-3,Math.min(d,end))).toISOString().slice(0,10);
}
function berlinReviewCurrency(cents){
 return new Intl.NumberFormat('zh-CN',{minimumFractionDigits:0,maximumFractionDigits:2})
   .format((Number(cents)||0)/100);
}
function berlinReviewSign(cents){
 return ((Number(cents)||0)>0?'+':'')+berlinReviewCurrency(cents);
}
function berlinReviewLetter(n){
 let s='';for(let k=n;k>0;k=Math.floor((k-1)/26))
  s=String.fromCharCode(65+(k-1)%26)+s;
 return s||'—';
}
function berlinReviewIndex(input){
 const people=(Array.isArray(input)?input:[]).filter(x=>x&&!x.deleted);
 const byId=new Map(people.map(m=>[String(m.id),m]));
 const children=new Map();
 for(const m of people){
  const p=String(m.parent_id??''),id=String(m.id);
  if(!p||p===id||!byId.has(p))continue;
  if(!children.has(p))children.set(p,[]);
  children.get(p).push(m);
 }
 const order=[],visited=new Set();
 for(const m of people){
  const stack=[[String(m.id),false]];
  while(stack.length){
   const [id,done]=stack.pop();
   if(done){order.push(id);continue}
   if(visited.has(id))continue;
   visited.add(id);stack.push([id,true]);
   for(const sub of children.get(id)||[]){
    const sid=String(sub.id);
    if(!visited.has(sid))stack.push([sid,false]);
   }
  }
 }
 const team=new Map();
 for(const id of order){
  const m=byId.get(id);
  if(!m)continue;
  const placeholder=String(m.remark||'')==='上级占位（待补资料）';
  const own=placeholder?0:1;
  let count=own,stake=placeholder?0:Number(m.stake_cents||0);
  let withdrawn=placeholder?0:Number(m.total_withdraw_cents||0);
  let latest='';
  for(const c of children.get(id)||[]){
   const info=team.get(String(c.id));
   if(!info)continue;
   count+=info.count;stake+=info.stake;withdrawn+=info.withdrawn;
   const joined=String(c.joined_on||'').slice(0,10);
   if(String(c.remark||'')!=='上级占位（待补资料）'&&berlinReviewValidDate(joined)&&joined>latest)latest=joined;
   if(info.latest>latest)latest=info.latest;
  }
  team.set(id,{count,stake,withdrawn,latest});
 }
 function group(m){
  const named=String(m.group_account||m.group_name||m.group_label||m.group||m.team_group||'').trim();
  if(named)return named;
  let cur=m,seen=new Set([String(m.id)]);
  while(cur.parent_id!=null){
   const p=byId.get(String(cur.parent_id));
   if(!p||seen.has(String(p.id)))break;
   seen.add(String(p.id));cur=p;
  }
  return String(cur.account||'未分组');
 }
 function level(m){
  let cur=m,edges=0,seen=new Set([String(m.id)]);
  while(cur.parent_id!=null){
   const p=byId.get(String(cur.parent_id));
   if(!p||seen.has(String(p.id)))break;
   seen.add(String(p.id));edges++;
   if(BERLIN_SAN_ROOTS.has(berlinReviewAccount(p.account)))
    return berlinReviewLetter(edges);
   cur=p;
  }
  return edges>0?berlinReviewLetter(edges):'—';
 }
 return {people,byId,children,team,group,level};
}
function berlinFlatlineRows(day=dateNow(),input=members){
 const tree=berlinReviewIndex(input),cutoff=berlinReviewCutoff(day);
 if(!cutoff)return [];
 const todayMs=Date.parse(day+'T00:00:00Z');
 return tree.people.filter(m=>{
   const joined=String(m.joined_on||'').slice(0,10);
   if(!berlinReviewValidDate(joined)||joined>cutoff)return false;
   if(Number(m.balance_cents||0)===0)return false;
   if(String(m.remark||'')==='上级占位（待补资料）')return false;
   if(BERLIN_SAN_ROOTS.has(berlinReviewAccount(m.account)))return false;
   const latest=tree.team.get(String(m.id))?.latest||'';
   if(latest&&latest>=cutoff)return false;
   return tree.level(m)!=='—';
 }).map(m=>{
   const dayJoined=String(m.joined_on).slice(0,10);
   const info=tree.team.get(String(m.id))||{count:1};
   return {m,group:tree.group(m),label:tree.level(m),day:dayJoined,
      days:Math.floor((todayMs-Date.parse(dayJoined+'T00:00:00Z'))/86400000),
      cents:Number(m.balance_cents||0),descendant_count:Math.max(0,info.count-1),
      net_win_cents:Number(m.stake_cents||0)-Number(m.total_withdraw_cents||0)};
 }).sort((a,b)=>b.days-a.days||String(a.m.account).localeCompare(String(b.m.account)));
}
function berlinLoanRows(input=members){
 const tree=berlinReviewIndex(input);
 return tree.people.filter(m=>String(m.remark||'')!=='上级占位（待补资料）').flatMap(m=>{
   const stake=Number(m.stake_cents||0),balance=Number(m.balance_cents||0);
   if(!Number.isFinite(stake)||!Number.isFinite(balance)||stake<=0||balance<=0)return [];
   const direct=(tree.children.get(String(m.id))||[]).filter(c=>
     String(c.remark||'')!=='上级占位（待补资料）').length;
   const rate=direct>=5?200:150;
   if(rate===200?balance<stake*2:balance*2<stake*3)return [];
   const info=tree.team.get(String(m.id))||{count:1,stake,withdrawn:Number(m.total_withdraw_cents||0)};
   return [{m,group:tree.group(m),direct_count:direct,
      umbrella_count:Math.max(0,info.count-1),stake_cents:stake,balance_cents:balance,
      target_percent:rate,target_cents:stake*rate/100,
      ratio:100*balance/stake,team_win_cents:info.stake-info.withdrawn}];
 });
}
function berlinReviewKnownGroups(){
 const config=(typeof TREE_GROUPS!=='undefined'&&Array.isArray(TREE_GROUPS))?TREE_GROUPS:[];
 const list=(Array.isArray(members)?members:[]).map(x=>
   String(x.group_account||x.group_name||x.group||'').trim()).filter(Boolean);
 return [...new Set([...config,...list])].sort((a,b)=>String(a).localeCompare(String(b),'zh-CN',{numeric:true}));
}
function berlinReviewOptions(select,rows){
 const old=select.value;
 const names=[...new Set([...berlinReviewKnownGroups(),...rows.map(x=>x.group)])]
   .filter(Boolean).sort((a,b)=>String(a).localeCompare(String(b),'zh-CN',{numeric:true}));
 select.replaceChildren();
 for(const [value,label] of [['','全部小组'],...names.map(x=>[x,x])]){
  const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);
 }
 select.value=names.includes(old)?old:'';
}
function berlinReviewSort(rows,key,descending){
 const mult=descending?-1:1;
 return rows.slice().sort((a,b)=>{
  const x=key==='account'?String(a.m.account||''):key==='remark'?String(a.m.remark||''):a[key];
  const y=key==='account'?String(b.m.account||''):key==='remark'?String(b.m.remark||''):b[key];
  const cmp=typeof x==='number'&&typeof y==='number'?(x-y):
    String(x).localeCompare(String(y),'zh-CN',{numeric:true});
  return mult*(cmp||String(a.m.account).localeCompare(String(b.m.account),'zh-CN',{numeric:true}));
 });
}
function berlinReviewTable(rows,headers,values,onSort,sortKey,descending,page,table){
 table.replaceChildren();
 const thead=document.createElement('thead'),tr=document.createElement('tr');
 for(const [key,label] of headers){
  const th=document.createElement('th'),btn=document.createElement('button');
  btn.type='button';btn.className='berlin-review-th-button';
  btn.textContent=label+(key===sortKey?(descending?' ↓':' ↑'):' ↕');
  btn.onclick=()=>onSort(key);
  th.append(btn);tr.append(th);
 }
 const th=document.createElement('th');th.textContent='定位';tr.append(th);
 thead.append(tr);table.append(thead);
 const body=document.createElement('tbody');
 for(const x of rows.slice(page*BERLIN_REVIEW_PAGE,(page+1)*BERLIN_REVIEW_PAGE)){
  const r=document.createElement('tr');
  for(const [idx,value] of values(x).entries()){
   const td=document.createElement('td');td.textContent=String(value);
   if(headers[idx][0]==='net_win_cents'||headers[idx][0]==='team_win_cents'){
    const cash=Number(x[headers[idx][0]]||0);
    td.className=cash<0?'berlin-review-negative':cash>0?'berlin-review-positive':'';
   }else if(headers[idx][0]==='cents'||headers[idx][0]==='balance_cents')
    td.className='berlin-review-positive';
   r.append(td);
  }
  const cell=document.createElement('td'),button=document.createElement('button');
  button.type='button';button.className='berlin-review-focus';button.textContent='查看';
  button.onclick=()=>{
   const panel=r.closest('.berlin-review-overlay');
   if(panel)panel.hidden=true;
   if(view==='branch'||view==='tree')berlinHistoryFocusMember(x.m);
  };
  cell.append(button);r.append(cell);body.append(r);
 }
 if(!rows.length){
  const r=document.createElement('tr'),td=document.createElement('td');
  td.colSpan=headers.length+1;td.textContent='当前分组暂无符合条件的会员';r.append(td);body.append(r);
 }
 table.append(body);
}
function berlinReviewWindow(kind){
 const overlay=document.createElement('div');
 overlay.className='berlin-review-overlay';overlay.hidden=true;
 overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');
 const panel=document.createElement('section');panel.className='berlin-review-panel';
 const header=document.createElement('div');header.className='berlin-review-header';
 const title=document.createElement('strong');title.textContent=kind==='loan'?'💰 放款名单':'📋 躺平名单';
 const close=document.createElement('button');close.type='button';close.textContent='关闭 ×';
 close.onclick=()=>{overlay.hidden=true};
 header.append(title,close);
 const note=document.createElement('p');note.className='berlin-review-note';
 const bar=document.createElement('div');bar.className='berlin-review-bar';
 const label=document.createElement('label');label.textContent='选择小组：';
 const select=document.createElement('select');select.setAttribute('aria-label','名单小组筛选');
 label.append(select);
 const summary=document.createElement('strong');summary.className='berlin-review-summary';
 bar.append(label,summary);
 const stat=document.createElement('div');stat.className='berlin-review-stats';
 const wrap=document.createElement('div');wrap.className='berlin-review-scroll';
 const table=document.createElement('table');table.className='berlin-review-table';wrap.append(table);
 const pager=document.createElement('div');pager.className='berlin-review-pager';
 const totals=document.createElement('div');totals.className='berlin-review-totals';
 panel.append(header,note,bar,stat,wrap,pager,totals);overlay.append(panel);
 document.body.append(overlay);
 overlay.onclick=e=>{if(e.target===overlay)overlay.hidden=true};
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape')overlay.hidden=true});
 select.onchange=()=>{if(kind==='loan'){berlinLoanPage=0;berlinLoanDraw()}
   else{berlinFlatPage=0;berlinFlatlineDraw()}};
 return {overlay,select,summary,note,stat,table,pager,totals};
}
function berlinReviewTotals(ui,rows,spec){
 ui.stat.replaceChildren();ui.totals.replaceChildren();
 const amount=rows.reduce((s,x)=>s+Number(x[spec.balance]||0),0);
 const groups=new Map();
 for(const x of rows){
  const g=groups.get(x.group)||{count:0,balance:0};
  g.count++;g.balance+=Number(x[spec.balance]||0);groups.set(x.group,g);
 }
 for(const [label,value] of [['符合条件',rows.length+' 人'],['当前余额合计',berlinReviewCurrency(amount)],
      ['涉及小组',groups.size+' 个']]){
  const card=document.createElement('div');card.className='berlin-review-stat';
  const small=document.createElement('span');small.textContent=label;
  const bold=document.createElement('strong');bold.textContent=value;card.append(small,bold);
  ui.stat.append(card);
 }
 const heading=document.createElement('strong');
 heading.textContent='总体结算：'+rows.length+' 人，当前余额合计 '+berlinReviewCurrency(amount);
 ui.totals.append(heading);
 for(const [name,x] of [...groups].sort((a,b)=>a[0].localeCompare(b[0],'zh-CN',{numeric:true}))){
  const span=document.createElement('span');
  span.textContent=name+'：'+x.count+'人 / '+berlinReviewCurrency(x.balance);
  ui.totals.append(span);
 }
}
function berlinReviewPager(ui,current,max,apply){
 ui.pager.replaceChildren();
 const prev=document.createElement('button');prev.type='button';prev.textContent='◀ 上一页';
 prev.disabled=current<=0;prev.onclick=()=>apply(current-1);
 const label=document.createElement('span');label.textContent='第 '+(current+1)+' / '+(max+1)+' 页';
 const next=document.createElement('button');next.type='button';next.textContent='下一页 ▶';
 next.disabled=current>=max;next.onclick=()=>apply(current+1);
 ui.pager.append(prev,label,next);
}
function berlinFlatlineEnsure(){
 const bar=berlinHistoryToolbar?.bar;if(!bar)return;
 let b=document.getElementById('berlinFlatlineOpen');
 if(!b){b=document.createElement('button');b.id='berlinFlatlineOpen';
   b.className='berlin-history-nav berlin-flatline-open';b.type='button';
   b.textContent='📋 躺平名单';b.onclick=berlinFlatlineOpen;}
 if(b.parentElement!==bar)bar.append(b);
}
function berlinLoanEnsure(){
 const bar=berlinHistoryToolbar?.bar;if(!bar)return;
 let b=document.getElementById('berlinLoanOpen');
 if(!b){b=document.createElement('button');b.id='berlinLoanOpen';
   b.className='berlin-history-nav berlin-loan-open';b.type='button';
   b.textContent='💰 放款名单';b.onclick=berlinLoanOpen;}
 if(b.parentElement!==bar)bar.append(b);
}
function berlinFlatlineOpen(){
 if(berlinLoanUI)berlinLoanUI.overlay.hidden=true;
 if(!berlinFlatlineUI)berlinFlatlineUI=berlinReviewWindow('flatline');
 berlinFlatPage=0;berlinFlatlineUI.overlay.hidden=false;berlinFlatlineDraw();
}
function berlinFlatlineDraw(){
 const ui=berlinFlatlineUI;if(!ui)return;
 const all=berlinFlatlineRows();berlinReviewOptions(ui.select,all);
 const rows=berlinReviewSort(all.filter(x=>!ui.select.value||x.group===ui.select.value),
   berlinFlatSort,berlinFlatDesc);
 const max=Math.max(0,Math.ceil(rows.length/BERLIN_REVIEW_PAGE)-1);
 berlinFlatPage=Math.min(berlinFlatPage,max);
 ui.note.textContent='加入满三个自然月、最近三个月本人全部下级（含间接下级）无新增；余额为0不计入；SAN01/02/05/06/08组长不排行，其直属下级为A。躺平天数从加入日算起。';
 ui.summary.textContent='符合条件 '+rows.length+' 人';
 const cols=[['group','所属分组'],['remark','会员备注'],['account','会员账号'],
  ['label','层级'],['day','加入日期'],['days','躺平天数'],['cents','当前余额'],
  ['descendant_count','历史下级数'],['net_win_cents','输赢']];
 berlinReviewTable(rows,cols,x=>[x.group,x.m.remark||'未填写备注',x.m.account,x.label,
    x.day,x.days+' 天',berlinReviewCurrency(x.cents),x.descendant_count,berlinReviewSign(x.net_win_cents)],
  key=>{if(key===berlinFlatSort)berlinFlatDesc=!berlinFlatDesc;
       else{berlinFlatSort=key;berlinFlatDesc=['days','cents','descendant_count','net_win_cents'].includes(key)}
       berlinFlatPage=0;berlinFlatlineDraw()},berlinFlatSort,berlinFlatDesc,berlinFlatPage,ui.table);
 berlinReviewPager(ui,berlinFlatPage,max,p=>{berlinFlatPage=p;berlinFlatlineDraw()});
 berlinReviewTotals(ui,rows,{balance:'cents'});
}
function berlinLoanOpen(){
 if(berlinFlatlineUI)berlinFlatlineUI.overlay.hidden=true;
 if(!berlinLoanUI)berlinLoanUI=berlinReviewWindow('loan');
 berlinLoanPage=0;berlinLoanUI.overlay.hidden=false;berlinLoanDraw();
}
function berlinLoanDraw(){
 const ui=berlinLoanUI;if(!ui)return;
 const all=berlinLoanRows();berlinReviewOptions(ui.select,all);
 const filtered=all.filter(x=>!ui.select.value||x.group===ui.select.value);
 const sorted=berlinReviewSort(filtered,berlinLoanSort,berlinLoanDesc);
 const max=Math.max(0,Math.ceil(sorted.length/BERLIN_REVIEW_PAGE)-1);
 berlinLoanPage=Math.min(berlinLoanPage,max);
 const overall=berlinReviewIndex(members).people.filter(x=>
  String(x.remark||'')!=='上级占位（待补资料）'&&
  (!ui.select.value||berlinReviewIndex(members).group(x)===ui.select.value))
    .reduce((s,x)=>s+Number(x.stake_cents||0)-Number(x.total_withdraw_cents||0),0);
 ui.note.textContent='直属下级不足5人：个人余额达到建仓150%；直属达到5人及以上：个人余额达到建仓200%。伞下总人数不含本人，输赢＝本人及全部下级建仓－累计提现。此名单只用于审核，不自动放款。';
 ui.summary.textContent='符合条件 '+sorted.length+' 人　｜　当前筛选范围整体输赢 '+berlinReviewSign(overall);
 const cols=[['group','所属分组'],['remark','会员备注'],['account','会员账号'],
  ['direct_count','直属下级'],['umbrella_count','伞下总人数'],['stake_cents','建仓资金'],
  ['balance_cents','当前仓位余额'],['target_percent','适用标准'],['target_cents','达标余额'],
  ['team_win_cents','伞下整体输赢'],['ratio','余额/建仓比例']];
 berlinReviewTable(sorted,cols,x=>[x.group,x.m.remark||'未填写备注',x.m.account,
   x.direct_count,x.umbrella_count,berlinReviewCurrency(x.stake_cents),
   berlinReviewCurrency(x.balance_cents),x.target_percent+'%',berlinReviewCurrency(x.target_cents),
   berlinReviewSign(x.team_win_cents),x.ratio.toFixed(2)+'%'],
  key=>{if(key===berlinLoanSort)berlinLoanDesc=!berlinLoanDesc;
       else{berlinLoanSort=key;berlinLoanDesc=['ratio','stake_cents','balance_cents','team_win_cents','umbrella_count','direct_count'].includes(key)}
       berlinLoanPage=0;berlinLoanDraw()},berlinLoanSort,berlinLoanDesc,berlinLoanPage,ui.table);
 berlinReviewPager(ui,berlinLoanPage,max,p=>{berlinLoanPage=p;berlinLoanDraw()});
 berlinReviewTotals(ui,sorted,{balance:'balance_cents'});
}
'''
j=j[:start]+script+"\n"+j[end:]
anchor=" berlinFlatlineEnsure();\n lastDisplayDay=businessDay||dateNow();"
assert j.count(anchor)==1,"Missing Berlin roster render hook"
j=j.replace(anchor," berlinFlatlineEnsure();\n berlinLoanEnsure();\n lastDisplayDay=businessDay||dateNow();",1)
css=r'''
<style id="berlin-v22-rosters-css">
.berlin-loan-open{font-weight:800!important;border-color:#8fc7a8!important;
 background:#ecfbf0!important;color:#17623a!important}
.berlin-review-overlay[hidden]{display:none!important}
.berlin-review-overlay{position:fixed;z-index:2147483642;inset:0;background:#0a2038bd;
 display:flex;align-items:center;justify-content:center;box-sizing:border-box;padding:12px}
.berlin-review-panel{box-sizing:border-box;width:min(1520px,99vw);max-height:94vh;height:min(92vh,960px);
 background:#fff;color:#1a3240;border-radius:13px;overflow:hidden;display:flex;flex-direction:column;
 box-shadow:0 20px 60px #061a3570}
.berlin-review-header{display:flex;justify-content:space-between;align-items:center;padding:12px 17px;
 background:#eaf4f5;border-bottom:1px solid #c9dae2;font-size:18px}
.berlin-review-header button,.berlin-review-focus,.berlin-review-pager button{
 border:1px solid #a9c2ce;color:#1b4b5d;background:#fff;border-radius:7px;
 padding:6px 10px;cursor:pointer}
.berlin-review-note{font-size:12px;color:#556b77;margin:8px 15px!important;line-height:1.6}
.berlin-review-bar{display:flex;gap:16px;align-items:center;flex-wrap:wrap;padding:9px 15px}
.berlin-review-bar label{display:flex;gap:8px;align-items:center;font-weight:750;font-size:13px}
.berlin-review-bar select{padding:6px;border:1px solid #9cc4d0;border-radius:7px;background:#fff;color:#203f50;min-width:140px}
.berlin-review-summary{color:#9a511e;font-size:13px}
.berlin-review-stats{display:flex;gap:9px;flex-wrap:wrap;padding:4px 15px 12px}
.berlin-review-stat{display:flex;flex-direction:column;gap:4px;min-width:140px;flex:1;
 border:1px solid #dce9ea;border-radius:9px;padding:10px 12px;background:#f5fafb}
.berlin-review-stat span{color:#607581;font-size:11px}
.berlin-review-stat strong{font-size:18px;color:#16596b}
.berlin-review-scroll{flex:1;min-height:90px;overflow:auto;margin:0 15px;
 scrollbar-width:auto;scrollbar-color:#6f99af #e7eef2}
.berlin-review-table{border-collapse:collapse;min-width:1220px;width:100%;font-size:12px;white-space:nowrap}
.berlin-review-table th{position:sticky;top:0;background:#e8f2f7;color:#1c4c61;z-index:2}
.berlin-review-table th,.berlin-review-table td{text-align:center;padding:9px;border-bottom:1px solid #e5edf0}
.berlin-review-table tr:nth-child(even){background:#f9fbfc}
.berlin-review-th-button{background:none;border:0;cursor:pointer;color:inherit;font-size:12px;font-weight:850;white-space:nowrap}
.berlin-review-th-button:hover{text-decoration:underline}
.berlin-review-positive{color:#13815b;font-weight:850;font-variant-numeric:tabular-nums}
.berlin-review-negative{color:#d03638;font-weight:850;font-variant-numeric:tabular-nums}
.berlin-review-pager{display:flex;gap:12px;align-items:center;justify-content:center;padding:9px;border-top:1px solid #d8e8ea}
.berlin-review-pager button:disabled{opacity:.4;cursor:default}
.berlin-review-totals{background:#f6fafb;max-height:110px;overflow:auto;display:flex;flex-wrap:wrap;gap:9px;
 border-top:1px solid #d8e8ea;padding:12px 15px;font-size:12px}
.berlin-review-totals strong{color:#95531c}
.berlin-review-totals span{border:1px solid #dfebed;padding:3px 7px;border-radius:5px}
@media(max-width:670px){.berlin-review-overlay{padding:4px}
.berlin-review-panel{height:calc(100dvh - 8px);max-height:none}
.berlin-review-stats{padding:4px 8px}.berlin-review-header{font-size:15px}}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count("function berlinFlatlineRows(")==1
assert j.count("function berlinLoanRows(")==1
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print("PASS: Berlin synchronized V22 dormant, zero balance/SAN rebase and read-only release eligibility lists")
