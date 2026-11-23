"""Isolated regression: Berlin balance A[account], B[blank], C[amount].
No real member or finance databases are touched. Both TSV paste and XLSX
must preserve two-column compatibility and round 3+ decimals half-up.
"""
import io,os,sys,tempfile,uuid,subprocess
from pathlib import Path
from openpyxl import Workbook
from sqlalchemy import text
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as tmp:
    os.environ['DATABASE_URL']='sqlite:///'+tmp+'/balance_tabs.sqlite'
    os.environ['ENABLE_MIDNIGHT_WORKER']='0'
    sys.path.insert(0,'member-tree')
    import app as a
    a.require=lambda req,role='viewer',mutation=False: {'role':'admin','username':'balance_blank_test'}
    a.db_init()
    today=a.current_day()
    with a.engine.begin() as db:
        for name,old in [('rjh185185',250000),('zxr516516',500),('139397',120000),('OtherAccount',123450)]:
            db.execute(text("""INSERT INTO members
                (id,account,joined_on,stake_cents,balance_cents,daily_withdraw_cents,total_withdraw_cents,created_at,updated_at)
                VALUES (:id,:name,:day,1000000,:balance,1800,7000,:now,:now)"""),
                {'id':str(uuid.uuid4()),'name':name,'day':today,'balance':old,'now':a.utc_now()})
    def get(acct):
        with a.engine.connect() as db:
            return dict(db.execute(text('SELECT * FROM members WHERE account=:a'),{'a':acct}).mappings().first())
    def preview(client,**kwargs):
        r=client.post('/api/import/preview',data={'mode':'balance','content':kwargs.get('content','')},
                 files=kwargs.get('files'))
        assert r.status_code==200,r.text
        q=r.json()
        assert q['valid'] and q['matched']==3 and q['unmatched_count']==0,q
        return q
    def confirm(client,q):
        r=client.post('/api/import/'+q['job_id']+'/confirm',json={})
        assert r.status_code==200,r.text
        return r.json()
    sample='rjh185185\t\t10000.75\nzxr516516\t\t10000.75\n139397\t\t10000.779'
    with TestClient(a.app) as client:
        q=preview(client,content=sample)
        confirm(client,q)
        assert get('rjh185185')['balance_cents']==1000075,get('rjh185185')
        assert get('zxr516516')['balance_cents']==1000075,get('zxr516516')
        assert get('139397')['balance_cents']==1000078,get('139397')
        assert get('OtherAccount')['balance_cents']==0,'Original full-snapshot semantics should persist'
        assert get('rjh185185')['daily_withdraw_cents']==1800
        assert get('rjh185185')['total_withdraw_cents']==7000
        # Identical upload must not add to balances.
        again=preview(client,content=sample)
        confirm(client,again)
        assert get('rjh185185')['balance_cents']==1000075
        # Same three-cell TSV but case-insensitive accounts and blank middle.
        q=preview(client,content='RJH185185\t\t10000.75\nZXR516516\t\t10000.75\n139397\t\t10000.779')
        confirm(client,q)
        assert get('rjh185185')['balance_cents']==1000075
        # The normal two-column input must remain accepted.
        q=preview(client,content='rjh185185\t10000.75\nzxr516516\t10000.75\n139397\t10000.779')
        confirm(client,q)
        # Header from the requested English export is optional.
        q=preview(client,content='Upload format for balance\n'+sample)
        confirm(client,q)
        # Excel three-column A/B(empty)/C uses third column, including numeric account.
        workbook=Workbook();sheet=workbook.active
        sheet.append(['会员账号',None,'余额'])
        sheet.append(['rjh185185',None,10000.75])
        sheet.append(['zxr516516',None,10000.75])
        sheet.append([139397,None,10000.779])
        buf=io.BytesIO();workbook.save(buf)
        q=preview(client,files={'upload':('balance.xlsx',buf.getvalue(),
           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        confirm(client,q)
        assert get('139397')['balance_cents']==1000078
        assert get('rjh185185')['balance_cents']==1000075
        # Old 2-column Excel must still work.
        book2=Workbook();sh2=book2.active
        sh2.append(['rjh185185',10000.75]);sh2.append(['zxr516516',10000.75]);sh2.append([139397,10000.779])
        bf=io.BytesIO();book2.save(bf)
        q=preview(client,files={'upload':('old_balance.xlsx',bf.getvalue(),
           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        confirm(client,q)
        # Invalid rows must fail preview, not partially change the database.
        r=client.post('/api/import/preview',data={'mode':'balance','content':'rjh185185\t\tNOT_MONEY'})
        assert r.status_code==400 or not r.json()['valid'],r.text
        assert get('rjh185185')['balance_cents']==1000075
    js=Path('member-tree/static/app.js').read_text(encoding='utf-8')
    assert '余额格式：账号' in js
    subprocess.run(['node','--check','member-tree/static/app.js'],check=True)
    print('PASS: Berlin balance A/account B/blank C/amount TSV XLSX 10000.779 rounding, existing 2-column, account case-insensitive, funds preserved')
