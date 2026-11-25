"""V22 week/month read-only withdrawal-day overview UI.
1 day red, 2-3 days amber, 4+ days purple, with account-level day counts.
"""
from pathlib import Path
jpath=Path('member-tree/static/app.js')
hpath=Path('member-tree/static/index.html')
j=jpath.read_text(encoding='utf-8')
h=hpath.read_text(encoding='utf-8')
def once(old,new):
    global j
    n=j.count(old)
    assert n==1,(n,old[:160])
    j=j.replace(old,new,1)

anchor="function v22HistSelected(){return v22HistDay||v22HistToday()}"
extra=r'''
function v22HistIsOverview(){return v22HistMode==='week'||v22HistMode==='month'}
function v22HistIsWithdrawMode(){return v22HistMode!=='new'}
function v22HistFrequency(){
 if(!v22HistIsOverview()||!v22HistResult?.recorded||
    v22HistResult.day!==v22HistSelected())return new Map();
 return new Map((v22HistResult.members||[]).map(x=>[x.id,x]));
}
function v22HistStep(day,dir){
 if(v22HistMode==='week')return v22HistShift(day,dir*7);
 if(v22HistMode==='month'){
  if(!v22HistShift(day,0))return null;
  const [y,m]=day.split('-').map(Number);
  return new Date(Date.UTC(y,m-1+dir,1)).toISOString().slice(0,10);
 }
 return v22HistShift(day,dir);
}
'''
once(anchor,anchor+"\n"+extra)
once("if(v22HistMode!=='withdraw'||!v22HistResult||",
     "if(!v22HistIsWithdrawMode()||!v22HistResult||")
once("return rows.filter(x=>Number(amounts.get(x.id)||0)!==0);",
     "return rows.filter(x=>v22HistIsOverview()?Number(amounts.get(x.id)||0)>0:Number(amounts.get(x.id)||0)!==0);")
once("if(!['new','withdraw'].includes(mode)||!v22HistShift(day,0))return;",
     "if(!['new','withdraw','week','month'].includes(mode)||!v22HistShift(day,0))return;")
once("const data=await api('/history/withdrawals?day='+encodeURIComponent(day));",
     """const path=v22HistIsOverview()
    ? '/history/withdrawals/overview?mode='+encodeURIComponent(mode)+'&day='+encodeURIComponent(day)
    : '/history/withdrawals?day='+encodeURIComponent(day);
  const data=await api(path);
  if(v22HistIsOverview()&&data.mode!==mode)throw Error('历史统计类型与请求不符');""")
once("b.setAttribute('aria-label','历史新增和提现日期日历');",
     "b.setAttribute('aria-label','历史新增、单日、本周和本月提现日历');")
once("const withdraw=mk('button','v22-hist-mode','🔴 历史提现');",
     """const withdraw=mk('button','v22-hist-mode','🔴 历史提现');
  const week=mk('button','v22-hist-mode','🟠 本周提现总览');
  const month=mk('button','v22-hist-mode','🟣 本月提现总览');
  week.dataset.mode='week';month.dataset.mode='month';""")
once("for(const button of [newer,withdraw,prev,next,yesterday,today])",
     "for(const button of [newer,withdraw,week,month,prev,next,yesterday,today])")
once("withdraw.onclick=()=>v22HistChange('withdraw',v22HistSelected());",
     """withdraw.onclick=()=>v22HistChange('withdraw',v22HistSelected());
  week.onclick=()=>v22HistChange('week',v22HistToday());
  month.onclick=()=>v22HistChange('month',v22HistToday());""")
once("prev.onclick=()=>v22HistChange(v22HistMode,v22HistShift(v22HistSelected(),-1));",
     "prev.onclick=()=>v22HistChange(v22HistMode,v22HistStep(v22HistSelected(),-1));")
once("next.onclick=()=>v22HistChange(v22HistMode,v22HistShift(v22HistSelected(),1));",
     "next.onclick=()=>v22HistChange(v22HistMode,v22HistStep(v22HistSelected(),1));")
once("b.append(label,newer,withdraw,prev,pick,next,yesterday,today,info,details,note);",
     "b.append(label,newer,withdraw,week,month,prev,pick,next,yesterday,today,info,details,note);")
once("v22HistToolbar={b,newer,withdraw,prev,pick,next,yesterday,today,info,details,list,note};",
     "v22HistToolbar={b,newer,withdraw,week,month,prev,pick,next,yesterday,today,info,details,list,note};")
once("t.prev.disabled=day<=earliest;t.next.disabled=day>=now;",
     """const before=v22HistStep(day,-1),after=v22HistStep(day,1);
 t.prev.disabled=!before||before<earliest;
 t.next.disabled=!after||after>now;""")
once("t.withdraw.classList.toggle('active',v22HistMode==='withdraw');",
     """t.withdraw.classList.toggle('active',v22HistMode==='withdraw');
 t.week.classList.toggle('active',v22HistMode==='week');
 t.month.classList.toggle('active',v22HistMode==='month');""")
once("t.withdraw.setAttribute('aria-pressed',String(v22HistMode==='withdraw'));",
     """t.withdraw.setAttribute('aria-pressed',String(v22HistMode==='withdraw'));
 t.week.setAttribute('aria-pressed',String(v22HistMode==='week'));
 t.month.setAttribute('aria-pressed',String(v22HistMode==='month'));""")
once("const matches=v22HistMatches(),amounts=v22HistAmounts();",
     "const matches=v22HistMatches(),amounts=v22HistAmounts(),frequency=v22HistFrequency();")
once("}else if(!v22HistResult?.recorded){\n  label='该日无已记录的提现数据';",
     """}else if(!v22HistResult?.recorded){
  label=v22HistIsOverview()?'该时间段无已记录的提现数据':'该日无已记录的提现数据';""")
once("}else{\n  label='提现记录 '+matches.length+' 人';\n  const returns=matches.filter",
     """}else if(v22HistIsOverview()){
  const period=v22HistMode==='week'?'本周':'本月';
  const repeat=matches.filter(x=>Number(frequency.get(x.id)?.days||0)>=2).length;
  const totalMoney=matches.reduce((sum,x)=>sum+Number(frequency.get(x.id)?.amount_cents||0),0);
  label=period+'提现 '+matches.length+' 人 · 重复 '+repeat+' 人 · 合计 '+money(totalMoney,true);
  note='红圈=1天 · 橙圈=2—3天 · 紫圈=4天以上 ｜ 已记录 '+
    v22HistResult.recorded_days+'/'+v22HistResult.expected_days+' 天'+
    (v22HistResult.missing_days?'，缺少 '+v22HistResult.missing_days+' 天':'，覆盖完整')+
    '；按不同提现日期计数';
 }else{
  label='提现记录 '+matches.length+' 人';
  const returns=matches.filter""")
once("const val=v22HistMode==='withdraw'?' · '+money(amounts.get(x.id)||0,true):'';",
     """const detail=frequency.get(x.id);
  const val=v22HistIsOverview()&&detail
   ? ' · '+detail.days+'天 · '+money(detail.amount_cents,true)
   : v22HistMode==='withdraw'?' · '+money(amounts.get(x.id)||0,true):'';""")
# Never overlay today's live rings in historical weekly/monthly modes.
old="withdrawGlowOn&&v22HistMode!=='withdraw'&&Number(m.daily_withdraw_cents||0)!==0"
assert j.count(old)==2,('Daily SVG marker count changed',j.count(old))
j=j.replace(old,"withdrawGlowOn&&v22HistMode==='new'&&Number(m.daily_withdraw_cents||0)!==0")
once("if(v22HistMode!=='withdraw'){","if(v22HistMode==='new'){")
once("const ownWithdraw=Number(x.daily_withdraw_cents||0),glow=withdrawGlowOn&&v22HistMode!=='withdraw'&&ownWithdraw!==0;",
     "const ownWithdraw=Number(x.daily_withdraw_cents||0),glow=withdrawGlowOn&&v22HistMode==='new'&&ownWithdraw!==0;")
once("const historyMatchIds=new Set(v22HistMatches().map(x=>x.id));",
     """const historyMatchIds=new Set(v22HistMatches().map(x=>x.id));
  const historyFrequency=v22HistFrequency();""")
once("group.classList.add(joined?'v22-hist-new':'v22-hist-withdraw');",
     """group.classList.add(joined?'v22-hist-new':'v22-hist-withdraw');
    const detail=historyFrequency.get(m.id);
    if(detail)group.classList.add('v22-hist-frequency-'+detail.tier);""")
once("    group.append(outer,mid,inner);",
     """    group.append(outer,mid,inner);
    if(detail){
     const badge=svgEl('g',{class:'v22-hist-count-badge',
       transform:'translate('+Math.max(0,cardW-65)+',-13)'});
     badge.append(svgEl('rect',{x:0,y:0,width:65,height:27,rx:11,
       class:'v22-hist-count-badge-bg v22-hist-count-bg-'+detail.tier}));
     badge.append(svgEl('text',{x:32,y:18,'text-anchor':'middle',
       class:'v22-hist-count-label'},String(detail.days)+'天'));
     group.append(badge);
    }""")
once("group.append(svgEl('title',{},v22HistSelected()+\n     (joined?' 新增会员 ':' 历史提现 ')+m.account));",
     """group.append(svgEl('title',{},v22HistSelected()+
     (joined?' 新增会员 ':' 历史提现 ')+m.account+
     (detail?' · '+detail.days+'天提现 · 累计 '+money(detail.amount_cents,true):'')));""")
once("const red=shownRows.filter(x=>v22HistMode==='withdraw'",
     "const red=shownRows.filter(x=>v22HistIsWithdrawMode()")
once("amount:v22HistMode==='withdraw'?Number(historyAmounts.get(x.id)||0):Number(x.daily_withdraw_cents||0)",
     "amount:v22HistIsWithdrawMode()?Number(historyAmounts.get(x.id)||0):Number(x.daily_withdraw_cents||0)")
once("const highlights=new Set(v22HistMatches().map(x=>x.id));",
     """const highlights=new Set(v22HistMatches().map(x=>x.id));
  const frequency=v22HistFrequency();""")
once("card.classList.toggle('v22-hist-withdraw',yes&&v22HistMode==='withdraw');",
     """card.classList.toggle('v22-hist-withdraw',yes&&v22HistIsWithdrawMode());
   const detail=frequency.get(card.dataset.memberId);
   for(const tier of ['low','mid','high'])
    card.classList.toggle('v22-hist-frequency-'+tier,yes&&detail?.tier===tier);
   if(detail)card.dataset.v22HistDays=String(detail.days);
   else delete card.dataset.v22HistDays;""")
css=r'''
<style id="v22-withdraw-frequency-css">
.v22-hist-mode[data-mode="week"].active{background:#ffe0ab!important;color:#743800!important;border-color:#ee9c21!important}
.v22-hist-mode[data-mode="month"].active{background:#e4cdff!important;color:#582392!important;border-color:#9d56ec!important}
.branch-node.v22-hist-frequency-mid .v22-hist-ring-crimson,
.branch-node.v22-hist-frequency-mid .v22-hist-ring-red,
.branch-node.v22-hist-frequency-mid .v22-hist-ring-pink{
 stroke:#ff9b15!important;filter:drop-shadow(0 0 12px #ffae16)!important}
.branch-node.v22-hist-frequency-mid .v22-hist-ring-red{stroke:#ffed6d!important}
.branch-node.v22-hist-frequency-high .v22-hist-ring-crimson,
.branch-node.v22-hist-frequency-high .v22-hist-ring-red,
.branch-node.v22-hist-frequency-high .v22-hist-ring-pink{
 stroke:#a54aff!important;filter:drop-shadow(0 0 13px #b56bff)!important}
.branch-node.v22-hist-frequency-high .v22-hist-ring-red{stroke:#f2baff!important}
.v22-hist-count-badge{pointer-events:none}
.v22-hist-count-badge-bg{stroke:white;stroke-width:2;fill:#d7183d}
.v22-hist-count-bg-mid{fill:#ed850a}
.v22-hist-count-bg-high{fill:#8945e6}
.v22-hist-count-label{fill:#fff;font-size:18px;font-weight:900;paint-order:stroke;stroke:#2a243540;stroke-width:.5px}
.member.v22-hist-withdraw.v22-hist-frequency-mid{
 outline-color:#f99f18!important;box-shadow:0 0 0 10px #f3a51eaa,0 0 25px 9px #ffb743c9!important}
.member.v22-hist-withdraw.v22-hist-frequency-high{
 outline-color:#a34fff!important;box-shadow:0 0 0 10px #ad59fcaa,0 0 25px 9px #c289ffc9!important}
.member.v22-hist-withdraw.v22-hist-frequency-mid::after{
 border-color:#ffad22!important;box-shadow:0 0 22px 8px #ffb940!important}
.member.v22-hist-withdraw.v22-hist-frequency-high::after{
 border-color:#ac4bff!important;box-shadow:0 0 24px 8px #b068ff!important}
.member.v22-hist-withdraw.v22-hist-frequency-low::before,
.member.v22-hist-withdraw.v22-hist-frequency-mid::before,
.member.v22-hist-withdraw.v22-hist-frequency-high::before{
 content:attr(data-v22-hist-days) "天提现"!important;color:#201127}
.member.v22-hist-withdraw.v22-hist-frequency-mid::before{background:#ffd28a!important}
.member.v22-hist-withdraw.v22-hist-frequency-high::before{background:#e4bdff!important}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count('function v22HistIsOverview(')==1
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print('PASS: V22 week/month overview controls, 1/2-3/4+ frequency colors, counts and coverage UI')
