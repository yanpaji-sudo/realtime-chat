"""Only synthetic V22 sandbox records. Never reads or imports production member data."""
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import text

GROUPS = ("SAN001", "SAN002", "SAN003", "SAN006", "SAN008")
NAMESPACE = uuid.UUID("bc58e258-f1aa-4d3f-9ca2-143326e8f100")

def seed_if_empty(engine):
    if os.environ.get("V22_SANDBOX") != "1":
        raise RuntimeError("Sandbox seed disabled outside isolated test service")
    if os.environ.get("V22_SANDBOX_DATA_SEED") != "SYNTHETIC_100_ONLY":
        raise RuntimeError("Sandbox seed confirmation is missing")
    with engine.begin() as db:
        count = int(db.execute(text("SELECT COUNT(*) FROM members")).scalar() or 0)
        if count:
            print("V22_SANDBOX: database already contains member rows; no seed changes applied", flush=True)
            return count

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        today = date.today()
        records = []
        for gi, account in enumerate(GROUPS):
            group_tag = account[-3:]
            root_id = str(uuid.uuid5(NAMESPACE, account))
            records.append(dict(
                id=root_id, account=account,
                joined_on=(today-timedelta(days=240)).isoformat(),
                parent_id=None, balance_cents=0, total_withdraw_cents=0,
                daily_withdraw_cents=0, stake_cents=1000000, daily_withdraw_on=None,
                remark="虚拟组长"+group_tag, created_at=now, updated_at=now
            ))
            branch_ids=[]
            for pos in range(1,20):
                demo_account="TEST"+group_tag+"_"+str(pos).zfill(3)
                uid=str(uuid.uuid5(NAMESPACE, demo_account))
                if pos<=5:
                    parent=root_id
                elif pos<=12:
                    parent=branch_ids[(pos-6)%5]
                elif pos<=17:
                    parent=branch_ids[5+(pos-13)%7]
                else:
                    parent=branch_ids[12+(pos-18)%5]
                days=(17*pos+29*gi)%168+4
                stake=500000 if pos%3==0 else 1000000
                balance=200000+(pos*197143+gi*389119)%2500000
                withdraw=(pos*125317+gi*82513)%400000
                daily=10000*(pos%4) if pos%7==0 else 0
                records.append(dict(
                    id=uid,account=demo_account,
                    joined_on=(today-timedelta(days=days)).isoformat(),
                    parent_id=parent,balance_cents=balance,
                    total_withdraw_cents=withdraw,
                    daily_withdraw_cents=daily,stake_cents=stake,
                    daily_withdraw_on=today.isoformat() if daily else None,
                    remark="虚拟"+group_tag+"组"+str(pos).zfill(2),
                    created_at=now,updated_at=now
                ))
                branch_ids.append(uid)
        assert len(records)==100 and len({r["account"] for r in records})==100
        statement=text("""INSERT INTO members(
            id,account,joined_on,parent_id,balance_cents,total_withdraw_cents,
            daily_withdraw_cents,stake_cents,daily_withdraw_on,remark,
            created_at,updated_at
        ) VALUES (
            :id,:account,:joined_on,:parent_id,:balance_cents,:total_withdraw_cents,
            :daily_withdraw_cents,:stake_cents,:daily_withdraw_on,:remark,
            :created_at,:updated_at
        )""")
        for row in records:
            db.execute(statement,row)
    print("V22_SANDBOX: created exactly 100 synthetic members, 5 demo group roots, isolated database",flush=True)
    return 100
