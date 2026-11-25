"""Read-only V22 follow-up roster.

Eligibility: joined on or after 2026-08-01, age STRICTLY more than 60
calendar days, and zero valid direct referrals since joining.
Works with the pre-existing unified Alt+Q toolbar after dormant/loan patches.
This never updates member data, finances, historical records or server APIs.
"""
from pathlib import Path
js=Path('member-tree/static/app.js')
style=Path('member-tree/static/style.css')
s=js.read_text(encoding='utf-8')
css=style.read_text(encoding='utf-8')
def once(original,replacement):
 global s
 n=s.count(original)
 assert n==1,('follow-up anchor changed',n,original[:150])
 s=s.replace(original,replacement,1)

helper=r'''
// Follow-up list, members joined since Aug 2026 who have NOT directly referred anyone after 60 full days.
let v22FollowPanel=null,v22FollowRows=[];
let v22FollowGroup='',v22FollowKeyword='',v22FollowPage=0,v22FollowSort='days',v22FollowDesc=true;
const V22_FOLLOW_EPOCH='2026-08-01',V22_FOLLOW_MIN_DAYS=60,V22_FOLLOW_PAGE_SIZE=100;
function v22FollowDays(join,today){
 const a=v22DormantDate(join),b=v22DormantDate(today);
 return a&&b&&b>=a?Math.floor((b-a)/86400000):null;
}
function v22FollowAnalyze(rows,today){
 if(!v22DormantDate(today))return [];
 const byId=new Map(rows.map(x=>[x.id,x]));
 const direct=new Map();
 for(const m of rows){
  if(!m||m.deleted||String(m.remark||'')==='上级占位（待补资料）')continue;
  if(!m.parent_id||!byId.has(m.parent_id)||m.parent_id===m.id)continue;
  direct.set(m.parent_id,(direct.get(m.parent_id)||0)+1);
 }
 const assignedGroup=m=>{
  const own=String(m.group_account||'').trim();
  if(own)return own;
  let cur=m,seen=new Set([m.id]);
  while(cur.parent_id&&byId.has(cur.parent_id)&&!seen.has(cur.parent_id)){
   cur=byId.get(cur.parent_id);seen.add(cur.id);
  }
  return String(cur.account||'未分组');
 };
 return rows.flatMap(m=>{
  if(!m||m.deleted||String(m.remark||'')==='上级占位（待补资料）')return [];
  if(V22_DORMANT_EXCLUDED_ACCOUNTS.has(v22DormantAccountKey(m.account)))return [];
  const joined=String(m.joined_on||'').slice(0,10);
  if(joined<V22_FOLLOW_EPOCH||!v22DormantDate(joined))return [];
  const days=v22FollowDays(joined,today);
  if(days===null||days<=V22_FOLLOW_MIN_DAYS)return [];
  if((direct.get(m.id)||0)!==0)return [];
  const tier=v22DormantDisplayLevel(m,byId);
  if(tier==='总节点')return [];
  return [{
   id:m.id,account:String(m.account||''),remark:String(m.remark||'').trim()||'未填写备注',
   group:assignedGroup(m),level:tier,joined,days,direct_count:0,
   balance_cents:Number(m.balance_cents||0),
   net_win_cents:Number(m.stake_cents||0)-Number(m.total_withdraw_cents||0),
   member:m
  }];
 });
}
function v22FollowClose(){
 if(!v22FollowPanel)return;
 v22FollowPanel.overlay.remove();v22FollowPanel=null;
 document.body.classList.remove('v22-follow-body-open');
}
function v22FollowSorted(rows){
 const field=v22FollowSort,sign=v22FollowDesc?-1:1;
 return rows.slice().sort((a,b)=>{
  const x=a[field],y=b[field];
  const cmp=typeof x==='number'?x-y:String(x).localeCompare(String(y),'zh-CN',{numeric:true});
  return (cmp||a.account.localeCompare(b.account,'zh-CN',{numeric:true}))*sign;
 });
}
function v22FollowRender(){
 const ui=v22FollowPanel;if(!ui)return;
 const allGroups=[...new Set([...TREE_GROUPS,
  ...members.map(x=>String(x.group_account||'').trim()),...v22FollowRows.map(x=>x.group)]
  .filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN',{numeric:true}));
 const active=ui.group.value||v22FollowGroup;
 ui.group.replaceChildren();
 const all=mk('option','','全部分组');all.value='';ui.group.append(all);
 for(const value of allGroups){const o=mk('option','',value);o.value=value;ui.group.append(o)}
 v22FollowGroup=allGroups.includes(active)?active:'';
 ui.group.value=v22FollowGroup;
 const kw=String(v22FollowKeyword||'').trim().toLocaleLowerCase();
 const matching=v22FollowRows.filter(r=>
   (!v22FollowGroup||r.group===v22FollowGroup)&&
   (!kw||r.account.toLocaleLowerCase().includes(kw)||r.remark.toLocaleLowerCase().includes(kw)));
 const rows=v22FollowSorted(matching);
 const sum=matching.reduce((v,r)=>v+r.balance_cents,0);
 const profit=matching.reduce((v,r)=>v+r.net_win_cents,0);
 const groups=new Set(matching.map(x=>x.group));
 ui.heading.textContent='跟进名单 · '+matching.length+' 人';
 ui.summary.textContent='符合条件 '+matching.length+' 人　｜　余额合计 '+money(sum,true)+
  '　｜　本人输赢合计 '+(profit>0?'+':'')+money(profit,true)+'　｜　涉及分组 '+groups.size+' 个';
 const max=Math.max(0,Math.ceil(rows.length/V22_FOLLOW_PAGE_SIZE)-1);
 v22FollowPage=Math.min(v22FollowPage,max);
 ui.table.replaceChildren();
 const cols=[['group','所属分组'],['remark','会员备注'],['account','会员账号'],
  ['level','层级'],['joined','加入日期'],['days','未裂变天数'],
  ['direct_count','直属裂变人数'],['balance_cents','当前余额'],['net_win_cents','本人输赢']];
 const th=mk('div','v22-follow-row v22-follow-header');
 for(const [key,label] of cols){
  const current=v22FollowSort===key;
  const b=mk('button','v22-follow-sort'+(current?' active':''),label+(current?(v22FollowDesc?' ↓':' ↑'):' ↕'));
  b.type='button';
  b.onclick=()=>{
   if(v22FollowSort===key)v22FollowDesc=!v22FollowDesc;
   else{v22FollowSort=key;v22FollowDesc=['days','balance_cents','net_win_cents'].includes(key)}
   v22FollowPage=0;v22FollowRender();
  };
  th.append(b);
 }
 ui.table.append(th);
 const page=rows.slice(v22FollowPage*V22_FOLLOW_PAGE_SIZE,(v22FollowPage+1)*V22_FOLLOW_PAGE_SIZE);
 for(const r of page){
  const tr=mk('div','v22-follow-row');
  const vals=[r.group,r.remark,r.account,r.level,r.joined,r.days+' 天',
   String(r.direct_count),money(r.balance_cents,true),(r.net_win_cents>0?'+':'')+money(r.net_win_cents,true)];
  vals.forEach((v,i)=>{
   const cls=i===7?'v22-follow-balance':i===8?
    r.net_win_cents>0?'v22-follow-positive':r.net_win_cents<0?'v22-follow-negative':'':'';
   const cell=mk('span',cls,String(v));cell.title=String(v);tr.append(cell);
  });
  ui.table.append(tr);
 }
 if(!page.length)ui.table.append(mk('p','v22-follow-empty','当前分组暂无符合条件的会员'));
 const groupStats=new Map();
 for(const x of matching){
  const row=groupStats.get(x.group)||{count:0,balance:0};
  row.count++;row.balance+=x.balance_cents;groupStats.set(x.group,row);
 }
 ui.total.replaceChildren();
 ui.total.append(mk('strong','','总体结算：'+matching.length+' 人 / 余额 '+money(sum,true)));
 for(const [group,data] of [...groupStats].sort((a,b)=>a[0].localeCompare(b[0],'zh-CN',{numeric:true})))
  ui.total.append(mk('span','',group+'：'+data.count+'人 / '+money(data.balance,true)));
 ui.footer.replaceChildren();
 const prev=mk('button','','◀ 上一页');prev.type='button';prev.disabled=v22FollowPage<=0;
 prev.onclick=()=>{v22FollowPage--;v22FollowRender()};
 const count=mk('span','','第 '+(v22FollowPage+1)+' / '+(max+1)+' 页 · 共 '+rows.length+' 人');
 const next=mk('button','','下一页 ▶');next.type='button';next.disabled=v22FollowPage>=max;
 next.onclick=()=>{v22FollowPage++;v22FollowRender()};
 ui.footer.append(prev,count,next);
 ui.explain.textContent='口径：2026年8月1日及以后加入，至统计当天入会已超过60天，且目前没有任何有效直属下级的会员进入跟进名单；60天当天不计入。历史成员、占位节点及五个SAN组长不计入。余额为当前余额；名单仅用于人工跟进，不自动修改任何会员数据。';
}
function v22FollowOpen(){
 if(v22HistMaximized)v22HistSetMaximized(false);
 if(v22DormantPanel)v22DormantClose();
 if(v22LoanPanel)v22LoanClose();
 v22FollowClose();
 v22FollowRows=v22FollowAnalyze(members,v22HistToday());
 v22FollowGroup=selectedTreeGroup||'';
 v22FollowKeyword='';v22FollowPage=0;v22FollowSort='days';v22FollowDesc=true;
 const overlay=mk('div','v22-follow-overlay');
 overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');
 overlay.setAttribute('aria-label','60天未裂变跟进名单');
 const panel=mk('section','v22-follow-panel');
 const header=mk('div','v22-follow-head');
 const heading=mk('h3','','跟进名单');
 const close=mk('button','v22-follow-close','✕ 关闭');close.type='button';
 close.onclick=v22FollowClose;header.append(heading,close);
 const filters=mk('div','v22-follow-filters');
 const label=mk('label','','选择分组：');
 const group=mk('select','v22-follow-group');group.setAttribute('aria-label','选择跟进名单分组');
 group.onchange=()=>{v22FollowGroup=group.value;v22FollowPage=0;v22FollowRender()};
 label.append(group);
 const keyword=mk('input','v22-follow-keyword');keyword.placeholder='搜索会员账号或备注';
 keyword.setAttribute('aria-label','搜索跟进会员账号或备注');
 keyword.oninput=()=>{v22FollowKeyword=keyword.value;v22FollowPage=0;v22FollowRender()};
 const summary=mk('strong','v22-follow-summary');
 filters.append(label,keyword,summary);
 const scroll=mk('div','v22-follow-scroll');
 const table=mk('div','v22-follow-table');scroll.append(table);
 const footer=mk('div','v22-follow-footer');
 const total=mk('div','v22-follow-total');
 const explain=mk('p','v22-follow-explain');
 panel.append(header,filters,scroll,footer,total,explain);overlay.append(panel);
 overlay.addEventListener('click',e=>{if(e.target===overlay)v22FollowClose()});
 overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();v22FollowClose()}});
 document.body.append(overlay);document.body.classList.add('v22-follow-body-open');
 v22FollowPanel={overlay,heading,group,keyword,summary,table,footer,total,explain};
 v22FollowRender();close.focus();
}
'''
once("function v22HistUpdateToolbar(){",helper+"\nfunction v22HistUpdateToolbar(){")
once("  loan.type='button';loan.onclick=v22LoanOpen;",
     "  loan.type='button';loan.onclick=v22LoanOpen;\n  const follow=mk('button','v22-hist-button v22-follow-trigger','📌 跟进名单');\n  follow.type='button';follow.onclick=v22FollowOpen;")
once("b.append(label,newer,withdraw,week,month,dormant,loan,prev,pick,next,yesterday,today,info,details,note);",
     "b.append(label,newer,withdraw,week,month,dormant,loan,follow,prev,pick,next,yesterday,today,info,details,note);")
# No mutation to database, render paths or core financial logic.
assert s.count('function v22FollowAnalyze(')==1
css+=r'''
/* V22 follow-up review only. The button lives inside unified Alt+Q dock. */
.v22-follow-trigger{color:#705219!important;border-color:#ceb687!important;background:#fff6df!important;font-weight:850!important}
.v22-follow-body-open{overflow:hidden!important}
.v22-follow-overlay{position:fixed!important;inset:0!important;z-index:2147483643!important;
 background:#081d35bb;display:flex;align-items:center;justify-content:center;padding:12px;box-sizing:border-box}
.v22-follow-panel{display:flex;flex-direction:column;width:min(1360px,100%);height:min(91dvh,940px);
 min-height:0;overflow:hidden;border-radius:12px;background:#fff;color:#263c4b;
 box-shadow:0 20px 55px #06284670}
.v22-follow-head{display:flex;justify-content:space-between;align-items:center;
 background:#fff6e6;border-bottom:1px solid #ead6ae;padding:11px 17px}
.v22-follow-head h3{margin:0;font-size:19px;color:#7c561b}
.v22-follow-close,.v22-follow-footer button{padding:7px 11px;border:1px solid #cfbfa4;
 border-radius:7px;background:#fff;color:#654b24;cursor:pointer}
.v22-follow-filters{display:flex;flex-wrap:wrap;gap:13px;align-items:center;
 border-bottom:1px solid #eee5d2;padding:10px 16px;background:#fcfbf7}
.v22-follow-filters label{display:flex;gap:8px;align-items:center;font-size:13px;font-weight:750}
.v22-follow-filters select,.v22-follow-keyword{border:1px solid #cdb78c;
 padding:7px 9px;border-radius:7px;color:#384f62;background:#fff}
.v22-follow-keyword{width:210px}
.v22-follow-summary{font-size:12px;color:#995922}
.v22-follow-scroll{min-height:90px;flex:1 1 0;overflow:auto;margin:0 14px;
 scrollbar-color:#c5a06e #faf3e9;scrollbar-width:auto}
.v22-follow-table{min-width:1060px}
.v22-follow-row{display:grid;grid-template-columns:minmax(80px,.8fr) minmax(115px,1.25fr)
 minmax(100px,1fr) minmax(65px,.55fr) minmax(100px,.95fr) minmax(100px,1fr)
 minmax(100px,1fr) minmax(125px,1.15fr) minmax(120px,1fr);
 align-items:center;gap:8px;padding:9px 10px;border-bottom:1px solid #e6edf1;font-size:12px}
.v22-follow-row:nth-child(even){background:#fafcfd}
.v22-follow-row>span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.v22-follow-header{background:#f3ead8;position:sticky;top:0;z-index:2;border-bottom:2px solid #dec9a0}
.v22-follow-sort{background:transparent;border:0;cursor:pointer;color:#6f5322;text-align:left;
 font-weight:850;font-size:12px;white-space:nowrap}
.v22-follow-sort.active{color:#b56c18}
.v22-follow-balance,.v22-follow-positive{font-weight:850;color:#138158}
.v22-follow-negative{font-weight:850;color:#c93434}
.v22-follow-footer{display:flex;align-items:center;justify-content:center;gap:12px;
 padding:9px;border-top:1px solid #e5d9c9}
.v22-follow-footer button:disabled{opacity:.42;cursor:default}
.v22-follow-total{display:flex;flex-wrap:wrap;align-items:center;gap:9px;
 padding:10px 14px;background:#fdf9f2;border-top:1px solid #e8dac1;font-size:12px;
 max-height:95px;overflow:auto}
.v22-follow-total strong{color:#88571d}
.v22-follow-total span{padding:3px 6px;border-radius:5px;border:1px solid #e5d8bf}
.v22-follow-explain{margin:0;padding:8px 14px;font-size:11px;line-height:1.6;
 color:#795e35;background:#fff7e9}
.v22-follow-empty{padding:24px;color:#7d7367;text-align:center}
@media(max-width:680px){
 .v22-follow-overlay{padding:4px}
 .v22-follow-panel{height:calc(100dvh - 8px);border-radius:5px}
 .v22-follow-filters{gap:6px;padding:8px}
 .v22-follow-keyword{width:160px}
}
'''
js.write_text(s,encoding='utf-8')
style.write_text(css,encoding='utf-8')
print('PASS: V22 follow-up cohort from 2026-08-01, >60 days, 0 direct referrals, grouped searchable paginated list')
