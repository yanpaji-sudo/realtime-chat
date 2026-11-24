"""Isolated Berlin finance import regression: both account/amount orders.
Simulates file uploads using temporary SQLite; never uses Render production DB.
"""
import io,os,sys,uuid,tempfile,subprocess
from pathlib import Path
from sqlalchemy import text
from fastapi.testclient import TestClient
from openpyxl import Workbook

with tempfile.TemporaryDirectory() as tmp:
    os.environ['DATABASE_URL']='sqlite:///'+tmp+'/bidirectional.sqlite'
    os.environ['ENABLE_MIDNIGHT_WORKER']='0'
    sys.path.insert(0,'member-tree')
    import app as a
    a.require=lambda req,role='viewer',mutation=False:{'role':'admin','username':'bidirectional_test'}
    a.db_init()
    today=a.current_day()
    with a.engine.begin() as db:
        for account in ['rjh185185','zxr516516','139397','Another1']:
            db.execute(text("""INSERT INTO members(
               id,account,joined_on,stake_cents,balance_cents,
               total_withdraw_cents,created_at,updated_at)
               VALUES(:id,:a,:day,100000,12000,0,:now,:now)"""),
               {'id':str(uuid.uuid4()),'a':account,'day':'2025-10-01','now':a.utc_now()})
    def member(account):
        with a.engine.connect() as db:
            row=db.execute(text('SELECT * FROM members WHERE lower(account)=lower(:a)'),
                       {'a':account}).mappings().first()
            return dict(row)
    def book(rows):
        wb=Workbook()
        for values in rows:wb.active.append(values)
        data=io.BytesIO();wb.save(data)
        return data.getvalue()
    def approve(client,mode,content='',files=None):
        endpoint='/api/recharge/preview' if mode=='recharge' else '/api/import/preview'
        form={'content':content}
        if mode!='recharge':form['mode']=mode
        resp=client.post(endpoint,data=form,files=files)
        assert resp.status_code==200,resp.text
        q=resp.json()
        assert q['valid'] and q['unmatched_count']==0,q
        job=q['job_id']
        dst=('/api/recharge/'+job+'/confirm' if mode=='recharge' else
             '/api/import/'+job+'/confirm')
        done=client.post(dst,json={})
        assert done.status_code==200,done.text
        return q,done.json()

    with TestClient(a.app) as client:
        # Account first, amount first, account number and comma thousands.
        q,_=approve(client,'balance',
            'rjh185185 10000.75\n10000.75 zxr516516\n10000.779 139397')
        assert q['matched']==3,q
        assert member('rjh185185')['balance_cents']==1000075
        assert member('zxr516516')['balance_cents']==1000075
        assert member('139397')['balance_cents']==1000078
        assert member('Another1')['balance_cents']==0
        # Full snapshot, no accumulation, 3rd-column old format still works.
        approve(client,'balance','10000.75 rjh185185\nzxr516516\t\t10000.75\n139397 10000.779')
        assert member('rjh185185')['balance_cents']==1000075
        # Reverse and standard orders can share an Excel sheet.
        rows=[['账号','余额'],[10000.75,'rjh185185'],['zxr516516',10000.75],
              [10000.779,139397]]
        q,_=approve(client,'balance',files={'upload':(
            'mixed_balance.xlsx',book(rows),
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        assert q['matched']==3,q
        assert member('139397')['balance_cents']==1000078
        # Thousands comma is part of a number, not a CSV field separator.
        approve(client,'balance','10,000.75 rjh185185\nzxr516516 10,000.75\n139397 10000.779')
        assert member('rjh185185')['balance_cents']==1000075
        # Recharges: use both directions and preserve the date + pending supplement.
        recharge='rjh185185 2500.25\n3000.779 zxr516516\n139397 100.50'
        q,out=approve(client,'recharge',recharge)
        assert q['matched']==3,q
        assert q['uploaded_cents']==250025+300078+10050,q
        def recharges():
            with a.engine.connect() as db:
                return {x['account']:int(x['daily_recharge_cents']) for x in a.active_rows(db)}
        assert recharges()['rjh185185']==250025
        assert recharges()['zxr516516']==300078
        assert recharges()['139397']==10050
        # Repeat in different order; same day's recharge snapshots are not double-counted.
        q,out=approve(client,'recharge',
            '2500.25 rjh185185\nzxr516516 3000.779\n100.50 139397')
        assert out['changed']==0,out
        # Another reverse Excel with a purely numeric account, plus account first.
        rows=[['会员账号','当日充值'],[2000,'rjh185185'],
              ['zxr516516',3000.779],[100.50,139397]]
        q,_=approve(client,'recharge',files={'upload':(
           'mixed_cash.xlsx',book(rows),
           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        assert q['matched']==3,q
        assert recharges()['rjh185185']==200000
        # Withdrawals: reversed positive means actual withdrawal, legacy
        # account-first positive remains a funds-return, negative actual payout.
        q,_=approve(client,'daily',
            '500 rjh185185\n139397 -200\nzxr516516 -250')
        assert q['matched']==3,q
        assert member('rjh185185')['daily_withdraw_cents']==50000
        assert member('139397')['daily_withdraw_cents']==20000
        assert member('zxr516516')['daily_withdraw_cents']==25000
        assert member('rjh185185')['total_withdraw_cents']==50000
        # Reverse numeric-account amount (new) and reverse alphanumeric amount (old).
        q,out=approve(client,'daily',
            'rjh185185 -500\n250 zxr516516\n200 139397')
        assert q['matched']==3 and out['withdraw_delta_cents']==0,(q,out)
        assert member('139397')['total_withdraw_cents']==20000
        # The legacy account-first positive still means returns, NOT withdrawals.
        q,_=approve(client,'daily','rjh185185 100\nzxr516516 -250\n139397 -200')
        assert member('rjh185185')['daily_withdraw_cents']==-10000
        assert member('rjh185185')['total_withdraw_cents']==-10000
        # When BOTH are real numeric account IDs, do not guess.
        with a.engine.begin() as db:
            db.execute(text("""INSERT INTO members(
                id,account,joined_on,stake_cents,created_at,updated_at)
                VALUES(:id,'500',:day,0,:now,:now)"""),
                {'id':str(uuid.uuid4()),'day':today,'now':a.utc_now()})
        conflict=client.post('/api/import/preview',data={
            'mode':'balance','content':'500 139397'})
        assert conflict.status_code==400 and '无法确定' in conflict.text,conflict.text
        assert member('139397')['balance_cents']==1000078
    subprocess.run(['node','--check','member-tree/static/app.js'],check=True)
    ui=Path('member-tree/static/app.js').read_text(encoding='utf-8')
    assert "10000.75 rjh185185" in ui
    print('PASS: mixed-direction balance, recharge, withdrawal, numeric accounts, XLSX, signed semantics, rounding, no duplicate ledger, ambiguity rejection')
