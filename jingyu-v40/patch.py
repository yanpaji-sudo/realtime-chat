"""Whale test V40 only: member-level, editable-stake >130% warning and yellow hints.

This patch is applied to the tested Whale V38 payload and never to the
production branch or production PostgreSQL database. Existing Whale members,
member hierarchy, manually edited stakes, and Academy content are untouched.
"""
from pathlib import Path
root=Path('member-tree')
p=root/'app.py'
s=p.read_text(encoding='utf-8')

start=s.index("def v33_position_limits(stake_cents,direct_count):")
end=s.index("\ndef v33_sync_position_alerts(db,rows,day):",start)
backend=r'''def v33_position_limits(stake_cents,direct_count):
    """Whale: alert only ABOVE 130% of the member's own stake.

    Money is represented as integer cents. floor(13*stake/10) is the
    greatest cent balance that does not exceed 130%. The old positional
    direct-count parameter is ignored for every member depth.
    Returns (alert_boundary, permitted_balance, clear_boundary).
    """
    stake=max(0,int(stake_cents or 0))
    if not stake:
        return 0,0,0
    limit=(stake*13)//10
    return limit,limit,limit

'''
s=s[:start]+backend+s[end:]
old="""        account=str(r['account']).casefold()
        balance=int(r.get('balance_cents') or 0)
        warn,target,clear=v33_position_limits(r.get('stake_cents',0),counts.get(r['id'],0))
        old=previous.get(account)
        # A warning remains active while a 10000 stake moves from >15000 down
        # toward 13000; it does not disappear at the warning trigger.
        if old and int(old['active'])==1:
            if balance<=clear:"""
new="""        account=str(r['account']).casefold()
        balance=int(r.get('balance_cents') or 0)
        stake=max(0,int(r.get('stake_cents') or 0))
        warn,target,clear=v33_position_limits(stake,counts.get(r['id'],0))
        old=previous.get(account)
        # Zero or invalid stake has no meaningful percentage threshold:
        # close any previous alert rather than warn on every positive balance.
        if stake<=0:
            if old and int(old['active'])==1:
                db.execute(text(\"\"\"UPDATE position_alert_state
                    SET active=0,closed_on=:day,updated_at=:stamp WHERE account=:account\"\"\"),
                    {'day':day,'stamp':utc_now(),'account':account})
            continue
        # Recalculate from this member's manually editable stake on EVERY
        # refresh. A balance equal to 130% is SAFE; clear at or below the limit.
        if old and int(old['active'])==1:
            if balance<=clear:"""
assert s.count(old)==1,('alert sync anchor not unique',s.count(old))
s=s.replace(old,new,1)
assert s.count("        elif balance>warn:")==1
# The original formula is now the desired minimum release: balance - permitted balance.
assert s.count("'suggest_cents':max(0,balance-target)")==1
p.write_text(s,encoding='utf-8')

jfile=root/'static/app.js'
js=jfile.read_text(encoding='utf-8')
start=js.index('function v29Position(m){')
end=js.index('function togglePositionAlarm(){',start)
js=js[:start]+'''function v29Position(m){
 // Member-only exact 130% alert. Cents stay integers to avoid rounding.
 const stake=Math.max(0,Math.round(Number(m.stake_cents||0)));
 const balance=Math.max(0,Math.round(Number(m.balance_cents||0)));
 const limit=stake>0?Math.floor(stake*13/10):0;
 const live=positionAlarmById&&positionAlarmById.get(m.id);
 // The current balance determines the visual alert, even if a cached
 // server alert exists; a balance at the limit cancels immediately.
 const active=stake>0&&balance>limit;
 const cents=active?balance-limit:0; // 10000 stake, 18000 balance => withdraw 5000
 return {active,cents,threshold:limit,trigger:limit,clear:limit,
         started_on:active?(live?.started_on||''):'',
         overdue_days:active?Number(live?.overdue_days||0):0,
         remaining_days:active?Number(live?.remaining_days||3):3};
}
'''+js[end:]
old="showToast(positionAlarmOn?'仓位告警已开启：5000仓位余额超过7500、10000仓位超过15000显示光圈；余额达到解除线自动清除':'仓位告警已关闭');"
new="showToast(positionAlarmOn?'压仓黄色提醒已开启：所有层级本人余额超过建仓的130%报警；建议最低放款为超出上限的差额；余额降至130%或以下解除':'压仓提醒已关闭');"
assert js.count(old)==1
js=js.replace(old,new,1)
old="const hint=mk('p','v33-alarm-tip','告警后3天内处理；余额降至解除线自动移出。列表只供核对，不自动放款。');"
new="const hint=mk('p','v33-alarm-tip','全部层级：本人余额超过建仓×130%才黄色提醒；建议最低放款=余额−建仓×130%；降至130%及以下解除。只用于核查，不自动放款。');"
assert js.count(old)==1
js=js.replace(old,new,1)
old="btn.append(mk('span','','仓位 '+money(m.stake_cents,true)+' · 余额 '+money(m.balance_cents,true)));"
new="btn.append(mk('span','','本人建仓 '+money(m.stake_cents,true)+' · 余额 '+money(m.balance_cents,true)+' · 130%线 '+money(w.trigger,true)));"
assert js.count(old)==1
js=js.replace(old,new,1)
# UI for each member already supports editable stake from any depth via
# openEdit(m), POST/PUT MemberIn, and #editStake number input (min=0.01).
assert "el('editStake').value=m?String(m.stake_cents/100):'10000';" in js
assert "stake:el('editStake').value" in js
assert "function openEdit(m=null)" in js
jfile.write_text(js,encoding='utf-8')

hfile=root/'static/index.html'
h=hfile.read_text(encoding='utf-8')
old='仓位告警：5000仓位超过7500；10000仓位超过15000；点击查看建议放款及到期天数'
new='鲸鱼V42：所有层级余额超过本人建仓×130%黄色报警，建议最低放款=余额−建仓×130%，降至130%及以下解除'
assert h.count(old)==1
h=h.replace(old,new,1)
hfile.write_text(h,encoding='utf-8')

cssfile=root/'static/style.css'
css=cssfile.read_text(encoding='utf-8')
css+="""
/* Whale-only V42: YELLOW warning above each member's own 130% line.
   Overdue rows intentionally retain the existing red status. */
.member.v29-position-alert{
 outline:3px solid #eab308!important;
 box-shadow:0 0 0 6px #fde047ba,0 0 20px 5px #eab308aa!important;
}
.member.v29-position-alert .v29-position-label{
 background:#facc15!important;border:2px solid #fef08a!important;
 color:#422006!important;box-shadow:0 0 12px #eab30877!important;
}
.branch-canvas .branch-position-alarm>.v29-position-ring{
 stroke:#facc15!important;
 filter:drop-shadow(0 0 6px #fef08a) drop-shadow(0 0 12px #facc15)!important;
}
.branch-canvas .branch-position-alarm .v29-position-svg-badge rect{
 fill:#facc15!important;stroke:#fef9c3!important;
 filter:drop-shadow(0 0 5px #eab308)!important;
}
.branch-canvas .branch-position-alarm .v29-position-svg-badge text{
 fill:#422006!important;
}
.v33-alarm-person{background:#fffce8!important;border-color:#eab308!important}
.v33-alarm-amount{color:#854d0e!important}
.v33-alarm-overdue{border-color:#dc2626!important;background:#fff0f0!important}
.v33-alarm-time.overdue{color:#b91c1c!important}
"""
cssfile.write_text(css,encoding='utf-8')

print('Whale V42 installed: all depths manual stake + >130% own-balance yellow warning + minimum excess release; no production changes')
