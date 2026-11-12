
from sqlalchemy import create_engine,text
from app import v33_sync_position_alerts, v33_position_limits, v33_capture_team_names, v33_restore_team_names

def db():
    eng=create_engine('sqlite://')
    with eng.begin() as d:
        d.execute(text("CREATE TABLE position_alert_state(account TEXT PRIMARY KEY,opened_on TEXT,closed_on TEXT,active INTEGER,updated_at TEXT)"))
        d.execute(text("CREATE TABLE members(id TEXT PRIMARY KEY,account TEXT,deleted INTEGER)"))
        d.execute(text("CREATE TABLE team_names(member_id TEXT PRIMARY KEY,name TEXT,updated_at TEXT)"))
    return eng

def mem(mid='id1',acct='member-a',bal=0,stake=1000000,parent=None):
    return {'id':mid,'account':acct,'balance_cents':bal,'stake_cents':stake,'parent_id':parent}

def test_warning_grace_overdue_recovery_and_reopen():
    eng=db()
    with eng.begin() as d:
        a=v33_sync_position_alerts(d,[mem(bal=1600000)],'2026-11-01')['id1']
        assert a['suggest_cents']==300000 and a['overdue_days']==0
        a=v33_sync_position_alerts(d,[mem(bal=1400000)],'2026-11-06')['id1']
        assert a['started_on']=='2026-11-01' and a['overdue_days']==2
        assert v33_sync_position_alerts(d,[mem(bal=1300000)],'2026-11-06')=={}
        assert d.execute(text("SELECT active FROM position_alert_state")).scalar()==0
        a=v33_sync_position_alerts(d,[mem(bal=1520000)],'2026-11-07')['id1']
        assert a['started_on']=='2026-11-07'
        assert d.execute(text("SELECT active FROM position_alert_state")).scalar()==1

def test_5000_warning_7500_clear_and_7000_target():
    eng=db()
    with eng.begin() as d:
        a=v33_sync_position_alerts(d,[mem(bal=900000,stake=500000)],'2026-11-01')['id1']
        assert a['warn_cents']==750000 and a['target_cents']==700000 and a['suggest_cents']==200000
        assert v33_sync_position_alerts(d,[mem(bal=750000,stake=500000)],'2026-11-02')=={}

def test_10000_and_under_5000_legacy():
    assert v33_position_limits(1000000,6)==(1500000,1300000,1300000)
    assert v33_position_limits(300000,1)==(1500000,1300000,1300000)
    assert v33_position_limits(1500000,5)==(2000000,2000000,2000000)

def test_team_name_survives_uuid_reassignment_and_does_not_override_backup_name():
    eng=db()
    with eng.begin() as d:
        d.execute(text("INSERT INTO members VALUES('old','member-a',0)"))
        d.execute(text("INSERT INTO team_names VALUES('old','old-team','2026-11-01')"))
        labels=v33_capture_team_names(d)
        d.execute(text("DELETE FROM team_names"))
        d.execute(text("DELETE FROM members"))
        d.execute(text("INSERT INTO members VALUES('new','member-a',0)"))
        v33_restore_team_names(d,labels)
        assert d.execute(text("SELECT name FROM team_names WHERE member_id='new'")).scalar()=='old-team'
        d.execute(text("UPDATE team_names SET name='backup-team' WHERE member_id='new'"))
        v33_restore_team_names(d,labels)
        assert d.execute(text("SELECT name FROM team_names WHERE member_id='new'")).scalar()=='backup-team'
