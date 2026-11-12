"""V21: current report must match /tree despite legacy manual overlays; history remains editable."""
import importlib, json, os, tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import text


def test_current_report_is_source_of_truth_and_history_stays_editable():
    with tempfile.TemporaryDirectory() as td:
        os.environ.update(DATABASE_URL='sqlite:///'+str(Path(td)/'a.db'),
                          SESSION_SECRET='v21-test-secret-43',SECURE_COOKIE='0')
        import app as m
        os.environ['ADMIN_USERS_JSON']=json.dumps({'admin01':m.hash_pw('pass1234')})
        os.environ['VIEWER_PASSWORD_HASH']=m.hash_pw('viewer123')
        importlib.reload(m)
        old=m.current_day
        m.current_day=lambda:'2026-11-06'
        try:
            with TestClient(m.app) as c:
                a=c.post('/api/login',json={'role':'admin','username':'admin01','password':'pass1234'})
                assert a.status_code==200,a.text
                h={'X-CSRF-Token':a.json()['csrf']}
                for account, parent, day in [('01',None,'2026-10-01'),('02',None,'2026-10-01'),('A','01','2026-11-06')]:
                    r=c.post('/api/members',headers=h,json=dict(account=account,parent_account=parent,joined_on=day,stake='10000'))
                    assert r.status_code==200,r.text
                def match_all():
                    view=c.get('/api/tree').json()
                    report=c.get('/api/reports?month=2026-11&group=all&day=2026-11-06').json()
                    all_row=next(x for x in report['overview'] if x['group_account']=='__ALL__')
                    assert all_row['member_count']==len(view['members'])
                    assert all_row['withdraw_cents']==view['totals']['daily_withdraw_cents']
                    assert all_row['balance_cents']==view['totals']['balance_cents']
                    assert all_row['new_stake_cents']==1000000
                    groups=[x for x in report['overview'] if x['group_account'] in ('01','02')]
                    assert sum(x['withdraw_cents'] for x in groups)==all_row['withdraw_cents']
                    assert sum(x['balance_cents'] for x in groups)==all_row['balance_cents']
                    return all_row
                assert match_all()['withdraw_cents']==0
                # A stale legacy manual override for today may exist: must NOT mask new uploads.
                with m.engine.begin() as db:
                    db.execute(text("INSERT INTO report_manual_overrides(business_day,group_account,values_json,operator,updated_at) VALUES ('2026-11-06','01',:v,'legacy','2026-11-05T00:00:00Z')"),
                               {'v':json.dumps({'member_count':2,'new_count':1,'new_stake_cents':100,'withdraw_cents':999999,'balance_cents':999999})})
                assert match_all()['withdraw_cents']==0
                # Import correct daily balances / withdrawals, and verify ALL totals are live.
                for b,w in [(100,50),(200,80),(220,30)]:
                    preview=c.post('/api/import/preview',headers=h,data={'mode':'both','content':f'A {b} {w}\n01 10 0\n02 25 2'})
                    assert preview.status_code==200,preview.text
                    job=preview.json();assert job['valid'],job
                    commit=c.post('/api/import/'+job['job_id']+'/confirm',headers=h)
                    assert commit.status_code==200,commit.text
                    live=match_all()
                    assert live['balance_cents']==(b+10+25)*100
                    assert live['withdraw_cents']==(w+2)*100
                    assert live['status']=='今日实时'
                # Active day must stay source-of-truth, historical days still support manual corrections.
                data={'day':'2026-11-06','group':'01','expected_updated_at':'',
                      'values':{'member_count':'2','new_count':'1','new_stake_cents':'10000','withdraw_cents':'0','balance_cents':'100'}}
                assert c.put('/api/admin/reports/override',headers=h,json=data).status_code==409
                m.current_day=lambda:'2026-11-07'
                # Preexisting overrides are still visible historically.
                history=c.get('/api/reports?month=2026-11&group=all&day=2026-11-06').json()
                old_row=next(x for x in history['overview'] if x['group_account']=='01')
                assert old_row['is_manual'] is True
                # historical correction continues to work.
                data['expected_updated_at']='2026-11-05T00:00:00Z'
                assert c.put('/api/admin/reports/override',headers=h,json=data).status_code==200
        finally:
            m.current_day=old
            for k in ('ADMIN_USERS_JSON','VIEWER_PASSWORD_HASH'):os.environ.pop(k,None)
