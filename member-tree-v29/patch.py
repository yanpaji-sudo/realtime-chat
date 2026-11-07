from pathlib import Path
root=Path('member-tree')
app_file=root/'static/app.js'
html_file=root/'static/index.html'
css_file=root/'static/style.css'
app=app_file.read_text(encoding='utf-8')
html=html_file.read_text(encoding='utf-8')
css=css_file.read_text(encoding='utf-8')

def replace_one(s,a,b,label):
    n=s.count(a)
    if n!=1:raise RuntimeError(label+' expected exactly one anchor, got '+str(n))
    return s.replace(a,b,1)

app=replace_one(app,"let riskMode=false,riskFocusId='',withdrawGlowOn=false,treeVertical=false,branchVertical=false;","let riskMode=false,riskFocusId='',withdrawGlowOn=false,treeVertical=false,branchVertical=false;\nlet positionAlarmOn=false;",'state')
app=replace_one(app,"Math.round(fission)+'%'","fission.toFixed(1)+'%'","one decimal")
helper="""
// V29: view-only alert based on OWN balance and number of direct referrals.
function v29Position(m){
 const threshold=(Number(m.direct_count||0)>=5?20000:13000)*100;
 const cents=Math.max(0,Number(m.balance_cents||0)-threshold);
 return {active:Number.isFinite(cents)&&cents>0,cents,threshold};
}
function togglePositionAlarm(){
 positionAlarmOn=!positionAlarmOn;
 hideCompactTooltip();
 render();
 showToast(positionAlarmOn?'仓位告警已开启：直属不足5人余额超过13000；直属至少5人余额超过20000':'仓位告警已关闭');
}
function v29TeamStats(m){
 const count=Math.max(1,Number(m.descendant_count||0)+1);
 const teamBalance=Number(m.subtree_balance_cents||0);
 const downCount=Number(m.descendant_count||0);
 const downAvg=downCount>0?(teamBalance-Number(m.balance_cents||0))/downCount:0;
 const months=Math.max(0,membershipMonths(m.joined_on,businessDay||dateNow()));
 const quota=Math.max(1,months);
 const children=new Map();
 for(const x of members){
  const kids=children.get(x.parent_id)||[];
  kids.push(x);
  children.set(x.parent_id,kids);
 }
 const pending=[m],seen=new Set();
 let suggest=0;
 while(pending.length){
  const x=pending.pop();
  if(seen.has(x.id))continue;
  seen.add(x.id);
  suggest+=v29Position(x).cents;
  for(const y of children.get(x.id)||[])pending.push(y);
 }
 return {count,teamBalance,average:teamBalance/count,downAvg,months,quota,qualified:count>=quota,suggest};
}
"""
app=replace_one(app,"function compactInfo(m){",helper+"\nfunction compactInfo(m){","insert helpers")
start=app.index("function compactInfo(m){")
end=app.index("function moveCompactTooltip(e,node){",start)
new_popup="""
function compactInfo(m){
 const stats=v29TeamStats(m),wrap=mk('div','v28-pop-body');
 wrap.append(mk('h3','v28-pop-title',m.account+' · 个人与团队数据'));
 const facts=mk('div','v28-pop-facts');
 const details=[
  ['备注信息',m.remark||'无'],
  ['会员账号',m.account],
  ['加入日期',m.joined_on||'—'],
  ['本人充值',money(Number(m.stake_cents||0),true)],
  ['本人总提现',money(Number(m.total_withdraw_cents||0),true)],
  ['本人输赢',money(Number(m.profit_cents||0),true)],
  ['直属人数',String(m.direct_count||0)],
  ['全部下级',String(m.descendant_count||0)],
  ['下级平均余额',money(stats.downAvg,true)]
 ];
 for(const d of details){
  facts.append(mk('span','',d[0]));
  const value=mk('b','',d[1]);
  if(d[0]==='本人输赢')value.classList.add(Number(m.profit_cents||0)>0?'v29-green':Number(m.profit_cents||0)<0?'v29-red':'v29-neutral');
  facts.append(value);
 }
 wrap.append(facts);
 const table=mk('table','v28-pop-table'),heading=mk('tr');
 heading.append(mk('th','','团队指标（含本人）'),mk('th','','汇总数值'));
 table.append(heading);
 const rows=[
  ['团队充值',Number(m.subtree_stake_cents||0),'v29-green'],
  ['团队总提现',Number(m.subtree_total_withdraw_cents||0),'v29-red'],
  ['团队余额',stats.teamBalance,stats.average>13000*100?'v29-red':'v29-green'],
  ['团队平均余额',stats.average,stats.average>13000*100?'v29-red':'v29-green'],
  ['团队总人数',stats.count,stats.qualified?'v29-green':'v29-red'],
  ['团队输赢',Number(m.subtree_profit_cents||0),Number(m.subtree_profit_cents||0)>0?'v29-green':Number(m.subtree_profit_cents||0)<0?'v29-red':'v29-neutral']
 ];
 for(const [label,value,cls] of rows){
  const tr=mk('tr');tr.append(mk('td','',label));
  const printed=label==='团队总人数'?(String(value)+'人（满'+stats.months+'月 / 目标≥'+stats.quota+'人）'):money(value,true);
  tr.append(mk('td',cls,printed));table.append(tr);
 }
 wrap.append(table);
 const risk=riskForMember(m);
 const foot=mk('div','v29-risk-footer');
 foot.append(mk('span','','团队风险：平均余额 '+money(stats.average,true)+' · 团队建议放款 '+money(stats.suggest,true)+' · 收益/余额 '));
 foot.append(mk('strong','v29-grade-'+risk.grade,risk.pct===null?'—':risk.pct.toFixed(1)+'%'));
 wrap.append(foot);
 wrap.append(mk('small','v28-pop-help','团队建议放款=所有团队成员各自超出其直属人数对应阈值的余额合计；仅为规则提示，不执行放款。'));
 return wrap;
}
"""
app=app[:start]+new_popup+app[end:]
# Mini and normal members share one visually distinct alert ring/label.
anchor="card.dataset.memberId=x.id;"
prefix="""if(positionAlarmOn){
  const notice=v29Position(x);
  if(notice.active){
   card.classList.add('v29-position-alert');
   const label=mk('span','v29-position-label','建议放款 '+money(notice.cents,true));
   card.append(label);
  }
 }
 """
app=replace_one(app,anchor,prefix+anchor,'DOM alarm')
# SVG rings/amount on both compact and expanded branch diagram.
anchor="group.append(svgEl('rect',{x:0,y:0,width:cardW,height:cardH,rx:compactMode?7:12}));if(compactMode)attachCompactHover(group,m);"
new=anchor+"""
    if(positionAlarmOn){
     const warn=v29Position(m);
     if(warn.active){
      group.classList.add('branch-position-alarm');
      group.append(svgEl('ellipse',{cx:cardW/2,cy:cardH/2,rx:cardW/2+9,ry:cardH/2+7,class:'v29-position-ring',fill:'none','aria-hidden':'true'}));
      const alertLabel=svgEl('g',{class:'v29-position-svg-badge','aria-label':'建议放款 '+money(warn.cents,true)});
      const textVal='建议放款 '+money(warn.cents,true);
      const badgeWidth=Math.min(cardW,Math.max(118,textVal.length*10+16));
      alertLabel.append(svgEl('rect',{x:0,y:-24,width:badgeWidth,height:21,rx:5}));
      alertLabel.append(svgEl('text',{x:6,y:-9},textVal));
      group.append(alertLabel);
     }
    }
"""
app=replace_one(app,anchor,new,'SVG alarm')
app=replace_one(app,"el('compactTreeBtn').classList.toggle('hidden',!['tree','branch'].includes(view));","el('compactTreeBtn').classList.toggle('hidden',!['tree','branch'].includes(view));el('positionAlarmBtn').classList.toggle('hidden',!['tree','branch'].includes(view));el('positionAlarmBtn').textContent=positionAlarmOn?'关闭仓位告警':'◉ 仓位告警';el('positionAlarmBtn').setAttribute('aria-pressed',String(positionAlarmOn));",'button display')
app=replace_one(app,"el('compactTreeBtn').onclick=toggleCompactTree;","el('compactTreeBtn').onclick=toggleCompactTree;el('positionAlarmBtn').onclick=togglePositionAlarm;",'button binding')
html=replace_one(html,'<button class="button hidden v28-compact-switch"','<button class="button hidden v29-position-switch" type="button" id="positionAlarmBtn" aria-pressed="false" title="标记直属不足5人本人余额超过13000、直属至少5人本人余额超过20000的会员">◉ 仓位告警</button><button class="button hidden v28-compact-switch"','html alarm button')
css += """
/* V29: conspicuous orange position alert on both tree UIs. */
.v29-position-switch{border:1px solid #e88713!important;background:#fff4dd!important;color:#98500b!important;font-weight:900!important}
.v29-position-switch[aria-pressed=true]{background:#d75307!important;color:#fff!important;border-color:#d75307!important}
.member.v29-position-alert{position:relative!important;outline:3px solid #ff8700!important;outline-offset:4px!important;box-shadow:0 0 0 6px #ffb52c9c,0 0 21px 6px #ff6d00bb!important}
.member.v29-position-alert .v29-position-label{position:absolute;top:-26px;right:0;z-index:5;background:#fb7a00;border:2px solid #ffd091;color:#fff!important;border-radius:6px;padding:1px 6px;font-size:11px!important;font-weight:900!important;white-space:nowrap;box-shadow:0 0 11px #fb7a00aa}
.branch-canvas .branch-position-alarm>.v29-position-ring{stroke:#ff8a00!important;stroke-width:5px!important;filter:drop-shadow(0 0 5px #fff) drop-shadow(0 0 11px #ff8a00) drop-shadow(0 0 19px #ff5300)!important;pointer-events:none}
.branch-canvas .branch-position-alarm .v29-position-svg-badge{pointer-events:none}
.branch-canvas .branch-position-alarm .v29-position-svg-badge rect{fill:#ff7900!important;stroke:#ffe6bc!important;stroke-width:1.5px!important;filter:drop-shadow(0 0 7px #f97316)!important}
.branch-canvas .branch-position-alarm .v29-position-svg-badge text{fill:#fff!important;font-family:"Microsoft YaHei",Arial,sans-serif;font-size:12px!important;font-weight:900!important}
.v28-compact-tooltip .v29-green{color:#057b45!important;font-weight:900!important}
.v28-compact-tooltip .v29-red{color:#ce212b!important;font-weight:900!important}
.v28-compact-tooltip .v29-neutral{color:#233e61!important;font-weight:800!important}
.v28-compact-tooltip .v29-risk-footer{font-size:12px;line-height:1.6;padding:8px 7px;border-top:1px solid #e2e8f0;background:#f5f8fc}
.v28-compact-tooltip .v29-grade-danger{color:#991b1b!important;font-weight:900!important}
.v28-compact-tooltip .v29-grade-warning{color:#ed777c!important;font-weight:900!important}
.v28-compact-tooltip .v29-grade-improve{color:#60b978!important;font-weight:900!important}
.v28-compact-tooltip .v29-grade-healthy{color:#176d46!important;font-weight:900!important}
.v28-compact-tooltip .v29-grade-unknown{color:#667085!important;font-weight:900!important}
"""
css_file.write_text(css,encoding='utf-8')
app_file.write_text(app,encoding='utf-8')
html_file.write_text(html,encoding='utf-8')
(root/'tests/test_v29_position_alert.cjs').write_text("""
const assert=require('node:assert/strict'),fs=require('node:fs');
const js=fs.readFileSync('static/app.js','utf8'),css=fs.readFileSync('static/style.css','utf8'),html=fs.readFileSync('static/index.html','utf8');
assert(js.includes('fission.toFixed(1)'));
assert(html.includes('id="positionAlarmBtn"'));
assert(js.includes("el('positionAlarmBtn').onclick=togglePositionAlarm"));
assert(js.includes("(Number(m.direct_count||0)>=5?20000:13000)*100"));
assert(js.includes('Number(m.balance_cents||0)-threshold'));
assert(js.includes("positionAlarmOn&&")===false || js.includes("positionAlarmOn"));
assert(js.includes("branch-position-alarm"));
assert(js.includes("v29-position-ring"));
assert(js.includes("function v29TeamStats(m)"));
assert(js.includes("const quota=Math.max(1,months)"));
assert(js.includes("qualified:count>=quota"));
assert(js.includes("['团队充值'"));
assert(js.includes("['团队总提现'"));
assert(js.includes("['团队余额'"));
assert(js.includes("['团队平均余额'"));
assert(js.includes("['团队总人数'"));
assert(js.includes("['团队输赢'"));
assert(js.includes("['下级平均余额'"));
assert(js.includes("['本人充值'"));
assert(js.includes("['本人总提现'"));
assert(js.includes("['本人输赢'"));
assert(js.includes('suggest+=v29Position(x).cents'));
assert(css.includes('.v29-grade-danger'));
console.log('V29 one-decimal KPI, own balance alarm rules, A-month quota, team tooltip pass');
""")
print('V29 view-only changes added. No database or API modifications.')
