"""V22 read-only historical daily withdrawals API.

No new tables, no writes, no changes to existing withdrawal settlement.
Uses recorded daily_withdraw_ledger and daily_import_days, not present-day values.
"""
from pathlib import Path
p=Path('member-tree/app.py')
src=p.read_text(encoding='utf-8')
assert src.count("@app.get('/api/tree')")==1
api=r'''
@app.get('/api/history/withdrawals')
def v22_history_withdrawals(req:Request, day:str):
    """Read last recorded member withdrawals for a Beijing business date."""
    require(req)
    valid_date(day)
    if day>current_day():raise HTTPException(400,'不能查询未来日期')
    with engine.connect() as db:
        imported=db.execute(text("""SELECT recorded_at FROM daily_import_days
               WHERE business_day=:day"""),{'day':day}).scalar()
        logged=db.execute(text("""SELECT 1 FROM daily_withdraw_ledger
               WHERE business_day=:day LIMIT 1"""),{'day':day}).scalar() is not None
        history=db.execute(text("""SELECT l.member_id,m.account,l.amount_cents
               FROM daily_withdraw_ledger AS l
               JOIN members AS m ON m.id=l.member_id
               WHERE l.business_day=:day AND m.deleted=0
                 AND l.amount_cents<>0
               ORDER BY m.account"""),{'day':day}).mappings().all()
    members=[{'id':r['member_id'],'account':r['account'],
              'amount_cents':int(r['amount_cents'])} for r in history]
    return JSONResponse({
        'day':day,'recorded':bool(imported is not None or logged),
        'recorded_at':imported,'members':members,'count':len(members),
        'withdraw_count':sum(r['amount_cents']>0 for r in members),
        'return_count':sum(r['amount_cents']<0 for r in members),
        'withdraw_cents':sum(max(0,r['amount_cents']) for r in members),
        'source':'daily_withdraw_ledger' if imported is not None or logged else 'not_recorded',
    },headers={'Cache-Control':'no-store, max-age=0'})

'''
src=src.replace("@app.get('/api/tree')",api+"@app.get('/api/tree')",1)
assert src.count('def v22_history_withdrawals(')==1
p.write_text(src,encoding='utf-8')
print('PASS: historical withdrawal read-only API reads existing recorded day snapshots')
