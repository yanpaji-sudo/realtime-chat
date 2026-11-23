"""Berlin: reconcile same-day manually created members against nightly recharge snapshots.

Tracked manually-added join-day members use uploaded amount as the authoritative
initial deposit. This avoids counting the manual initial deposit twice and lets
a new member with 0 initial capital acquire the uploaded deposit automatically.

Historical members, bulk-imported members and genuine supplementary deposits
retain the prior unchanged settlement logic. All changes are transactional;
same-day reuploads are idempotent and do not alter bank balances or withdrawals.
"""
meta_sql="""CREATE TABLE IF NOT EXISTS berlin_manual_join_deposits (
    member_id TEXT PRIMARY KEY,
    business_day TEXT NOT NULL,
    manual_base_cents BIGINT NOT NULL,
    marked_at TEXT NOT NULL
)"""
# 1. Mark only a manually inserted/overwritten member whose joined_on is today
# and does not already have a confirmed daily recharge for the day.
create_begin=a.index("def create_member(data: MemberIn, req: Request):")
create_end=a.index("\n@app.put('/api/members/{mid}')",create_begin)
create=a[create_begin:create_end]
anchor="        capture_current_report(db)"
assert create.count(anchor)==1,'Manual member create function changed'
stamp=r'''        if data.joined_on==current_day():
            db.execute(text("""CREATE TABLE IF NOT EXISTS berlin_manual_join_deposits (
                member_id TEXT PRIMARY KEY,
                business_day TEXT NOT NULL,
                manual_base_cents BIGINT NOT NULL,
                marked_at TEXT NOT NULL
            )"""))
            seen_cashflow=db.execute(text("""SELECT 1 FROM berlin_daily_recharge
                WHERE member_id=:m AND business_day=:d"""),
                {'m':mid,'d':current_day()}).scalar()
            if not seen_cashflow:
                db.execute(text("""INSERT INTO berlin_manual_join_deposits
                    (member_id,business_day,manual_base_cents,marked_at)
                    VALUES (:m,:d,:v,:t)
                    ON CONFLICT(member_id) DO UPDATE SET
                    business_day=excluded.business_day,
                    manual_base_cents=excluded.manual_base_cents,
                    marked_at=excluded.marked_at"""),
                    {'m':mid,'d':current_day(),'v':stake,'t':utc_now()})
'''
create=create.replace(anchor,stamp+anchor,1)
a=a[:create_begin]+create+a[create_end:]
# 2. Existing /edit screen may adjust a manually-entered stake BEFORE the
# daily upload; keep the original manual base synchronized until first upload.
edit_begin=a.index("def update_member(mid: str, data: MemberIn, req: Request):")
edit_end=a.index("\n@app.delete('/api/members/{mid}')",edit_begin)
edit=a[edit_begin:edit_end]
edit_anchor="            record_undo(db,operator.get('username',''),'update',f'编辑会员 {account}',"
assert edit.count(edit_anchor)==1,'Manual member edit function changed'
edit_stamp=r'''            if data.joined_on==current_day():
                db.execute(text("""CREATE TABLE IF NOT EXISTS berlin_manual_join_deposits (
                    member_id TEXT PRIMARY KEY, business_day TEXT NOT NULL,
                    manual_base_cents BIGINT NOT NULL, marked_at TEXT NOT NULL
                )"""))
                existing_marker=db.execute(text("""SELECT 1 FROM berlin_manual_join_deposits
                    WHERE member_id=:m AND business_day=:d"""),
                    {'m':mid,'d':current_day()}).scalar()
                cashflow=db.execute(text("""SELECT 1 FROM berlin_daily_recharge
                    WHERE member_id=:m AND business_day=:d"""),
                    {'m':mid,'d':current_day()}).scalar()
                if existing_marker and not cashflow:
                    db.execute(text("""UPDATE berlin_manual_join_deposits
                        SET manual_base_cents=:v,marked_at=:t
                        WHERE member_id=:m AND business_day=:d"""),
                        {'m':mid,'d':current_day(),'v':stake,'t':utc_now()})
'''
edit=edit.replace(edit_anchor,edit_stamp+edit_anchor,1)
a=a[:edit_begin]+edit+a[edit_end:]
# 3. Shared metadata query. Only same-day manually-added members are eligible.
helper=r'''
def berlin_join_manual_markers(db,day):
    db.execute(text("""CREATE TABLE IF NOT EXISTS berlin_manual_join_deposits (
        member_id TEXT PRIMARY KEY,
        business_day TEXT NOT NULL,
        manual_base_cents BIGINT NOT NULL,
        marked_at TEXT NOT NULL
    )"""))
    return {str(r['member_id']):dict(r) for r in
        db.execute(text("""SELECT member_id,business_day,manual_base_cents
           FROM berlin_manual_join_deposits WHERE business_day=:d"""),
           {'d':day}).mappings()}
'''
begin=a.index("@app.post('/api/recharge/preview')")
a=a[:begin]+helper+"\n"+a[begin:]

# 4. Preview: for today's manual members, recharge is entirely initial
# capital, not a supplemental deposit. Show accurate expected totals.
begin=a.index("def berlin_recharge_preview(")
end=a.index("\n@app.post('/api/recharge/{jobid}/confirm')",begin)
segment=a[begin:end]
anchor="        day=current_day()\n        uploaded=covered=supplement=0"
assert segment.count(anchor)==1,'Recharge preview aggregation anchor changed'
segment=segment.replace(anchor,"        day=current_day()\n        manual_marks=berlin_join_manual_markers(db,day)\n        uploaded=covered=supplement=0",1)
anchor="            extra,base=berlin_recharge_supplement(row,day,amt)\n            uploaded+=amt;covered+=base;supplement+=extra"
assert segment.count(anchor)==1,'Recharge preview amounts anchor changed'
segment=segment.replace(anchor,
"""            extra,base=berlin_recharge_supplement(row,day,amt)
            if row['id'] in manual_marks and row['joined_on']==day and row['account'] in result:
                extra,base=0,amt
            uploaded+=amt;covered+=base;supplement+=extra""",1)
old_summary="'summary':'按完整会员账号覆盖今天的充值快照；入会当天已记入建仓的金额只算一次，超出部分算补仓。入会后日期的充值均为补仓。补仓于北京时间次日0点结转到总充值。'"
assert segment.count(old_summary)==1, 'Recharge preview summary anchor changed'
segment=segment.replace(old_summary,"'summary':'今天手动新增的会员，上传充值金额直接同步为建仓（已填金额覆盖、0元建仓补入），不重复累计；其他会员仍按原规则处理补仓，次日结算。'",1)
a=a[:begin]+segment+a[end:]

# 5. Confirmation: revise the member stake, recharge snapshot and undo
# record in the same transaction. Never touch balance_cents or withdraws.
begin=a.index("def berlin_recharge_confirm(")
end=a.index("\n@app.post('/api/import/{jobid}/confirm')",begin)
segment=a[begin:end]
anchor="""        previous={row['member_id']:dict(row) for row in db.execute(text('''SELECT *
                  FROM berlin_daily_recharge WHERE business_day=:d'''),{'d':today}).mappings()}"""
assert segment.count(anchor)==1, 'Recharge snapshot anchor changed'
segment=segment.replace(anchor,anchor+"\n        manual_marks=berlin_join_manual_markers(db,today)",1)
old=r'''            extra,base=berlin_recharge_supplement(row,today,new)
            uploaded+=new;covered+=base;extra_total+=extra
            prior=previous.get(mid)
            if prior and (int(prior['uploaded_cents']),int(prior['supplement_cents']))==(new,extra):
                continue
            if not prior and new==0:continue
            before=snapshot(db,mid)'''
assert segment.count(old)==1,'Recharge loop core changed'
newtext=r'''            extra,base=berlin_recharge_supplement(row,today,new)
            prior=previous.get(mid)
            stake_override=None
            marker=manual_marks.get(mid)
            if marker and row['joined_on']==today:
                # An explicit uploaded amount (including zero) replaces the
                # manually entered initial deposit, rather than supplementing it.
                if row['account'] in amounts:
                    stake_override=new
                    extra,base=0,new
                elif prior:
                    # A previously imported snapshot was removed by the next
                    # full-day upload: restore the pre-upload manual value.
                    stake_override=int(marker['manual_base_cents'])
                    extra,base=0,0
            uploaded+=new;covered+=base;extra_total+=extra
            changed_stake=stake_override is not None and stake_override!=int(row['stake_cents'])
            if prior and (int(prior['uploaded_cents']),int(prior['supplement_cents']))==(new,extra) and not changed_stake:
                continue
            if not prior and new==0 and not changed_stake:continue
            before=snapshot(db,mid)
            if changed_stake:
                db.execute(text("""UPDATE members SET stake_cents=:value
                    WHERE id=:mid"""),{'value':stake_override,'mid':mid})'''
segment=segment.replace(old,newtext,1)
# A reupload of an identical snapshot has no write to the member or ledger.
# More importantly, changing the snapshot never adds new to the old stake.
a=a[:begin]+segment+a[end:]
assert a.count("def berlin_join_manual_markers(")==1
assert "stake_override=new" in a
assert a.count("berlin_join_manual_markers(db,today)")==1
ap.write_text(a,encoding='utf-8')
