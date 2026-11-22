"""Berlin-only sign normalization and real-time idempotent withdrawal credit.

Daily source amount negative = cash withdrawal; positive = funds returned.
Internal daily_withdraw_cents is the opposite signed net withdrawal.
Credit the delta immediately, use daily_withdraw_credit for idempotence,
and preserve credit metadata on undo. Balance imports remain independent.
"""
def replace_once(old, new, target='a'):
    global a, j
    value = a if target == 'a' else j
    count = value.count(old)
    assert count == 1, f'{target} expected one anchor but found {count}: {old[:110]!r}'
    value = value.replace(old, new, 1)
    if target == 'a': a = value
    else: j = value

replace_once(
    '            values = [berlin_import_amount_cents(v) for v in parts[1:]]',
    "            values = [berlin_import_amount_cents(v) for v in parts[1:]]\n"
    "            if mode == 'daily': values[0] = -values[0]\n"
    "            elif mode == 'both': values[1] = -values[1]"
)
replace_once(
    "    today = current_day()\n    delta = 0\n    if mode in ('daily', 'both'):",
    """    today = current_day()
    delta = 0
    credited_today = {}
    if mode in ('daily', 'both'):
        with engine.connect() as db:
            credited_today = {r['member_id']:int(r['credited_cents']) for r in
                db.execute(text('SELECT member_id,credited_cents FROM daily_withdraw_credit '
                                'WHERE business_day=:day'),{'day':today}).mappings()}
    if mode in ('daily', 'both'):"""
)
replace_once(
    "            old_daily = int(r['daily_withdraw_cents']) if r.get('daily_withdraw_on') == today else 0\n"
    "            new_daily = int(parsed.get(r['account'], [0]*(pos+1))[pos])\n"
    "            delta += new_daily-old_daily",
    "            already_credited = credited_today.get(r['id'],0)\n"
    "            new_daily = int(parsed.get(r['account'], [0]*(pos+1))[pos])\n"
    "            delta += new_daily-already_credited"
)
replace_once(
    "            'summary': ('余额及当日提现只保留最新上传结果；累计总提现不在同日反复累计，待跨日结算时只计入最终快照。' if mode!='balance' else '只更新余额，不影响提现数据。') + ' 未出现账号的所选字段置零；上传中未匹配的账号不会自动创建会员。'",
    "            'summary': ('负数为实际提现（增加当日净提现及累计提现）；正数为资金回流（冲减当日净提现及累计提现）。当天按上传差额立即更新累计提现，同日覆盖不重复累计，跨日不重复计入。余额以余额文件为准，不因资金回流重复自动加款。' if mode!='balance' else '只更新余额，不影响提现数据。') + ' 未出现账号的所选字段置零；上传中未匹配的账号不会自动创建会员。'"
)
replace_once(
    "        before_import={r['id']:snapshot(db,r['id']) for r in rows}\n        for r in rows:",
    """        before_import={r['id']:snapshot(db,r['id']) for r in rows}
        credit_before = {}
        if use_daily:
            credit_before={x['member_id']:dict(x) for x in
                db.execute(text('''SELECT member_id,business_day,credited_cents,settled_at
                    FROM daily_withdraw_credit WHERE business_day=:today'''),
                    {'today':today}).mappings()}
        for r in rows:"""
)
replace_once(
    "                prior_daily = int(r['daily_withdraw_cents']) if r.get('daily_withdraw_on') == today else 0\n"
    "                new_daily = values[idx_daily] if values is not None else 0\n"
    "                delta = new_daily - prior_daily\n"
    "                withdraw_delta += delta\n"
    "                params.update({'today':today,'daily':new_daily})\n"
    "                # Today's withdrawals are provisional; settle once after midnight.\n"
    "                updates.extend(['daily_withdraw_cents=:daily','daily_withdraw_on=:today'])",
    "                new_daily = int(values[idx_daily]) if values is not None else 0\n"
    "                previous_credit=credit_before.get(r['id'])\n"
    "                already_credited=int(previous_credit['credited_cents']) if previous_credit else 0\n"
    "                delta = new_daily - already_credited\n"
    "                withdraw_delta += delta\n"
    "                params.update({'today':today,'daily':new_daily,'total_delta':delta})\n"
    "                # Credit today's net withdrawal immediately; settlement sees\n"
    "                # the same credited snapshot and must not double-count it.\n"
    "                updates.extend(['daily_withdraw_cents=:daily','daily_withdraw_on=:today',\n"
    "                                'total_withdraw_cents=total_withdraw_cents+:total_delta'])"
)
replace_once(
    "            if use_daily:\n                set_daily_ledger(db,r['id'],today,new_daily)\n        if use_daily:",
    """            if use_daily:
                set_daily_ledger(db,r['id'],today,new_daily)
                if new_daily or previous_credit is not None:
                    db.execute(text('''INSERT INTO daily_withdraw_credit
                        (member_id,business_day,credited_cents,settled_at)
                        VALUES (:i,:d,:v,NULL) ON CONFLICT(member_id,business_day)
                        DO UPDATE SET credited_cents=excluded.credited_cents,
                                      settled_at=NULL'''),
                        {'i':r['id'],'d':today,'v':new_daily})
        if use_daily:"""
)
replace_once(
    "                    [{'id':r['id'],'account':r['account'],'before':before_import[r['id']],\n"
    "                      'after':snapshot(db,r['id'])} for r in rows])",
    "                    [{'id':r['id'],'account':r['account'],'before':before_import[r['id']],\n"
    "                      'after':snapshot(db,r['id']),\n"
    "                      'withdraw_credit_day':today if use_daily else None,\n"
    "                      'withdraw_credit_before':credit_before.get(r['id']) if use_daily else None}\n"
    "                     for r in rows])"
)
replace_once(
    "                set_daily_ledger(db,change['id'],affected,prior)\n"
    "        db.execute(text('UPDATE undo_actions SET undone=1,undone_at=:now WHERE id=:id'),",
    """                set_daily_ledger(db,change['id'],affected,prior)
                credit_day=change.get('withdraw_credit_day')
                if credit_day:
                    old_credit=change.get('withdraw_credit_before')
                    if old_credit is None:
                        db.execute(text('''DELETE FROM daily_withdraw_credit
                            WHERE member_id=:i AND business_day=:d'''),
                            {'i':change['id'],'d':credit_day})
                    else:
                        db.execute(text('''INSERT INTO daily_withdraw_credit
                          (member_id,business_day,credited_cents,settled_at)
                          VALUES (:i,:d,:v,:s) ON CONFLICT(member_id,business_day)
                          DO UPDATE SET credited_cents=excluded.credited_cents,
                                        settled_at=excluded.settled_at'''),
                          {'i':change['id'],'d':credit_day,
                           'v':int(old_credit['credited_cents']),
                           's':old_credit['settled_at']})
        db.execute(text('UPDATE undo_actions SET undone=1,undone_at=:now WHERE id=:id'),"""
)
replace_once(
    '每日提现最后一次上传为准：</b>同日多次上传只是更新当日快照；待当天结束、下次系统执行跨日结算时才一次性计入累计总提现。',
    '每日提现最后一次上传为准：</b>负数表示实际提现，正数表示资金回流。上传后立即按差额调整累计提现；同日重复上传不重复累计，跨日也不会再计一次。','j'
)
replace_once(
    '上传“当日提现”将自动只覆盖当日提现快照；总提现在跨日结算时按最终数据计入。',
    '提现原始数据负数视为实际提现、正数视为资金回流；系统实时按净额更新今日提现与累计提现。余额以独立余额数据为准。','j'
)
replace_once(
    '本次当日提现快照修正差额（非立即计入累计提现）',
    '本次累计净提现立即调整金额','j'
)
assert 'delta = new_daily - prior_daily' not in a
assert 'credit_before={x' in a
assert "'withdraw_credit_before':credit_before.get(r['id'])" in a
assert 'values[0] = -values[0]' in a and 'values[1] = -values[1]' in a
ap.write_text(a,encoding='utf-8')
jp.write_text(j,encoding='utf-8')
