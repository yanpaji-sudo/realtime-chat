import os,io,json,importlib,tempfile,csv
from pathlib import Path
from fastapi.testclient import TestClient
from openpyxl import Workbook


def test_csv_preview_commit_and_atomicity():
  with tempfile.TemporaryDirectory() as td:
    os.environ['DATABASE_URL']='sqlite:///'+str(Path(td)/'member.db')
    os.environ['SESSION_SECRET']='test-session-secret-'+'y'*40
    os.environ['SECURE_COOKIE']='0'
    import app
    os.environ['ADMIN_USERS_JSON']=json.dumps({f'admin{i:02d}':app.hash_pw(f'password-for-admin{i:02d}') for i in range(1,9)})
    os.environ['VIEWER_PASSWORD_HASH']=app.hash_pw('viewer-secret')
    importlib.reload(app)
    with TestClient(app.app) as cli:
      li=cli.post('/api/login',json={'role':'admin','username':'admin01','password':'password-for-admin01'})
      assert li.status_code==200
      auth={'X-CSRF-Token':li.json()['csrf']}
      create=cli.post('/api/members',headers=auth,json={'account':'OldOne','joined_on':'2026-01-01','stake':'5000'})
      assert create.status_code==200,create.text
      original=cli.get('/api/tree').json()['members']
      writer=io.StringIO();csvw=csv.writer(writer)
      csvw.writerow(['会员账号','加入日期','所在分组','直属上级账号','所属关系路径','层级','直属人数','全部下级人数','备注','本人建仓资金','本人余额','本人总提现','本人当日提现','本人输赢'])
      csvw.writerow(['ROOT001','2026-03-01','ROOT001','','ROOT001',1,1,1,'根备注','10000.00','8500.50','300','0','9700'])
      csvw.writerow(['CHILD002','2026-04-01','ROOT001','ROOT001','ROOT001/CHILD002',2,0,0,'子备注','5000.00','1800.00','200','0','4800'])
      file=('members-all.csv',('\ufeff'+writer.getvalue()).encode('utf-8-sig'),'text/csv')
      preview=cli.post('/api/admin/legacy/preview',headers=auth,files={'upload':file})
      assert preview.status_code==200,preview.text
      assert preview.json()['members']==2 and preview.json()['roots']==1
      assert cli.get('/api/tree').json()['members']==original  # preview never mutates
      jid=preview.json()['job_id']
      bad=cli.post('/api/admin/legacy/'+jid+'/confirm',headers=auth,json={'confirm':'no'})
      assert bad.status_code==400
      assert cli.get('/api/tree').json()['members']==original
      good=cli.post('/api/admin/legacy/'+jid+'/confirm',headers=auth,json={'confirm':'确认覆盖旧会员数据'})
      assert good.status_code==200,good.text
      rows=cli.get('/api/tree').json()['members']
      assert len(rows)==2,rows
      root=next(x for x in rows if x['account']=='ROOT001')
      child=next(x for x in rows if x['account']=='CHILD002')
      assert child['parent_id']==root['id']
      assert root['remark']=='根备注' and child['remark']=='子备注'
      assert root['stake_cents']==1000000 and root['balance_cents']==850050 and root['total_withdraw_cents']==30000
      assert child['stake_cents']==500000
      assert cli.post('/api/admin/legacy/'+jid+'/confirm',headers=auth,json={'confirm':'确认覆盖旧会员数据'}).status_code==404
      # Invalid input and missing parent never alter restored data.
      bad_csv='会员账号,加入日期,直属上级账号,建仓资金\nA,2026-01-05,NOT-EXIST,10000\n'
      assert cli.post('/api/admin/legacy/preview',headers=auth,files={'upload':('members-all.csv',bad_csv.encode(),'text/csv')}).status_code==400
      assert cli.get('/api/tree').json()['members']==rows
      assert len(cli.get('/api/admin/logs').json()['logs'])>=1
    os.environ.pop('ADMIN_USERS_JSON',None);os.environ.pop('VIEWER_PASSWORD_HASH',None)


def test_xlsx_leading_zeros_and_permission():
  with tempfile.TemporaryDirectory() as td:
    os.environ['DATABASE_URL']='sqlite:///'+str(Path(td)/'member.db')
    os.environ['SESSION_SECRET']='test-session-secret-'+'z'*40
    os.environ['SECURE_COOKIE']='0'
    import app
    os.environ['ADMIN_USERS_JSON']=json.dumps({'admin08':app.hash_pw('secret-admin08')})
    os.environ['VIEWER_PASSWORD_HASH']=app.hash_pw('secret-viewer')
    importlib.reload(app)
    wb=Workbook();ws=wb.active
    ws.append(['会员账号','加入日期','直属上级账号','建仓资金','余额','累计提现','当日提现','备注'])
    ws.append([123,'2026-06-05','',10000,3000,200,0,'测试'])
    ws['A2'].number_format='000000'
    stream=io.BytesIO();wb.save(stream)
    with TestClient(app.app) as cli:
      assert cli.post('/api/login',json={'role':'viewer','password':'secret-viewer'}).status_code==200
      assert cli.post('/api/admin/legacy/preview',files={'upload':('a.xlsx',stream.getvalue(),'application/octet-stream')}).status_code==403
      li=cli.post('/api/login',json={'role':'admin','username':'admin08','password':'secret-admin08'})
      auth={'X-CSRF-Token':li.json()['csrf']}
      preview=cli.post('/api/admin/legacy/preview',headers=auth,files={'upload':('a.xlsx',stream.getvalue(),'application/octet-stream')})
      assert preview.status_code==200,preview.text
      assert preview.json()['sample'][0]['account']=='000123'
      assert cli.post('/api/admin/legacy/'+preview.json()['job_id']+'/confirm',headers=auth,json={'confirm':'确认覆盖旧会员数据'}).status_code==200
      assert cli.get('/api/tree').json()['members'][0]['account']=='000123'
    os.environ.pop('ADMIN_USERS_JSON',None);os.environ.pop('VIEWER_PASSWORD_HASH',None)
