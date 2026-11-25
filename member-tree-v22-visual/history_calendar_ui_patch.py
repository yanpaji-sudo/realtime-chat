"""V22 historical date browse with neon newcomer and recorded withdrawal rings.

Static UI only. Uses existing joined_on and GET /api/history/withdrawals.
No member or financial data updates; old daily-red rings preserved in new-member
mode and hidden in historical-withdraw mode to prevent date confusion.
"""
from pathlib import Path
p=Path('member-tree/static/app.js')
hp=Path('member-tree/static/index.html')
j=p.read_text(encoding='utf-8')
h=hp.read_text(encoding='utf-8')
def replace1(a,b):
    global j
    assert j.count(a)==1,('Expected exactly one JS anchor',a[:100],j.count(a))
    j=j.replace(a,b,1)

helper=r'''
let v22HistMode='new',v22HistDay=null,v22HistResult=null;
let v22HistLoading=false,v22HistError='',v22HistRequest=0;
let v22HistToolbar=null,v22HistBranch=null;
function v22HistToday(){return businessDay||dateNow()}
function v22HistSelected(){return v22HistDay||v22HistToday()}
function v22HistShift(day,delta){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(String(day||'')))return null;
 const d=new Date(day+'T00:00:00Z');
 if(!Number.isFinite(d.getTime())||d.toISOString().slice(0,10)!==day)return null;
 d.setUTCDate(d.getUTCDate()+delta);return d.toISOString().slice(0,10);
}
function v22HistOldest(){
 const dates=members.map(x=>String(x.joined_on||'').slice(0,10))
  .filter(x=>v22HistShift(x,0)!==null);
 if(historyCoverage&&v22HistShift(historyCoverage.tracking_since,0))
  dates.push(historyCoverage.tracking_since);
 return dates.length?dates.sort()[0]:v22HistToday();
}
function v22HistShown(){
 return view==='branch'&&teamFocusId?teamExportRows(teamFocusId):shownTreeMembers();
}
function v22HistAmounts(){
 if(v22HistMode!=='withdraw'||!v22HistResult||
    v22HistResult.day!==v22HistSelected()||!v22HistResult.recorded)return new Map();
 return new Map((v22HistResult.members||[]).map(x=>[x.id,Number(x.amount_cents||0)]));
}
function v22HistMatches(){
 const rows=v22HistShown();
 if(v22HistMode==='new'){
  return rows.filter(x=>String(x.joined_on||'').slice(0,10)===v22HistSelected()&&
   String(x.remark||'')!=='上级占位（待补资料）');
 }
 const amounts=v22HistAmounts();
 return rows.filter(x=>Number(amounts.get(x.id)||0)!==0);
}
function v22HistUnfold(ids,closed){
 const lookup=new Map(members.map(x=>[x.id,x]));
 for(const id of ids){
  let x=lookup.get(id),seen=new Set(),depth=0;
  while(x&&x.parent_id&&!seen.has(x.id)&&depth++<members.length){
   seen.add(x.id);closed.delete(x.parent_id);x=lookup.get(x.parent_id);
  }
 }
}
function v22HistFocus(id){
 if(!id)return;
 if(view==='branch'&&v22HistBranch){
  v22HistBranch.reveal(id);
 }else if(view==='tree'){
  v22HistUnfold([id],collapsed);render();
  requestAnimationFrame(()=>{
   const card=[...document.querySelectorAll('.member[data-member-id]')]
     .find(x=>x.dataset.memberId===id);
   card?.scrollIntoView({behavior:'smooth',block:'center',inline:'center'});
  });
 }
}
function v22HistApply(focus=true){
 const matches=v22HistMatches();
 if(view==='branch'&&v22HistBranch){
  v22HistBranch.reveal(focus?matches[0]?.id||null:null);
 }else if(view==='tree'){
  v22HistUnfold(matches.map(x=>x.id),collapsed);
  render();
  if(focus&&matches.length){
   requestAnimationFrame(()=>{
    const card=[...document.querySelectorAll('.member[data-member-id]')]
      .find(x=>x.dataset.memberId===matches[0].id);
    card?.scrollIntoView({behavior:'smooth',block:'center',inline:'center'});
   });
  }
 }
 v22HistUpdateToolbar();
}
async function v22HistChange(mode,day){
 if(!['new','withdraw'].includes(mode)||!v22HistShift(day,0))return;
 if(day<v22HistOldest()||day>v22HistToday())return;
 v22HistMode=mode;v22HistDay=day;
 const request=++v22HistRequest;
 v22HistResult=null;v22HistLoading=mode==='withdraw';v22HistError='';
 v22HistApply(false);
 if(mode==='new'){v22HistApply(true);return}
 try{
  const data=await api('/history/withdrawals?day='+encodeURIComponent(day));
  if(request!==v22HistRequest)return;
  if(data.day!==day)throw Error('历史日期不一致');
  v22HistResult=data;
 }catch(err){
  if(request!==v22HistRequest)return;
  v22HistError=err.message||'数据读取失败';
 }finally{
  if(request===v22HistRequest){
   v22HistLoading=false;v22HistApply(true);
  }
 }
}
function v22HistUpdateToolbar(){
 const container=el('content');
 if(!container)return;
 if(!v22HistToolbar){
  const b=mk('div','v22-hist-toolbar');
  b.id='v22HistoryCalendar';b.setAttribute('role','region');
  b.setAttribute('aria-label','历史新增和提现日期日历');
  const label=mk('strong','v22-hist-label','📅 历史查询');
  const newer=mk('button','v22-hist-mode','✨ 历史新增');
  const withdraw=mk('button','v22-hist-mode','🔴 历史提现');
  const prev=mk('button','v22-hist-button','◀ 前一天');
  const pick=mk('input','v22-hist-date');pick.type='date';
  pick.id='v22HistoryDate';pick.setAttribute('aria-label','选择历史日期');
  const next=mk('button','v22-hist-button','后一天 ▶');
  const yesterday=mk('button','v22-hist-button','昨天');
  const today=mk('button','v22-hist-button','今天');
  const info=mk('span','v22-hist-count');
  const details=mk('details','v22-hist-details');
  const summary=mk('summary','','查看账号');
  const list=mk('div','v22-hist-accounts');
  details.append(summary,list);
  const note=mk('span','v22-hist-note');
  for(const button of [newer,withdraw,prev,next,yesterday,today])
   button.type='button';
  newer.onclick=()=>v22HistChange('new',v22HistSelected());
  withdraw.onclick=()=>v22HistChange('withdraw',v22HistSelected());
  prev.onclick=()=>v22HistChange(v22HistMode,v22HistShift(v22HistSelected(),-1));
  next.onclick=()=>v22HistChange(v22HistMode,v22HistShift(v22HistSelected(),1));
  yesterday.onclick=()=>v22HistChange(v22HistMode,v22HistShift(v22HistToday(),-1));
  today.onclick=()=>v22HistChange(v22HistMode,v22HistToday());
  pick.onchange=()=>v22HistChange(v22HistMode,pick.value);
  b.append(label,newer,withdraw,prev,pick,next,yesterday,today,info,details,note);
  v22HistToolbar={b,newer,withdraw,prev,pick,next,yesterday,today,info,details,list,note};
 }
 const t=v22HistToolbar;
 if(container.parentElement&&t.b.parentElement!==container.parentElement)
  container.parentElement.insertBefore(t.b,container);
 const on=view==='tree'||view==='branch';
 t.b.hidden=!on;
 if(!on)return;
 const day=v22HistSelected(),now=v22HistToday(),earliest=v22HistOldest();
 t.pick.value=day;t.pick.max=now;t.pick.min=earliest;
 t.prev.disabled=day<=earliest;t.next.disabled=day>=now;
 t.yesterday.disabled=v22HistShift(now,-1)<earliest;
 t.today.disabled=day===now;
 t.newer.classList.toggle('active',v22HistMode==='new');
 t.withdraw.classList.toggle('active',v22HistMode==='withdraw');
 t.newer.setAttribute('aria-pressed',String(v22HistMode==='new'));
 t.withdraw.setAttribute('aria-pressed',String(v22HistMode==='withdraw'));
 const matches=v22HistMatches(),amounts=v22HistAmounts();
 let label='',note='';
 if(v22HistMode==='new'){
  label='新增 '+matches.length+' 人';
  note='黄蓝双层光圈＝该日新增；普通红圈仍为今日提现';
 }else if(v22HistLoading){
  label='正在读取 '+day+' 的提现…';note='按该日期查询历史提现台账';
 }else if(v22HistError){
  label='提现数据读取失败';note=v22HistError;
 }else if(!v22HistResult?.recorded){
  label='该日无已记录的提现数据';
  note='尚无该日上传记录，不能把今日提现算到昨日';
 }else{
  label='提现记录 '+matches.length+' 人';
  const returns=matches.filter(x=>Number(amounts.get(x.id)||0)<0).length;
  note='红色双层光圈＝该日提现流水'+(returns?'；含 '+returns+' 条负数回流':'');
 }
 t.info.textContent=label;t.note.textContent=note;
 t.details.hidden=!matches.length;
 t.details.querySelector('summary').textContent='查看 '+matches.length+' 个账号';
 t.list.replaceChildren();
 for(const x of matches.slice(0,400)){
  const val=v22HistMode==='withdraw'?' · '+money(amounts.get(x.id)||0,true):'';
  const btn=mk('button','v22-hist-account',x.account+val);
  btn.type='button';btn.onclick=()=>v22HistFocus(x.id);
  t.list.append(btn);
 }
 if(matches.length>400)t.list.append(mk('span','v22-hist-note','仅列出前400位；所有命中会员都已标记'));
}
'''
replace1("function renderBranch(){",helper+"\nfunction renderBranch(){")
replace1("function renderBranch(){\n if(v22VisionStop){v22VisionStop();v22VisionStop=null;}",
 "function renderBranch(){\n if(v22VisionStop){v22VisionStop();v22VisionStop=null;}\n v22HistBranch=null;")
# Suppress live-date withdrawal rings ONLY while inspecting another day's
# withdrawal records. New-member browsing keeps the original display.
old="withdrawGlowOn&&Number(m.daily_withdraw_cents||0)!==0"
assert j.count(old)==3,('red SVG live-day anchors changed',j.count(old))
j=j.replace(old,"withdrawGlowOn&&v22HistMode!=='withdraw'&&Number(m.daily_withdraw_cents||0)!==0")
replace1("const ownWithdraw=Number(x.daily_withdraw_cents||0),glow=withdrawGlowOn&&ownWithdraw!==0;",
 "const ownWithdraw=Number(x.daily_withdraw_cents||0),glow=withdrawGlowOn&&v22HistMode!=='withdraw'&&ownWithdraw!==0;")
# The viewport only draws visible nodes; selected rings have a non-scaling
# stroke so that the user's minimum-zoom view remains legible.
replace1("  const highlight=branchSelectedAccount,day=businessDay||dateNow();",
 """  const highlight=branchSelectedAccount,day=businessDay||dateNow();
  const historyMatchIds=new Set(v22HistMatches().map(x=>x.id));""")
ring=r'''   if(historyMatchIds.has(m.id)){
    const joined=v22HistMode==='new';
    group.classList.add(joined?'v22-hist-new':'v22-hist-withdraw');
    const cx=cardW/2,cy=cardH/2;
    const outer=svgEl('ellipse',{
      cx,cy,rx:compactMode?144:225,ry:compactMode?58:134,
      class:joined?'v22-hist-ring-gold':'v22-hist-ring-crimson',
      'vector-effect':'non-scaling-stroke',fill:'none','aria-hidden':'true'
    });
    const mid=svgEl('ellipse',{
      cx,cy,rx:compactMode?117:192,ry:compactMode?46:107,
      class:joined?'v22-hist-ring-yellow':'v22-hist-ring-red',
      'vector-effect':'non-scaling-stroke',fill:'none','aria-hidden':'true'
    });
    const inner=svgEl('ellipse',{
      cx,cy,rx:compactMode?99:166,ry:compactMode?38:90,
      class:joined?'v22-hist-ring-cyan':'v22-hist-ring-pink',
      'vector-effect':'non-scaling-stroke',fill:'none','aria-hidden':'true'
    });
    group.append(outer,mid,inner);
    group.append(svgEl('title',{},v22HistSelected()+
     (joined?' 新增会员 ':' 历史提现 ')+m.account));
   }
'''
replace1("   if(riskMode){const r=riskForMember(m);group.append(svgEl('title',{},",
 ring+"   if(riskMode){const r=riskForMember(m);group.append(svgEl('title',{},")
# Reveal affected member ancestors and focus the first recorded account.
control=r''' v22HistBranch={
  reveal(id=null){
   if(v22VisionMode==='auto')exitVision();
   const matches=v22HistMatches();
   v22HistUnfold(matches.map(x=>x.id),branchClosed);
   cachedLayout=null;
   if(id){
    const pos=getLayout().positions.get(id);
    if(pos){
     const W=Math.max(300,host.clientWidth||1000),
       H=Math.max(320,host.clientHeight||580);
     const zoom=Math.max(.4,Math.min(.95,branchTransform.scale||.7));
     branchTransform.scale=zoom;
     branchTransform.dx=W/2-(pos.x+(compactMode?76:130))*zoom;
     branchTransform.dy=H/2-pos.y*zoom;
     branchViewportReady=true;branchResetRequested=false;
    }
   }
   if(v22VisionMode==='density')startDensity();else draw();
  }
 };
'''
replace1(" // Mode controls are local to each SVG host; no mutations or API calls.",
 control+" // Mode controls are local to each SVG host; no mutations or API calls.")
# Existing burst-red density now ranks the SELECTED historical day when that
# mode is chosen; otherwise the original today algorithm remains unchanged.
replace1("const red=shownRows.filter(x=>Number(x.daily_withdraw_cents||0)!==0)",
 """const historyAmounts=v22HistAmounts();
  const red=shownRows.filter(x=>v22HistMode==='withdraw'
    ? Number(historyAmounts.get(x.id)||0)!==0
    : Number(x.daily_withdraw_cents||0)!==0)""")
replace1("return p?{x:p.x+(compactMode?76:130),y:p.y,amount:Number(x.daily_withdraw_cents||0)}:null",
 "return p?{x:p.x+(compactMode?76:130),y:p.y,amount:v22HistMode==='withdraw'?Number(historyAmounts.get(x.id)||0):Number(x.daily_withdraw_cents||0)}:null")
# On the main tree add an unmistakable border + label; date changes update
# existing tree without touching funds.
replace1(" lastDisplayDay=businessDay||dateNow();",r""" if(view==='tree'){
  const highlights=new Set(v22HistMatches().map(x=>x.id));
  for(const card of c.querySelectorAll('.member[data-member-id]')){
   const yes=highlights.has(card.dataset.memberId);
   card.classList.toggle('v22-hist-new',yes&&v22HistMode==='new');
   card.classList.toggle('v22-hist-withdraw',yes&&v22HistMode==='withdraw');
  }
 }
 v22HistUpdateToolbar();
 lastDisplayDay=businessDay||dateNow();""")
# If a prior historical date was selected in the other tree view, expand the
# necessary paths before the branch layout gets cached.
replace1(" const shownRows=teamFocusId?teamExportRows(teamFocusId):shownTreeMembers();\n // 10k+ nodes",
 """ const shownRows=teamFocusId?teamExportRows(teamFocusId):shownTreeMembers();
 v22HistUnfold(v22HistMatches().map(x=>x.id),branchClosed);
 // 10k+ nodes""")
css=r'''
<style id="v22-historical-browse-css">
.v22-hist-toolbar[hidden],.v22-hist-details[hidden]{display:none!important}
.v22-hist-toolbar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;width:100%;
 box-sizing:border-box;padding:9px 11px;margin:7px 0 13px;border-radius:12px;
 background:#eef8ff;color:#18465d;border:1px solid #9bcadd;
 box-shadow:0 2px 10px #0f526914}
.v22-hist-label{font-weight:900;font-size:13px;color:#145776}
.v22-hist-mode,.v22-hist-button,.v22-hist-account{border:1px solid #9bc6d9;
 border-radius:8px;background:#fff;color:#16455a;cursor:pointer;
 font-size:12px;padding:7px 9px}
.v22-hist-mode:hover,.v22-hist-button:hover{background:#d8f2ff}
.v22-hist-mode.active{background:#fff092;color:#53360b;
 border-color:#ecb62f;font-weight:900}
.v22-hist-mode.active:nth-of-type(2){background:#ffcbd2;color:#79132a;
 border-color:#ee465e}
.v22-hist-button:disabled{opacity:.42;cursor:default}
.v22-hist-date{width:149px;padding:6px 7px;border:1px solid #a1c7df;
 border-radius:8px;background:white;color:#183d52}
.v22-hist-count{background:#ffefa0;border:2px solid #e9ba36;
 border-radius:8px;font-size:13px;font-weight:900;padding:5px 8px}
.v22-hist-details{position:relative}
.v22-hist-details>summary{cursor:pointer;font-size:12px;color:#116180}
.v22-hist-accounts{position:absolute;top:100%;right:0;z-index:52;
 min-width:250px;width:min(440px,85vw);max-height:260px;overflow:auto;
 display:flex;flex-wrap:wrap;gap:5px;padding:10px;background:white;
 border:1px solid #a8c5d3;border-radius:9px;box-shadow:0 8px 26px #0a25394b}
.v22-hist-note{font-size:11px;color:#6b5c26}
.v22-hist-ring-gold{stroke:#ff9f00;stroke-width:11px;
 filter:drop-shadow(0 0 11px #ffa900);animation:v22-hist-flash 1.8s ease-in-out infinite}
.v22-hist-ring-yellow{stroke:#ffec00;stroke-width:8px;
 filter:drop-shadow(0 0 7px #fff76d)}
.v22-hist-ring-cyan{stroke:#15eaff;stroke-width:5px;
 filter:drop-shadow(0 0 6px #14eaff)}
.v22-hist-ring-crimson{stroke:#f51242;stroke-width:12px;
 filter:drop-shadow(0 0 11px #ff1238);animation:v22-hist-flash 1.8s ease-in-out infinite}
.v22-hist-ring-red{stroke:#ff3045;stroke-width:8px;
 filter:drop-shadow(0 0 8px #ff1e3e)}
.v22-hist-ring-pink{stroke:#ffc9d3;stroke-width:5px;
 filter:drop-shadow(0 0 5px #ff9daf)}
.v22-hist-ring-gold,.v22-hist-ring-yellow,.v22-hist-ring-cyan,
.v22-hist-ring-crimson,.v22-hist-ring-red,.v22-hist-ring-pink{pointer-events:none}
.member.v22-hist-new,.member.v22-hist-withdraw{
 position:relative;overflow:visible!important;z-index:5}
.member.v22-hist-new{outline:5px solid #ffea00!important;outline-offset:6px;
 box-shadow:0 0 0 9px #ffaf00bb,0 0 23px 8px #ffe500c0!important}
.member.v22-hist-withdraw{outline:5px solid #ff1645!important;outline-offset:6px;
 box-shadow:0 0 0 9px #fa2355a8,0 0 23px 8px #ff1239c0!important}
.member.v22-hist-new::after,.member.v22-hist-withdraw::after{
 content:"";position:absolute;inset:-13px;border-radius:27px;border:6px solid;
 pointer-events:none;animation:v22-hist-flash 1.8s ease-in-out infinite}
.member.v22-hist-new::after{border-color:#fff500;box-shadow:0 0 20px 6px #ffd500}
.member.v22-hist-withdraw::after{border-color:#ff1842;box-shadow:0 0 20px 6px #ff1842}
.member.v22-hist-new::before,.member.v22-hist-withdraw::before{
 position:absolute;top:-28px;right:-10px;z-index:10;
 padding:4px 10px;border:2px solid white;border-radius:99px;
 color:#1c2431;font-size:12px;font-weight:900;white-space:nowrap;
 pointer-events:none;box-shadow:0 3px 12px #1423318a}
.member.v22-hist-new::before{content:"✦ 历史新增";background:#fff000}
.member.v22-hist-withdraw::before{content:"🔴 历史提现";background:#ffb4c4}
@keyframes v22-hist-flash{0%,100%{opacity:1}50%{opacity:.65}}
@media(prefers-reduced-motion:reduce){
 .v22-hist-ring-gold,.v22-hist-ring-crimson,
 .member.v22-hist-new::after,.member.v22-hist-withdraw::after{
 animation:none!important;opacity:1!important}}
@media(max-width:650px){.v22-hist-toolbar{padding:6px;gap:4px}
 .v22-hist-mode,.v22-hist-button{padding:5px;font-size:11px}
 .v22-hist-date{width:142px}}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count('function v22HistShift(')==1
assert j.count("'vector-effect':'non-scaling-stroke'")==3
p.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print('PASS: V22 new member gold ring and historical red withdrawal ring integrated into both tree views')
