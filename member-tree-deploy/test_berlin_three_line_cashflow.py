"""Isolated regression test for Berlin three-line finance upload formats.
No live Render or production database connections. Run after payload is built.
"""
import io
import os
import sys
import uuid
import tempfile
from pathlib import Path
from datetime import date, timedelta
from openpyxl import Workbook
from fastapi.testclient import TestClient
from sqlalchemy import text

with tempfile.TemporaryDirectory() as directory:
    os.environ['DATABASE_URL']='sqlite:///'+directory+'/finance_test.sqlite'
    os.environ['ENABLE_MIDNIGHT_WORKER']='0'
    sys.path.insert(0,'member-tree')
    import app as a
    a.require=lambda req,role='viewer',mutation=False:{'role':'admin','username':'test'}
    a.db_init()
    today=a.current_day()
    older=(date.fromisoformat(today)-timedelta(days=2)).isoformat()
    with a.engine.begin() as db:
        for account,joined in [('F123576',today),('hkfu258',older),('Cxy197875',older),('why66888',older),('dwz123',older)]:
            db.execute(text('''INSERT INTO members (id,account,joined_on,stake_cents,created_at,updated_at)
                               VALUES (:i,:a,:j,0,:n,:n)'''),
                       {'i':str(uuid.uuid4()),'a':account,'j':joined,'n':a.utc_now()})
    recharge='\n'.join([
        '首次存款','F123576','3000',
        '充值/更换电池','hkfu258','184.786',
        '首次存款','Cxy197875','2502.45',
        '首次存款','hkfu258','4934.885'])
    def single_column_xlsx(lines):
        book=Workbook()
        for value in lines.splitlines():
            book.active.append([value])
        buffer=io.BytesIO()
        book.save(buffer)
        return buffer.getvalue()
    with TestClient(a.app) as client:
        # User-reported simplest Chinese-label / account / integer recharge case.
        q_simple=client.post('/api/recharge/preview',data={'content':'首次充值\ndwz123\n100'}).json()
        assert q_simple['valid'] and q_simple['matched']==1 and q_simple['three_line_events']==1 and q_simple['uploaded_cents']==10000,q_simple
        # Ensure the actual shipped JavaScript routes pasted labeled transactions automatically.
        import subprocess
        subprocess.run(['node','--check','member-tree/static/app.js'],check=True)
        ui=Path('member-tree/static/app.js').read_text(encoding='utf-8')
        assert 'const clearTriplet=typedLines.length>=3' in ui
        assert '已自动识别为当日充值流水' in ui
        assert '未找到会员账号' in ui
        q_xlsx=client.post('/api/recharge/preview',files={
            'upload':('simple.xlsx',single_column_xlsx('首次充值\ndwz123\n100'),
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}).json()
        assert q_xlsx['valid'] and q_xlsx['matched']==1 and q_xlsx['uploaded_cents']==10000,q_xlsx
        r=client.post('/api/recharge/preview',data={'content':recharge})
        assert r.status_code==200,r.text
        q=r.json()
        assert q['valid'] and q['matched']==3 and q['three_line_events']==4,q
        assert q['three_line_repeated']==1,q
        assert q['uploaded_cents']==300000+18479+250245+493489,q
        r=client.post('/api/recharge/'+q['job_id']+'/confirm',json={})
        assert r.status_code==200,r.text
        with a.engine.connect() as db:
            rows={row['account']:row for row in a.active_rows(db)}
            assert rows['hkfu258']['daily_recharge_cents']==511968,rows['hkfu258']
        # A second identical snapshot must not double-add.
        q=client.post('/api/recharge/preview',data={'content':recharge}).json()
        assert q['valid'],q
        r=client.post('/api/recharge/'+q['job_id']+'/confirm',json={})
        assert r.status_code==200 and r.json()['changed']==0,r.text
        r=client.post('/api/recharge/preview',files={
            'upload':('recharge.xlsx',single_column_xlsx(recharge),
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        assert r.status_code==200 and r.json()['valid'],r.text
        assert r.json()['three_line_events']==4,r.json()

        withdrawal='首次提现\nwhy66888\n500\n首次提现\nwhy66888\n250'
        q=client.post('/api/import/preview',data={'mode':'daily','content':withdrawal}).json()
        assert q['valid'] and q['three_line_events']==2 and q['three_line_repeated']==1,q
        assert q['withdraw_delta_cents']==75000,q
        r=client.post('/api/import/'+q['job_id']+'/confirm',json={})
        assert r.status_code==200,r.text
        with a.engine.connect() as db:
            rows={row['account']:row for row in a.active_rows(db)}
            assert rows['why66888']['daily_withdraw_cents']==75000
            assert rows['why66888']['total_withdraw_cents']==75000
        r=client.post('/api/import/preview',data={'mode':'daily'},files={
            'upload':('withdrawals.xlsx',single_column_xlsx(withdrawal),
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        assert r.status_code==200 and r.json()['valid'],r.text
        # Two-column positive amount remains a funds return (negative internal net).
        q=client.post('/api/import/preview',data={'mode':'daily','content':'why66888 200'}).json()
        assert q['valid'] and q['withdraw_delta_cents']==-95000,q
        # Two-column comma separated header is not mistaken for a 3-line record.
        q=client.post('/api/recharge/preview',data={'content':'会员账号,当日充值\nF123576,3000'}).json()
        assert q['valid'] and q['three_line_events']==0,q
        # Reverse order: amount / optional Chinese note / account; repeated rows summed.
        reverse_recharge='\n'.join([
            '3000','首次存款','F123576',
            '184.786','充值/更换电池','hkfu258',
            '4934.885','hkfu258','2502.45','Cxy197875'])
        q=client.post('/api/recharge/preview',data={'content':reverse_recharge}).json()
        assert q['valid'] and q['three_line_events']==4 and q['three_line_repeated']==1,q
        assert q['uploaded_cents']==300000+18479+493489+250245,q
        r=client.post('/api/recharge/'+q['job_id']+'/confirm',json={})
        assert r.status_code==200 and r.json()['changed']==0,r.text
        # Forward and reversed events can coexist without losing any transaction.
        q=client.post('/api/recharge/preview',
            data={'content':'首次存款\nF123576\n100\n200\nF123576'}).json()
        assert q['valid'] and q['three_line_events']==2 and q['three_line_repeated']==1,q
        assert q['uploaded_cents']==30000,q
        # Reverse withdrawal keeps positive 500 as an actual cash-out.
        q=client.post('/api/import/preview',
            data={'mode':'daily','content':'500\n首次提现\nwhy66888'}).json()
        assert q['valid'] and q['three_line_events']==1,q
        assert q['withdraw_delta_cents']==-25000,q  # previous snapshot 750
        q=client.post('/api/import/preview',
            data={'mode':'daily','content':'500\t\nwhy66888'}).json()
        assert q['valid'] and q['three_line_events']==1 and q['withdraw_delta_cents']==-25000,q
        q=client.post('/api/import/preview',
            data={'mode':'daily','content':'500\twhy66888'}).json()
        assert q['valid'] and q['three_line_events']==1 and q['withdraw_delta_cents']==-25000,q
        q=client.post('/api/import/preview',data={
            'mode':'daily','content':'首次提现\nwhy66888\n500\n200\nwhy66888'}).json()
        assert q['valid'] and q['three_line_events']==2 and q['three_line_repeated']==1,q
        assert q['withdraw_delta_cents']==-5000,q
        q=client.post('/api/recharge/preview',files={
            'upload':('reverse.xlsx',single_column_xlsx(reverse_recharge),
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}).json()
        assert q['valid'] and q['three_line_events']==4,q
        r=client.post('/api/import/preview',data={'mode':'daily','content':'500'})
        assert r.status_code==400 and '缺少会员账号' in r.text,r.text
    print("===BERLIN_ADD_MEMBER_UI===")
    code=Path('member-tree/static/app.js').read_text(encoding='utf-8')
    for kw in ('新增会员','+ 新增','+','addMember','member/create','/members','新建会员'):
        positions=[];idx=0
        while len(positions)<4:
            idx=code.find(kw,idx)
            if idx<0:break
            positions.append(idx);idx+=len(kw)
        for pos in positions:
            print('UI',repr(kw),pos,repr(code[max(0,pos-1100):pos+2100]))
    print("===BERLIN_ROUTES===")
    for route in a.app.routes:
        if hasattr(route,'path') and any(k in route.path.lower() for k in ('member','legacy','recharge','admin')):
            print(route.path,route.methods,getattr(route.endpoint,'__name__',''))
    print("===BERLIN_HTML_ADD_BUTTON===")
    html=Path('member-tree/static/index.html').read_text(encoding='utf-8')
    for kw in ('addButton','addMember','新增会员','openEdit','quickAdd','fab','floating','memberAdd','memberDialog'):
        pos=html.find(kw)
        if pos>=0:print('HTML',kw,pos,repr(html[max(0,pos-1500):pos+2300]))
    print("===BERLIN_IMPORT_JOB===")
    import inspect
    for route in a.app.routes:
        if hasattr(route,'path') and route.path in ('/api/member','/api/members','/api/members/new','/api/admin/legacy/confirm','/api/admin/legacy/preview'):
            print('ROUTE_SOURCE',route.path,inspect.getsource(route.endpoint)[:12000])
    print('PASS: three-line recharge/withdrawal, duplicate sums, xlsx, daily idempotence, original signed two-column behavior')
