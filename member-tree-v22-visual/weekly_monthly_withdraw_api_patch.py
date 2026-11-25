"""V22: read-only current/historical week and month withdrawal overviews.

Daily snapshot ledger has unique (member_id,business_day), so frequency means
distinct positive-withdrawal days, NOT intra-day transactions. Same-day repeated
uploads replace the snapshot and do not increase frequency.
No database schema changes, writes, or adjustments to existing money records.
"""
from pathlib import Path
p=Path('member-tree/app.py')
src=p.read_text(encoding='utf-8')
anchor="@app.get('/api/history/withdrawals')"
assert src.count(anchor)==1,'V22 historical withdrawal endpoint has changed'
api=r'''
@app.get('/api/history/withdrawals/overview')
def v22_history_withdrawal_overview(req:Request, mode:str, day:str):
    """Summarize member withdrawal DAYS for the calendar week/month containing day.

    Positive final daily ledger rows indicate withdrawals. Negative rows are
    returns and must not count as withdrawals. Days without uploaded/captured
    records remain explicitly missing; no synthetic zeros or older balances.
    """
    require(req)
    valid_date(day)
    today=current_day()
    if day>today:raise HTTPException(400,'不能查询未来日期')
    if mode not in ('week','month'):
        raise HTTPException(400,'仅支持本周或本月提现总览')
    anchor_day=date.fromisoformat(day)
    if mode=='week':
        start_day=anchor_day-timedelta(days=anchor_day.weekday())
        last_day=start_day+timedelta(days=6)
    else:
        start_day=anchor_day.replace(day=1)
        next_month=(start_day.replace(year=start_day.year+1,month=1)
                    if start_day.month==12 else
                    start_day.replace(month=start_day.month+1))
        last_day=next_month-timedelta(days=1)
    first=start_day.isoformat()
    end=min(last_day,date.fromisoformat(today)).isoformat()
    with engine.connect() as db:
        # Include import-day markers for days with zero withdrawals; include
        # ledger-only days for manually-entered daily snapshots as well.
        recorded_days=set(r[0] for r in db.execute(text("""
            SELECT business_day FROM daily_import_days
               WHERE business_day>=:first AND business_day<=:last
            UNION
            SELECT DISTINCT business_day FROM daily_withdraw_ledger
               WHERE business_day>=:first AND business_day<=:last
            """),{'first':first,'last':end}).all())
        by_member=db.execute(text("""
            SELECT l.member_id AS member_id,m.account AS account,
              COUNT(DISTINCT l.business_day) AS withdrawal_days,
              SUM(l.amount_cents) AS amount_cents,
              MIN(l.business_day) AS first_withdraw_day,
              MAX(l.business_day) AS last_withdraw_day
            FROM daily_withdraw_ledger l
            JOIN members m ON m.id=l.member_id
            WHERE l.business_day>=:first AND l.business_day<=:last
              AND m.deleted=0 AND l.amount_cents>0
            GROUP BY l.member_id,m.account
            ORDER BY withdrawal_days DESC,amount_cents DESC,m.account
            """),{'first':first,'last':end}).mappings().all()
    result=[]
    for item in by_member:
        times=int(item['withdrawal_days'])
        amount=int(item['amount_cents'])
        result.append({
            'id':item['member_id'],'account':item['account'],
            'days':times,'amount_cents':amount,
            'first_day':item['first_withdraw_day'],
            'last_day':item['last_withdraw_day'],
            'tier':'high' if times>=4 else 'mid' if times>=2 else 'low'
        })
    period_days=(date.fromisoformat(end)-start_day).days+1
    return JSONResponse({
        'mode':mode,'day':day,'start_day':first,'end_day':end,
        'recorded':bool(recorded_days),'recorded_days':len(recorded_days),
        'expected_days':period_days,
        'missing_days':period_days-len(recorded_days),
        'complete':len(recorded_days)==period_days,
        'members':result,'count':len(result),
        'total_withdraw_cents':sum(r['amount_cents'] for r in result),
        'once_count':sum(r['tier']=='low' for r in result),
        'repeat_count':sum(r['days']>=2 for r in result),
        'two_three_count':sum(r['tier']=='mid' for r in result),
        'four_plus_count':sum(r['tier']=='high' for r in result),
        'frequency_definition':'one_positive_final_ledger_day_per_member',
        'source':'daily_withdraw_ledger'
    },headers={'Cache-Control':'no-store, max-age=0'})

'''
src=src.replace(anchor,api+anchor,1)
assert src.count('def v22_history_withdrawal_overview(')==1
p.write_text(src,encoding='utf-8')
print('PASS: V22 weekly/monthly read-only withdrawal-day overview from recorded final daily ledgers')
