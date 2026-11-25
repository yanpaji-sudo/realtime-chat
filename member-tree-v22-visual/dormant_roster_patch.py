"""V22 historical-toolbar "躺平名单": read-only 3-month downline inactivity.

An eligible member has been registered for at least 3 calendar months and has
no new member anywhere in their descendant subtree during the last 3 calendar
months (inclusive of the cutoff). This avoids counting recently-joined
members as already inactive. Time shown is days since personal join date.

Groups use existing member.group_account, fallback to the original top-level
ancestor's account when the group field is blank; depth 2=A, 3=B, 4=C...
The entire result is calculated from existing in-memory membership data.
No new SQL table, uploads, financial API, member writes or data mutation.
"""
from pathlib import Path
js=Path("member-tree/static/app.js")
html=Path("member-tree/static/index.html")
s=js.read_text(encoding="utf-8")
h=html.read_text(encoding="utf-8")
def replace_once(before,after):
 global s
 n=s.count(before)
 assert n==1,("V22 historical toolbar source changed",n,before[:155])
 s=s.replace(before,after,1)

# No render() changes: existing history toolbar is mounted for either tree view.
helper=r'''
// Dormant teams: 3 complete CALENDAR months without a new descendant,
// not simply 90 days, not merely zero direct children.
let v22DormantPanel=null;
let v22DormantGroup='',v22DormantPage=0;
let v22DormantSort='days',v22DormantDesc=true,v22DormantRows=[];
const V22_DORMANT_PAGE_SIZE=100;
const V22_DORMANT_EXCLUDED_ACCOUNTS=new Set(['SAN001','SAN002','SAN005','SAN006','SAN008']);
// For only these five structural groups, their children restart at tier A.
function v22DormantDisplayLevel(member,byId){
 let current=member,seen=new Set([member.id]),distance=0;
 while(current.parent_id&&byId.has(current.parent_id)){
  const parent=byId.get(current.parent_id);
  if(seen.has(parent.id))break;
  seen.add(parent.id);distance++;
  if(V22_DORMANT_EXCLUDED_ACCOUNTS.has(String(parent.account||'').trim().toUpperCase()))
   return v22DormantLevel(distance+1);
  current=parent;
 }
 return v22DormantLevel(Number(member.level||0));
}
function v22DormantDate(day){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(String(day||'')))return null;
 const d=new Date(day+'T00:00:00Z');
 return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===day?d:null;
}
function v22DormantCutoff(day){
 const today=v22DormantDate(day);
 if(!today)return null;
 const y=today.getUTCFullYear(),m=today.getUTCMonth(),dd=today.getUTCDate();
 const targetLast=new Date(Date.UTC(y,m-2,0)).getUTCDate();
 return new Date(Date.UTC(y,m-3,Math.min(dd,targetLast))).toISOString().slice(0,10);
}
function v22DormantDays(joinDay,todayDay){
 const a=v22DormantDate(joinDay),b=v22DormantDate(todayDay);
 if(!a||!b||a>b)return null;
 return Math.round((b.getTime()-a.getTime())/86400000);
}
function v22DormantLevel(depth){
 const n=Number(depth);
 if(!Number.isInteger(n)||n<2)return '总节点';
 let x=n-2,out='';
 do{out=String.fromCharCode(65+(x%26))+out;x=Math.floor(x/26)-1}while(x>=0);
 return out;
}
function v22DormantAnalyze(rows,day){
 const cutoff=v22DormantCutoff(day);
 if(!cutoff)return [];
 const byId=new Map(rows.map(x=>[x.id,x]));
 const children=new Map();
 for(const item of rows){
  if(!item.parent_id||!byId.has(item.parent_id)||item.parent_id===item.id)continue;
  if(!children.has(item.parent_id))children.set(item.parent_id,[]);
  children.get(item.parent_id).push(item);
 }
 // Iterative postorder: linear-time even for deep downlines. Do not depend
 // on every imported member having a perfectly accurate numeric level.
 const done=new Set(),post=[];
 for(const member of rows){
  const stack=[[member.id,false]];
  while(stack.length){
   const [id,complete]=stack.pop();
   if(complete){post.push(id);continue}
   if(done.has(id))continue;
   done.add(id);
   stack.push([id,true]);
   for(const sub of children.get(id)||[]){
    if(!done.has(sub.id))stack.push([sub.id,false]);
   }
  }
 }
 const newest=new Map(),sizes=new Map();
 for(const id of post){
  let latest='',count=0;
  for(const child of children.get(id)||[]){
   const childJoined=String(child.joined_on||'').slice(0,10);
   if(v22DormantDate(childJoined)&&childJoined>latest)latest=childJoined;
   const below=newest.get(child.id)||'';
   if(below>latest)latest=below;
   count+=1+(sizes.get(child.id)||0);
  }
  newest.set(id,latest);sizes.set(id,count);
 }
 function inheritedGroup(member){
  const assigned=String(member.group_account||'').trim();
  if(assigned)return assigned;
  let cur=member,seen=new Set();
  while(cur.parent_id&&byId.has(cur.parent_id)&&!seen.has(cur.id)){
   seen.add(cur.id);cur=byId.get(cur.parent_id);
  }
  return String(cur.account||'未分组');
 }
 const result=[];
 for(const member of rows){
  const joined=String(member.joined_on||'').slice(0,10);
  if(!v22DormantDate(joined)||joined>cutoff||member.deleted)continue;
  if(V22_DORMANT_EXCLUDED_ACCOUNTS.has(String(member.account||'').trim().toUpperCase()))continue;
  // Placeholder ancestors are not actual eligible members.
  if(String(member.remark||'')==='上级占位（待补资料）')continue;
  const latest=newest.get(member.id)||'';
  if(latest&&latest>=cutoff)continue;
  const level=Number(member.level||0);
  if(level<2)continue; // A is the second tier, not the artificial root.
  const days=v22DormantDays(joined,day);
  if(days===null)continue;
  result.push({
   id:member.id,account:String(member.account||''),
   remark:String(member.remark||'').trim()||'未填写备注',
   group:inheritedGroup(member),level:v22DormantDisplayLevel(member,byId),
   joined,days,balance_cents:Number(member.balance_cents||0),
   net_win_cents:Number(member.stake_cents||0)-Number(member.total_withdraw_cents||0),
   descendant_count:sizes.get(member.id)||0,
   latest_descendant_join:latest||'从未新增',
  });
 }
 return result;
}
function v22DormantClose(){
 if(!v22DormantPanel)return;
 v22DormantPanel.overlay.remove();
 v22DormantPanel=null;
 document.body.classList.remove('v22-dormant-body-open');
}
function v22DormantSortRows(rows){
 const field=v22DormantSort,desc=v22DormantDesc?-1:1;
 return rows.slice().sort((a,b)=>{
  const aa=a[field],bb=b[field];
  let cmp=typeof aa==='number'?aa-bb:
    String(aa).localeCompare(String(bb),'zh-CN',{numeric:true});
  return (cmp||a.account.localeCompare(b.account,'zh-CN',{numeric:true}))*desc;
 });
}
function v22DormantRender(){
 const state=v22DormantPanel;if(!state)return;
 const visible=v22DormantRows.filter(x=>!v22DormantGroup||x.group===v22DormantGroup);
 const sorted=v22DormantSortRows(visible);
 const sum=visible.reduce((n,x)=>n+Number(x.balance_cents||0),0);
 const activeGroups=new Set(visible.map(x=>x.group));
 const {heading,summary,group,total,table,footer,oldest}=state;
 heading.textContent='躺平名单 · '+visible.length+' 人';
 summary.textContent='符合条件 '+visible.length+' 人　｜　当前余额合计 '+money(sum,true)+'　｜　涉及分组 '+activeGroups.size+' 个';
 const groupValues=[...TREE_GROUPS,...members.map(x=>String(x.group_account||'').trim()),...v22DormantRows.map(x=>x.group)];
 const groups=[...new Set(groupValues.filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN',{numeric:true}));
 group.replaceChildren();
 const all=mk('option','','全部分组');all.value='';
 group.append(all);
 for(const name of groups){
  const o=mk('option','',name);o.value=name;group.append(o);
 }
 if(v22DormantGroup&&!groups.includes(v22DormantGroup))v22DormantGroup='';
 group.value=v22DormantGroup;
 const end=Math.max(0,Math.ceil(sorted.length/V22_DORMANT_PAGE_SIZE)-1);
 v22DormantPage=Math.min(v22DormantPage,end);
 const pageRows=sorted.slice(v22DormantPage*V22_DORMANT_PAGE_SIZE,
  (v22DormantPage+1)*V22_DORMANT_PAGE_SIZE);
 table.replaceChildren();
 const names=[['group','所属分组'],['remark','会员备注'],['account','会员账号'],
   ['level','层级'],['joined','加入日期'],['days','躺平时间'],
   ['balance_cents','当前余额'],['descendant_count','历史下级数'],
   ['net_win_cents','输赢']];
 const head=mk('div','v22-dormant-record v22-dormant-record-head');
 for(const [key,label] of names){
  const selected=v22DormantSort===key;
  const btn=mk('button','v22-dormant-sort'+(selected?' active':''),
    label+(selected?(v22DormantDesc?' ↓':' ↑'):' ↕'));
  btn.type='button';btn.title='点击排序'+label;
  btn.onclick=()=>{
   if(v22DormantSort===key)v22DormantDesc=!v22DormantDesc;
   else{v22DormantSort=key;v22DormantDesc=['days','balance_cents','descendant_count','net_win_cents'].includes(key)}
   v22DormantPage=0;v22DormantRender();
  };
  head.append(btn);
 }
 table.append(head);
 for(const entry of pageRows){
  const tr=mk('div','v22-dormant-record');
  const values=[entry.group,entry.remark,entry.account,entry.level,entry.joined,
    entry.days+' 天',money(entry.balance_cents,true),String(entry.descendant_count),
    (entry.net_win_cents>0?'+':'')+money(entry.net_win_cents,true)];
  for(let i=0;i<values.length;i++){
   const netClass=i===8?(entry.net_win_cents>0?'v22-dormant-profit-positive':entry.net_win_cents<0?'v22-dormant-profit-negative':'v22-dormant-profit-zero'):'';
   const cell=mk('span',i===6?'v22-dormant-money':netClass,values[i]);
   cell.title=String(values[i]);
   tr.append(cell);
  }
  table.append(tr);
 }
 const byGroup=new Map();
 for(const item of visible){
  let t=byGroup.get(item.group);
  if(!t){t={count:0,balance:0};byGroup.set(item.group,t)}
  t.count++;t.balance+=Number(item.balance_cents||0);
 }
 total.replaceChildren();
 total.append(mk('strong','','总体结算：'+visible.length+' 人，当前余额共 '+money(sum,true)));
 const groupsSummary=[...byGroup.entries()].sort((a,b)=>a[0].localeCompare(b[0],'zh-CN',{numeric:true}));
 for(const [name,row] of groupsSummary){
  total.append(mk('span','',name+'：'+row.count+'人 / '+money(row.balance,true)));
 }
 oldest.textContent='口径：加入满三个自然月、最近三个自然月全部下级（含间接下级）无新增；五个 SAN 总节点不参与名单，其下级从 A 层起算。躺平时间＝本人加入日至今天；输赢＝本人建仓－累计提现；余额为当前余额。';
 footer.replaceChildren();
 const prev=mk('button','','◀ 上一页');prev.type='button';
 prev.disabled=v22DormantPage<=0;
 prev.onclick=()=>{v22DormantPage--;v22DormantRender()};
 const pager=mk('span','','第 '+(v22DormantPage+1)+' / '+(end+1)+' 页 · 共 '+sorted.length+' 人');
 const next=mk('button','','下一页 ▶');next.type='button';
 next.disabled=v22DormantPage>=end;
 next.onclick=()=>{v22DormantPage++;v22DormantRender()};
 footer.append(prev,pager,next);
}
function v22DormantOpen(){
 // Do not leave two competing fullscreen overlays visible.
 if(v22HistMaximized)v22HistSetMaximized(false);
 v22DormantClose();
 v22DormantRows=v22DormantAnalyze(members,v22HistToday());
 v22DormantGroup=selectedTreeGroup||'';
 v22DormantPage=0;v22DormantSort='days';v22DormantDesc=true;
 const overlay=mk('div','v22-dormant-overlay');
 overlay.setAttribute('role','dialog');
 overlay.setAttribute('aria-modal','true');
 overlay.setAttribute('aria-label','躺平名单，按分组查看');
 const panel=mk('section','v22-dormant-panel');
 const head=mk('div','v22-dormant-head');
 const heading=mk('h3','','躺平名单');
 const close=mk('button','v22-dormant-close','✕ 关闭');close.type='button';
 close.onclick=v22DormantClose;
 head.append(heading,close);
 const filters=mk('div','v22-dormant-filters');
 const groupLabel=mk('label','','选择分组：');
 const group=mk('select','v22-dormant-group');
 group.setAttribute('aria-label','筛选躺平会员分组');
 group.onchange=()=>{v22DormantGroup=group.value;v22DormantPage=0;v22DormantRender()};
 groupLabel.append(group);
 const summary=mk('strong','v22-dormant-summary');
 filters.append(groupLabel,summary);
 const scroll=mk('div','v22-dormant-scroll');
 const table=mk('div','v22-dormant-table');
 scroll.append(table);
 const footer=mk('div','v22-dormant-footer');
 const total=mk('div','v22-dormant-total');
 const oldest=mk('p','v22-dormant-explain');
 panel.append(head,filters,scroll,footer,total,oldest);
 overlay.append(panel);
 overlay.addEventListener('click',event=>{if(event.target===overlay)v22DormantClose()});
 overlay.addEventListener('keydown',event=>{
  if(event.key==='Escape'){event.preventDefault();v22DormantClose()}
 });
 document.body.append(overlay);
 document.body.classList.add('v22-dormant-body-open');
 v22DormantPanel={overlay,heading,summary,group,table,footer,total,oldest};
 v22DormantRender();
 close.focus();
}
'''
replace_once("function v22HistUpdateToolbar(){",helper+"\nfunction v22HistUpdateToolbar(){")
replace_once("""  week.dataset.mode='week';month.dataset.mode='month';""",
"""  week.dataset.mode='week';month.dataset.mode='month';
  const dormant=mk('button','v22-hist-button v22-dormant-trigger','📋 躺平名单');
  dormant.type='button';dormant.onclick=v22DormantOpen;""")
replace_once("b.append(label,newer,withdraw,week,month,prev,pick,next,yesterday,today,info,details,note);",
  "b.append(label,newer,withdraw,week,month,dormant,prev,pick,next,yesterday,today,info,details,note);")
# Closing login / leaving tree view also closes the read-only modal.
replace_once(""" t.b.hidden=!on;
 if(!on){""",
""" t.b.hidden=!on;
 if(!on&&v22DormantPanel)v22DormantClose();
 if(!on){""")
css=r'''
<style id="v22-dormant-roster-style">
.v22-dormant-trigger{border-color:#c9a56c!important;background:#fff9ed!important;
 color:#725222!important;font-weight:800!important}
.v22-dormant-trigger:hover{background:#ffeccb!important}
body.v22-dormant-body-open{overflow:hidden!important}
.v22-dormant-overlay{
 position:fixed!important;inset:0!important;z-index:2147483642!important;
 background:#091c32b9;display:flex;align-items:center;justify-content:center;
 padding:12px;box-sizing:border-box!important;
}
.v22-dormant-panel{
 display:flex;flex-direction:column;min-height:0;
 width:min(1450px,100%);height:min(92dvh,1000px);max-height:95dvh;
 overflow:hidden;border-radius:12px;background:#fff;
 box-shadow:0 18px 65px #061b326b;color:#243444;
}
.v22-dormant-head{
 display:flex;align-items:center;justify-content:space-between;
 background:#eaf3fc;border-bottom:1px solid #b8d0e4;
 padding:12px 17px;gap:14px;flex-shrink:0;
}
.v22-dormant-head h3{margin:0;font-weight:900;font-size:19px;color:#123e5e}
.v22-dormant-close{
 border:1px solid #9bb7c9;border-radius:7px;background:white;
 padding:7px 12px;color:#125078;font-weight:800;cursor:pointer
}
.v22-dormant-filters{
 display:flex;flex-wrap:wrap;align-items:center;gap:18px;
 padding:11px 16px;background:#f8fbff;border-bottom:1px solid #dce7ef;
 flex-shrink:0
}
.v22-dormant-filters label{font-size:13px;font-weight:800}
.v22-dormant-group{border:1px solid #8eafc7;padding:7px 10px;
 background:#fff;border-radius:7px;min-width:140px;color:#163e57}
.v22-dormant-summary{color:#9c4a18;font-size:13px}
.v22-dormant-scroll{min-height:0;flex:1 1 0;overflow:auto;
 scrollbar-width:auto;scrollbar-color:#7094ad #e8eff4;
 scrollbar-gutter:stable}
.v22-dormant-scroll::-webkit-scrollbar{width:13px;height:11px}
.v22-dormant-scroll::-webkit-scrollbar-thumb{background:#789cb7;
 border-radius:10px;border:2px solid #e8eff4}
.v22-dormant-table{min-width:1080px;width:100%}
.v22-dormant-record{
 display:grid;grid-template-columns:minmax(90px,.8fr) minmax(170px,1.6fr)
 minmax(110px,1fr) minmax(60px,.48fr) minmax(112px,.85fr)
 minmax(108px,.85fr) minmax(110px,1fr) minmax(85px,.7fr)
 minmax(125px,.95fr);align-items:center;gap:8px;
 padding:10px 12px;border-bottom:1px solid #e4ebf1;font-size:12px;
}
.v22-dormant-record:not(.v22-dormant-record-head):nth-child(2n){background:#f9fbfd}
.v22-dormant-record>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.v22-dormant-record-head{position:sticky;top:0;z-index:2;
 background:#e9f1fa;padding:7px 12px;border-bottom:2px solid #a7c5dc}
.v22-dormant-sort{background:none;border:0;color:#23536c;padding:6px 0;
 text-align:left;white-space:nowrap;cursor:pointer;font-size:12px;font-weight:900}
.v22-dormant-sort.active{color:#a04e1f}
.v22-dormant-sort:hover{text-decoration:underline}
.v22-dormant-money{font-variant-numeric:tabular-nums;
 color:#1a8060;font-weight:900}
.v22-dormant-profit-positive{color:#168053;font-weight:900;font-variant-numeric:tabular-nums}
.v22-dormant-profit-negative{color:#c93535;font-weight:900;font-variant-numeric:tabular-nums}
.v22-dormant-profit-zero{color:#4e6270;font-weight:700;font-variant-numeric:tabular-nums}
.v22-dormant-footer{display:flex;justify-content:center;align-items:center;
 gap:14px;padding:9px 12px;border-top:1px solid #e0e6ec;flex-shrink:0}
.v22-dormant-footer button{border:1px solid #97b7cb;border-radius:7px;
 background:#f4f9fc;color:#175276;padding:7px 12px;cursor:pointer}
.v22-dormant-footer button:disabled{opacity:.45;cursor:not-allowed}
.v22-dormant-total{display:flex;align-items:center;flex-wrap:wrap;gap:10px;
 padding:10px 14px;border-top:1px solid #d2e0eb;background:#f4f9fc;
 font-size:12px;flex-shrink:0;max-height:105px;overflow:auto}
.v22-dormant-total>strong{color:#98501f;font-size:14px}
.v22-dormant-total>span{padding:3px 7px;border-radius:6px;
 background:#fff;border:1px solid #dbe7ed}
.v22-dormant-explain{margin:0;padding:8px 14px;background:#fff7e8;
 color:#755c36;font-size:11px;line-height:1.5;flex-shrink:0}
@media(max-width:760px){
 .v22-dormant-overlay{padding:4px}
 .v22-dormant-panel{height:calc(100dvh - 8px);max-height:none;border-radius:6px}
 .v22-dormant-head{padding:9px}
 .v22-dormant-record{padding:8px}
}
</style>
'''
assert h.count("</body>")==1
h=h.replace("</body>",css+"</body>",1)
assert s.count("function v22DormantAnalyze(")==1
assert s.count("v22-dormant-trigger")==1
js.write_text(s,encoding="utf-8")
html.write_text(h,encoding="utf-8")
print("PASS: V22 3-month dormant roster, 5 SAN root exclusions, descendant A-tier rebasing, personal win/loss")
