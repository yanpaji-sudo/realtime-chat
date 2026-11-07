from pathlib import Path
p=Path('member-tree/app.py')
s=p.read_text(encoding='utf-8')
def swap(txt,a,b,label):
    n=txt.count(a)
    if n!=1: raise RuntimeError(f"{label}: expected exactly one occurrence, got {n}")
    return txt.replace(a,b,1)

schema='        db.execute(text("CREATE TABLE IF NOT EXISTS team_names (member_id TEXT PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT NOT NULL)"))'
s=swap(s,schema,schema+'''
        # V33: small, independent status log. Existing member/finance tables unchanged.
        db.execute(text("""CREATE TABLE IF NOT EXISTS position_alert_state (
            account TEXT PRIMARY KEY,opened_on TEXT NOT NULL,closed_on TEXT,
            active INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL)"""))
'''.rstrip(),'schema')

helper='''
# V33 position display is not an instruction or authorization to move money.
def v33_position_limits(stake_cents,direct_count):
    stake=int(stake_cents or 0)
    direct=int(direct_count or 0)
    if stake==500000:
        # 5000 stake: warning above 7500; the suggested amount still targets 7000.
        return 750000,700000,750000
    if stake<=1000000:
        # 10000 stake (and <5000 as previously requested): warn at 15000;
        # suggest a reduction to 13000, and remain open until <=13000.
        return 1500000,1300000,1300000
    # Other larger stake sizes continue their pre-V33 behavior.
    limit=2000000 if direct>=5 else 1300000
    return limit,limit,limit

def v33_sync_position_alerts(db,rows,day):
    counts={}
    for r in rows:
        parent=r.get('parent_id')
        if parent:counts[parent]=counts.get(parent,0)+1
    previous={x['account']:dict(x) for x in
         db.execute(text("SELECT account,opened_on,closed_on,active,updated_at FROM position_alert_state")).mappings()}
    results={}
    for r in rows:
        account=str(r['account']).casefold()
        balance=int(r.get('balance_cents') or 0)
        warn,target,clear=v33_position_limits(r.get('stake_cents',0),counts.get(r['id'],0))
        old=previous.get(account)
        # A warning remains active while a 10000 stake moves from >15000 down
        # toward 13000; it does not disappear at the warning trigger.
        if old and int(old['active'])==1:
            if balance<=clear:
                db.execute(text("""UPDATE position_alert_state
                    SET active=0,closed_on=:day,updated_at=:stamp WHERE account=:account"""),
                    {'day':day,'stamp':utc_now(),'account':account})
                continue
            opened=old['opened_on']
        elif balance>warn:
            opened=day
            db.execute(text("""INSERT INTO position_alert_state
              (account,opened_on,closed_on,active,updated_at)
              VALUES (:account,:opened,NULL,1,:stamp)
              ON CONFLICT(account) DO UPDATE SET
              opened_on=excluded.opened_on,closed_on=NULL,
              active=1,updated_at=excluded.updated_at"""),
              {'account':account,'opened':opened,'stamp':utc_now()})
        else:
            continue
        # Account-based identity keeps the age stable if a backup changes member IDs.
        elapsed=max(0,(date.fromisoformat(day)-date.fromisoformat(opened)).days)
        results[r['id']]={
          'started_on':opened,'elapsed_days':elapsed,'overdue_days':max(0,elapsed-3),
          'remaining_days':max(0,3-elapsed),'warn_cents':warn,
          'target_cents':target,'clear_cents':clear,
          'suggest_cents':max(0,balance-target)
        }
    return results

def v33_capture_team_names(db):
    return [dict(r) for r in db.execute(text("""
        SELECT m.account AS account,t.name AS name,t.updated_at AS updated_at
        FROM team_names t JOIN members m ON m.id=t.member_id
        WHERE m.deleted=0 AND t.name<>''""")).mappings().all()]

def v33_restore_team_names(db,retained):
    # Missing labels after a full restore are restored by account, never by an
    # old UUID. Labels explicitly present in the backup are authoritative.
    rows=db.execute(text("SELECT id,account FROM members WHERE deleted=0")).mappings().all()
    account_to_id={str(r['account']).casefold():r['id'] for r in rows}
    for r in retained:
        mid=account_to_id.get(str(r['account']).casefold())
        if not mid: continue
        db.execute(text("""INSERT INTO team_names(member_id,name,updated_at)
          VALUES (:id,:name,:updated)
          ON CONFLICT(member_id) DO NOTHING"""),
          {'id':mid,'name':r['name'],'updated':r['updated_at']})
'''
s=swap(s,"@app.get('/api/tree')",helper+"\n@app.get('/api/tree')",'v33 helpers')
start=s.index("@app.get('/api/tree')")
stop=s.index("\ndef cents(",start)
chunk=s[start:stop]
chunk=swap(chunk,"        rows=active_rows(db)\n        events=","        rows=active_rows(db)\n        position_alerts=v33_sync_position_alerts(db,rows,day)\n        events=",'tree alerts')
chunk=swap(chunk,"return {'members':output,'totals':totals,","return {'members':output,'totals':totals,'position_alerts':position_alerts,",'tree return')
s=s[:start]+chunk+s[stop:]
# Preserve already named teams through a full backup restore (including V11
# archives without team_names). This is inside the existing atomic transaction.
start=s.index("@app.post('/api/admin/restore')")
stop=s.index("# V14: restore members",start)
chunk=s[start:stop]
chunk=swap(chunk,"        db.execute(text('DELETE FROM team_names'))","        preserved_team_names=v33_capture_team_names(db)\n        db.execute(text('DELETE FROM team_names'))",'restore backup capture labels')
chunk=swap(chunk,"        for item in report_overrides:\n            db.execute(text(","        v33_restore_team_names(db,preserved_team_names)\n        for item in report_overrides:\n            db.execute(text(",'restore backup labels')
s=s[:start]+chunk+s[stop:]
# Old CSV/XLSX recovery generates new member IDs; preserve names by account.
start=s.index("# V14: restore members")
stop=s.index("# V15 report extension",start)
chunk=s[start:stop]
chunk=swap(chunk,"        db.execute(text('DELETE FROM team_names'))","        preserved_team_names=v33_capture_team_names(db)\n        db.execute(text('DELETE FROM team_names'))",'restore legacy capture labels')
chunk=swap(chunk,"        db.execute(text(\"UPDATE reporting_meta SET value=:d WHERE name='tracking_since'\"),",
 "        v33_restore_team_names(db,preserved_team_names)\n        db.execute(text(\"UPDATE reporting_meta SET value=:d WHERE name='tracking_since'\"),",'restore legacy labels')
s=s[:start]+chunk+s[stop:]
p.write_text(s,encoding='utf-8')
Path('member-tree/tests/test_v33_alert_state.py').write_text('''
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
''',encoding='utf-8')
print('V33 backend patch added additive alarm table and team-label preservation; existing member data not changed.')
