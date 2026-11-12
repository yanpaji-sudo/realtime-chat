"""V20: live group statistics + last-import-wins + midnight settlement safeguards."""
import importlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import text


def test_v20_live_reports_last_upload_only_and_historical_days():
    with TemporaryDirectory() as td:
        os.environ['DATABASE_URL']='sqlite:///'+str(Path(td)/'test.db')
        os.environ['SESSION_SECRET']='v20-integrity-and-history-test-secret'
        os.environ['SECURE_COOKIE']='0'
        import app as m
        os.environ['ADMIN_USERS_JSON']=json.dumps({'admin01':m.hash_pw('pass1234')})
        os.environ['VIEWER_PASSWORD_HASH']=m.hash_pw('viewer123')
        importlib.reload(m)
        old_day=m.current_day
        old_datetime=m.datetime
        current=['2026-11-06']
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):
                original=datetime.fromisoformat(current[0]+'T21:30:00+08:00')
                return original.astimezone(tz) if tz else original.replace(tzinfo=None)
        m.datetime=Clock
        m.current_day=lambda:current[0]
        try:
            with TestClient(m.app) as c:
                r=c.post('/api/login',json={'role':'admin','username':'admin01','password':'pass1234'})
                assert r.status_code==200,r.text
                h={'X-CSRF-Token':r.json()['csrf']}
                def add(account,parent,day='2026-11-01'):
                    r=c.post('/api/members',headers=h,json={'account':account,'parent_account':parent,'joined_on':day,'stake':'10000'})
                    assert r.status_code==200,r.text
                add('01',None)
                add('child','01','2026-11-06')
                def upload(balance,withdraw):
                    payload='child '+str(balance)+' '+str(withdraw)
                    r=c.post('/api/import/preview',headers=h,data={'mode':'both','content':payload})
                    assert r.status_code==200,r.text
                    job=r.json()
                    assert job['valid'],job
                    r=c.post('/api/import/'+job['job_id']+'/confirm',headers=h)
                    assert r.status_code==200,r.text
                for balance,withdraw in [('100','50'),('180','65'),('250','20')]:
                    upload(balance,withdraw)
                    view=c.get('/api/tree').json()
                    child=next(x for x in view['members'] if x['account']=='child')
                    assert child['total_withdraw_cents']==0, 'Total cannot change before the day closes'
                    assert child['daily_withdraw_cents']==int(withdraw)*100
                    report=c.get('/api/reports?month=2026-11&group=all&day=2026-11-06').json()
                    summary=next(x for x in report['overview'] if x['group_account']=='__ALL__')
                    assert summary['balance_cents']==int(balance)*100
                    assert summary['withdraw_cents']==int(withdraw)*100
                    assert summary['new_stake_cents']==1000000
                    assert summary['member_count']==2
                # Yesterday's last uploaded values are retained and credited ONCE on next-day read.
                current[0]='2026-11-07'
                r=c.get('/api/tree').json();child=next(x for x in r['members'] if x['account']=='child')
                assert child['daily_withdraw_cents']==0
                assert child['total_withdraw_cents']==2000
                historical=c.get('/api/reports?month=2026-11&group=all&day=2026-11-06').json()
                assert historical['selected_day']=='2026-11-06'
                history_total=next(x for x in historical['overview'] if x['group_account']=='__ALL__')
                assert history_total['balance_cents']==25000
                assert history_total['withdraw_cents']==2000
                assert '历史已结算' in history_total['status']
                assert history_total['close_quality']=='latest_observation'
                assert c.get('/api/tree').json()['totals']['total_withdraw_cents']==2000
                # A new day upload must NOT be instantly double-credited.
                upload('230','40')
                assert c.get('/api/tree').json()['totals']['total_withdraw_cents']==2000
                second=c.get('/api/reports?month=2026-11&group=01&day=2026-11-07').json()
                row=second['overview'][0]
                assert row['bubble_change_cents']==-2000
                assert row['betting_cents']==-2000
                current[0]='2026-11-08'
                assert c.get('/api/tree').json()['totals']['total_withdraw_cents']==6000
                assert c.get('/api/tree').json()['totals']['total_withdraw_cents']==6000
                backup=c.get('/api/admin/backup').json()['state']
                assert backup['business_closes'] and backup['withdraw_credit']
                assert c.post('/api/admin/restore',headers=h,json={'state':backup,'confirm':'RESTORE_WITH_BACKUP'}).status_code==200
                assert c.get('/api/tree').json()['totals']['total_withdraw_cents']==6000
        finally:
            m.datetime=old_datetime;m.current_day=old_day
            for key in ('ADMIN_USERS_JSON','VIEWER_PASSWORD_HASH','DATABASE_URL','SESSION_SECRET','SECURE_COOKIE'):
                os.environ.pop(key,None)


def test_v20_legacy_credited_amount_corrected_to_zero_at_close():
    with TemporaryDirectory() as td:
        os.environ['DATABASE_URL']='sqlite:///'+str(Path(td)/'test.db')
        os.environ['SESSION_SECRET']='v20-legacy-correction-test-secret'
        os.environ['SECURE_COOKIE']='0'
        import app as m
        os.environ['ADMIN_USERS_JSON']=json.dumps({'admin01':m.hash_pw('pass1234')})
        os.environ['VIEWER_PASSWORD_HASH']=m.hash_pw('viewer123')
        importlib.reload(m)
        old_day=m.current_day
        old_datetime=m.datetime
        current=['2026-11-06']
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):
                t=datetime.fromisoformat(current[0]+'T21:00:00+08:00')
                return t.astimezone(tz) if tz else t.replace(tzinfo=None)
        m.datetime=Clock;m.current_day=lambda:current[0]
        try:
            with TestClient(m.app) as c:
                r=c.post('/api/login',json={'role':'admin','username':'admin01','password':'pass1234'});h={'X-CSRF-Token':r.json()['csrf']}
                added=c.post('/api/members',headers=h,json={'account':'01','joined_on':'2026-11-01','stake':'10000','total_withdraw':'120'})
                assert added.status_code==200
                mid=added.json()['id']
                # Simulate migration from older version which already included 30 into total.
                with m.engine.begin() as db:
                    db.execute(text("UPDATE members SET daily_withdraw_cents=3000,daily_withdraw_on='2026-11-06' WHERE id=:i"),{'i':mid})
                    m.set_daily_ledger(db,mid,'2026-11-06',3000)
                    db.execute(text("DELETE FROM reporting_meta WHERE name='v20_withdraw_credit_migrated'"))
                m.db_init()  # seeds 30 as already credited; must not alter total
                with m.engine.connect() as db:
                    assert db.execute(text('SELECT credited_cents FROM daily_withdraw_credit WHERE member_id=:i'),{'i':mid}).scalar()==3000
                p=c.post('/api/import/preview',headers=h,data={'mode':'daily','content':'01 0'}).json();assert p['valid'],p
                assert c.post('/api/import/'+p['job_id']+'/confirm',headers=h).status_code==200
                assert c.get('/api/tree').json()['totals']['total_withdraw_cents']==12000
                current[0]='2026-11-07'
                assert c.get('/api/tree').json()['totals']['total_withdraw_cents']==9000
                assert c.get('/api/tree').json()['totals']['total_withdraw_cents']==9000
        finally:
            m.datetime=old_datetime;m.current_day=old_day
            for key in ('ADMIN_USERS_JSON','VIEWER_PASSWORD_HASH','DATABASE_URL','SESSION_SECRET','SECURE_COOKIE'):
                os.environ.pop(key,None)
