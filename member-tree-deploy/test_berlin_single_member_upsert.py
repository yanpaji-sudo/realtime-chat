"""Regression: Berlin single-member + button accepts existing accounts as overwrite.
Uses isolated temporary SQLite, never the user's Render database.
"""
import os, sys, tempfile, uuid, subprocess
from datetime import date, timedelta
from pathlib import Path
from sqlalchemy import text
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as folder:
    os.environ['DATABASE_URL']='sqlite:///'+folder+'/single_upsert_test.sqlite'
    os.environ['ENABLE_MIDNIGHT_WORKER']='0'
    sys.path.insert(0,'member-tree')
    import app as a
    a.require=lambda req,role='viewer',mutation=False:{'role':'admin','username':'single_upsert_test'}
    a.db_init()
    today=a.current_day()
    older=(date.fromisoformat(today)-timedelta(days=2)).isoformat()
    root_id,child_id,unlisted_id=[str(uuid.uuid4()) for _ in range(3)]
    with a.engine.begin() as db:
        for mid,acct,par,amount,withdraw,balance,remark in [
            (root_id,'root700',None,1100000,0,1230000,'原上级'),
            (child_id,'user900',root_id,500000,10000,777000,'原会员'),
            (unlisted_id,'someone_else',root_id,123400,2000,345600,'其他账号')]:
            db.execute(text("""INSERT INTO members
             (id,account,joined_on,parent_id,stake_cents,total_withdraw_cents,
              balance_cents,daily_withdraw_cents,remark,created_at,updated_at)
             VALUES (:id,:a,:j,:p,:s,:w,:b,1700,:r,:now,:now)"""),
             {'id':mid,'a':acct,'j':older,'p':par,'s':amount,'w':withdraw,
              'b':balance,'r':remark,'now':a.utc_now()})
    def get(account):
        with a.engine.connect() as db:
            return dict(db.execute(text('SELECT * FROM members WHERE lower(account)=lower(:a)'),
                    {'a':account}).mappings().first())
    def count():
        with a.engine.connect() as db:
            return db.execute(text('SELECT COUNT(*) FROM members')).scalar()
    existing=get('user900')
    with TestClient(a.app) as client:
        payload={'account':'user900','joined_on':today,'parent_account':'root700',
                 'stake':'8500','total_withdraw':'250.50','remark':'单个覆盖',
                 'expected_revision':existing['revision']}
        r=client.post('/api/members',json=payload)
        assert r.status_code==200,r.text
        assert r.json()['mode']=='updated' and r.json()['id']==child_id,r.text
        now=get('user900')
        assert count()==3 and now['id']==child_id
        assert now['joined_on']==today and now['parent_id']==root_id
        assert now['stake_cents']==850000 and now['total_withdraw_cents']==25050
        assert now['remark']=='单个覆盖'
        assert now['balance_cents']==777000 and now['daily_withdraw_cents']==1700
        assert get('someone_else')['stake_cents']==123400
        # Last saved version wins; same account keeps same ID and no duplicate.
        payload.update({'stake':'9000','remark':'再次保存最新资料','expected_revision':now['revision']})
        r=client.post('/api/members',json=payload)
        assert r.status_code==200 and r.json()['mode']=='updated',r.text
        updated=get('user900')
        assert updated['stake_cents']==900000 and updated['remark']=='再次保存最新资料'
        assert updated['id']==child_id and count()==3
        # Reject stale submit rather than silently overwriting other admins.
        payload.update({'stake':'10000','expected_revision':existing['revision']})
        r=client.post('/api/members',json=payload)
        assert r.status_code==409,r.text
        assert get('user900')['stake_cents']==900000
        # Reject a tree cycle created through the + overwrite action.
        cycle={'account':'root700','joined_on':older,'parent_account':'user900',
               'stake':'10000','total_withdraw':'0','remark':'坏的关系'}
        r=client.post('/api/members',json=cycle)
        assert r.status_code==400 and '自己或下级' in r.text,r.text
        assert get('root700')['parent_id'] is None
        # Ordinary new-account creation remains exactly usable.
        added={'account':'fresh_new901','joined_on':today,'parent_account':'user900',
               'stake':'10000','total_withdraw':'0','remark':'正常新增'}
        r=client.post('/api/members',json=added)
        assert r.status_code==200 and r.json()['mode']=='created',r.text
        assert get('fresh_new901')['parent_id']==child_id and count()==4
        assert get('user900')['balance_cents']==777000
    ui=Path('member-tree/static/app.js').read_text(encoding='utf-8')
    assert '新增会员 / 覆盖已有账号' in ui
    assert "response.mode==='updated'" in ui
    assert '保存将覆盖' in ui
    subprocess.run(['node','--check','member-tree/static/app.js'],check=True)
    print('PASS: single + member overwrite, no duplicates, keep ID/balance/daily, latest wins, stale conflict, cycle rejection, new add')

# Temporary visibility check for case-insensitive smart paste and parent selection.
source=Path('member-tree/static/app.js').read_text(encoding='utf-8')
for key in ("function smartParseMemberText(", "function smartPasteReset(", "function smartFillMember", "function smart", "function openEdit(", "function saveEdit(", "function search", "editParentAccount", "parentAccounts", "sgz7750"):
 idx=source.find(key)
 print("===CASE_INSPECT===" + key + "@" + str(idx),flush=True)
 if idx>=0:print(source[max(0,idx-450):idx+4500],flush=True)
import inspect
print('===PARENT_IMPL===',inspect.getsource(a.resolved_parent),flush=True)
