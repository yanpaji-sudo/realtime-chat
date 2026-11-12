"""Password rotation must affect only admin04 and revoke old admin04 sessions."""
import importlib, os, tempfile, json
from pathlib import Path
from fastapi.testclient import TestClient

def test_admin04_only_password_override_and_cookie_revocation():
    with tempfile.TemporaryDirectory() as d:
        os.environ['DATABASE_URL'] = 'sqlite:///'+str(Path(d)/'test.db')
        os.environ['SESSION_SECRET'] = 'admin04-specific-rotation-test-session-secret-2026'
        os.environ['SECURE_COOKIE'] = '0'
        os.environ.pop('ADMIN04_PASSWORD_HASH',None)
        import app as m
        importlib.reload(m)
        old_accounts={f'admin{i:02d}':m.hash_pw(f'unchanged-original-{i}') for i in range(1,9)}
        os.environ['ADMIN_USERS_JSON']=json.dumps(old_accounts)
        os.environ['VIEWER_PASSWORD_HASH']=m.hash_pw('viewer-pass')
        importlib.reload(m)
        stale=TestClient(m.app);stale.__enter__()
        try:
            old=stale.post('/api/login',json={'role':'admin','username':'admin04','password':'unchanged-original-4'})
            assert old.status_code==200,old.text
            assert stale.get('/api/tree').status_code==200
            os.environ['ADMIN04_PASSWORD_HASH']=m.hash_pw('new-strong-private-password')
            importlib.reload(m)
            # Old signed sessions must be refused after password rotation.
            assert stale.get('/api/tree').status_code==401
            assert stale.post('/api/login',json={'role':'admin','username':'admin04','password':'unchanged-original-4'}).status_code==401
            good=stale.post('/api/login',json={'role':'admin','username':'admin04','password':'new-strong-private-password'})
            assert good.status_code==200,good.text
            assert stale.get('/api/tree').status_code==200
            for i in [1,2,3,5,6,7,8]:
                c=TestClient(m.app)
                ans=c.post('/api/login',json={'role':'admin','username':f'admin{i:02d}','password':f'unchanged-original-{i}'})
                assert ans.status_code==200,(i,ans.text)
        finally:
            stale.__exit__(None,None,None)
            os.environ.pop('ADMIN04_PASSWORD_HASH',None)
            os.environ.pop('ADMIN_USERS_JSON',None)
