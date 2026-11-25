"""V22 history read-only API: real last recorded daily ledger, not live amounts.

Isolated temp SQLite. Never connects to formal Render PostgreSQL.
"""
import os,sys,tempfile,uuid
from datetime import date,timedelta
from sqlalchemy import text
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as folder:
    os.environ['DATABASE_URL']='sqlite:///'+folder+'/v22_daily_history.sqlite'
    os.environ['ENABLE_MIDNIGHT_WORKER']='0'
    sys.path.insert(0,'member-tree')
    import app as a
    a.require=lambda req,role='viewer',mutation=False:{'role':'viewer','username':'history_test'}
    a.db_init()
    today=a.current_day()
    yesterday=(date.fromisoformat(today)-timedelta(days=1)).isoformat()
    older=(date.fromisoformat(today)-timedelta(days=3)).isoformat()
    missing=(date.fromisoformat(today)-timedelta(days=5)).isoformat()
    future=(date.fromisoformat(today)+timedelta(days=1)).isoformat()
    ids={x:str(uuid.uuid4()) for x in ['alice','bob','carol','deleted']}
    with a.engine.begin() as db:
        for account in ids:
            db.execute(text("""INSERT INTO members(
                id,account,joined_on,balance_cents,total_withdraw_cents,
                daily_withdraw_cents,daily_withdraw_on,stake_cents,deleted,
                created_at,updated_at)
                VALUES (:id,:account,:join,999000,567800,900000,:today,1000000,
                        :deleted,:now,:now)"""),
                {'id':ids[account],'account':account,'join':older,'today':today,
                 'deleted':int(account=='deleted'),'now':a.utc_now()})
        for account,amount in [('alice',50000),('bob',-2500),('deleted',10000)]:
            db.execute(text("""INSERT INTO daily_withdraw_ledger(
                member_id,business_day,amount_cents) VALUES (:id,:day,:amount)"""),
                {'id':ids[account],'day':yesterday,'amount':amount})
        db.execute(text("""INSERT INTO daily_import_days(business_day,recorded_at)
            VALUES (:day,:time)"""),{'day':yesterday,'time':a.utc_now()})
        db.execute(text("""INSERT INTO daily_import_days(business_day,recorded_at)
            VALUES (:day,:time)"""),{'day':older,'time':a.utc_now()})
    def funds():
        with a.engine.connect() as db:
            return tuple((r['id'],r['balance_cents'],r['total_withdraw_cents'],
                          r['daily_withdraw_cents']) for r in
                          db.execute(text("""SELECT id,balance_cents,total_withdraw_cents,
                            daily_withdraw_cents FROM members ORDER BY id""")).mappings())
    before=funds()
    with TestClient(a.app) as client:
        resp=client.get('/api/history/withdrawals',params={'day':yesterday})
        assert resp.status_code==200,resp.text
        record=resp.json()
        assert record['recorded'] is True and record['day']==yesterday,record
        assert record['count']==2,record
        assert record['withdraw_count']==1 and record['return_count']==1,record
        assert record['withdraw_cents']==50000,record
        assert {r['account']:r['amount_cents'] for r in record['members']}=={
            'alice':50000,'bob':-2500},record
        assert all(r['id']!=ids['deleted'] for r in record['members'])
        assert resp.headers.get('cache-control','').startswith('no-store')
        # Known imported day with NO withdrawals must be distinguished from
        # a date with no ledger and no recorded import.
        zero=client.get('/api/history/withdrawals',params={'day':older})
        assert zero.status_code==200 and zero.json()['recorded'] is True
        assert zero.json()['count']==0 and zero.json()['members']==[]
        none=client.get('/api/history/withdrawals',params={'day':missing})
        assert none.status_code==200 and none.json()['recorded'] is False
        assert none.json()['members']==[]
        # Current daily amount 900000 cannot be copied into an unrecorded day.
        today_record=client.get('/api/history/withdrawals',params={'day':today})
        assert today_record.status_code==200
        assert today_record.json()['count']==0
        assert today_record.json()['recorded'] is False
        assert client.get('/api/history/withdrawals',params={'day':future}).status_code==400
        assert client.get('/api/history/withdrawals',params={'day':'2026-02-30'}).status_code==400
        assert client.get('/api/history/withdrawals',params={'day':'notadate'}).status_code==400
    assert funds()==before,'The historical GET endpoint must not change members or finances'
    print('PASS: V22 previous-day recorded ledger, zero vs missing day, signed withdrawals, hidden deleted IDs, future rejection, no financial writes')
