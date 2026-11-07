from pathlib import Path
root=Path('member-tree')
p=root/'static/app.js'
cssp=root/'static/style.css'
s=p.read_text(encoding='utf-8')
css=cssp.read_text(encoding='utf-8')
def swap(src,a,b,label):
    n=src.count(a)
    if n!=1:raise RuntimeError(label+' expected exactly one anchor, got '+str(n))
    return src.replace(a,b,1)

s=swap(s,"let positionAlarmOn=false;","let positionAlarmOn=false;\nlet positionAlarmById=null;",'persistent alert map')
beg=s.index('function v29Position(m){')
end=s.index('function togglePositionAlarm(){',beg)
new='''function v29Position(m){
 // V33 thresholds are in cents; status comes from the shared database.
 const stake=Number(m.stake_cents||0),direct=Number(m.direct_count||0);
 const trigger=stake===500000?750000:stake<=1000000?1500000:(direct>=5?2000000:1300000);
 const target=stake===500000?700000:stake<=1000000?1300000:trigger;
 const clear=stake===500000?750000:target;
 const balance=Number(m.balance_cents||0);
 const live=positionAlarmById&&positionAlarmById.get(m.id);
 const active=positionAlarmById!==null?Boolean(live):(Number.isFinite(balance)&&balance>trigger);
 const cents=live?Number(live.suggest_cents||0):Number.isFinite(balance)?Math.max(0,balance-target):0;
 return {active,cents,threshold:target,trigger,clear,
         started_on:live?.started_on||'',overdue_days:Number(live?.overdue_days||0),
         remaining_days:Number(live?.remaining_days||3)};
}
'''
s=s[:beg]+new+s[end:]
old="showToast(positionAlarmOn?'仓位告警已开启：5000仓位告警线7000；其他仓位按直属人数分档13000或20000':'仓位告警已关闭');"
new="showToast(positionAlarmOn?'仓位告警已开启：5000仓位余额超过7500、10000仓位超过15000显示光圈；余额达到解除线自动清除':'仓位告警已关闭');"
s=swap(s,old,new,'alert toast')
s=swap(s,'  suggest+=v29Position(x).cents;','  const warn=v29Position(x);if(warn.active)suggest+=warn.cents;','team suggestion active only')

panel='''// V33: compact left-column review queue, one line per active warning.
function v33AlertPanel(visibleRows){
 const box=mk('aside','v33-alarm-sidebar');
 box.setAttribute('role','region');
 box.setAttribute('aria-label','待处理仓位告警人员名单');
 const visible=new Set(visibleRows.map(x=>x.id));
 const ranked=members.filter(x=>visible.has(x.id)&&v29Position(x).active).map(x=>({member:x,alert:v29Position(x)}));
 ranked.sort((a,b)=>b.alert.overdue_days-a.alert.overdue_days||b.alert.cents-a.alert.cents||a.member.account.localeCompare(b.member.account));
 const title=mk('div','v33-alarm-heading');
 title.append(mk('strong','','待处理仓位告警 · '+ranked.length+'人'));
 const hide=mk('button','tiny','收起');
 hide.type='button';hide.onclick=togglePositionAlarm;title.append(hide);box.append(title);
 const hint=mk('p','v33-alarm-tip','告警后3天内处理；余额降至解除线自动移出。列表只供核对，不自动放款。');
 box.append(hint);
 const list=mk('div','v33-alarm-list');
 if(!ranked.length)list.append(mk('p','v33-alarm-empty','当前没有待处理的仓位告警'));
 for(const entry of ranked){
  const m=entry.member,w=entry.alert;
  const over=w.overdue_days>0;
  const btn=mk('button','v33-alarm-person'+(over?' v33-alarm-overdue':''),'');
  btn.type='button';btn.title='定位会员 '+m.account;
  btn.append(mk('b','v33-alarm-account',m.account));
  btn.append(mk('span','','仓位 '+money(m.stake_cents,true)+' · 余额 '+money(m.balance_cents,true)));
  btn.append(mk('strong','v33-alarm-amount','建议放款 '+money(w.cents,true)));
  btn.append(mk('small','v33-alarm-time'+(over?' overdue':''),
   over?'已超期'+w.overdue_days+'天':('剩余'+w.remaining_days+'天 · 告警日 '+(w.started_on||'今日'))));
  btn.onclick=()=>{
    if(view!=='branch')view='branch';
    if(selectedTreeGroup&&selectedTreeGroup!==m.group_account)selectedTreeGroup=m.group_account||'';
    branchClosed.clear();
    branchSelectedAccount=m.account;
    branchFocusRequested=true;branchViewportReady=false;branchResetRequested=true;
    persistTabView();render();
  };
  list.append(btn);
 }
 box.append(list);return box;
}
'''
s=swap(s,'function renderTree(){',panel+'\nfunction renderTree(){','left queue helper')
s=swap(s," if(riskMode)outer.append(riskBanner());\n if(withdrawGlowOn)outer.append",
''' if(riskMode)outer.append(riskBanner());
 if(positionAlarmOn)outer.append(v33AlertPanel(shownTreeMembers()));
 if(withdrawGlowOn)outer.append''','tree left queue')
s=swap(s," const shownRows=shownTreeMembers();\n function draw(){"," const shownRows=shownTreeMembers();\n if(positionAlarmOn)host.append(v33AlertPanel(shownRows));\n function draw(){",'branch left queue')

# Rank expansion is now individual member lines with nonzero deposit or withdrawal
# for the selected current period, not an aggregate of all levels including zeros.
ranking_helper='''function v33ActiveRankingMembers(entry,rows,day,period){
 const byParent=new Map();
 for(const member of rows){
  const items=byParent.get(member.parent_id)||[];
  items.push(member);byParent.set(member.parent_id,items);
 }
 const selected=[],todo=[entry.id],seen=new Set();
 const index=new Map(rows.map(m=>[m.id,m]));
 while(todo.length){
  const id=todo.pop();
  if(seen.has(id))continue;
  seen.add(id);
  const m=index.get(id);
  if(!m)continue;
  const amount=periodAmounts(m,day,period);
  if(amount.deposit!==0||amount.withdraw!==0){
   selected.push({member:m,deposit:amount.deposit,withdraw:amount.withdraw,score:amount.deposit-amount.withdraw});
  }
  for(const child of byParent.get(id)||[])todo.push(child.id);
 }
 selected.sort((a,b)=>Number(a.member.level||0)-Number(b.member.level||0)||b.deposit-a.deposit||b.withdraw-a.withdraw||a.member.account.localeCompare(b.member.account));
 return selected;
}
'''
s=swap(s,'function renderRanking(){',ranking_helper+'\nfunction renderRanking(){','ranking members helper')
s=swap(s,
 "header.append(mk('p','ranking-note','默认只显示第2层会员账号；成绩包括本人及全部下级，点击「详细」查看第3层至最深层逐层汇总。'));",
 "header.append(mk('p','ranking-note','排行榜统计整个团队；点击「详细」仅列出本期有充值或提现的会员账号，零活动会员不列出。'));",
 'ranking help')
start=s.index('if(open){',s.index('function renderRanking(){'))
end=s.index('}',s.index('cell.append(subt);detailRow.append(cell);body.append(detailRow);',start))+1
old=s[start:end]
assert 'for(const layer of entry.layers)' in old and 'detailRow' in old,'ranking detail source changed'
replace='''   if(open){
    const detailRow=mk('tr','ranking-detail-row'),cell=mk('td','ranking-detail-cell');cell.colSpan=10;
    const active=v33ActiveRankingMembers(entry,members,day,rankPeriod);
    cell.append(mk('b','','本期有充值或提现的会员明细（'+active.length+'人）'));
    const subt=mk('table','v12-layer-table'),th=mk('tr');
    ['会员账号','所属层级','备注',prefix+'充值',prefix+'提现',prefix+'输赢','本人余额'].forEach(z=>th.append(mk('th','',z)));
    subt.append(th);
    for(const entry of active){
     const m=entry.member,rt=mk('tr');
     const values=[m.account,'第'+m.level+'层',m.remark||'—',
       money(entry.deposit,true),money(entry.withdraw,true),
       (entry.score>0?'+':'')+money(entry.score,true),money(m.balance_cents,true)];
     values.forEach((value,k)=>{
      const cls=k===3?(entry.deposit>0?'amount-green':'amount-black'):
                k===4?amountClass(entry.withdraw,'daily'):
                k===5?amountClass(entry.score,'profit'):k===6?amountClass(m.balance_cents):'';
      rt.append(mk('td',cls,value));
     });
     subt.append(rt);
    }
    if(!active.length){
     const tr=mk('tr'),td=mk('td','empty','本期该团队没有充值或提现记录');
     td.colSpan=7;tr.append(td);subt.append(tr);
    }
    cell.append(subt);detailRow.append(cell);body.append(detailRow);
   }'''
s=s[:start]+replace+s[end:]
# On refresh also react when a withdrawal drops an alert even without changes
# to member list or when overdue age increases on a new day.
anchor="const dateChanged=businessDay!==d.business_day;const previousDay=businessDay;members=d.members;"
replacement="""const dateChanged=businessDay!==d.business_day;const previousDay=businessDay;
 const latestAlerts=new Map(Object.entries(d.position_alerts||{}));
 const alarmsChanged=JSON.stringify([...latestAlerts])!==JSON.stringify([...(positionAlarmById||new Map())]);
 positionAlarmById=latestAlerts;
 members=d.members;"""
s=swap(s,anchor,replacement,'refresh alert states')
s=swap(s,"if(changed||dateChanged||!silent||dateNow()!==lastDisplayDay)render();",
         "if(changed||dateChanged||alarmsChanged||!silent||dateNow()!==lastDisplayDay)render();",
         'render when warnings changed')
p.write_text(s,encoding='utf-8')

css+='''

/* V33: one left-side person per line, with persistent 3-day age. */
.v33-alarm-sidebar{
 position:absolute;z-index:65;top:9px;left:9px;width:270px;max-width:min(270px,72vw);
 max-height:calc(100% - 18px);display:flex;flex-direction:column;gap:6px;
 background:#fffdf6;color:#343e4b;border:2px solid #e88712;border-radius:11px;
 box-shadow:0 6px 24px #0009;padding:9px;overflow:hidden;font-size:12px;line-height:1.4;
}
.v33-alarm-heading{display:flex;align-items:center;justify-content:space-between;gap:6px;color:#964200}
.v33-alarm-heading strong{font-size:13px}
.v33-alarm-tip{color:#7b6035;margin:0 0 3px;font-size:10px}
.v33-alarm-list{overflow:auto;min-height:0;display:flex;flex-direction:column;gap:5px;flex:1}
.v33-alarm-person{border:1px solid #e9b26f;border-radius:7px;background:#fff6e8;color:#42301f;display:flex;
 flex-direction:column;align-items:stretch;text-align:left;padding:6px 8px;gap:2px;width:100%;cursor:pointer}
.v33-alarm-person:hover,.v33-alarm-person:focus-visible{outline:2px solid #fb8a0c;outline-offset:-1px}
.v33-alarm-account{font-size:13px;color:#172c42;overflow-wrap:anywhere}
.v33-alarm-amount{color:#dc5110;font-size:12px}
.v33-alarm-time{color:#785722;font-size:10px;font-weight:700}
.v33-alarm-overdue{border-color:#d20c28;background:#fff0f0}
.v33-alarm-time.overdue{color:#bf0e27;font-size:11px;font-weight:900}
.v33-alarm-empty{margin:8px 0;color:#4b6950;text-align:center}
.tree-main:has(>.v33-alarm-sidebar){position:relative;min-height:460px}
.tree-main>.v33-alarm-sidebar{position:sticky;float:left;top:5px;left:0;margin-right:12px;height:min(80vh,640px);max-height:80vh}
.branch-canvas.branch-risk-mode .v33-alarm-sidebar{top:min(55vh,490px);max-height:42vh}
.panel:fullscreen .v33-alarm-sidebar,.panel.fullscreen-fallback .v33-alarm-sidebar{z-index:250}
@media(max-width:720px){.v33-alarm-sidebar{width:215px;max-width:60vw}.v33-alarm-heading strong{font-size:11px}}
'''
cssp.write_text(css,encoding='utf-8')
(root/'tests/test_v33_rank_alert.cjs').write_text(r'''const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync('static/app.js','utf8');
const css=fs.readFileSync('static/style.css','utf8');
assert(s.includes("new Map(Object.entries(d.position_alerts||{}))"));
assert(s.includes("positionAlarmOn)host.append(v33AlertPanel(shownRows))"));
assert(s.includes("positionAlarmOn)outer.append(v33AlertPanel(shownTreeMembers()))"));
assert(s.includes('over?'+'' )===false||s.includes('已超期'));
assert(s.includes("suggest+=warn.cents"));
assert(css.includes('.v33-alarm-sidebar'));
const a=s.indexOf('function v33ActiveRankingMembers('),b=s.indexOf('function renderRanking(){',a);
assert(a>0&&b>a);
const part=s.slice(a,b);
const sandbox={};
vm.createContext(sandbox);
vm.runInContext(
 "const periodAmounts=(m,day,period)=>({deposit:period==='week'&&m.newFlag?m.stake_cents:0,withdraw:m.week_withdraw_cents||0});\n"+
 part+"\nthis.filter=v33ActiveRankingMembers;",sandbox);
const rows=[
 {id:'one',account:'leader',parent_id:null,level:2,stake_cents:1000,newFlag:false,week_withdraw_cents:0},
 {id:'two',account:'deposit',parent_id:'one',level:3,stake_cents:1000,newFlag:true,week_withdraw_cents:0},
 {id:'three',account:'withdraw',parent_id:'two',level:4,stake_cents:1000,newFlag:false,week_withdraw_cents:200},
 {id:'four',account:'inactive',parent_id:'two',level:4,stake_cents:1000,newFlag:false,week_withdraw_cents:0},
 {id:'five',account:'other-team',parent_id:null,level:2,stake_cents:1000,newFlag:true,week_withdraw_cents:300}
];
assert.deepEqual(Array.from(sandbox.filter({id:'one'},rows,'2026-11-08','week'),x=>x.member.account),['deposit','withdraw']);
console.log('V33 ranking detailed member filter and alert list state tests passed');
''',encoding='utf-8')
print('V33 frontend filter+left warning list added; no member data changes.')
