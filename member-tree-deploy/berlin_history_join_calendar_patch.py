"""Berlin browser-only historical join-day calendar, day-by-day navigation and rings.

Overlay supports both standard member tree and branch SVG. It uses the existing
member.joined_on value and never changes transaction snapshots, accounts, roles
or database schemas. Existing red withdrawal rings remain independent.
"""
from pathlib import Path
helper=r"""
// Highlight members whose stored joining date matches the selected calendar day.
// This does not restore an old balance; it is an audit view of CURRENT member
// records filtered by joined_on (which managers may subsequently edit).
let berlinHistorySelectedDay=dateNow();
let berlinHistoryToolbar=null,berlinHistoryBranchController=null;
const berlinHistoryPlaceholder='上级占位（待补资料）';
function berlinHistoryDateShift(value,days){
 const match=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value||''));
 if(!match)return null;
 const date=new Date(Date.UTC(+match[1],+match[2]-1,+match[3]));
 if(date.toISOString().slice(0,10)!==value)return null;
 date.setUTCDate(date.getUTCDate()+days);
 return date.toISOString().slice(0,10);
}
function berlinHistoryRows(){
 if(view==='branch'&&teamFocusId)return teamExportRows(teamFocusId);
 return shownTreeMembers();
}
function berlinHistoryMatches(day=berlinHistorySelectedDay){
 return berlinHistoryRows().filter(m=>String(m.joined_on||'').slice(0,10)===day&&
   String(m.remark||'')!==berlinHistoryPlaceholder);
}
function berlinHistoryExpandAncestors(targetIds,closedSet){
 const byId=new Map(members.map(m=>[m.id,m]));
 for(const id of targetIds){
  let node=byId.get(id),count=0;
  while(node&&node.parent_id&&count++<members.length){
   closedSet.delete(node.parent_id);
   node=byId.get(node.parent_id);
  }
 }
}
function berlinHistoryScrollTree(id){
 if(!id)return;
 requestAnimationFrame(()=>{
  const card=[...document.querySelectorAll('.member[data-member-id]')]
     .find(x=>x.dataset.memberId===id);
  if(card)card.scrollIntoView({behavior:'smooth',block:'center',inline:'center'});
 });
}
function berlinHistoryFocusMember(member){
 if(!member)return;
 if(view==='branch'&&berlinHistoryBranchController){
  berlinHistoryBranchController.revealAndDraw(member.id);
 }else if(view==='tree'){
  berlinHistoryExpandAncestors([member.id],collapsed);
  render();
  berlinHistoryScrollTree(member.id);
 }
}
function berlinHistorySwitchDate(next){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(next)||!berlinHistoryDateShift(next,0))return;
 const today=dateNow(),oldest=members.map(m=>String(m.joined_on||'').slice(0,10))
   .filter(s=>/^\d{4}-\d{2}-\d{2}$/.test(s)).sort()[0]||today;
 if(next>today||next<oldest)return;
 berlinHistorySelectedDay=next;
 const hits=berlinHistoryMatches();
 if(view==='branch'&&berlinHistoryBranchController){
  berlinHistoryBranchController.revealAndDraw(hits[0]?.id||null);
  berlinHistoryEnsureControls();
 }else{
  if(view==='tree')berlinHistoryExpandAncestors(hits.map(x=>x.id),collapsed);
  render();
  if(view==='tree')berlinHistoryScrollTree(hits[0]?.id);
 }
}
function berlinHistoryEnsureControls(){
 const title=el('sectionTitle'),visible=view==='tree'||view==='branch';
 if(!title)return;
 if(!berlinHistoryToolbar){
  const bar=mk('div','berlin-history-toolbar');
  bar.id='berlinHistoryCalendar';
  bar.setAttribute('role','region');
  bar.setAttribute('aria-label','历史每天新增会员日历');
  const label=mk('strong','berlin-history-heading','📅 历史新增');
  const previous=mk('button','berlin-history-nav','◀ 前一天');
  previous.type='button';previous.title='查看前一天新增账号';
  previous.onclick=()=>berlinHistorySwitchDate(berlinHistoryDateShift(berlinHistorySelectedDay,-1));
  const date=mk('input','berlin-history-input');
  date.type='date';date.id='berlinHistoryDate';date.title='选择历史新增日期';
  date.setAttribute('aria-label','选择会员加入日期');
  date.onchange=()=>berlinHistorySwitchDate(date.value);
  const next=mk('button','berlin-history-nav','后一天 ▶');
  next.type='button';next.title='查看后一天新增账号';
  next.onclick=()=>berlinHistorySwitchDate(berlinHistoryDateShift(berlinHistorySelectedDay,1));
  const todayBtn=mk('button','berlin-history-nav','今天');
  todayBtn.type='button';todayBtn.onclick=()=>berlinHistorySwitchDate(dateNow());
  const count=mk('span','berlin-history-count');
  count.id='berlinHistoryCount';
  const details=mk('details','berlin-history-members');
  const summary=mk('summary','','查看当天新增账号');
  const accounts=mk('div','berlin-history-account-list');
  accounts.id='berlinHistoryAccounts';
  details.append(summary,accounts);
  const note=mk('span','berlin-history-note','按现存档案加入日期统计 · 蓝色光圈');
  bar.append(label,previous,date,next,todayBtn,count,details,note);
  berlinHistoryToolbar={bar,previous,date,next,todayBtn,count,details,accounts,note};
 }
 const controls=berlinHistoryToolbar;
 if(controls.bar.parentElement!==title.parentElement)
     title.parentElement.insertBefore(controls.bar,title.nextSibling);
 controls.bar.hidden=!visible;
 if(!visible)return;
 const today=dateNow();
 const current=berlinHistorySelectedDay;
 const oldest=members.map(m=>String(m.joined_on||'').slice(0,10))
   .filter(v=>/^\d{4}-\d{2}-\d{2}$/.test(v)).sort()[0]||today;
 controls.date.value=current;controls.date.min=oldest;controls.date.max=today;
 controls.previous.disabled=current<=oldest;
 controls.next.disabled=current>=today;
 controls.todayBtn.disabled=current===today;
 const matching=berlinHistoryMatches();
 controls.count.textContent='本日新增 '+matching.length+' 人';
 controls.details.hidden=!matching.length;
 controls.details.querySelector('summary').textContent='查看当天 '+matching.length+' 个账号';
 controls.accounts.replaceChildren();
 // All accounts remain ring-marked; the compact list avoids DOM overload on
 // dates with thousands of signups.
 for(const m of matching.slice(0,400)){
  const b=mk('button','berlin-history-account',m.account);
  b.type='button';b.title='定位：'+m.account;
  b.onclick=()=>berlinHistoryFocusMember(m);
  controls.accounts.append(b);
 }
 if(matching.length>400)
  controls.accounts.append(mk('span','berlin-history-list-more',
    '仅列前400个，其他账号也已在树状图用蓝圈标记'));
}
"""
anchor="function renderBranch(){"
assert j.count(anchor)==1
j=j.replace(anchor,helper+'\n'+anchor,1)
# A recycled SVG host must not remain registered as the current branch target.
anchor="function renderBranch(){\n if(berlinVisionCurrentStop){berlinVisionCurrentStop();berlinVisionCurrentStop=null;}"
assert j.count(anchor)==1
j=j.replace(anchor,anchor+"\n berlinHistoryBranchController=null;",1)

# The SVG's existing join-day highlight remains keyed to the live business day.
# The user-selected day gets an INDEPENDENT cyan ellipse, even alongside red rings.
anchor="   if(riskMode){const r=riskForMember(m);group.append(svgEl('title',{},"
assert j.count(anchor)==1
new=r"""   if(String(m.joined_on||'').slice(0,10)===berlinHistorySelectedDay&&
      String(m.remark||'')!==berlinHistoryPlaceholder){
    group.classList.add('berlin-history-new');
    group.append(svgEl('ellipse',{
      cx:cardW/2,cy:cardH/2,
      rx:compactMode?112:178,ry:compactMode?43:101,
      class:'berlin-history-svg-ring',
      fill:'none','aria-hidden':'true'
    }));
    group.append(svgEl('title',{},'历史新增 '+berlinHistorySelectedDay+'：'+m.account));
   }
"""
j=j.replace(anchor,new+anchor,1)

# The branch control shares the same layout cache, so changing the calendar
# re-renders just the SVG while retaining independent current-day withdrawals.
anchor=" // On-screen visual modes use the same virtualized SVG viewport, with no network writes."
assert j.count(anchor)==1
control=r""" berlinHistoryBranchController={
  revealAndDraw(memberId){
   if(berlinVisionMode==='auto')leaveVision();
   if(memberId)berlinHistoryExpandAncestors([memberId],branchClosed);
   const dayIds=shownRows.filter(m=>String(m.joined_on||'').slice(0,10)===berlinHistorySelectedDay&&
     String(m.remark||'')!==berlinHistoryPlaceholder).map(m=>m.id);
   berlinHistoryExpandAncestors(dayIds,branchClosed);
   berlinLayoutCache=null;
   if(memberId){
    const layout=getBerlinLayout(),p=layout.positions.get(memberId);
    if(p){
     const W=Math.max(300,host.clientWidth||1100);
     const H=Math.max(320,host.clientHeight||590);
     // Mid-level zoom gives adequate context around each highlighted signup.
     const zoom=Math.max(.42,Math.min(1.0,branchTransform.scale||.7));
     branchTransform.scale=zoom;
     branchTransform.dx=W/2-(p.x+(compactMode?76:130))*zoom;
     branchTransform.dy=H/2-p.y*zoom;
     branchViewportReady=true;branchResetRequested=false;
    }
   }
   draw();persistTabView();
  }
 };
"""
j=j.replace(anchor,control+anchor,1)
# Main tree has HTML member cards. Apply class after renderTree(); cards may
# already be collapsed, so the selected-day ancestor paths are expanded on date change.
anchor=" lastDisplayDay=businessDay||dateNow();"
assert j.count(anchor)==1
j=j.replace(anchor,''' if(view==='tree'){
  const selectedIds=new Set(berlinHistoryMatches().map(m=>m.id));
  for(const card of c.querySelectorAll('.member[data-member-id]'))
   card.classList.toggle('berlin-history-new',selectedIds.has(card.dataset.memberId));
 }
 berlinHistoryEnsureControls();
'''+anchor,1)
# Remove the persistent toolbar when logged out; hidden on all non-tree views.
anchor="function render(){\n if(view!=='branch'&&berlinVisionCurrentStop)"
assert j.count(anchor)==1
# No extra login side effects.
# Add a durable visual legend and contrast distinct from withdrawal rings.
css=r"""
<style id="berlin-history-calendar-css">
.berlin-history-toolbar[hidden],.berlin-history-members[hidden]{display:none!important}
.berlin-history-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:7px;
 border:1px solid #abcddd;border-radius:11px;padding:9px 10px;margin:6px 0 12px;
 background:#eff8ff;color:#143747;box-shadow:0 1px 5px #0e678615}
.berlin-history-heading{font-weight:800;font-size:13px;color:#075985}
.berlin-history-nav,.berlin-history-account{border:1px solid #afd3e6;background:white;
 border-radius:7px;color:#164e63;cursor:pointer;font-size:12px;padding:6px 9px}
.berlin-history-nav:hover,.berlin-history-account:hover{background:#d5f2ff}
.berlin-history-nav:disabled{opacity:.42;cursor:default}
.berlin-history-input{background:#fff;border:1px solid #8ab8d2;border-radius:7px;
 padding:5px 7px;color:#0e3c54;font-size:13px;width:150px;max-width:100%}
.berlin-history-count{font-size:13px;font-weight:800;color:#0a648c}
.berlin-history-members{position:relative}
.berlin-history-members summary{font-size:12px;color:#075985;cursor:pointer}
.berlin-history-account-list{position:absolute;z-index:48;right:0;top:100%;
 min-width:230px;width:min(420px,85vw);max-height:265px;overflow:auto;
 display:flex;flex-wrap:wrap;gap:5px;padding:9px;background:#fff;
 border:1px solid #8ab8d2;border-radius:9px;box-shadow:0 8px 24px #001e2852}
.berlin-history-list-more,.berlin-history-note{font-size:11px;color:#50788a}
.berlin-history-svg-ring{stroke:#19bdff;stroke-width:4.5;stroke-opacity:1;
 filter:drop-shadow(0 0 7px #02aaff);pointer-events:none;
 animation:berlin-history-ring-pulse 2s ease-in-out infinite}
.branch-node.berlin-history-new{isolation:isolate}
.member.berlin-history-new{position:relative;z-index:2}
.member.berlin-history-new::after{content:"";position:absolute;inset:-8px;
 border:3px solid #20b9f5;border-radius:32px;box-shadow:0 0 0 3px #76d9ff88,0 0 19px #18b0faaa;
 pointer-events:none;animation:berlin-history-ring-pulse 2s ease-in-out infinite}
@keyframes berlin-history-ring-pulse{
 0%,100%{stroke-opacity:.85;opacity:.8}
 50%{stroke-opacity:1;opacity:1}
}
@media(prefers-reduced-motion:reduce){
 .berlin-history-svg-ring,.member.berlin-history-new::after{animation:none}
}
@media(max-width:650px){
 .berlin-history-toolbar{padding:7px;gap:5px}
 .berlin-history-nav{padding:5px}
 .berlin-history-input{width:145px}
}
</style>
"""
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count('function berlinHistoryDateShift(')==1
assert j.count('berlinHistoryEnsureControls();')==2
assert j.count('berlin-history-svg-ring')==1
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print('PASS: Berlin history calendar UI integrated, view-only, branch SVG and main tree')
