"""Berlin batch-import override: uploaded rows are authoritative for their accounts.
New accounts insert; old accounts update the six supplied fields; omitted accounts
and unrelated balance/daily finance ledgers remain untouched.
"""
# Reuse previously verified multicolumn Excel/CSV header and amount parsing.
begin=a.index('def berlin_today_sheet(payload, filename):')
end=a.index("\n@app.post('/api/berlin/daily-new/preview')",begin)
parser=a[begin:end]
replacements=[
    ("accepted=[];old=0;seen=set();repeated=0",
     "accepted_by_account={};old=0;seen=set();repeated=0"),
    ("        if key in seen:\n            repeated+=1;continue\n        seen.add(key)",
     "        if key in seen:repeated+=1\n        seen.add(key)"),
    ("        if joined!=today:\n            old+=1;continue",
     "        if joined!=today:old+=1"),
    ("        accepted.append({'account':acct,'parent_account':parent,'joined_on':joined,",
     "        accepted_by_account[key]={'account':acct,'parent_account':parent,'joined_on':joined,"),
    ("                         'total_cents':cents(value(row,'total'),idx,'历史总提现')})",
     "                         'total_cents':cents(value(row,'total'),idx,'历史总提现')}"),
    ("    return {'records':accepted,'total_rows':len(seen),'other_date':old,",
     "    return {'records':list(accepted_by_account.values()),'total_rows':len(seen),'other_date':old,")
]
for old,new in replacements:
    assert parser.count(old)==1, f'Berlin parser replacement anchor mismatch: {old[:80]}'
    parser=parser.replace(old,new,1)

api_code=r'''
@app.post('/api/berlin/daily-new/preview')
async def berlin_new_preview(req:Request, upload:UploadFile=File(...)):
    require(req,'admin',True)
    raw=await upload.read(15*1024*1024+1)
    if len(raw)>15*1024*1024:raise HTTPException(400,'文件不得超过15MB')
    parsed=berlin_today_sheet(raw,upload.filename or '')
    with engine.begin() as db:
        write_lock(db)
        members=active_rows(db)
        stamp=roster_stamp(members)
        existing_rows=db.execute(text('SELECT id,account,deleted FROM members')).mappings().all()
        existing={str(r['account']).casefold():r for r in existing_rows}
        records=parsed['records']
        new_records=[r for r in records if r['account'].casefold() not in existing]
        update_records=[r for r in records if r['account'].casefold() in existing]
        incoming={r['account'].casefold() for r in records}
        placeholders=sorted(
          {r['parent_account'] for r in records if r['parent_account']
           and r['parent_account'].casefold() not in existing
           and r['parent_account'].casefold() not in incoming},
          key=str.casefold)
        jobid=None
        if records:
            db.execute(text("""CREATE TABLE IF NOT EXISTS berlin_bulk_new_jobs
                (id TEXT PRIMARY KEY, rows_json TEXT NOT NULL,
                 source_stamp TEXT NOT NULL,created_at TEXT NOT NULL)"""))
            jobid=str(uuid.uuid4())
            db.execute(text("""INSERT INTO berlin_bulk_new_jobs(id,rows_json,source_stamp,created_at)
                 VALUES (:id,:data,:stamp,:created)"""),
                 {'id':jobid,
                  'data':json.dumps({'records':records,'placeholders':placeholders},ensure_ascii=False),
                  'stamp':stamp,'created':utc_now()})
    return {'valid':bool(records),'job_id':jobid,
        'business_day':parsed['today'],'header_row':parsed['header_row'],
        'total_rows':parsed['total_rows'],'new_count':len(new_records),
        'updated_count':len(update_records),
        'old_count':parsed['other_date'],'existing_count':len(update_records),
        'duplicate_count':parsed['repeated'],'placeholder_count':len(placeholders),
        'placeholder_examples':placeholders[:15],'fields':parsed['columns'],
        'stake_cents':sum(r['stake_cents'] for r in records),
        'total_withdraw_cents':sum(r['total_cents'] for r in records),
        'sample':records[:8],
        'message':'本次文件为最新数据：已存在账号覆盖姓名、上级、建仓、累计提现和注册日期；不存在账号新增。未上传账号及其余额、当日资金流水不清空。'}

@app.post('/api/berlin/daily-new/{job_id}/confirm')
def berlin_new_confirm(job_id:str,req:Request):
    actor=require(req,'admin',True)
    with engine.begin() as db:
        write_lock(db)
        settle_past_days(db)
        db.execute(text("""CREATE TABLE IF NOT EXISTS berlin_bulk_new_jobs
            (id TEXT PRIMARY KEY, rows_json TEXT NOT NULL,
             source_stamp TEXT NOT NULL,created_at TEXT NOT NULL)"""))
        row=db.execute(text('SELECT * FROM berlin_bulk_new_jobs WHERE id=:i'),{'i':job_id}).mappings().first()
        if not row:raise HTTPException(404,'预览已失效，请重新上传文件')
        if roster_stamp(active_rows(db))!=row['source_stamp']:
            raise HTTPException(409,'会员资料已被其他管理员修改，请重新预览，确保最后提交的文件为准')
        saved=json.loads(row['rows_json'])
        records=saved.get('records',[])
        placeholders=saved['placeholders']
        if not records:raise HTTPException(400,'没有可导入的会员')
        existing_rows=db.execute(text('SELECT id,account,parent_id,deleted FROM members')).mappings().all()
        existing={str(r['account']).casefold():r for r in existing_rows}
        known={k:str(r['id']) for k,r in existing.items()}
        for rec in records:
            key=rec['account'].casefold()
            if key not in known:known[key]=str(uuid.uuid4())
        for parent in placeholders:
            known.setdefault(parent.casefold(),str(uuid.uuid4()))
        # Build planned parent graph before writing anything. Catch cycles
        # spanning an imported existing member and any unchanged account.
        parent_graph={str(r['id']):str(r['parent_id']) if r['parent_id'] else None
                      for r in existing_rows}
        for parent in placeholders:
            parent_graph.setdefault(known[parent.casefold()],None)
        for rec in records:
            mid=known[rec['account'].casefold()]
            parent=rec['parent_account']
            parent_graph[mid]=known.get(parent.casefold()) if parent else None
            if parent and parent.casefold() not in known:
                raise HTTPException(400,'未找到上级会员：'+parent)
        for rec in records:
            start=known[rec['account'].casefold()]
            seen=set();step=start
            while step:
                if step in seen:raise HTTPException(400,'导入后形成循环推荐关系：'+rec['account'])
                seen.add(step)
                step=parent_graph.get(step)
        now=utc_now()
        changes=[];created=updated=0
        for parent in placeholders:
            key=parent.casefold()
            if key in existing:continue
            mid=known[key]
            db.execute(text("""INSERT INTO members
                (id,account,joined_on,parent_id,stake_cents,total_withdraw_cents,remark,created_at,updated_at)
                VALUES (:id,:account,:joined,NULL,0,0,:remark,:now,:now)"""),
                {'id':mid,'account':parent,'joined':current_day(),
                 'remark':'上级占位（待补资料）','now':now})
            changes.append({'id':mid,'account':parent,'before':None})
        db.execute(text("""CREATE TABLE IF NOT EXISTS member_registration_times
            (member_id TEXT PRIMARY KEY, registered_at TEXT NOT NULL)"""))
        for rec in records:
            key=rec['account'].casefold();mid=known[key]
            data={'id':mid,'account':rec['account'],'joined':rec['joined_on'],
                  'stake':rec['stake_cents'],'total':rec['total_cents'],
                  'remark':rec['remark'],'now':now}
            if key in existing:
                before=snapshot(db,mid)
                db.execute(text("""UPDATE members SET account=:account,joined_on=:joined,
                    parent_id=NULL,stake_cents=:stake,total_withdraw_cents=:total,
                    remark=:remark,deleted=0,revision=revision+1,updated_at=:now
                    WHERE id=:id"""),data)
                updated+=1
            else:
                before=None
                db.execute(text("""INSERT INTO members
                    (id,account,joined_on,parent_id,stake_cents,total_withdraw_cents,remark,created_at,updated_at)
                    VALUES (:id,:account,:joined,NULL,:stake,:total,:remark,:now,:now)"""),data)
                created+=1
            changes.append({'id':mid,'account':rec['account'],'before':before})
            db.execute(text("""INSERT INTO member_registration_times(member_id,registered_at)
                VALUES (:i,:t) ON CONFLICT(member_id) DO UPDATE SET registered_at=excluded.registered_at"""),
                {'i':mid,'t':rec['joined_on']})
        for rec in records:
            parent=rec['parent_account']
            if parent:
                db.execute(text('UPDATE members SET parent_id=:p WHERE id=:i'),
                  {'i':known[rec['account'].casefold()],'p':known[parent.casefold()]})
        if len(changes)<=500:
            record_undo(db,actor.get('username',''),'update',
                f'批量同步会员：新增{created}、覆盖{updated}',
                [dict(c,after=snapshot(db,c['id'])) for c in changes])
        audit(db,'update',{'mode':'berlin_bulk_latest_wins',
            'created':created,'updated':updated,'placeholders':len(placeholders),
            'accounts':[r['account'] for r in records[:25]]},actor.get('username',''))
        capture_current_report(db)
        db.execute(text('DELETE FROM berlin_bulk_new_jobs WHERE id=:i'),{'i':job_id})
    return {'ok':True,'created':created,'updated':updated,
            'placeholders':len(placeholders),'total_added':created+len(placeholders),
            'preserved_unlisted':True,'latest_wins':True}
'''
route_start=a.index("\n@app.post('/api/berlin/daily-new/preview')",begin)
route_end=a.index("\n@app.post('/api/admin/legacy/preview')",route_start)
a=a[:begin]+parser+api_code+a[route_end:]
assert a.count('def berlin_new_confirm(')==1
assert a.count('def berlin_new_preview(')==1
# UI: Keep same original server URL and button, but state exact overwrite semantics.
h=h.replace('📥 今日会员批量导入','📥 批量导入 / 覆盖')
h=h.replace('批量导入今日新增会员','批量同步会员（新增／覆盖）')
h=h.replace('只新增注册日期为今天且尚未建档的会员，其他日期及原有会员一律保留。不存在的上级自动创建零金额占位节点。',
  '表格中出现的会员账号均按最后上传的数据为准，已有会员覆盖六项资料，新会员新增；未在文件中的会员保留。余额及当日流水不清空。')
h=h.replace('② 确认导入今日新增','② 确认批量新增／覆盖')
# UI preview -- preserve async preview/confirm interaction.
old_preview="result.textContent='文件会员账号数：'+d.total_rows+'\\n今日注册记录：'+(d.new_count+d.existing_count)+"
start=j.index(old_preview)
end=j.index("    jobId=d.job_id;confirm.disabled=!d.valid;",start)
replacement=r"""result.textContent='文件会员账号数：'+d.total_rows+
      '\n新账号（新增）：'+d.new_count+' 位\n同账号（覆盖）：'+d.updated_count+
      ' 位\n非今日注册：'+d.old_count+' 位（也按最后上传覆盖）\n本文件内重复账号：'+d.duplicate_count+
      ' 位（仅最后一条有效）\n需补建上级：'+d.placeholder_count+' 位'+
      '\n本次表格建仓合计：'+money(d.stake_cents,true)+
      '\n本次表格累计提现合计：'+money(d.total_withdraw_cents,true)+
      '\n表头位于第 '+d.header_row+' 行'+
      '\n未知上级示例：'+(d.placeholder_examples||[]).join('、')+
      '\n前8条会员预览：\n'+sample+'\n\n'+d.message+
      (d.valid?'\n请核对后确认提交。':'\n文件没有有效会员，请检查源数据。');
"""
j=j[:start]+replacement+j[end:]
j=j.replace("result.textContent='正在检查六项数据与今日新增名单…';",
            "result.textContent='正在检查新会员、重复账号与六项覆盖数据…';")
j=j.replace("if(!window.confirm('仅新增今天注册且尚未建档的会员，保留历史数据，确认执行吗？'))return;",
            "if(!window.confirm('表格内已存在的账号将按最后上传的六项数据覆盖，未在表格内的账号不动。确认提交吗？'))return;")
j=j.replace("result.textContent='已成功增加 '+d.created+' 位今日会员；补建上级 '+d.placeholders+' 位。原会员及原资金数据未覆盖。';",
            "result.textContent='已新增 '+d.created+' 位，已覆盖 '+d.updated+' 位；补建上级 '+d.placeholders+' 位。未上传会员及其余额、当日资金流水均保留。';")
j=j.replace("showToast('今日会员批量导入成功：'+d.created+' 位')",
            "showToast('批量同步成功：新增'+d.created+'，覆盖'+d.updated+'位')")
assert "同账号（覆盖）" in j
assert "最新数据" in a
ap.write_text(a,encoding='utf-8')
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
