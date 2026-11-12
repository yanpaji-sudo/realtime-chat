import importlib
import io
import os
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import text


def test_member_layer_export_and_role_color():
    with tempfile.TemporaryDirectory() as d:
        os.environ['DATABASE_URL']='sqlite:///'+str(Path(d)/'members.db')
        os.environ['SECURE_COOKIE']='0'
        os.environ['SESSION_SECRET']='test-secret-string-unique-and-not-real-54321'
        import app as module
        importlib.reload(module)
        os.environ['ADMIN_PASSWORD_HASH']=module.hash_pw('ADMIN_TEST_ONLY')
        os.environ['VIEWER_PASSWORD_HASH']=module.hash_pw('VIEWER_TEST_ONLY')
        importlib.reload(module)
        with TestClient(module.app) as client:
            assert client.get('/api/export/layers.xlsx',params={'account':'000A'}).status_code==401
            admin=client.post('/api/login',json={'role':'admin','password':'ADMIN_TEST_ONLY'}).json()
            token={'x-csrf-token':admin['csrf']}
            def add(a,parent,stake,withdraw):
                res=client.post('/api/members',headers=token,json={'account':a,'joined_on':'2026-11-05','parent_account':parent,'stake':str(stake),'total_withdraw':str(withdraw)})
                assert res.status_code==200, res.text
                return res.json()['id']
            ids={}
            for account, parent, stake, withdrawn in [
                ('000A',None,10000,12000),
                ('000B','000A',5000,1000),
                ('000C','000A',10000,9000),
                ('000D','000B',5000,6000),
                ('000E','000B',10000,2000),
                ('000F','000C',5000,9000),
                ('000G','000D',10000,2000),
                ('000X',None,10000,9999)]:
                ids[account]=add(account,parent,stake,withdrawn)
            # User's visible daily payouts, mixing positive, zero and negative win.
            with module.engine.begin() as db:
                for account,day in [('000A',100),('000B',250),('000C',500),('000D',900),('000E',0),('000F',1000),('000G',20)]:
                    db.execute(text('UPDATE members SET daily_withdraw_cents=:n,daily_withdraw_on=:day WHERE id=:id'),{'n':day*100,'day':module.current_day(),'id':ids[account]})
            payload=client.get('/api/export/layers.xlsx',params={'account':'000A'})
            assert payload.status_code==200,payload.text[:200]
            assert 'spreadsheetml' in payload.headers['content-type']
            w=load_workbook(io.BytesIO(payload.content))
            s=w.active
            assert s.title=='逐层统计'
            assert [s.cell(row,1).value for row in range(5,9)] == ['本人','第1层汇总','第2层汇总','第3层汇总']
            assert s['B5'].value=='000A' and s['B5'].number_format=='@'
            assert [s.cell(row,3).value for row in range(5,9)] == [1,2,3,1]
            # Column D stake, E balance, F withdraw, G daily withdraw, H win
            assert [s.cell(row,4).value for row in range(5,9)]==[10000,15000,20000,10000]
            assert [s.cell(row,6).value for row in range(5,9)]==[12000,10000,17000,2000]
            assert [s.cell(row,7).value for row in range(5,9)]==[100,750,1900,20]
            assert [s.cell(row,8).value for row in range(5,9)]==[-2000,5000,3000,8000]
            total={k:sum(int(r[k]) for r in module.active_rows(module.engine.connect()) if r['account'] in ('000A','000B','000C','000D','000E','000F','000G')) for k in ('stake_cents','total_withdraw_cents')}
            assert sum(int(s.cell(row,4).value*100) for row in range(5,9)) == total['stake_cents']
            assert sum(int(s.cell(row,6).value*100) for row in range(5,9)) == total['total_withdraw_cents']
            assert s['G5'].font.color.rgb[-6:]=='111827'
            assert s['G6'].font.color.rgb[-6:]=='111827'
            assert s['D5'].font.color.rgb[-6:]=='111827'
            assert s['G5'].number_format == '#,##0;[Red]-#,##0;0'
            assert s['F5'].number_format == '#,##0;[Red]-#,##0;0'
            assert s['H5'].font.color.rgb[-6:]=='C62828'
            assert s['H6'].font.color.rgb[-6:]=='111827'
            assert s.max_row==8  # No extra person rows; exactly one row per depth.
            # Intermediate node has only itself plus its own descendants.
            b=load_workbook(io.BytesIO(client.get('/api/export/layers.xlsx',params={'account':'000B'}).content)).active
            assert [b.cell(row,3).value for row in range(5,8)] == [1,2,1]
            assert b.max_row==7
            x=load_workbook(io.BytesIO(client.get('/api/export/layers.xlsx',params={'account':'000X'}).content)).active
            assert x.max_row==5 and x['B5'].value=='000X'
            assert client.get('/api/export/layers.xlsx',params={'account':'NOTFOUND'}).status_code==404
            # Viewers can export authorized aggregated statistics, but cannot mutate.
            client.post('/api/logout',headers=token)
            vr=client.post('/api/login',json={'role':'viewer','password':'VIEWER_TEST_ONLY'}).json()
            assert client.get('/api/export/layers.xlsx',params={'account':'000A'}).status_code==200
            assert client.post('/api/members',headers={'x-csrf-token':vr['csrf']},json={'account':'NO','joined_on':'2026-11-05','stake':'5000'}).status_code==403
            # Both interactive scripts expose the correct color helpers and buttons.
            js=(Path(__file__).resolve().parent.parent/'static/app.js').read_text()
            css=(Path(__file__).resolve().parent.parent/'static/style.css').read_text()
            assert 'function amountClass' in js and 'amount-red' in css
            assert "metric('当日提现',x.daily_withdraw_cents,x.direct_daily_withdraw_cents,x.subtree_daily_withdraw_cents,true)" in js
            assert 'function downloadLayers(account)' in js
            assert '逐层导出' in js
