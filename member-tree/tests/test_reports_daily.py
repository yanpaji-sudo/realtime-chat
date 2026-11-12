"""Report timeline is captured per day, never guessed for missing dates."""
import importlib, json, os, tempfile
from pathlib import Path
from fastapi.testclient import TestClient


def test_daily_group_and_monthly_comparison():
    with tempfile.TemporaryDirectory() as td:
        os.environ['DATABASE_URL']='sqlite:///'+str(Path(td)/'r.db')
        os.environ['SECURE_COOKIE']='0'
        os.environ['SESSION_SECRET']='local-long-test-secret-for-reporting'
        import app as module
        os.environ['ADMIN_USERS_JSON']=json.dumps({'admin01':module.hash_pw('testpass')})
        os.environ['VIEWER_PASSWORD_HASH']=module.hash_pw('viewpass')
        importlib.reload(module)
        orig=module.current_day
        module.current_day=lambda:'2026-11-04'
        try:
            with TestClient(module.app) as c:
                login=c.post('/api/login',json={'role':'admin','username':'admin01','password':'testpass'})
                assert login.status_code==200,login.text
                h={'X-CSRF-Token':login.json()['csrf']}
                def add(account,parent,day,stake='10000'):
                    r=c.post('/api/members',headers=h,json={'account':account,'parent_account':parent,'joined_on':day,'stake':stake})
                    assert r.status_code==200,r.text
                add('01',None,'2026-11-01')
                add('02',None,'2026-11-01')
                add('A','01','2026-11-04','5000')
                add('B','02','2026-11-04','10000')
                report=c.get('/api/reports?month=2026-11&group=all')
                assert report.status_code==200,report.text
                data=report.json()
                group01=next(x for x in data['overview'] if x['group_account']=='01')
                group02=next(x for x in data['overview'] if x['group_account']=='02')
                allrow=next(x for x in data['overview'] if x['group_account']=='__ALL__')
                assert (group01['member_count'],group01['new_count'],group01['new_stake_cents'])==(2,1,500000)
                assert (group02['member_count'],group02['new_count'],group02['new_stake_cents'])==(2,1,1000000)
                assert (allrow['member_count'],allrow['new_count'],allrow['new_stake_cents'])==(4,2,1500000)
                assert allrow['count_change'] is None  # No Nov 3 end-of-day snapshot: no invention.
                assert data['daily'][0]['status']=='未记录'
                assert data['daily'][3]['status']=='今日实时'
                # Simulate new business day and deposit; yesterday is now an observed sample.
                module.current_day=lambda:'2026-11-05'
                add('C','01','2026-11-05','5000')
                next_day=c.get('/api/reports?month=2026-11&group=01').json()
                today=next_day['daily'][-1]
                assert today['member_count']==3 and today['count_change']==1
                assert today['new_stake_cents']==500000
                assert today['monthly_profit_cents'] is None
                assert next_day['daily'][1]['status']=='未记录'
                full=c.get('/api/reports/export.xlsx?month=2026-11&group=all')
                assert full.status_code==200 and full.content.startswith(b'PK')
                # Encrypted backup payload must include the daily report snapshots.
                backup=c.get('/api/admin/backup').json()['state']
                assert len(backup['report_snapshots'])>=3
                # Original rows are untouched by the read-only report derivations.
                assert len(c.get('/api/tree').json()['members'])==5
                restore=c.post('/api/admin/restore',headers=h,json={'confirm':'RESTORE_WITH_BACKUP','state':backup})
                assert restore.status_code==200,restore.text
                assert len(c.get('/api/admin/backup').json()['state']['report_snapshots'])==len(backup['report_snapshots'])
        finally:
            module.current_day=orig
            for k in ('ADMIN_USERS_JSON','VIEWER_PASSWORD_HASH'):
                os.environ.pop(k,None)
