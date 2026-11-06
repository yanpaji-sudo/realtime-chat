from pathlib import Path

root = Path("member-tree")
app_path = root / "app.py"
js_path = root / "static/app.js"
css_path = root / "static/style.css"

helper = '''
# V26: preflight duplicate reconciliation for encrypted member backups.
# No database writes occur here. Financial conflicts abort the entire restore.
def _v26_reconcile_restore_duplicates(original_state):
    import copy
    from fastapi import HTTPException

    if not isinstance(original_state, dict) or not isinstance(original_state.get('rows'), list):
        return original_state, 0
    state = copy.deepcopy(original_state)
    winners, by_account, by_id, aliases = [], {}, {}, {}
    removed = 0
    monetary = ('balance_cents', 'total_withdraw_cents', 'daily_withdraw_cents', 'stake_cents')
    for row in state['rows']:
        if not isinstance(row, dict):
            winners.append(row)
            continue
        rid = str(row.get('id', ''))
        account = str(row.get('account', '')).casefold()
        previous = by_id.get(rid)
        if previous is not None and str(previous.get('account','')).casefold() != account:
            raise HTTPException(400, '备份同一会员ID对应不同账号，请人工核对')
        target = by_account.get(account) if account else None
        if target is None:
            target = previous
        if target is None:
            winners.append(row)
            if account: by_account[account] = row
            if rid: by_id[rid] = row
            continue
        removed += 1
        if rid and rid != str(target.get('id', '')):
            aliases[rid] = str(target['id'])
        for field in monetary:
            a, b = target.get(field), row.get(field)
            if type(a) is not int or type(b) is not int:
                raise HTTPException(400, '重复账号存在无效的金额字段')
            if a and b and a != b:
                raise HTTPException(400, '重复账号 ' + str(row.get('account','')) + ' 的' + field + '金额冲突，已取消恢复，原数据未更改')
            if not a and b: target[field] = b
        p1, p2 = target.get('parent_id'), row.get('parent_id')
        if p1 and p2 and str(p1) != str(p2):
            raise HTTPException(400, '重复账号 ' + str(row.get('account','')) + ' 的上级关系冲突，已取消恢复')
        if not p1 and p2: target['parent_id'] = p2
        if not target.get('remark') and row.get('remark'): target['remark'] = row['remark']
        if row.get('joined_on') and row['joined_on'] < str(target.get('joined_on','9999-99-99')):
            target['joined_on'] = row['joined_on']
        if row.get('daily_withdraw_cents', 0) and not target.get('daily_withdraw_on'):
            target['daily_withdraw_on'] = row.get('daily_withdraw_on')
        for field in ('revision',):
            if type(row.get(field)) is int and type(target.get(field)) is int:
                target[field] = max(target[field], row[field])
        if row.get('deleted') == 0: target['deleted'] = 0
        for field, choose in (('created_at', min), ('updated_at', max)):
            if isinstance(row.get(field),str) and isinstance(target.get(field),str):
                target[field] = choose(target[field], row[field])
    if not removed:
        return state, 0

    def canonical(mid):
        x = str(mid)
        seen = set()
        while x in aliases:
            if x in seen: raise HTTPException(400, '重复会员ID映射发生循环，停止恢复')
            seen.add(x)
            x = aliases[x]
        return x

    for row in winners:
        if isinstance(row, dict) and row.get('parent_id') is not None:
            row['parent_id'] = canonical(row['parent_id'])
    state['rows'] = winners

    # Preserve all linked history. Identical colliding records are merged;
    # genuinely different monetary records are rejected, never discarded.
    related = (
        ('withdrawals', ('member_id', 'business_day'), ('amount_cents',)),
        ('withdraw_credit', ('member_id', 'business_day'), ('credited_cents',)),
        ('daily_fission', ('member_id', 'business_day'), ('ratio_bp',)),
        ('team_names', ('member_id',), ('name',)),
    )
    for name, key_fields, protected_fields in related:
        values = state.get(name, [])
        if not isinstance(values, list): continue
        seen, kept = {}, []
        for item in values:
            if not isinstance(item,dict):
                kept.append(item)
                continue
            if 'member_id' in item: item['member_id'] = canonical(item['member_id'])
            key = tuple(str(item.get(k)) for k in key_fields)
            if key in seen:
                prior = seen[key]
                if any(prior.get(k) != item.get(k) for k in protected_fields):
                    raise HTTPException(400, '重复会员关联的' + name + '记录金额或内容冲突，恢复已停止')
                # Keep a nonempty settlement date and freshest metadata.
                for k,v in item.items():
                    if k not in protected_fields and k not in key_fields and v is not None:
                        if prior.get(k) is None or (isinstance(v,str) and isinstance(prior.get(k),str) and v > prior[k]):
                            prior[k] = v
            else:
                seen[key] = item
                kept.append(item)
        state[name] = kept

    # Only discard truly identical duplicated audit/undo rows.
    for name in ('logs', 'history'):
        values = state.get(name, [])
        if not isinstance(values,list): continue
        seen, kept = {}, []
        for item in values:
            if not isinstance(item,dict):
                kept.append(item)
                continue
            key = str(item.get('id'))
            if key in seen:
                if seen[key] != item:
                    raise HTTPException(400, '备份' + name + '有相同ID但内容不同的记录，恢复已停止')
            else:
                seen[key] = item
                kept.append(item)
        state[name] = kept

    # Other unique-key snapshots: remove only exact copies.
    for name, fields in (
        ('report_snapshots', ('business_day', 'group_account')),
        ('report_overrides', ('business_day', 'group_account')),
        ('business_closes', ('business_day',)),
    ):
        values = state.get(name, [])
        if not isinstance(values,list): continue
        seen, kept = {}, []
        for item in values:
            if not isinstance(item,dict):
                kept.append(item)
                continue
            key = tuple(str(item.get(k)) for k in fields)
            if key in seen:
                if seen[key] != item:
                    raise HTTPException(400, '备份' + name + '存在同键不同内容，恢复已停止')
            else:
                seen[key] = item
                kept.append(item)
        state[name] = kept
    return state, removed
'''

app = app_path.read_text(encoding="utf-8")
anchor = "@app.post('/api/admin/restore')"
assert app.count(anchor) == 1, "restore endpoint anchor changed"
assert "_v26_reconcile_restore_duplicates" not in app, "already patched"
app = app.replace(anchor, helper + "\n" + anchor)
old = "    state=data.get('state')\n    if not isinstance(state,dict): raise HTTPException(400,'备份结构无效')"
new = "    state=data.get('state')\n    if not isinstance(state,dict): raise HTTPException(400,'备份结构无效')\n    state, duplicate_members_removed = _v26_reconcile_restore_duplicates(state)"
assert app.count(old) == 1, "restore state anchor changed"
app = app.replace(old, new)
old = "    return {'ok':True,'members':len(rows),'logs':len(logs)}"
new = "    return {'ok':True,'members':len(rows),'logs':len(logs),'duplicate_members_removed':duplicate_members_removed}"
assert app.count(old) == 1, "restore return anchor changed"
app = app.replace(old, new)
app_path.write_text(app, encoding="utf-8")

js = js_path.read_text(encoding="utf-8")
checks = [
    ("||ids.has(r.id)", ""),
    ("if(accounts.has(lower))throw Error('备份包含重复会员账号');", ""),
    ("await api('/admin/restore','POST',{state:data,confirm:'RESTORE_WITH_BACKUP'});",
     "const restoreResult=await api('/admin/restore','POST',{state:data,confirm:'RESTORE_WITH_BACKUP'});"),
    ("showToast(\`已从加密备份恢复 \${active.length} 位会员及操作日志\`)",
     "showToast(\`成功恢复 \${restoreResult.members} 位会员；安全去重 \${restoreResult.duplicate_members_removed||0} 条\`)"),
    ("🔵 今日提现：", "⚡ 今日提现："),
]
for a, b in checks:
    assert js.count(a) == 1, "JS pattern missing or repeated: " + a
    js = js.replace(a, b)
js_path.write_text(js, encoding="utf-8")

css = css_path.read_text(encoding="utf-8")
assert "V26 NEON WITHDRAWAL" not in css, "CSS already patched"
css += """
/* V26 NEON WITHDRAWAL: high contrast on dark canvas, independent of card age and risk mode. */
.branch-canvas .branch-node.branch-withdraw-glow>rect,
.branch-canvas.branch-risk-mode .branch-node.branch-withdraw-glow>rect{
 stroke:#fff100!important;stroke-width:7px!important;
 filter:drop-shadow(0 0 3px #ffffff) drop-shadow(0 0 13px #ffed00) drop-shadow(0 0 29px #ff7b00) drop-shadow(0 0 48px #ff3c00)!important;
 animation:v26-withdraw-neon 1.75s ease-in-out infinite;
}
@keyframes v26-withdraw-neon{
 0%,100%{stroke:#fff300;stroke-width:7px;filter:drop-shadow(0 0 4px #ffffff) drop-shadow(0 0 15px #ffdf00) drop-shadow(0 0 30px #ff7b00) drop-shadow(0 0 49px #ff4500)}
 50%{stroke:#fff;stroke-width:9px;filter:drop-shadow(0 0 6px #ffffff) drop-shadow(0 0 22px #fff100) drop-shadow(0 0 42px #ff9d00) drop-shadow(0 0 60px #ff3a00)}
}
.branch-canvas .branch-withdraw-badge rect{fill:#ffd800!important;stroke:#fff8aa!important;stroke-width:2.5px!important;filter:drop-shadow(0 0 7px #ffb100)!important}
.branch-canvas .branch-withdraw-badge text{fill:#3b1b00!important;font-size:15px!important;font-weight:900!important}
.member.withdraw-glow{border:4px solid #ffed00!important;outline:4px solid #fff100!important;outline-offset:3px!important;box-shadow:0 0 0 9px #ffe600aa,0 0 24px #ffac00,0 0 48px #ff4500!important;animation:v26-member-neon 1.75s ease-in-out infinite}
@keyframes v26-member-neon{0%,100%{box-shadow:0 0 0 9px #ffe600aa,0 0 24px #ffac00,0 0 48px #ff4500}50%{box-shadow:0 0 0 12px #ffe600ee,0 0 33px #ffbf00,0 0 64px #ff4500}}
.withdraw-glow-amount{color:#432200!important;background:#ffe050!important;border:2px solid #ffb600!important;font-weight:900!important}
@media(prefers-reduced-motion:reduce){.branch-canvas .branch-node.branch-withdraw-glow>rect,.member.withdraw-glow{animation:none!important}}
"""
css_path.write_text(css, encoding="utf-8")

# Isolated unit tests: no production credentials and no database writes.
(root / "tests/test_v26_duplicate_reconcile.py").write_text('''
from fastapi import HTTPException
from app import _v26_reconcile_restore_duplicates

def row(ident, account, parent=None, balance=0):
    return {'id':ident,'account':account,'parent_id':parent,
            'balance_cents':balance,'total_withdraw_cents':0,
            'daily_withdraw_cents':0,'stake_cents':1000000,
            'remark':'','joined_on':'2026-11-01','daily_withdraw_on':None,
            'revision':1,'deleted':0,'created_at':'2026-11-01T00:00:00',
            'updated_at':'2026-11-01T00:00:00'}

def state(rows):
    return dict(rows=rows,history=[],logs=[],withdrawals=[],withdraw_credit=[],
        daily_fission=[],team_names=[],report_snapshots=[],report_overrides=[],
        business_closes=[])

def test_v26_merges_zero_balance_duplicate_preserves_child_and_links():
    original=state([row('one','ACCT',balance=0),
                    row('two','acct',balance=23000),
                    row('three','child',parent='two')])
    original['withdrawals']=[{'member_id':'two','business_day':'2026-11-01','amount_cents':400}]
    fixed,n=_v26_reconcile_restore_duplicates(original)
    assert n==1 and len(fixed['rows'])==2
    assert fixed['rows'][0]['balance_cents']==23000
    assert fixed['rows'][1]['parent_id']=='one'
    assert fixed['withdrawals'][0]['member_id']=='one'
    assert len(original['rows'])==3

def test_v26_identical_duplicate_does_not_double_withdraw():
    s=state([row('one','ACCT'),row('one','ACCT')])
    s['withdrawals']=[{'member_id':'one','business_day':'2026-11-01','amount_cents':400}]*2
    fixed,n=_v26_reconcile_restore_duplicates(s)
    assert n==1 and len(fixed['withdrawals'])==1

def test_v26_conflicting_nonzero_amount_refused_without_mutation():
    s=state([row('one','ACCT',balance=500),row('two','acct',balance=600)])
    try: _v26_reconcile_restore_duplicates(s)
    except HTTPException as ex:
        assert ex.status_code==400 and '金额冲突' in ex.detail
    else: raise AssertionError('must abort conflicting balances')
    assert len(s['rows'])==2

def test_v26_conflicting_withdraw_ledger_refused():
    s=state([row('one','ACCT'),row('two','acct')])
    s['withdrawals']=[
      {'member_id':'one','business_day':'2026-11-01','amount_cents':400},
      {'member_id':'two','business_day':'2026-11-01','amount_cents':800}]
    try: _v26_reconcile_restore_duplicates(s)
    except HTTPException as ex: assert '记录金额或内容冲突' in ex.detail
    else: raise AssertionError('must not silently discard distinct withdrawals')
''', encoding='utf-8')
print("V26 patch applied to isolated extracted bundle.")
