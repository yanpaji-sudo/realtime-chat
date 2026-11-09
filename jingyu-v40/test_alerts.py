"""Whale-only V42: own stake at all depths, >130% warning, excess-only release."""
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from app import (v33_position_limits, v33_sync_position_alerts,
                 validate_stake_for_level, validate_member, MemberIn)

def make_db():
    db = create_engine('sqlite://',poolclass=StaticPool,
             connect_args={'check_same_thread':False})
    with db.begin() as d:
        d.execute(text("""CREATE TABLE position_alert_state(
            account TEXT PRIMARY KEY,opened_on TEXT,closed_on TEXT,
            active INTEGER,updated_at TEXT)"""))
        d.execute(text("""CREATE TABLE members(
            id TEXT PRIMARY KEY,account TEXT,parent_id TEXT,deleted INTEGER DEFAULT 0)"""))
    return db

def member(stake,balance,account='A',mid='id-a',parent=None):
    return {'id':mid,'account':account,'parent_id':parent,
            'stake_cents':int(round(stake*100)),
            'balance_cents':int(round(balance*100))}

def test_exact_130_percent_limits_all_stakes():
    for stake,expected in [(0,0),(100,130),(5000,6500),
                           (10000,13000),(1700,2210),
                           (123.45,160.48),(20000,26000)]:
        for direct in (0,2,5,12):
            warn,target,clear=v33_position_limits(int(round(stake*100)),direct)
            assert warn==round(expected*100),(stake,direct,warn)
            assert target==warn==clear

def test_user_example_10000_18000_suggests_only_5000():
    db=make_db()
    with db.begin() as d:
        assert v33_sync_position_alerts(d,[member(10000,13000)],'2026-11-09')=={}
        alert=v33_sync_position_alerts(d,[member(10000,18000)],'2026-11-09')['id-a']
        assert alert['warn_cents']==1300000
        assert alert['target_cents']==1300000
        assert alert['suggest_cents']==500000
        assert alert['remaining_days']==3
        assert v33_sync_position_alerts(d,[member(10000,13000)],'2026-11-09')=={}
        assert d.execute(text("SELECT active FROM position_alert_state WHERE account='a'")).scalar()==0

def test_boundary_and_recompute_on_current_balance():
    db=make_db()
    with db.begin() as d:
        assert v33_sync_position_alerts(d,[member(100,120)],'2026-11-09')=={}
        assert v33_sync_position_alerts(d,[member(100,130)],'2026-11-09')=={}
        a=v33_sync_position_alerts(d,[member(100,160)],'2026-11-09')['id-a']
        assert a['warn_cents']==13000
        assert a['suggest_cents']==3000
        a=v33_sync_position_alerts(d,[member(100,180)],'2026-11-11')['id-a']
        assert a['suggest_cents']==5000
        assert a['remaining_days']==1
        assert v33_sync_position_alerts(d,[member(100,130)],'2026-11-11')=={}
        assert v33_sync_position_alerts(d,[member(100,130.01)],'2026-11-12')['id-a']['suggest_cents']==1

def test_change_member_stake_recomputes_without_fixed_tiers():
    db=make_db()
    with db.begin() as d:
        assert v33_sync_position_alerts(d,[member(5000,7000)],'2026-11-09')['id-a']['suggest_cents']==50000
        assert v33_sync_position_alerts(d,[member(10000,7000)],'2026-11-09')=={}
        assert v33_sync_position_alerts(d,[member(200,261)],'2026-11-09')['id-a']['suggest_cents']==100
        assert v33_sync_position_alerts(d,[member(200,260)],'2026-11-09')=={}

def test_fractional_cent_boundary():
    # 123.45 * 1.3 = 160.485; greatest safe one-cent balance is 160.48.
    db=make_db()
    with db.begin() as d:
        assert v33_sync_position_alerts(d,[member(123.45,160.48)],'2026-11-09')=={}
        alert=v33_sync_position_alerts(d,[member(123.45,160.49)],'2026-11-09')['id-a']
        assert alert['suggest_cents']==1
        assert v33_sync_position_alerts(d,[member(123.45,160.48)],'2026-11-09')=={}

def test_zero_stake_does_not_raise_warning():
    db=make_db()
    with db.begin() as d:
        assert 'id-a' in v33_sync_position_alerts(d,[member(100,160)],'2026-11-09')
        assert v33_sync_position_alerts(d,[member(0,999)],'2026-11-09')=={}
        assert d.execute(text("SELECT active FROM position_alert_state WHERE account='a'")).scalar()==0

def test_all_levels_stakes_remain_manually_editable():
    db=make_db()
    with db.begin() as d:
        for id_,acct,parent in [
            ('root','ROOT',None),('child','CHILD','root'),
            ('third','THIRD','child'),('fourth','FOURTH','third')]:
            d.execute(text("INSERT INTO members(id,account,parent_id,deleted) VALUES(:i,:a,:p,0)"),
                {'i':id_,'a':acct,'p':parent})
        for parent,amount in [(None,'100'),('root','5000'),('child','123.45'),('third','20000')]:
            value=int(round(float(amount)*100))
            validate_stake_for_level(d,parent,value)
            member_in=MemberIn(account='EXAMPLE',joined_on='2026-11-09',stake=amount)
            _,_,stake=validate_member(member_in)
            assert stake==value

def test_individual_alerts_not_aggregated_subtree_balances():
    db=make_db()
    with db.begin() as d:
        rows=[member(100,160,mid='r',account='R'),
              member(5000,4500,mid='c',account='C',parent='r'),
              member(10000,18000,mid='g',account='G',parent='c')]
        result=v33_sync_position_alerts(d,rows,'2026-11-09')
        assert set(result)=={'r','g'}
        assert result['r']['suggest_cents']==3000
        assert result['g']['suggest_cents']==500000
        assert result['r']['warn_cents']==13000
        assert result['g']['warn_cents']==1300000
