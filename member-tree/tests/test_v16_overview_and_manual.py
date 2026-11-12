"""V16 homepage totals, audited manual report overlays, cross-admin conflict."""
import importlib, os, json, tempfile
from pathlib import Path
from fastapi.testclient import TestClient


def test_report_overlays_never_modify_member_balances():
    with tempfile.TemporaryDirectory() as td:
        os.environ.update({'DATABASE_URL':'sqlite:///'+str(Path(td)/'t.db'),'SECURE_COOKIE':'0','SESSION_SECRET':'unique-safe-v16-test-only-secret'})
        import app
        os.environ['ADMIN_USERS_JSON']=json.dumps({'admin01':app.hash_pw('12345678'), 'admin02':app.hash_pw('87654321')})
        os.environ['VIEWER_PASSWORD_HASH']=app.hash_pw('viewer123')
        importlib.reload(app)
        old=app.current_day
        app.current_day=lambda:'2026-11-05'
        try:
            with TestClient(app.app) as c:
                auth=c.post('/api/login',json={'role':'admin','username':'admin01','password':'12345678'})
                assert auth.status_code==200,auth.text
                header={'X-CSRF-Token':auth.json()['csrf']}
                for account, parent, stake in [('01',None,'10000'),('02',None,'20000'),('A','01','5000')]:
                    result=c.post('/api/members',headers=header,json={'account':account,'parent_account':parent,'joined_on':'2026-11-05','stake':stake})
                    assert result.status_code==200,result.text
                before=c.get('/api/tree').json()
                report=c.get('/api/reports?month=2026-11&group=all').json()
                g01=next(x for x in report['overview'] if x['group_account']=='01')
                total=next(x for x in report['overview'] if x['group_account']=='__ALL__')
                assert g01['new_stake_cents']==1500000
                assert total['new_stake_cents']==3500000
                # Yesterday's records remain manually adjustable; today's live totals must not be overridden.
                app.current_day=lambda:'2026-11-06'
                override={'day':'2026-11-05','group':'01','expected_updated_at':'',
                          'values':{'member_count':'2','new_count':'2','new_stake_cents':'16000','withdraw_cents':'500','balance_cents':'25000'}}
                save=c.put('/api/admin/reports/override',headers=header,json=override)
                assert save.status_code==200,save.text
                report=c.get('/api/reports?month=2026-11&group=all&day=2026-11-05').json()
                group=next(x for x in report['overview'] if x['group_account']=='01')
                grand=next(x for x in report['overview'] if x['group_account']=='__ALL__')
                assert group['is_manual'] and group['new_stake_cents']==1600000 and group['withdraw_cents']==50000
                assert grand['new_stake_cents']==3600000 and grand['withdraw_cents']==50000
                assert grand['profit_cents']==3550000
                assert [{k:m[k] for k in ('id','account','joined_on','stake_cents','balance_cents','total_withdraw_cents','daily_withdraw_cents','parent_id','remark')} for m in c.get('/api/tree').json()['members']]==[{k:m[k] for k in ('id','account','joined_on','stake_cents','balance_cents','total_withdraw_cents','daily_withdraw_cents','parent_id','remark')} for m in before['members']]
                # Same browser with stale revision cannot overwrite someone else's edit
                assert c.put('/api/admin/reports/override',headers=header,json=override).status_code==409
                # The encrypted production backup payload contains these corrections.
                backup=c.get('/api/admin/backup').json()['state']
                assert len(backup['report_overrides'])==1
                assert c.post('/api/admin/restore',headers=header,json={'confirm':'RESTORE_WITH_BACKUP','state':backup}).status_code==200
                again=c.get('/api/reports?month=2026-11&group=all&day=2026-11-05').json()
                assert next(x for x in again['overview'] if x['group_account']=='01')['new_stake_cents']==1600000
                # Read-only role cannot change the report.
                viewer=c.post('/api/login',json={'role':'viewer','password':'viewer123','username':''})
                assert viewer.status_code==200
                assert c.put('/api/admin/reports/override',headers={'X-CSRF-Token':viewer.json()['csrf']},json=override).status_code==403
                # Re-login as administrator to reset the overlay.
                admin=c.post('/api/login',json={'role':'admin','username':'admin02','password':'87654321'})
                header={'X-CSRF-Token':admin.json()['csrf']}
                corrected=next(r for r in c.get('/api/reports?month=2026-11&group=01').json()['daily'] if r['business_day']=='2026-11-05')
                reset=c.request('DELETE','/api/admin/reports/override',headers=header,json={'day':'2026-11-05','group':'01','expected_updated_at':corrected['manual_updated_at']})
                assert reset.status_code==200,reset.text
                reverted=next(r for r in c.get('/api/reports?month=2026-11&group=01').json()['daily'] if r['business_day']=='2026-11-05')
                assert not reverted['is_manual'] and reverted['new_stake_cents']==1500000
                assert [{k:m[k] for k in ('id','account','joined_on','stake_cents','balance_cents','total_withdraw_cents','daily_withdraw_cents','parent_id','remark')} for m in c.get('/api/tree').json()['members']]==[{k:m[k] for k in ('id','account','joined_on','stake_cents','balance_cents','total_withdraw_cents','daily_withdraw_cents','parent_id','remark')} for m in before['members']]
        finally:
            app.current_day=old
            for k in ('ADMIN_USERS_JSON','VIEWER_PASSWORD_HASH'):os.environ.pop(k,None)
