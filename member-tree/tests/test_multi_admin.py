import importlib, tempfile, os, json
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import text


def test_eight_distinct_admins_remark_level_and_concurrent_edits():
    with tempfile.TemporaryDirectory() as d:
        os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(d) / 'test.db')
        os.environ['SESSION_SECRET'] = 'test-multi-admin-unique-session-key-012345'
        os.environ['SECURE_COOKIE'] = '0'
        import app as module
        importlib.reload(module)
        os.environ['ADMIN_USERS_JSON'] = json.dumps({f'admin{i:02d}':module.hash_pw(f'private-{i}-long-test-pass') for i in range(1,9)})
        os.environ['VIEWER_PASSWORD_HASH'] = module.hash_pw('safe-viewer-test-password')
        importlib.reload(module)
        clients=[]
        try:
            for i in range(1,9):
                c=TestClient(module.app)
                c.__enter__()
                login=c.post('/api/login',json={'role':'admin','username':f'admin{i:02d}','password':f'private-{i}-long-test-pass'})
                assert login.status_code==200,login.text
                assert login.json()['username']==f'admin{i:02d}'
                clients.append((c,{'x-csrf-token':login.json()['csrf']}))
            c,h=clients[0]
            j={'account':'ROOT001','joined_on':'2026-11-05','stake':'10000','total_withdraw':'50','remark':'重点跟进'}
            r=c.post('/api/members',headers=h,json=j)
            assert r.status_code==200,r.text
            root=r.json()['id']
            j2={'account':'CHILD01','joined_on':'2026-11-05','stake':'5000','total_withdraw':'200','parent_account':'ROOT001','remark':'已回访'}
            r2=clients[1][0].post('/api/members',headers=clients[1][1],json=j2)
            assert r2.status_code==200,r2.text
            data={m['account']:m for m in c.get('/api/tree').json()['members']}
            assert data['ROOT001']['level']==1
            assert data['CHILD01']['level']==2
            assert data['ROOT001']['remark']=='重点跟进'
            assert data['CHILD01']['remark']=='已回访'
            assert data['ROOT001']['subtree_stake_cents']==1500000
            # Separate sessions see the same live DB and totals.
            assert len(clients[7][0].get('/api/tree').json()['members'])==2
            initial=data['ROOT001']['revision']
            update={**j,'remark':'备注已更新','expected_revision':initial}
            ok=clients[2][0].put('/api/members/'+root,headers=clients[2][1],json=update)
            assert ok.status_code==200,ok.text
            # Administrator 4 opened the same stale version; do not silently lose edits.
            stale=clients[3][0].put('/api/members/'+root,headers=clients[3][1],json={**j,'remark':'覆盖别人的内容','expected_revision':initial})
            assert stale.status_code==409,stale.text
            # Validation of >20 chars on the server even if JS is bypassed.
            too_long=clients[4][0].post('/api/members',headers=clients[4][1],json={**j,'account':'BAD999','remark':'一'*21})
            assert too_long.status_code==422
            with module.engine.connect() as db:
                audit_rows=db.execute(text('SELECT event, detail FROM audit_logs WHERE event IN (\'create\',\'update\')')).all()
                assert len(audit_rows)==3
                assert any('admin03' in row[1] for row in audit_rows)
            # Guest and wrong password rejected; viewer may not modify.
            unknown=clients[5][0].post('/api/login',json={'role':'admin','username':'admin99','password':'private-6-long-test-pass'})
            assert unknown.status_code==401
            v=TestClient(module.app);v.__enter__()
            try:
                log=v.post('/api/login',json={'role':'viewer','password':'safe-viewer-test-password'}).json()
                assert v.post('/api/members',headers={'x-csrf-token':log['csrf']},json=j).status_code==403
            finally:
                v.__exit__(None,None,None)
            js=(Path(__file__).resolve().parent.parent/'static/app.js').read_text()
            assert 'remark-tag' in js and 'level-tag' in js
            assert 'editRemark' in js and 'loginUsername' in js
            assert 'expected_revision' in js
        finally:
            for c,h in clients:c.__exit__(None,None,None)
            os.environ.pop('ADMIN_USERS_JSON',None)
