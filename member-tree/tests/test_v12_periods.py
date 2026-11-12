"""V12 regression tests: daily history, weekly/monthly aggregation, undo and encrypted backup state."""
import importlib, json, os, tempfile
from pathlib import Path
from fastapi.testclient import TestClient


def test_history_snapshots_undo_and_restore():
    with tempfile.TemporaryDirectory() as td:
        os.environ['DATABASE_URL']='sqlite:///'+str(Path(td)/'members.db')
        os.environ['SECURE_COOKIE']='0'
        os.environ['SESSION_SECRET']='this-is-a-long-test-only-password-secret'
        import app
        os.environ['ADMIN_USERS_JSON']=json.dumps({f'admin{i:02d}':app.hash_pw('test-'+str(i)) for i in range(1,9)})
        os.environ['VIEWER_PASSWORD_HASH']=app.hash_pw('testviewer')
        importlib.reload(app)
        real_day=app.current_day
        real_datetime=app.datetime
        app.current_day=lambda:'2026-11-05'
        # Align simulated timestamps with the simulated Beijing business day;
        # the import endpoint rightly rejects real 2026-11-06 vs test 2026-11-05.
        class TestDateTime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                val=real_datetime.fromisoformat(app.current_day()+'T12:00:00+08:00')
                return val.astimezone(tz) if tz else val.replace(tzinfo=None)
        app.datetime=TestDateTime
        try:
            with TestClient(app.app) as c:
                login=c.post('/api/login',json={'role':'admin','username':'admin01','password':'test-1'})
                assert login.status_code==200,login.text
                h={'X-CSRF-Token':login.json()['csrf']}
                def add(account,parent,when,stake='5000'):
                    r=c.post('/api/members',headers=h,json={'account':account,'parent_account':parent,'joined_on':when,'stake':stake})
                    assert r.status_code==200,r.text
                add('A',None,'2026-11-01','10000')
                add('B','A','2026-11-02')
                add('C','B','2026-11-05')
                def imported(data):
                    p=c.post('/api/import/preview',headers=h,data={'mode':'daily','content':data}).json()
                    assert p['valid'],p
                    r=c.post('/api/import/'+p['job_id']+'/confirm',headers=h)
                    assert r.status_code==200,r.text
                imported('B 100\nC 50')
                r=c.get('/api/tree').json()
                by={x['account']:x for x in r['members']}
                assert by['B']['week_withdraw_cents']==10000
                assert by['B']['month_withdraw_cents']==10000
                assert by['C']['week_withdraw_cents']==5000
                assert r['history_coverage']['imported_days']==['2026-11-05']
                assert r['history_coverage']['tracking_since']=='2026-11-05'
                state=c.get('/api/admin/backup').json()['state']
                assert len(state['withdrawals'])==2
                assert state['import_days']==['2026-11-05']
                # New date changes today's display, but retains previous date in weekly/monthly history.
                app.current_day=lambda:'2026-11-06'
                assert all(x['daily_withdraw_cents']==0 for x in c.get('/api/tree').json()['members'])
                imported('B 200')
                by={x['account']:x for x in c.get('/api/tree').json()['members']}
                assert by['B']['week_withdraw_cents']==30000
                assert by['B']['month_withdraw_cents']==30000
                assert by['B']['daily_withdraw_cents']==20000
                imported('B 180')
                by={x['account']:x for x in c.get('/api/tree').json()['members']}
                assert by['B']['week_withdraw_cents']==28000
                assert by['B']['total_withdraw_cents']==10000
                undo=c.get('/api/admin/undo/status').json()
                assert undo['can_undo']
                result=c.post('/api/admin/undo',headers=h,json={'action_id':undo['action_id']})
                assert result.status_code==200,result.text
                by={x['account']:x for x in c.get('/api/tree').json()['members']}
                assert by['B']['week_withdraw_cents']==30000
                assert by['B']['total_withdraw_cents']==10000
                # Restore legacy/new backups atomically, including original history.
                restored=c.post('/api/admin/restore',headers=h,json={'state':state,'confirm':'RESTORE_WITH_BACKUP'})
                assert restored.status_code==200,restored.text
                now=c.get('/api/tree').json()
                assert {x['account']:x['month_withdraw_cents'] for x in now['members']}['B']==10000
                assert now['history_coverage']['imported_days']==['2026-11-05']
                assert len(c.get('/api/admin/backup').json()['state']['withdrawals'])==2
        finally:
            app.datetime=real_datetime
            app.current_day=real_day
            os.environ.pop('ADMIN_USERS_JSON',None)
            os.environ.pop('VIEWER_PASSWORD_HASH',None)
