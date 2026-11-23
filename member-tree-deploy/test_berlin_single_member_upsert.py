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

        # All-case variants of a known parent are the same member.
        r=client.post('/api/members',json={
          'account':'SGR771','joined_on':today,'parent_account':'ROOT700',
          'stake':'10000','total_withdraw':'0','remark':'大写新会员'})
        assert r.status_code==200 and r.json()['mode']=='created',r.text
        case_id=r.json()['id']
        assert get('SGR771')['parent_id']==root_id
        assert count()==5
        # Mixed case must UPDATE original member, never create duplicate, keep the original casing.
        original=get('user900')
        r=client.post('/api/members',json={
          'account':'UsEr900','joined_on':today,'parent_account':'RoOt700',
          'stake':'9550','total_withdraw':'250.50','remark':'不同大小写覆盖',
          'expected_revision':original['revision']})
        assert r.status_code==200 and r.json()['mode']=='updated' and r.json()['id']==child_id,r.text
        assert count()==5
        case_member=get('USER900')
        assert case_member['account']=='user900'
        assert case_member['balance_cents']==777000 and case_member['daily_withdraw_cents']==1700
        # Existing member editing likewise treats case-only spelling as same identity.
        r=client.put('/api/members/'+child_id,json={
          'account':'USER900','joined_on':today,'parent_account':'ROOT700',
          'stake':'9550','total_withdraw':'250.50','remark':'保持账号原样',
          'expected_revision':case_member['revision']})
        assert r.status_code==200,r.text
        assert get('user900')['account']=='user900'
        assert count()==5
        # The cycle guard must still work under case-insensitive parent lookups.
        r=client.post('/api/members',json={
          'account':'root700','joined_on':older,'parent_account':'sGr771',
          'stake':'10000','total_withdraw':'0','remark':'循环测试'})
        assert r.status_code==400 and '自己或下级' in r.text,r.text
        assert get('root700')['parent_id'] is None

    ui=Path('member-tree/static/app.js').read_text(encoding='utf-8')
    assert '新增会员 / 覆盖已有账号' in ui
    assert "response.mode==='updated'" in ui
    assert '保存将覆盖' in ui

    # Parse the exact 8-slash screenshot format with uppercase member and parent.
    node_test=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('member-tree/static/app.js','utf-8');
const start=src.indexOf('function smartParseMemberText(value,nowOverride)');
const stop=src.indexOf('window.smartParseMemberText=smartParseMemberText;',start);
const helper=src.indexOf('function berlinMatchMemberAccount(value)');
const helperEnd=src.indexOf('function smartPasteApply()',helper);
assert(start>=0&&stop>start&&helper>stop&&helperEnd>helper);
const ctx={window:{},members:[{account:'sgr771'},{account:'sgz7750'}]};
vm.runInNewContext(src.slice(start,stop)+'\n'+src.slice(helper,helperEnd)+'\nthis.parse=smartParseMemberText;this.canonical=berlinMatchMemberAccount;',ctx);
const parsed=ctx.parse('09.25/宋桂荣/SGR771/69/女/13945331241/黑龙江/SGZ7750','2026-11-23');
assert.strictEqual(parsed.account,'SGR771');
assert.strictEqual(parsed.parent_account,'SGZ7750');
assert.strictEqual(parsed.joined_on,'2026-09-25');
assert.strictEqual(ctx.canonical(parsed.account)?.account,'sgr771');
assert.strictEqual(ctx.canonical(parsed.parent_account)?.account,'sgz7750');
console.log('PASS: case-insensitive account/parent lookup for uppercase slash-format smart paste');
"""
    subprocess.run(['node','-e',node_test],check=True)
    subprocess.run(['node','--check','member-tree/static/app.js'],check=True)
    print('PASS: single + member overwrite, no duplicates, keep ID/balance/daily, latest wins, stale conflict, cycle rejection, new add')
