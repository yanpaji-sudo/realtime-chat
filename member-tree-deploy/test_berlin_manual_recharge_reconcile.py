"""Test same-day manual vs daily recharge reconciliation in isolated SQLite.
No production data connections. New record: uploaded nightly value replaces
manual initial stake. Zero manual stake: receives uploaded amount. Older/bulk:
existing supplemental rules. No accumulation on same-day reupload.
"""
import os,sys,tempfile,uuid
from datetime import date,timedelta
from sqlalchemy import text
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as work:
    os.environ['DATABASE_URL']='sqlite:///'+work+'/recharge-reconcile.sqlite'
    os.environ['ENABLE_MIDNIGHT_WORKER']='0'
    sys.path.insert(0,'member-tree')
    import app as a
    a.require=lambda req,role='viewer',mutation=False: {'role':'admin','username':'reconcile_test'}
    a.db_init()
    today=a.current_day()
    yesterday=(date.fromisoformat(today)-timedelta(days=1)).isoformat()
    tomorrow=(date.fromisoformat(today)+timedelta(days=1)).isoformat()

    def select(acct):
        with a.engine.connect() as db:
            return dict(db.execute(text('SELECT * FROM members WHERE lower(account)=lower(:a)'),
                    {'a':acct}).mappings().first())

    def row(acct):
        with a.engine.connect() as db:
            vals=[dict(x) for x in a.active_rows(db) if x['account'].lower()==acct.lower()]
        assert len(vals)==1,acct
        return vals[0]

    def mark_count():
        with a.engine.connect() as db:
            return db.execute(text('SELECT COUNT(*) FROM berlin_manual_join_deposits')).scalar()

    with TestClient(a.app) as client:
        def new_member(account,stake,day=today):
            payload={'account':account,'joined_on':day,'parent_account':None,
              'stake':str(stake),'total_withdraw':'0','remark':account[:20]}
            r=client.post('/api/members',json=payload)
            assert r.status_code==200,r.text
            return r.json()['id']

        ids={
          'ManualFixed':new_member('ManualFixed',10000),
          'ManualZero':new_member('ManualZero',0),
          'ManualUnlisted':new_member('ManualUnlisted',4500),
          'OlderAccount':new_member('OlderAccount',6000,yesterday),
          'ManualEdited':new_member('ManualEdited',10000)
        }
        # Editing a newly-created entry before first upload updates its baseline.
        old=select('ManualEdited')
        r=client.put('/api/members/'+ids['ManualEdited'],json={
            'account':'ManualEdited','joined_on':today,'parent_account':None,
            'stake':'5000','total_withdraw':'0','remark':'edited',
            'expected_revision':old['revision']})
        assert r.status_code==200,r.text
        # This member is imported from another path and must retain old rules.
        with a.engine.begin() as db:
            db.execute(text("""INSERT INTO members(
                id,account,joined_on,stake_cents,created_at,updated_at
                ) VALUES (:id,'BulkToday',:day,700000,:now,:now)"""),
                {'id':str(uuid.uuid4()),'day':today,'now':a.utc_now()})
        assert mark_count()==4

        def recharge(s):
            preview=client.post('/api/recharge/preview',data={'content':s})
            assert preview.status_code==200,preview.text
            q=preview.json()
            assert q['valid'],q
            done=client.post('/api/recharge/'+q['job_id']+'/confirm',json={})
            assert done.status_code==200,done.text
            return q,done.json()

        content='\n'.join([
           '首次充值','MANUALFIXED','12000',
           '首次充值','manualzero','2300',
           '首次充值','ManualEdited','5500',
           '首次充值','OlderAccount','350',
           '首次充值','BulkToday','9000'])
        preview,done=recharge(content)
        assert preview['matched']==5,preview
        assert done['changed']==5,done
        fixed=row('ManualFixed')
        zero=row('ManualZero')
        edited=row('ManualEdited')
        old=row('OlderAccount')
        bulk=row('BulkToday')
        assert fixed['stake_cents']==1200000 and fixed['total_recharge_cents']==1200000,fixed
        assert fixed['pending_recharge_cents']==0 and fixed['daily_recharge_cents']==1200000,fixed
        assert zero['stake_cents']==230000 and zero['total_recharge_cents']==230000,zero
        assert zero['pending_recharge_cents']==0 and zero['daily_recharge_cents']==230000,zero
        assert edited['stake_cents']==550000 and edited['pending_recharge_cents']==0,edited
        assert old['stake_cents']==600000 and old['pending_recharge_cents']==35000,old
        assert bulk['stake_cents']==700000 and bulk['pending_recharge_cents']==200000,bulk
        assert row('ManualUnlisted')['stake_cents']==450000
        for account,id in ids.items():
            assert select(account)['id']==id
        # Re-upload identical snapshot never adds to original capital.
        again,done=recharge(content)
        assert done['changed']==0,done
        assert row('ManualFixed')['stake_cents']==1200000
        assert row('ManualZero')['stake_cents']==230000

        # Upload a newer corrected daily snapshot. Same-day amount overwrites.
        changed='\n'.join([
           '首次充值','ManualFixed','8000',
           '首次充值','ManualZero','2500',
           '首次充值','ManualEdited','5500',
           '首次充值','OlderAccount','350',
           '首次充值','BulkToday','9000'])
        q,done=recharge(changed)
        assert done['changed']==2,done
        assert row('ManualFixed')['stake_cents']==800000
        assert row('ManualFixed')['total_recharge_cents']==800000
        assert row('ManualZero')['stake_cents']==250000
        assert row('ManualZero')['total_recharge_cents']==250000
        assert row('ManualUnlisted')['stake_cents']==450000

        # Explicit 0 in nightly correction also overrides a manual stake to zero.
        zeroed='\n'.join([
           '首次充值','ManualFixed','0',
           '首次充值','ManualZero','2500',
           '首次充值','ManualEdited','5500',
           '首次充值','OlderAccount','350',
           '首次充值','BulkToday','9000'])
        _,done=recharge(zeroed)
        assert done['changed']==1,done
        assert row('ManualFixed')['stake_cents']==0
        assert row('ManualFixed')['total_recharge_cents']==0
        # Remove a member from the next full snapshot: restore initial manual base,
        # rather than retaining stale imported values or double-counting.
        omitted='\n'.join([
           '首次充值','ManualFixed','0',
           '首次充值','ManualEdited','5500',
           '首次充值','OlderAccount','350',
           '首次充值','BulkToday','9000'])
        _,done=recharge(omitted)
        assert row('ManualZero')['stake_cents']==0
        assert row('ManualZero')['total_recharge_cents']==0

        # The next business day closes supplements once for older and bulk
        # members; manually-added initial deposits are never added a second time.
        with a.engine.begin() as db:
            a.settle_past_days(db,tomorrow)
        assert row('OlderAccount')['total_recharge_cents']==635000
        assert row('BulkToday')['total_recharge_cents']==900000
        assert row('ManualEdited')['total_recharge_cents']==550000
        assert row('ManualFixed')['total_recharge_cents']==0
        assert row('ManualZero')['total_recharge_cents']==0
        with a.engine.begin() as db:
            a.settle_past_days(db,tomorrow)
        assert row('OlderAccount')['total_recharge_cents']==635000
    print('PASS: manual same-day replace, zero deposit add, edit baseline, reupload idempotent, true topups retained, midnight once')
