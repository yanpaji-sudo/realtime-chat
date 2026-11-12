
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
