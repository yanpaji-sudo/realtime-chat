"""Unit tests for isolated DFX restore correction. No live DB access."""
import copy
import pytest
from fastapi import HTTPException
from app import _v26_reconcile_restore_duplicates

def member(mid,acct,balance=50000):
    return {'id':mid,'account':acct,'parent_id':None,
            'stake_cents':100000,'balance_cents':balance,
            'total_withdraw_cents':5000,'daily_withdraw_cents':0,
            'joined_on':'2026-10-01','remark':'','revision':0,
            'deleted':0,'created_at':'2026-10-01T12:00:00Z',
            'updated_at':'2026-11-11T00:00:00Z'}

def state():
    return {'rows':[member('a','DUP'),member('b','dup')],
            'daily_fission':[
             {'member_id':'a','business_day':'2026-11-10','ratio_bp':120,'captured_at':'2026-11-10T10:00:00+00:00'},
             {'member_id':'b','business_day':'2026-11-10','ratio_bp':250,'captured_at':'2026-11-10T11:00:00+00:00'}],
            'withdrawals':[],'withdraw_credit':[],'team_names':[],
            'logs':[],'history':[]}

def test_fission_conflicts_keep_freshest_no_money_changes():
    original=state()
    recovered,removed=_v26_reconcile_restore_duplicates(original)
    assert removed==1
    assert recovered['_fission_conflicts_reconciled']==1
    assert len(recovered['rows'])==1
    assert recovered['rows'][0]['balance_cents']==50000
    assert recovered['rows'][0]['stake_cents']==100000
    assert len(recovered['daily_fission'])==1
    assert recovered['daily_fission'][0]['ratio_bp']==250
    assert recovered['daily_fission'][0]['member_id']=='a'
    assert len(original['rows'])==2 and len(original['daily_fission'])==2

def test_old_snapshot_loses_to_canonical_newer():
    s=state()
    s['daily_fission'][0]['captured_at']='2026-11-10T15:00:00+00:00'
    v,n=_v26_reconcile_restore_duplicates(s)
    assert n==1
    assert v['daily_fission'][0]['ratio_bp']==120
    assert v['_fission_conflicts_reconciled']==1

def test_equal_timestamp_prefers_canonical_member():
    s=state()
    s['daily_fission'][0]['captured_at']='2026-11-10T11:00:00+00:00'
    v,n=_v26_reconcile_restore_duplicates(s)
    assert v['daily_fission'][0]['ratio_bp']==120
    assert v['_fission_conflicts_reconciled']==1

def test_money_conflict_still_blocks_restore():
    s=state()
    s['rows'][1]['balance_cents']=51000
    with pytest.raises(HTTPException,match='金额冲突'):
        _v26_reconcile_restore_duplicates(s)

def test_withdrawal_conflict_still_blocks_restore():
    s=state()
    s['withdrawals']=[
      {'member_id':'a','business_day':'2026-11-10','amount_cents':100},
      {'member_id':'b','business_day':'2026-11-10','amount_cents':200},
    ]
    with pytest.raises(HTTPException,match='withdrawals'):
        _v26_reconcile_restore_duplicates(s)

def test_withdrawal_credit_conflict_still_blocks_restore():
    s=state()
    s['withdraw_credit']=[
      {'member_id':'a','business_day':'2026-11-10','credited_cents':100},
      {'member_id':'b','business_day':'2026-11-10','credited_cents':200},
    ]
    with pytest.raises(HTTPException,match='withdraw_credit'):
        _v26_reconcile_restore_duplicates(s)

def test_original_without_duplicate_members_untouched():
    s=state()
    s['rows']=s['rows'][:1]
    s['daily_fission']=s['daily_fission'][:1]
    v,n=_v26_reconcile_restore_duplicates(s)
    assert n==0
    assert v==s
