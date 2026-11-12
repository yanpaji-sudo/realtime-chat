import importlib, os, json, tempfile
from pathlib import Path
from fastapi.testclient import TestClient

def test_team_name_and_observed_low_fission_days():
    with tempfile.TemporaryDirectory() as td:
        os.environ.update({'DATABASE_URL':'sqlite:///'+str(Path(td)/'v15.db'),'SECURE_COOKIE':'0','SESSION_SECRET':'local-v15-long-session-secret'})
        import app
        os.environ['ADMIN_USERS_JSON']=json.dumps({'admin01':app.hash_pw('safepass')})
        os.environ['VIEWER_PASSWORD_HASH']=app.hash_pw('safeviewer')
        importlib.reload(app)
        prior=app.current_day
        app.current_day=lambda:'2026-11-03'
        try:
            with TestClient(app.app) as c:
                login=c.post('/api/login',json={'role':'admin','username':'admin01','password':'safepass'})
                assert login.status_code==200,login.text
                h={'X-CSRF-Token':login.json()['csrf']}
                for account,parent in [('01',None),('B','01')]:
                    r=c.post('/api/members',headers=h,json={'account':account,'parent_account':parent,'joined_on':'2026-10-10','stake':'10000'})
                    assert r.status_code==200,r.text
                r=c.get('/api/tree').json()['members']; b=next(x for x in r if x['account']=='B')
                assert b['low_fission_streak']==1
                assert c.post('/api/admin/team-name/'+b['id'],headers=h,json={'name':'先锋队'}).status_code==200
                assert next(x for x in c.get('/api/tree').json()['members'] if x['account']=='B')['team_name']=='先锋队'
                app.current_day=lambda:'2026-11-04'
                assert next(x for x in c.get('/api/tree').json()['members'] if x['account']=='B')['low_fission_streak']==2
                backup=c.get('/api/admin/backup').json()['state']
                assert backup['team_names'][0]['name']=='先锋队'
                assert len(backup['daily_fission'])==4
                assert c.post('/api/admin/restore',headers=h,json={'state':backup,'confirm':'RESTORE_WITH_BACKUP'}).status_code==200
                assert next(x for x in c.get('/api/tree').json()['members'] if x['account']=='B')['team_name']=='先锋队'
                # Viewer must never edit team labels.
                viewer=c.post('/api/login',json={'role':'viewer','password':'safeviewer','username':''}).json()
                assert c.post('/api/admin/team-name/'+b['id'],headers={'X-CSRF-Token':viewer['csrf']},json={'name':'fake'}).status_code==403
        finally:
            app.current_day=prior
            for k in ('ADMIN_USERS_JSON','VIEWER_PASSWORD_HASH'):os.environ.pop(k,None)
