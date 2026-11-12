import importlib
import os
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient


def test_finance_tree_and_repeat_import():
    with tempfile.TemporaryDirectory() as d:
        os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(d)/'test.db')
        os.environ['SECURE_COOKIE'] = '0'
        os.environ['SESSION_SECRET'] = 'test-secret-longer-than-32-characters'
        import app as module
        importlib.reload(module)
        os.environ['ADMIN_PASSWORD_HASH'] = module.hash_pw('ADM-test-PASSWORD')
        os.environ['VIEWER_PASSWORD_HASH'] = module.hash_pw('VIEW-test-PASSWORD')
        importlib.reload(module)
        with TestClient(module.app) as c:
            assert c.get('/api/health').status_code == 200
            assert c.get('/api/tree').status_code == 401
            login = c.post('/api/login', json={'role': 'viewer','password': 'VIEW-test-PASSWORD'})
            assert login.status_code == 200
            v_csrf={'x-csrf-token': login.json()['csrf']}
            assert c.post('/api/members',headers=v_csrf,json={'account':'A','joined_on':'2026-11-04','stake':'10000'}).status_code==403
            c.post('/api/logout', headers=v_csrf)
            login = c.post('/api/login', json={'role':'admin', 'password':'ADM-test-PASSWORD'})
            assert login.status_code==200
            hdr={'x-csrf-token':login.json()['csrf']}
            def add(account,parent,stake,withdraw):
                res=c.post('/api/members', headers=hdr, json={'account':account,'joined_on':'2026-11-04', 'parent_account':parent, 'stake':str(stake), 'total_withdraw':str(withdraw)})
                assert res.status_code==200,res.text
                return res.json()['id']
            a=add('000A',None,10000,200)
            b=add('000B','000A',5000,1000)
            cc=add('000C','000B',10000,300)
            dd=add('000D','000A',5000,100)
            assert c.post('/api/members',headers=hdr,json={'account':'000X','parent_account':'000B','joined_on':'2026-11-04','stake':'0'}).status_code==400
            assert c.post('/api/members',headers=hdr,json={'account':'000X','joined_on':'2026-11-04','stake':'5000','parent_account':'notfound'}).status_code==400
            assert c.post('/api/members',headers=hdr,json={'account':'000A','joined_on':'2026-11-04','stake':'5000'}).status_code==409
            rows={r['account']:r for r in c.get('/api/tree').json()['members']}
            assert rows['000A']['stake_cents']==1000000
            assert rows['000A']['direct_stake_cents']==1000000 # B + D
            assert rows['000A']['subtree_stake_cents']==3000000 # A + B + C + D
            assert rows['000A']['subtree_total_withdraw_cents']==160000
            assert rows['000A']['direct_total_withdraw_cents']==110000
            assert rows['000A']['profit_cents']==980000
            assert rows['000A']['direct_profit_cents']==890000
            assert rows['000A']['subtree_profit_cents']==2840000
            assert rows['000A']['direct_count']==2
            assert rows['000A']['descendant_count']==3
            bad=c.put(f'/api/members/{a}',headers=hdr,json={'account':'000A','joined_on':'2026-11-04','stake':'10000','total_withdraw':'200','parent_account':'000C', 'expected_revision':rows['000A']['revision']})
            assert bad.status_code==400
            def imported(mode, content):
                pre=c.post('/api/import/preview',headers=hdr,data={'mode':mode,'content':content})
                assert pre.status_code==200,pre.text
                job=pre.json(); assert job['valid'],job
                response=c.post('/api/import/'+job['job_id']+'/confirm', headers=hdr)
                assert response.status_code==200,response.text
                return job,response.json()
            imported('balance','000B 880.55\n000C 2000')
            m={r['account']:r for r in c.get('/api/tree').json()['members']}
            assert m['000A']['balance_cents']==0
            assert m['000A']['subtree_balance_cents']==288055
            assert m['000A']['direct_balance_cents']==88055
            first, result=imported('daily','000B 100\n000C 50')
            assert first['withdraw_delta_cents']==15000
            assert result['withdraw_delta_cents']==15000
            m={r['account']:r for r in c.get('/api/tree').json()['members']}
            assert m['000B']['total_withdraw_cents']==100000
            assert m['000C']['total_withdraw_cents']==30000
            assert m['000A']['subtree_daily_withdraw_cents']==15000
            # A second upload of exactly the same day's snapshot must not add again
            second, result=imported('daily','000B 100\n000C 50')
            assert second['withdraw_delta_cents']==0
            assert result['withdraw_delta_cents']==0
            # Correct today snapshot: B +30, C -50, and other accounts are 0
            _, result=imported('daily','000B 130')
            assert result['withdraw_delta_cents']==-2000
            m={r['account']:r for r in c.get('/api/tree').json()['members']}
            assert m['000B']['total_withdraw_cents']==100000
            assert m['000C']['total_withdraw_cents']==30000
            assert m['000B']['daily_withdraw_cents']==13000
            assert m['000C']['daily_withdraw_cents']==0
            assert m['000B']['balance_cents']==88055
            # A new calendar day should add fresh daily withdrawals instead of subtracting prior day.
            actual_day=module.current_day
            actual_utc_now=module.utc_now
            from datetime import date, timedelta
            nextday=(date.fromisoformat(actual_day())+timedelta(days=1)).isoformat()
            module.current_day=lambda: nextday
            from datetime import datetime, timezone
            from zoneinfo import ZoneInfo
            mocked_utc=datetime.fromisoformat(nextday + 'T00:01:00').replace(tzinfo=ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc).isoformat()
            module.utc_now=lambda: mocked_utc
            try:
                assert {r['account']:r for r in c.get('/api/tree').json()['members']}['000B']['daily_withdraw_cents']==0
                _,result=imported('daily','000B 20')
                assert result['withdraw_delta_cents']==2000
                assert {r['account']:r for r in c.get('/api/tree').json()['members']}['000B']['total_withdraw_cents']==113000
            finally:
                module.current_day=actual_day
                module.utc_now=actual_utc_now
            # A changed roster or financial state invalidates an earlier preview
            pre=c.post('/api/import/preview',headers=hdr,data={'mode':'balance','content':'000A 3'}).json()
            add('000E','000D',5000,0)
            assert c.post('/api/import/'+pre['job_id']+'/confirm',headers=hdr).status_code==409
            # All-pasted three-column mode accepts missing last daily amount as zero.
            preview=c.post('/api/import/preview',headers=hdr,data={'mode':'both','content':'000A 500.25 8\n000B 900.50\n000C\t\t7\n000D,1.25,2\n000E 0.20'}).json()
            assert preview['valid'],preview
            assert preview['filled_daily_zero_count']==2,preview
            assert preview['matched']==5
            confirmed=c.post('/api/import/'+preview['job_id']+'/confirm',headers=hdr)
            assert confirmed.status_code==200,confirmed.text
            mm={r['account']:r for r in c.get('/api/tree').json()['members']}
            assert mm['000B']['daily_withdraw_cents']==0
            assert mm['000A']['balance_cents']==50025
            assert mm['000C']['balance_cents']==0
            assert mm['000C']['daily_withdraw_cents']==700
            assert mm['000A']['group_account']=='000A'
            assert mm['000C']['group_path']=='000A / 000B / 000C'
            assert mm['000C']['level']==3
            assert mm['000C']['parent_account']=='000B'
            assert mm['000B']['subtree_profit_cents']==mm['000B']['subtree_stake_cents']-mm['000B']['subtree_total_withdraw_cents']
            # No matching member must be clearly rejected (not silently zero everyone).
            no_match=c.post('/api/import/preview',headers=hdr,data={'mode':'balance','content':'NOT_EXIST 22'}).json()
            assert not no_match['valid'] and no_match['matched']==0
            assert any('没有匹配到' in x for x in no_match['errors'])
            # XLSX importing formatted numeric accounts keeps leading zeros.
            from openpyxl import Workbook,load_workbook
            import io
            book=Workbook();sh=book.active
            sh.append(['会员账号','余额','当日提现'])
            sh.append([1,15.33,None]);sh['A2'].number_format='000000'
            sh.append(['000B',55.55,None])
            output=io.BytesIO();book.save(output)
            # Existing accounts may not include 000001, so this is an unmatched warning, not an error.
            xres=c.post('/api/import/preview',headers=hdr,data={'mode':'both','content':''},files={'upload':('amounts.xlsx',output.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}).json()
            assert xres['valid'] and xres['matched']==1,xres
            assert xres['unmatched_count']==1
            assert xres['filled_daily_zero_count']==2
            assert xres['errors']==[]
            # Export by single node includes itself and all its descendants, not siblings.
            csv_out=c.get('/api/export.csv',params={'root_account':'000B'})
            assert csv_out.status_code==200
            assert '000B' in csv_out.text and '000C' in csv_out.text and '000D' not in csv_out.text
            assert '所在分组' in csv_out.text and '所属关系路径' in csv_out.text
            book_out=c.get('/api/export.xlsx',params={'root_account':'000B'})
            assert book_out.status_code==200
            book2=load_workbook(io.BytesIO(book_out.content))
            assert {book2.active['A2'].value,book2.active['A3'].value}=={'000B','000C'}
            assert book2.active['A2'].number_format=='@'
            assert book2.active['A3'].number_format=='@'
            assert book2.active['H1'].value=='全部下级人数'
            assert c.get('/api/export.xlsx',params={'root_account':'BAD'}).status_code==404
            assert c.get('/api/export.xlsx').status_code==200
            duplicate=c.post('/api/import/preview',headers=hdr,data={'mode':'both','content':'000A 1 2\n000A 2 4'}).json()
            assert not duplicate['valid'] and duplicate['duplicates']
            assert c.get('/api/export.csv').status_code==200
            body=c.get('/api/export.csv').text
            assert '直属一层建仓资金' in body and '节点全层级输赢' in body
            # Check editing stake and parent searching by account, and recomputation after moving nodes
            u=c.put(f'/api/members/{cc}',headers=hdr,json={'account':'000C','joined_on':'2026-11-04','stake':'5000','total_withdraw':'300','parent_account':'000D', 'expected_revision':mm['000C']['revision']})
            assert u.status_code==200,u.text
            m={r['account']:r for r in c.get('/api/tree').json()['members']}
            assert m['000B']['direct_count']==0
            assert m['000D']['direct_stake_cents']==1000000
            assert m['000A']['subtree_stake_cents']==3000000
            assert c.delete('/api/members/'+a,params={'expected_revision':m['000A']['revision']},headers=hdr).status_code==409


def test_migration_from_old_schema():
    import sqlite3
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'old.db'
        con=sqlite3.connect(path)
        con.execute('''CREATE TABLE members (id TEXT PRIMARY KEY, account TEXT NOT NULL UNIQUE,joined_on TEXT NOT NULL,parent_id TEXT,balance_cents BIGINT NOT NULL DEFAULT 0,total_withdraw_cents BIGINT NOT NULL DEFAULT 0,daily_withdraw_cents BIGINT NOT NULL DEFAULT 0,deleted INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
        con.execute("INSERT INTO members(id, account,joined_on,total_withdraw_cents,daily_withdraw_cents,created_at,updated_at) VALUES ('x','000X','2026-10-20',10000,2000,'x','x')")
        con.commit();con.close()
        os.environ['DATABASE_URL']='sqlite:///'+str(path)
        os.environ['SESSION_SECRET']='test-secret-longer-than-32-characters'
        import app as module
        importlib.reload(module)
        with TestClient(module.app) as client:
            assert client.get('/api/health').status_code==200
            from sqlalchemy import text
            with module.engine.connect() as db:
                row=db.execute(text('SELECT stake_cents, daily_withdraw_on,total_withdraw_cents FROM members')).first()
                assert row[0]==0 and row[1] == module.current_day() and row[2]==10000
