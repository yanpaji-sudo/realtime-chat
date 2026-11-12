import importlib
import os
import tempfile
from pathlib import Path
from sqlalchemy import text
from fastapi.testclient import TestClient


def test_restart_and_read_only_ranking_do_not_change_rows():
    with tempfile.TemporaryDirectory() as t:
        os.environ['DATABASE_URL']='sqlite:///'+str(Path(t)/'members.db')
        os.environ['SECURE_COOKIE']='0'
        os.environ['SESSION_SECRET']='local-test-secret-not-production'
        import app as appmodule
        importlib.reload(appmodule)
        os.environ['ADMIN_PASSWORD_HASH']=appmodule.hash_pw('DUMMY_ADMIN')
        os.environ['VIEWER_PASSWORD_HASH']=appmodule.hash_pw('DUMMY_VIEW')
        importlib.reload(appmodule)
        with TestClient(appmodule.app) as client:
            cred=client.post('/api/login',json={'role':'admin','password':'DUMMY_ADMIN'}).json()
            headers={'x-csrf-token':cred['csrf']}
            assert client.post('/api/members',headers=headers,json={'account':'0001','joined_on':'2026-11-05','stake':'10000','total_withdraw':'125.35'}).status_code == 200
            with appmodule.engine.connect() as db:
                before=[tuple(row) for row in db.execute(text('SELECT * FROM members'))]
            appmodule.db_init() # repeated startup should not mutate member rows
            assert client.get('/api/tree').status_code == 200
            with appmodule.engine.connect() as db:
                after=[tuple(row) for row in db.execute(text('SELECT * FROM members'))]
            assert before == after
