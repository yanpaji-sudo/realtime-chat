"""Regression for Berlin incremental daily member Excel import.
Strictly isolated in SQLite; never touches deployed databases.
"""
import io, os, sys, uuid, tempfile, subprocess
from datetime import datetime, date, timedelta, time
from pathlib import Path
from openpyxl import Workbook
from fastapi.testclient import TestClient
from sqlalchemy import text

with tempfile.TemporaryDirectory() as directory:
    os.environ['DATABASE_URL']='sqlite:///'+directory+'/daily_new_members.sqlite'
    os.environ['ENABLE_MIDNIGHT_WORKER']='0'
    sys.path.insert(0,'member-tree')
    import app as a
    a.require=lambda req,role='viewer',mutation=False:{'role':'admin','username':'bulk_test'}
    a.db_init()
    today=a.current_day()
    older=(date.fromisoformat(today)-timedelta(days=3)).isoformat()
    with a.engine.begin() as db:
        db.execute(text('''INSERT INTO members
            (id,account,joined_on,stake_cents,total_withdraw_cents,remark,created_at,updated_at)
            VALUES (:i,'F123576',:j,777700,4500,'老成员保留',:n,:n)'''),
            {'i':str(uuid.uuid4()),'j':older,'n':a.utc_now()})
    book=Workbook();ws=book.active
    ws.append(['会员信息'])
    ws.append(['会员id','会员账号','真实姓名','会员昵称','会员状态',
               '会员等级','会员分群','直属代理商','历史累计打针次数',
               '历史总充值','历史总提现','注册时间','其他统计'])
    today_excel=datetime.combine(date.fromisoformat(today),time(10,20))
    old_excel=datetime.combine(date.fromisoformat(older),time(14,0))
    def row(id,account,name,parent,stake,withdraw,registered):
        return [id,account,name,account,'在用','1级','Default',parent,0,stake,withdraw,registered,0]
    ws.append(row(501,'user_new1','张三','F123576',10000.25,50.5,today_excel))
    ws.append(row(502,'user_new2','李四','user_new1',5000,100,today_excel))
    ws.append(row(503,'new_orphan','王五','unknown_parent7',0,0,today_excel))
    ws.append(row(504,'F123576','老成员','root',99999,99999,old_excel))
    ws.append(row(505,'yesterday_member','旧记录','root',2000,500,old_excel))
    output=io.BytesIO();book.save(output)
    data=output.getvalue()
    with TestClient(a.app) as client:
        res=client.post('/api/berlin/daily-new/preview',files={'upload':(
            '会员信息.xlsx',data,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        assert res.status_code==200,res.text
        q=res.json()
        assert q['valid'] and q['new_count']==3 and q['old_count']==2,q
        assert q['placeholder_count']==1 and q['total_rows']==5,q
        assert q['stake_cents']==1500025 and q['total_withdraw_cents']==15050,q
        job=q['job_id']
        r=client.post('/api/berlin/daily-new/'+job+'/confirm',json={})
        assert r.status_code==200,r.text
        assert r.json()['created']==3 and r.json()['total_added']==4,r.json()
        with a.engine.connect() as db:
            members={x['account']:dict(x) for x in
                     db.execute(text('SELECT id,account,parent_id,stake_cents,total_withdraw_cents,remark,joined_on FROM members')).mappings().all()}
        assert members['F123576']['stake_cents']==777700,members
        assert members['F123576']['total_withdraw_cents']==4500,members
        assert members['user_new1']['parent_id']==members['F123576']['id'],members
        assert members['user_new2']['parent_id']==members['user_new1']['id'],members
        assert members['new_orphan']['parent_id']==members['unknown_parent7']['id'],members
        assert members['user_new1']['stake_cents']==1000025,members
        assert 'yesterday_member' not in members,members
        r=client.post('/api/berlin/daily-new/preview',files={'upload':(
            '会员信息.xlsx',data,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        assert r.status_code==200,r.text
        q=r.json()
        assert q['new_count']==0 and not q['valid'] and not q['job_id'],q
        assert q['existing_count']==3 and q['old_count']==2,q
        assert len(members)==5,members
    subprocess.run(['node','--check','member-tree/static/app.js'],check=True)
    html=Path('member-tree/static/index.html').read_text(encoding='utf-8')
    assert 'berlinBulkLaunch' in html and 'berlinBulkDialog' in html
    print('PASS: full member Excel with banner row, six columns, daily-only append, parent tree, zero account duplication, preserve existing records and funds')
