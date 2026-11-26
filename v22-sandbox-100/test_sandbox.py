"""Offline regression for isolated V22 sandbox: no production database or network use."""
import os, sys, tempfile
from pathlib import Path
from sqlalchemy import text
sys.path.insert(0,str(Path("member-tree").resolve()))
with tempfile.TemporaryDirectory() as d:
    db_file=Path(d)/"v22-sandbox-only.db"
    os.environ["DATABASE_URL"]="sqlite:///"+str(db_file)
    os.environ["V22_SANDBOX"]="1"
    os.environ["V22_SANDBOX_DATA_SEED"]="SYNTHETIC_100_ONLY"
    os.environ["ENABLE_MIDNIGHT_WORKER"]="0"
    import app
    app.startup()
    with app.engine.begin() as db:
        items=[dict(x) for x in db.execute(text("SELECT id,account,parent_id,remark,balance_cents FROM members")).mappings().all()]
        assert len(items)==100,(len(items),"Expected 100 unique synthetic records")
        accounts={x["account"] for x in items}
        assert len(accounts)==100
        assert all(a.startswith("TEST") or a in ("SAN001","SAN002","SAN003","SAN006","SAN008") for a in accounts)
        roots=[x for x in items if x["parent_id"] is None]
        assert len(roots)==5, roots
        valid_ids={x["id"] for x in items}
        assert all(x["parent_id"] is None or x["parent_id"] in valid_ids for x in items)
        target=next(x for x in items if x["account"]=="TEST001_001")
        db.execute(text("UPDATE members SET balance_cents=98765432,remark='manual edit kept' WHERE id=:i"),{"i":target["id"]})
    app.startup()
    with app.engine.connect() as db:
        assert int(db.execute(text("SELECT COUNT(*) FROM members")).scalar())==100
        r=db.execute(text("SELECT balance_cents,remark FROM members WHERE account='TEST001_001'")).one()
        assert r.balance_cents==98765432 and r.remark=="manual edit kept",r
    print("PASS: exactly 100 fake member rows; 5 roots; valid tree links; idempotent; edits preserved")
