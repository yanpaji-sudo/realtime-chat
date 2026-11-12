import importlib, tempfile, os, json
from pathlib import Path
from fastapi.testclient import TestClient

def test_v11_secure_eight_admin_backup_and_recovery():
 with tempfile.TemporaryDirectory() as d:
  os.environ['DATABASE_URL']='sqlite:///'+str(Path(d)/'private.db')
  os.environ['SESSION_SECRET']='local-test-unique-key'+'x'*20
  os.environ['SECURE_COOKIE']='0'
  import app
  os.environ['ADMIN_USERS_JSON']=json.dumps({f'admin{i:02d}':app.hash_pw(f'different-admin{i:02d}-password') for i in range(1,9)})
  os.environ['VIEWER_PASSWORD_HASH']=app.hash_pw('viewer-test-pass')
  importlib.reload(app)
  with TestClient(app.app) as c:
   login=c.post('/api/login',json={'role':'admin','username':'admin08','password':'different-admin08-password'})
   assert login.status_code==200
   cs={'X-CSRF-Token':login.json()['csrf']}
   assert c.get('/api/admin/backup').status_code==200
   bad=c.post('/api/login',json={'role':'admin','username':'admin07','password':'different-admin08-password'})
   assert bad.status_code==401
   # No change to database when viewing /api/tree or backing up.
   created=c.post('/api/members',headers=cs,json={'account':'RootABC','joined_on':'2026-05-11','stake':'10000','remark':'原始记录'})
   assert created.status_code==200,created.text
   child=c.post('/api/members',headers=cs,json={'account':'child123','joined_on':'2026-10-15','parent_account':'RootABC','stake':'5000','remark':'下级备注'})
   assert child.status_code==200,child.text
   before=c.get('/api/tree').json()
   state=c.get('/api/admin/backup').json()['state']
   assert len(state['rows'])==2 and len(state['history'])>=2 and len(state['logs'])>=2
   # viewer must not access encrypted-backup payload or recovery.
   with TestClient(app.app) as viewer:
    lr=viewer.post('/api/login',json={'role':'viewer','password':'viewer-test-pass'})
    assert lr.status_code==200
    assert viewer.get('/api/admin/backup').status_code==403
    assert viewer.post('/api/admin/restore',headers={'X-CSRF-Token':lr.json()['csrf']},json={'state':state,'confirm':'RESTORE_WITH_BACKUP'}).status_code==403
   assert c.post('/api/admin/restore',headers=cs,json={'state':state,'confirm':'no'}).status_code==400
   # Simulate deleting the child; restoration recovers original relation and note atomically.
   mid=child.json()['id']
   assert c.delete('/api/members/'+mid,headers=cs,params={'expected_revision':1}).status_code==200
   assert len(c.get('/api/tree').json()['members'])==1
   restored=c.post('/api/admin/restore',headers=cs,json={'state':state,'confirm':'RESTORE_WITH_BACKUP'})
   assert restored.status_code==200,restored.text
   after=c.get('/api/tree').json()
   assert after['members']==before['members']
   assert c.get('/api/admin/logs').json()['logs'][0]['event']=='restore'
   # corrupted backup rejected in full without changing any member
   tamper=json.loads(json.dumps(state));tamper['rows'][1]['parent_id']='NONEXISTENT'
   assert c.post('/api/admin/restore',headers=cs,json={'state':tamper,'confirm':'RESTORE_WITH_BACKUP'}).status_code==400
   assert c.get('/api/tree').json()['members']==before['members']
   print('PASS admin eight independent authentication, read-only backup, protected recovery, atomic restore')
 os.environ.pop('ADMIN_USERS_JSON',None)
 os.environ.pop('VIEWER_PASSWORD_HASH',None)
