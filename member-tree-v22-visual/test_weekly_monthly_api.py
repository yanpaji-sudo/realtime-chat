"""V22 week/month positive final snapshot days from isolated SQLite.

Repeated same-day uploads overwrite (not count twice); negative returns excluded.
Do not connect to production database or mutate financial/member records via GET.
"""
import os,sys,tempfile,uuid
from datetime import date,timedelta
from sqlalchemy import text
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as folder:
    os.environ['DATABASE_URL']='sqlite:///'+folder+'/v22_week_month.sqlite'
    os.environ['ENABLE_MIDNIGHT_WORKER']='0'
    sys.path.insert(0,'member-tree')
    import app as a
    a.require=lambda req,role='viewer',mutation=False: {'role':'viewer','username':'week_month_test'}
    a.db_init()
    today=a.current_day()
    now=date.fromisoformat(today)
    week_start=now-timedelta(days=now.weekday())
    month_start=now.replace(day=1)
    yesterday=(now-timedelta(days=1)).isoformat()
    one_week_day=week_start.isoformat()
    # Current date's month needs >=4 elapsed days to test high-frequency tier.
    assert now.day>=5,'Test needs at least five elapsed days in current calendar month'
    month_days=[(month_start+timedelta(days=i)).isoformat() for i in range(5)]
    ids={name:str(uuid.uuid4()) for name in ['alice','bob','carol','david','eve','deleted']}
    with a.engine.begin() as db:
        for name,mid in ids.items():
            db.execute(text("""INSERT INTO members
              (id,account,joined_on,balance_cents,total_withdraw_cents,
               daily_withdraw_cents,stake_cents,deleted,created_at,updated_at)
              VALUES (:id,:name,:joined,550000,250000,900000,1000000,:deleted,:t,:t)"""),
              {'id':mid,'name':name,'joined':month_start.isoformat(),
               'deleted':int(name=='deleted'),'t':a.utc_now()})
        def ledger(account,day,cents):
            db.execute(text("""INSERT INTO daily_withdraw_ledger
                   (member_id,business_day,amount_cents)
                   VALUES (:id,:d,:c)
                   ON CONFLICT(member_id,business_day)
                   DO UPDATE SET amount_cents=excluded.amount_cents"""),
                   {'id':ids[account],'d':day,'c':cents})
        # Ensure red(1), amber(2+), purple(4+) within the month.
        for day in month_days:
            ledger('alice',day,10000)
        ledger('bob',one_week_day,25000)
        ledger('carol',one_week_day,12000)
        ledger('carol',yesterday,18000)
        ledger('david',month_days[1],5000)
        ledger('david',month_days[2],15000)
        ledger('eve',month_days[0],-50000)  # return, NOT withdrawal
        ledger('deleted',month_days[0],30000)
        # Repeated same-day imported overwrite: only ONE day counted and
        # the last amount is used, no additive transaction count.
        ledger('alice',month_days[0],11000)
        db.execute(text("""INSERT INTO daily_import_days(business_day,recorded_at)
            VALUES (:d,:t)"""),{'d':today,'t':a.utc_now()})
    with a.engine.connect() as db:
        original={r['id']:(r['balance_cents'],r['total_withdraw_cents'],
                           r['daily_withdraw_cents']) for r in
            db.execute(text("""SELECT id,balance_cents,total_withdraw_cents,
             daily_withdraw_cents FROM members""")).mappings()}
    with TestClient(a.app) as client:
        def overview(mode,day=today):
            r=client.get('/api/history/withdrawals/overview',
                         params={'mode':mode,'day':day})
            assert r.status_code==200,r.text
            q=r.json()
            assert q['mode']==mode and q['day']==day,q
            assert r.headers['cache-control'].startswith('no-store')
            return q
        month=overview('month')
        assert month['start_day']==month_start.isoformat() and month['end_day']==today
        people={r['account']:r for r in month['members']}
        assert set(people)=={'alice','bob','carol','david'},month
        assert people['alice']['days']==5 and people['alice']['tier']=='high',month
        assert people['alice']['amount_cents']==51000,month
        assert people['david']['days']==2 and people['david']['tier']=='mid'
        assert people['carol']['days']==2 and people['carol']['amount_cents']==30000
        assert people['bob']['days']==1 and people['bob']['tier']=='low'
        assert month['count']==4 and month['once_count']==1,month
        assert month['repeat_count']==3 and month['four_plus_count']==1,month
        assert 'eve' not in people and 'deleted' not in people
        assert month['total_withdraw_cents']==51000+25000+30000+20000,month
        assert month['recorded'] and month['recorded_days']>=6,month
        assert month['expected_days']==now.day,month
        assert month['missing_days']==now.day-month['recorded_days'],month
        week=overview('week')
        assert week['start_day']==week_start.isoformat()
        assert week['end_day']==today
        week_people={r['account']:r for r in week['members']}
        assert 'bob' in week_people and week_people['bob']['days']==1,week
        if one_week_day!=yesterday:
            assert 'carol' in week_people and week_people['carol']['days']==2
        # Imported zero day without any positive payout is still recorded.
        empty=overview('week',(week_start-timedelta(days=8)).isoformat())
        assert empty['recorded'] is False and empty['count']==0
        assert empty['missing_days']==empty['expected_days']
        # Existing single-day GET must remain independently functional.
        single=client.get('/api/history/withdrawals',params={'day':month_days[0]})
        assert single.status_code==200 and single.json()['recorded'] is True
        assert any(row['account']=='eve' and row['amount_cents']<0 for row in single.json()['members'])
        for params in [
            {'mode':'year','day':today},
            {'mode':'month','day':(now+timedelta(days=1)).isoformat()},
            {'mode':'week','day':'2026-02-30'},
            {'mode':'week','day':'notaday'}]:
            resp=client.get('/api/history/withdrawals/overview',params=params)
            assert resp.status_code==400,(params,resp.text)
    with a.engine.connect() as db:
        final={r['id']:(r['balance_cents'],r['total_withdraw_cents'],
                        r['daily_withdraw_cents']) for r in
          db.execute(text("""SELECT id,balance_cents,total_withdraw_cents,
           daily_withdraw_cents FROM members""")).mappings()}
    assert original==final,'Viewing history must never modify member balances/withdrawals'
    print('PASS: V22 weekly/monthly positive withdrawal-day frequency, repeat corrections idempotent, amber/purple tiers, coverage gaps, auth route, no writes')
