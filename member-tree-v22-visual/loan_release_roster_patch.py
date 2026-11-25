"""V22 read-only disbursement eligibility monitor.

No payouts, transactions or member edits. All results are calculated in the browser
from the active tree snapshot. Eligibility is individual current balance at least
150% of deposited stake if direct recruits <5; at least 200% otherwise.
"""
from pathlib import Path
p=Path("member-tree/static/app.js")
hp=Path("member-tree/static/index.html")
s=p.read_text(encoding="utf-8")
h=hp.read_text(encoding="utf-8")
def once(old,new):
 global s
 assert s.count(old)==1,("V22 loan-list anchor changed",s.count(old),old[:120])
 s=s.replace(old,new,1)
helper=r'''
// Eligibility list is display-only. Nothing here posts funds or edits members.
let v22LoanPanel=null,v22LoanGroup='',v22LoanSort='ratio',v22LoanDesc=true,
    v22LoanPage=0,v22LoanRows=[],v22LoanAllPeople=[];
const V22_LOAN_PAGE_SIZE=100;
function v22LoanGroupOf(m,byId){
 const assigned=String(m.group_account||'').trim();
 if(assigned)return assigned;
 let curr=m,seen=new Set();
 while(curr.parent_id&&byId.has(String(curr.parent_id))&&!seen.has(String(curr.id))){
  seen.add(String(curr.id));curr=byId.get(String(curr.parent_id));
 }
 return String(curr.account||'未分组');
}
function v22LoanAnalyze(people){
 const rows=(Array.isArray(people)?people:[]).filter(m=>m&&!m.deleted);
 const byId=new Map(rows.map(m=>[String(m.id),m]));
 const children=new Map();
 for(const m of rows){
  const key=String(m.parent_id||'');
  if(!key||key===String(m.id)||!byId.has(key))continue;
  if(!children.has(key))children.set(key,[]);
  children.get(key).push(m);
 }
 const order=[],visited=new Set();
 for(const m of rows){
  const stack=[[String(m.id),false]];
  while(stack.length){
   const [id,complete]=stack.pop();
   if(complete){order.push(id);continue}
   if(visited.has(id))continue;
   visited.add(id);stack.push([id,true]);
   for(const child of children.get(id)||[]){
    const ck=String(child.id);
    if(!visited.has(ck))stack.push([ck,false]);
   }
  }
 }
 const team=new Map();
 for(const id of order){
  const m=byId.get(id);
  const isPlaceholder=String(m.remark||'')==='上级占位（待补资料）';
  let count=isPlaceholder?0:1;
  let stake=isPlaceholder?0:Number(m.stake_cents||0);
  let withdraw=isPlaceholder?0:Number(m.total_withdraw_cents||0);
  for(const c of children.get(id)||[]){
   const sub=team.get(String(c.id));
   if(!sub)continue;
   count+=sub.count;stake+=sub.stake;withdraw+=sub.withdraw;
  }
  team.set(id,{count,stake,withdraw});
 }
 const allPeople=rows.filter(m=>String(m.remark||'')!=='上级占位（待补资料）')
    .map(m=>({member:m,group:v22LoanGroupOf(m,byId)}));
 const eligible=[];
 for(const {member:m,group} of allPeople){
  const stake=Number(m.stake_cents||0),balance=Number(m.balance_cents||0);
  // Stake must be positive. Zero-capital or zero-balance accounts cannot qualify.
  if(!Number.isFinite(stake)||!Number.isFinite(balance)||stake<=0||balance<=0)continue;
  const direct=(children.get(String(m.id))||[]).filter(c=>
    !c.deleted&&String(c.remark||'')!=='上级占位（待补资料）').length;
  const target=direct>=5?200:150;
  // Integer cents comparison avoids floating point boundary surprises.
  const qualifies=target===200?balance>=stake*2:balance*2>=stake*3;
  if(!qualifies)continue;
  const t=team.get(String(m.id))||{count:1,stake,withdraw:Number(m.total_withdraw_cents||0)};
  eligible.push({
    id:m.id,account:String(m.account||''),remark:String(m.remark||'').trim()||'未填写备注',
    group,direct_count:direct,umbrella_count:Math.max(0,t.count-1),
    stake_cents:stake,balance_cents:balance,required_percent:target,
    required_cents:stake*target/100,
    ratio:Math.round(balance/stake*10000)/100,
    team_win_cents:t.stake-t.withdraw
  });
 }
 return {eligible,allPeople};
}
function v22LoanClose(){
 if(!v22LoanPanel)return;
 v22LoanPanel.overlay.remove();v22LoanPanel=null;
 document.body.classList.remove('v22-loan-body-open');
}
function v22LoanSorted(list){
 const sign=v22LoanDesc?-1:1;
 return list.slice().sort((a,b)=>{
  const x=a[v22LoanSort],y=b[v22LoanSort];
  const c=typeof x==='number'?(x-y):
    String(x).localeCompare(String(y),'zh-CN',{numeric:true});
  return sign*(c||String(a.account).localeCompare(String(b.account),'zh-CN',{numeric:true}));
 });
}
function v22LoanMoney(v){return (v>0?'+':'')+money(v,true)}
function v22LoanRender(){
 const ui=v22LoanPanel;if(!ui)return;
 const showing=v22LoanRows.filter(r=>!v22LoanGroup||r.group===v22LoanGroup);
 const list=v22LoanSorted(showing);
 const allSum=v22LoanAllPeople.filter(r=>!v22LoanGroup||r.group===v22LoanGroup)
    .reduce((n,r)=>n+Number(r.member.stake_cents||0)-Number(r.member.total_withdraw_cents||0),0);
 const balance=showing.reduce((n,r)=>n+r.balance_cents,0);
 const groups=[...new Set([...TREE_GROUPS,
   ...v22LoanAllPeople.map(r=>r.group),...v22LoanRows.map(r=>r.group)]
   .filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN',{numeric:true}));
 ui.group.replaceChildren();
 const all=mk('option','','全部分组');all.value='';ui.group.append(all);
 for(const g of groups){const o=mk('option','',g);o.value=g;ui.group.append(o)}
 if(v22LoanGroup&&!groups.includes(v22LoanGroup))v22LoanGroup='';
 ui.group.value=v22LoanGroup;
 ui.heading.textContent='放款名单 · '+showing.length+' 人';
 ui.summary.textContent='符合条件 '+showing.length+' 人　｜　当前仓位余额合计 '+
    money(balance,true)+'　｜　筛选范围整体输赢 '+v22LoanMoney(allSum);
 ui.summary.className='v22-loan-summary'+(allSum<0?' v22-loan-loss':'');
 const names=[
  ['group','所属分组'],['remark','会员备注'],['account','会员账号'],
  ['direct_count','直属下级'],['umbrella_count','伞下总人数'],
  ['stake_cents','建仓资金'],['balance_cents','当前仓位余额'],
  ['required_percent','适用标准'],['required_cents','达标余额'],
  ['team_win_cents','伞下整体输赢'],['ratio','余额/建仓比例']
 ];
 const end=Math.max(0,Math.ceil(list.length/V22_LOAN_PAGE_SIZE)-1);
 v22LoanPage=Math.min(v22LoanPage,end);
 const page=list.slice(v22LoanPage*V22_LOAN_PAGE_SIZE,(v22LoanPage+1)*V22_LOAN_PAGE_SIZE);
 ui.table.replaceChildren();
 const head=mk('div','v22-loan-row v22-loan-row-head');
 for(const [field,label] of names){
  const selected=v22LoanSort===field;
  const b=mk('button','v22-loan-sort'+(selected?' is-active':''),
   label+(selected?(v22LoanDesc?' ↓':' ↑'):' ↕'));
  b.type='button';b.onclick=()=>{
   if(v22LoanSort===field)v22LoanDesc=!v22LoanDesc;
   else{v22LoanSort=field;v22LoanDesc=['ratio','balance_cents','team_win_cents',
       'umbrella_count','direct_count','stake_cents'].includes(field)}
   v22LoanPage=0;v22LoanRender();
  };
  head.append(b);
 }
 ui.table.append(head);
 for(const r of page){
  const values=[r.group,r.remark,r.account,String(r.direct_count),
     String(r.umbrella_count),money(r.stake_cents,true),
     money(r.balance_cents,true),r.required_percent+'%',
     money(r.required_cents,true),v22LoanMoney(r.team_win_cents),r.ratio.toFixed(2)+'%'];
  const row=mk('div','v22-loan-row');
  values.forEach((v,i)=>{
   const cls=i===9?(r.team_win_cents>0?'v22-loan-gain':r.team_win_cents<0?'v22-loan-loss':'v22-loan-neutral'):
      i===6?'v22-loan-balance':'';
   const cell=mk('span',cls,v);cell.title=String(v);row.append(cell);
  });
  ui.table.append(row);
 }
 const perGroup=new Map();
 for(const r of showing){
  const obj=perGroup.get(r.group)||{count:0,balance:0};
  obj.count++;obj.balance+=r.balance_cents;perGroup.set(r.group,obj);
 }
 ui.total.replaceChildren();
 ui.total.append(mk('strong','','名单结算：'+showing.length+' 人，仓位余额合计 '+money(balance,true)));
 for(const [g,obj] of [...perGroup].sort((a,b)=>a[0].localeCompare(b[0],'zh-CN',{numeric:true})))
  ui.total.append(mk('span','',g+'：'+obj.count+'人 / '+money(obj.balance,true)));
 ui.footer.replaceChildren();
 const prev=mk('button','','◀ 上一页');prev.type='button';prev.disabled=v22LoanPage<=0;
 prev.onclick=()=>{v22LoanPage--;v22LoanRender()};
 const middle=mk('span','','第 '+(v22LoanPage+1)+' / '+(end+1)+' 页 · 共 '+list.length+' 人');
 const next=mk('button','','下一页 ▶');next.type='button';next.disabled=v22LoanPage>=end;
 next.onclick=()=>{v22LoanPage++;v22LoanRender()};
 ui.footer.append(prev,middle,next);
 ui.explain.textContent='统计口径：直属下级不足5人，个人当前余额须达到建仓资金150%；直属下级达到5人及以上，须达到200%。'+
  '伞下总人数不含本人，伞下整体输赢＝本人及全部伞下成员建仓总额－累计提现总额；顶部整体输赢按筛选范围的独立会员统计，不重复汇总上下级。'+
  '名单仅供审核，系统不自动放款，不改写会员或财务数据。';
}
function v22LoanOpen(){
 if(v22HistMaximized)v22HistSetMaximized(false);
 if(v22DormantPanel)v22DormantClose();
 v22LoanClose();
 const data=v22LoanAnalyze(members);
 v22LoanRows=data.eligible;v22LoanAllPeople=data.allPeople;
 v22LoanGroup=selectedTreeGroup||'';v22LoanPage=0;v22LoanSort='ratio';v22LoanDesc=true;
 const overlay=mk('div','v22-loan-overlay');
 overlay.setAttribute('role','dialog');
 overlay.setAttribute('aria-modal','true');overlay.setAttribute('aria-label','放款名单');
 const panel=mk('section','v22-loan-panel');
 const header=mk('div','v22-loan-head');
 const heading=mk('h3','','放款名单');
 const close=mk('button','v22-loan-close','✕ 关闭');close.type='button';
 close.onclick=v22LoanClose;header.append(heading,close);
 const filters=mk('div','v22-loan-filters');
 const label=mk('label','','选择分组：');
 const group=mk('select','v22-loan-group');group.setAttribute('aria-label','筛选放款名单分组');
 group.onchange=()=>{v22LoanGroup=group.value;v22LoanPage=0;v22LoanRender()};
 label.append(group);
 const summary=mk('strong','v22-loan-summary');
 filters.append(label,summary);
 const scroll=mk('div','v22-loan-scroll');
 const table=mk('div','v22-loan-table');scroll.append(table);
 const footer=mk('div','v22-loan-footer'),total=mk('div','v22-loan-total'),
  explain=mk('p','v22-loan-explain');
 panel.append(header,filters,scroll,footer,total,explain);overlay.append(panel);
 overlay.addEventListener('click',e=>{if(e.target===overlay)v22LoanClose()});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();v22LoanClose()}});
 document.body.append(overlay);document.body.classList.add('v22-loan-body-open');
 v22LoanPanel={overlay,heading,group,summary,table,footer,total,explain};
 v22LoanRender();close.focus();
}
'''
once("function v22HistUpdateToolbar(){",helper+"\nfunction v22HistUpdateToolbar(){")
once("""  dormant.type='button';dormant.onclick=v22DormantOpen;""",
"""  dormant.type='button';dormant.onclick=v22DormantOpen;
  const loan=mk('button','v22-hist-button v22-loan-trigger','💰 放款名单');
  loan.type='button';loan.onclick=v22LoanOpen;""")
once("b.append(label,newer,withdraw,week,month,dormant,prev,pick,next,yesterday,today,info,details,note);",
    "b.append(label,newer,withdraw,week,month,dormant,loan,prev,pick,next,yesterday,today,info,details,note);")
once(""" if(!on&&v22DormantPanel)v22DormantClose();
 if(!on){""",
""" if(!on&&v22DormantPanel)v22DormantClose();
 if(!on&&v22LoanPanel)v22LoanClose();
 if(!on){""")
css=r'''
<style id="v22-loan-roster-style">
.v22-loan-trigger{border-color:#9bbda3!important;background:#ebfaee!important;color:#126136!important;font-weight:800!important}
.v22-loan-trigger:hover{background:#d0efd8!important}
body.v22-loan-body-open{overflow:hidden!important}
.v22-loan-overlay{position:fixed!important;inset:0!important;z-index:2147483642!important;
 background:#091c32bb;display:flex;align-items:center;justify-content:center;padding:12px;box-sizing:border-box!important}
.v22-loan-panel{display:flex;flex-direction:column;min-height:0;width:min(1500px,100%);
 height:min(92dvh,1030px);max-height:95dvh;overflow:hidden;border-radius:12px;
 background:#fff;box-shadow:0 18px 65px #061b326b;color:#243444}
.v22-loan-head{display:flex;justify-content:space-between;align-items:center;gap:12px;
 padding:12px 17px;background:#ebf6f1;border-bottom:1px solid #b4d6c2;flex-shrink:0}
.v22-loan-head h3{font-size:19px;font-weight:900;color:#145636;margin:0}
.v22-loan-close{border:1px solid #98bfaa;border-radius:7px;background:#fff;color:#155639;padding:7px 12px;font-weight:800;cursor:pointer}
.v22-loan-filters{display:flex;flex-wrap:wrap;gap:17px;align-items:center;
 padding:11px 16px;background:#f8fbf9;border-bottom:1px solid #dce9e1;flex-shrink:0}
.v22-loan-filters label{font-size:13px;font-weight:800}
.v22-loan-group{border:1px solid #8fbca6;padding:7px 10px;background:#fff;border-radius:7px;min-width:138px;color:#174e33}
.v22-loan-summary{font-size:13px;color:#23704d}
.v22-loan-scroll{min-height:0;flex:1 1 0;overflow:auto;scrollbar-width:auto;scrollbar-color:#71a790 #e8f0eb;scrollbar-gutter:stable}
.v22-loan-scroll::-webkit-scrollbar{width:13px;height:11px}
.v22-loan-scroll::-webkit-scrollbar-thumb{background:#70a58a;border:2px solid #e8f0eb;border-radius:10px}
.v22-loan-table{min-width:1430px;width:100%}
.v22-loan-row{display:grid;grid-template-columns:minmax(75px,.65fr) minmax(130px,1.2fr) minmax(110px,1.1fr)
 minmax(82px,.7fr) minmax(105px,.9fr) minmax(115px,1fr) minmax(120px,1fr)
 minmax(88px,.8fr) minmax(120px,1fr) minmax(130px,1.1fr) minmax(120px,1fr);
 gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid #e4ebe7;font-size:12px}
.v22-loan-row:not(.v22-loan-row-head):nth-child(even){background:#f8fcf9}
.v22-loan-row>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.v22-loan-row-head{position:sticky;top:0;z-index:2;background:#e8f3ec;border-bottom:2px solid #9ccbaa;padding:7px 12px}
.v22-loan-sort{border:0;background:none;padding:6px 0;color:#21573b;text-align:left;
 white-space:nowrap;cursor:pointer;font-weight:900;font-size:12px}
.v22-loan-sort.is-active{color:#bb681e}
.v22-loan-sort:hover{text-decoration:underline}
.v22-loan-gain,.v22-loan-balance{color:#168052;font-weight:900;font-variant-numeric:tabular-nums}
.v22-loan-loss{color:#c83738!important;font-weight:900;font-variant-numeric:tabular-nums}
.v22-loan-neutral{color:#5b6d64;font-variant-numeric:tabular-nums}
.v22-loan-footer{display:flex;align-items:center;justify-content:center;gap:12px;padding:9px 12px;border-top:1px solid #d9e9de;flex-shrink:0}
.v22-loan-footer button{border:1px solid #a4c9b3;background:#f3fbf6;color:#175d3e;border-radius:7px;padding:7px 12px;cursor:pointer}
.v22-loan-footer button:disabled{opacity:.45;cursor:not-allowed}
.v22-loan-total{display:flex;align-items:center;flex-wrap:wrap;gap:10px;padding:10px 14px;border-top:1px solid #d2e3d7;
 background:#f6faf7;font-size:12px;flex-shrink:0;max-height:105px;overflow:auto}
.v22-loan-total>strong{color:#176541;font-size:14px}
.v22-loan-total>span{padding:3px 7px;border:1px solid #d5e5db;background:#fff;border-radius:6px}
.v22-loan-explain{margin:0;padding:8px 14px;background:#fff7e8;color:#755c36;font-size:11px;line-height:1.6;flex-shrink:0}
@media(max-width:760px){.v22-loan-overlay{padding:4px}
 .v22-loan-panel{height:calc(100dvh - 8px);max-height:none;border-radius:6px}
 .v22-loan-row{padding:8px}.v22-loan-head{padding:9px}}
</style>
'''
assert h.count("</body>")==1
h=h.replace("</body>",css+"</body>",1)
assert s.count("function v22LoanAnalyze(")==1
assert s.count("v22-loan-trigger")==1
p.write_text(s,encoding='utf-8');hp.write_text(h,encoding='utf-8')
print("PASS: V22 read-only loan-eligible roster, direct-5 thresholds, umbrella stats, current balances, group totals")
