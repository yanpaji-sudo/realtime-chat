"""Whale-only V40: arbitrary member stake, alert at 130%, suggest stake."""
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

def test_130pct_limits_any_stake_and_directs():
    for stake,expected in [(0,0),(100,130),(5000,6500),
                           (10000,13000),(1700,2210),
                           (123.45,160.49),(20000,26000)]:
        for direct in (0,2,5,12):
            warn,target,clear=v33_position_limits(int(round(stake*100)),direct)
            assert warn==round(expected*100),(stake,direct,warn)
            assert target==round(stake*100)
            assert clear==warn

def test_boundary_and_suggestion_equal_stake():
    db=make_db()
    with db.begin() as d:
        assert v33_sync_position_alerts(d,[member(100,120)],'2026-11-09')=={}
        a=v33_sync_position_alerts(d,[member(100,130)],'2026-11-09')['id-a']
        assert a['warn_cents']==13000
        assert a['suggest_cents']==10000
        assert a['target_cents']==10000
        assert a['remaining_days']==3
        a=v33_sync_position_alerts(d,[member(100,140)],'2026-11-11')['id-a']
        assert a['suggest_cents']==10000
        assert a['remaining_days']==1
        assert v33_sync_position_alerts(d,[member(100,129.99)],'2026-11-11')=={}
        assert d.execute(text("SELECT active FROM position_alert_state WHERE account='a'")).scalar()==0
        a=v33_sync_position_alerts(d,[member(100,140)],'2026-11-12')['id-a']
        assert a['started_on']=='2026-11-12'
        assert a['suggest_cents']==10000

def test_change_stake_recomputes_alert_without_old_fixed_rules():
    db=make_db()
    with db.begin() as d:
        assert v33_sync_position_alerts(d,[member(5000,6500)],'2026-11-09')['id-a']['suggest_cents']==500000
        # Manually changed this member to 10,000: the old 6,500 no longer alarms.
        assert v33_sync_position_alerts(d,[member(10000,6500)],'2026-11-09')=={}
        # Any amount (e.g. 200) must now work without 5k or 10k special cases.
        assert v33_sync_position_alerts(d,[member(200,260)],'2026-11-09')['id-a']['suggest_cents']==20000
        assert v33_sync_position_alerts(d,[member(200,259.99)],'2026-11-09')=={}

def test_zero_stake_no_warning_and_closed_previous_alert():
    db=make_db()
    with db.begin() as d:
        assert 'id-a' in v33_sync_position_alerts(d,[member(100,140)],'2026-11-09')
        assert v33_sync_position_alerts(d,[member(0,999)],'2026-11-09')=={}
        assert d.execute(text("SELECT active FROM position_alert_state WHERE account='a'")).scalar()==0

def test_all_levels_stake_remains_manually_validated():
    db=make_db()
    with db.begin() as d:
        for id_,acct,parent in [
            ('root','ROOT',None),
            ('child','CHILD','root'),
            ('third','THIRD','child'),
            ('fourth','FOURTH','third')]:
            d.execute(text("INSERT INTO members(id,account,parent_id,deleted) VALUES(:i,:a,:p,0)"),
                {'i':id_,'a':acct,'p':parent})
        for parent,stake_amount in [(None,'100'),('root','5000'),('child','123.45'),('third','20000')]:
            stake=int(round(float(stake_amount)*100))
            validate_stake_for_level(d,parent,stake)
            member_in=MemberIn(account='EXAMPLE',joined_on='2026-11-09',stake=stake_amount)
            _,_,amount=validate_member(member_in)
            assert amount==stake

def test_independent_member_alerts_without_subtree_balance():
    db=make_db()
    with db.begin() as d:
        rows=[member(100,140,mid='r',account='R'),
              member(5000,4500,mid='c',account='C',parent='r'),
              member(10000,14000,mid='g',account='G',parent='c')]
        result=v33_sync_position_alerts(d,rows,'2026-11-09')
        assert set(result)=={'r','g'}
        assert result['r']['suggest_cents']==10000
        assert result['g']['suggest_cents']==1000000
        assert result['r']['warn_cents']==13000
        assert result['g']['warn_cents']==1300000
