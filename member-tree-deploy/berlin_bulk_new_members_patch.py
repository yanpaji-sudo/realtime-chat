"""Berlin-only incremental import of today's newly registered members.

This feature intentionally does NOT invoke the existing six-column full-replacement
importer. It never deletes or resets current members or finance balances.
"""
backend=r'''
def berlin_today_sheet(payload, filename):
    """Read the six tree fields from a full multi-column member export."""
    from datetime import datetime, date
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    ext=os.path.splitext((filename or '').lower())[1]
    rows=[]
    if ext in ('.xlsx','.xlsm'):
        try:
            book=load_workbook(io.BytesIO(payload),read_only=True,data_only=True)
            for sheet in book:
                for row in sheet.iter_rows(values_only=True):
                    rows.append(list(row))
                    if len(rows)>70000:raise HTTPException(400,'表格最多70000行')
            book.close()
        except HTTPException:raise
        except Exception as exc:raise HTTPException(400,'无法读取Excel表格：'+str(exc)[:130])
    elif ext in ('.csv','.txt','.tsv'):
        try:
            raw=payload.decode('utf-8-sig')
        except UnicodeDecodeError:
            raw=payload.decode('gb18030')
        try:
            sample=raw[:4096]
            delimiter=('\t' if sample.count('\t')>sample.count(',') else ',')
            rows=list(csv.reader(io.StringIO(raw),delimiter=delimiter))
        except Exception as exc:raise HTTPException(400,'CSV表格读取失败：'+str(exc)[:130])
        if len(rows)>70000:raise HTTPException(400,'表格最多70000行')
    else:
        raise HTTPException(400,'请上传Excel .xlsx/.xlsm或CSV表格')
    if not rows:raise HTTPException(400,'文件中没有数据')
    aliases={
      'account':['会员账号','会员帐号','账号','会员账户'],
      'remark':['真实姓名','会员姓名','姓名'],
      'parent':['直属代理商','隶属代理商','直属上级','上级账号','推荐人账号','推荐人','上级会员账号'],
      'stake':['历史总充值','历史累计充值','历史充值总额','累计充值金额','总充值','历史总存款','总存款','历史累计存款'],
      'total':['历史总提现','历史累计提现','历史提现总额','累计提现金额','总提现','历史累计提款','总提款'],
      'joined':['注册时间','注册日期','加入时间','加入日期','入会时间','开户时间']
    }
    def norm(x):
        return re.sub(r'[\s：:（）()]','',str(x or '').replace('\ufeff','')).strip()
    header_at=None;columns={}
    for idx,row in enumerate(rows[:25]):
        heads=[norm(v) for v in row]
        mapping={}
        for field,options in aliases.items():
            for name in options:
                if name in heads:
                    mapping[field]=heads.index(name);break
        if 'account' in mapping and len(mapping)>=3:
            header_at=idx;columns=mapping;break
    if header_at is None:
        raise HTTPException(400,'没有识别到会员信息表头：请使用包含“会员账号、直属代理商、注册时间”等列的原始导出表')
    missing=[{'account':'会员账号','remark':'真实姓名','parent':'直属代理商','stake':'历史总充值','total':'历史总提现','joined':'注册时间'}[k] for k in aliases if k not in columns]
    if missing:
        raise HTTPException(400,'无法自动提取完整六项数据，缺少列：'+'、'.join(missing)+'。请上传包含全部列的原始会员表格')
    def value(row,key):
        at=columns[key]
        return row[at] if len(row)>at else None
    def account_str(v):
        if v is None:return ''
        if isinstance(v,float) and v.is_integer():return str(int(v))
        return str(v).strip()
    def cents(v,line,field):
        if v is None or str(v).strip() in ('','-','—'):return 0
        raw=str(v).replace(',','').replace('￥','').replace('¥','').strip()
        try:
            d=Decimal(raw)
            if not d.is_finite() or d<0 or d>Decimal('1000000000000'):raise ValueError()
            return int((d*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        except (InvalidOperation,ValueError):
            raise HTTPException(400,f'Excel第{line}行{field}不是非负金额：{str(v)[:30]}')
    def joined_date(v,line):
        if isinstance(v,datetime):return v.date().isoformat()
        if isinstance(v,date):return v.isoformat()
        if isinstance(v,(int,float)) and v>20000:
            try:
                from openpyxl.utils.datetime import from_excel
                return from_excel(v).date().isoformat()
            except Exception:pass
        s=str(v or '').strip()
        m=re.match(r'^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})',s)
        if m:
            try:return date(*[int(g) for g in m.groups()]).isoformat()
            except ValueError:pass
        raise HTTPException(400,f'Excel第{line}行注册时间无效或为空，不能认定为今日新增')
    today=current_day()
    accepted=[];old=0;seen=set();repeated=0
    for idx,row in enumerate(rows[header_at+1:],header_at+2):
        acct=account_str(value(row,'account'))
        if not acct or acct in ('会员账号','会员帐号'):continue
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',acct):
            raise HTTPException(400,f'Excel第{idx}行会员账号格式错误：{acct[:30]}')
        key=acct.casefold()
        if key in seen:
            repeated+=1;continue
        seen.add(key)
        joined=joined_date(value(row,'joined'),idx)
        if joined!=today:
            old+=1;continue
        parent=account_str(value(row,'parent'))
        if parent in ('—','-','无','根节点','None','null'):parent=''
        if parent and not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',parent):
            raise HTTPException(400,f'Excel第{idx}行直属代理商账号格式错误')
        if parent.casefold()==key:
            raise HTTPException(400,f'Excel第{idx}行上级不能是本人')
        remark=str(value(row,'remark') or '').strip()
        if len(remark)>20:raise HTTPException(400,f'Excel第{idx}行真实姓名超过20字')
        accepted.append({'account':acct,'parent_account':parent,'joined_on':joined,
                         'remark':remark,'stake_cents':cents(value(row,'stake'),idx,'历史总充值'),
                         'total_cents':cents(value(row,'total'),idx,'历史总提现')})
    return {'records':accepted,'total_rows':len(seen),'other_date':old,
            'repeated':repeated,'header_row':header_at+1,'today':today,
            'columns':{key:columns[key]+1 for key in columns}}

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
        present={str(m['account']).casefold() for m in members}
        all_rows=db.execute(text('SELECT account FROM members')).mappings().all()
        historical={str(m['account']).casefold() for m in all_rows}
        candidates=[r for r in parsed['records'] if r['account'].casefold() not in historical]
        skipped_existing=len(parsed['records'])-len(candidates)
        incoming={r['account'].casefold() for r in candidates}
        placeholders=sorted({r['parent_account'] for r in candidates if r['parent_account'] and
                 r['parent_account'].casefold() not in historical and
                 r['parent_account'].casefold() not in incoming},key=str.casefold)
        jobid=None
        if candidates:
            db.execute(text("""CREATE TABLE IF NOT EXISTS berlin_bulk_new_jobs
                (id TEXT PRIMARY KEY, rows_json TEXT NOT NULL,
                 source_stamp TEXT NOT NULL,created_at TEXT NOT NULL)"""))
            jobid=str(uuid.uuid4())
            db.execute(text("""INSERT INTO berlin_bulk_new_jobs(id,rows_json,source_stamp,created_at)
                 VALUES (:id,:data,:stamp,:created)"""),
                 {'id':jobid,'data':json.dumps({'candidates':candidates,'placeholders':placeholders},ensure_ascii=False),
                  'stamp':stamp,'created':utc_now()})
    return {'valid':bool(candidates),'job_id':jobid,
        'business_day':parsed['today'],'header_row':parsed['header_row'],
        'total_rows':parsed['total_rows'],'new_count':len(candidates),
        'old_count':parsed['other_date'],'existing_count':skipped_existing,
        'duplicate_count':parsed['repeated'],'placeholder_count':len(placeholders),
        'placeholder_examples':placeholders[:15],'fields':parsed['columns'],
        'stake_cents':sum(r['stake_cents'] for r in candidates),
        'total_withdraw_cents':sum(r['total_cents'] for r in candidates),
        'sample':candidates[:8],
        'message':'仅增加今日未建档会员，历史会员与资金不覆盖；未知上级自动创建零金额占位节点。'}

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
        if not row:raise HTTPException(404,'预览已失效，请重新选择文件')
        now_members=active_rows(db)
        if roster_stamp(now_members)!=row['source_stamp']:
            raise HTTPException(409,'其他管理员已更新会员资料，请重新预览，避免覆盖或重复')
        saved=json.loads(row['rows_json'])
        candidates=saved['candidates'];placeholders=saved['placeholders']
        if not candidates:raise HTTPException(400,'没有可新增会员')
        current={str(m['account']).casefold():str(m['id']) for m in
                 db.execute(text('SELECT id,account FROM members')).mappings().all()}
        for rec in candidates:
            if rec['account'].casefold() in current:raise HTTPException(409,'会员已存在，请重新预览')
        now=utc_now()
        from datetime import date
        all_new=[]
        # All new members/placeholder IDs allocated before relationship linking.
        for account in placeholders:
            if account.casefold() not in current:
                current[account.casefold()]=str(uuid.uuid4())
        for rec in candidates:
            current[rec['account'].casefold()]=str(uuid.uuid4())
        for account in placeholders:
            mid=current[account.casefold()]
            db.execute(text("""INSERT INTO members
                (id,account,joined_on,parent_id,stake_cents,total_withdraw_cents,remark,created_at,updated_at)
                VALUES (:id,:account,:joined,NULL,0,0,:remark,:now,:now)"""),
                {'id':mid,'account':account,'joined':current_day(),
                 'remark':'上级占位（待补资料）','now':now})
            all_new.append((mid,account))
        db.execute(text("""CREATE TABLE IF NOT EXISTS member_registration_times
            (member_id TEXT PRIMARY KEY, registered_at TEXT NOT NULL)"""))
        for rec in candidates:
            mid=current[rec['account'].casefold()]
            db.execute(text("""INSERT INTO members
                (id,account,joined_on,parent_id,stake_cents,total_withdraw_cents,remark,created_at,updated_at)
                VALUES (:id,:account,:joined,NULL,:stake,:total,:remark,:now,:now)"""),
                {'id':mid,'account':rec['account'],'joined':rec['joined_on'],
                 'stake':rec['stake_cents'],'total':rec['total_cents'],
                 'remark':rec['remark'],'now':now})
            db.execute(text("""INSERT INTO member_registration_times(member_id,registered_at)
                VALUES (:i,:t) ON CONFLICT(member_id) DO UPDATE SET registered_at=excluded.registered_at"""),
                {'i':mid,'t':rec['joined_on']})
            all_new.append((mid,rec['account']))
        # Reject cycles in the uploaded portion; ensure references are fully resolvable.
        links={r['account'].casefold():r['parent_account'].casefold() for r in candidates if r['parent_account']}
        for start in links:
            seen=set();pos=start
            while pos in links:
                if pos in seen:raise HTTPException(400,'表格存在循环的上下级推荐关系')
                seen.add(pos);pos=links[pos]
        for rec in candidates:
            if rec['parent_account']:
                pid=current.get(rec['parent_account'].casefold())
                if not pid:raise HTTPException(400,'直属代理商尚未建档：'+rec['parent_account'])
                db.execute(text('UPDATE members SET parent_id=:p WHERE id=:i'),
                    {'i':current[rec['account'].casefold()],'p':pid})
        if len(all_new)<=500:
            record_undo(db,actor.get('username',''),'create',
                f"批量新增今日会员{len(candidates)}位",
                [{'id':mid,'account':name,'before':None,'after':snapshot(db,mid)}
                 for mid,name in all_new])
        audit(db,'create',{'mode':'berlin_daily_new','count':len(candidates),
            'placeholders':len(placeholders),'accounts':[r['account'] for r in candidates[:20]]},
            actor.get('username',''))
        capture_current_report(db)
        db.execute(text('DELETE FROM berlin_bulk_new_jobs WHERE id=:i'),{'i':job_id})
    return {'ok':True,'created':len(candidates),'placeholders':len(placeholders),
            'total_added':len(all_new),'preserved_existing':True}
'''
anchor="@app.post('/api/admin/legacy/preview')"
assert a.count(anchor)==1,'Expected one import endpoint insertion point'
a=a.replace(anchor,backend+"\n"+anchor,1)
# Keep the one-at-a-time "+" button; add nearby floating import button with a separate dialog.
marker='<button class="button primary admin-only floating-add" id="addButton"'
assert h.count(marker)==1,'Add member button not found'
h=h.replace(marker,'<button class="button primary admin-only berlin-bulk-launch" type="button" id="berlinBulkLaunch">📥 今日会员批量导入</button>'+marker,1)
dialog=r'''
<dialog id="berlinBulkDialog" class="berlin-bulk-dialog">
 <h2>批量导入今日新增会员</h2>
 <p>直接选择会员后台导出的完整 Excel 文件；可包含几十列。系统自动识别六项：会员账号、真实姓名、直属代理商、历史总充值、历史总提现、注册时间。</p>
 <p>只新增注册日期为今天且尚未建档的会员，其他日期及原有会员一律保留。不存在的上级自动创建零金额占位节点。</p>
 <input id="berlinBulkFile" type="file" accept=".xlsx,.xlsm,.csv,.txt,.tsv">
 <div class="berlin-bulk-buttons">
  <button type="button" class="button primary" id="berlinBulkPreview">① 解析并预览</button>
  <button type="button" class="button primary" id="berlinBulkConfirm" disabled>② 确认导入今日新增</button>
  <button type="button" class="button" id="berlinBulkClose">关闭</button>
 </div>
 <pre id="berlinBulkResult" aria-live="polite">尚未上传文件。</pre>
</dialog>
<style>
.berlin-bulk-launch{position:fixed;right:25px;bottom:90px;z-index:39;box-shadow:0 7px 22px #0002;border-radius:12px}
.berlin-bulk-dialog{max-width:min(720px,94vw);width:660px;max-height:85vh;overflow:auto;border:1px solid #b9c5cb;border-radius:16px;padding:24px;background:var(--panel,#fff);color:inherit;box-shadow:0 18px 60px #0005}
.berlin-bulk-dialog::backdrop{background:#0008}
.berlin-bulk-dialog h2{margin-top:0;font-size:21px}
.berlin-bulk-dialog p{line-height:1.65;font-size:14px}
.berlin-bulk-dialog input{width:100%;padding:11px;border:1px dashed #8195a0;border-radius:9px}
.berlin-bulk-buttons{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
.berlin-bulk-dialog pre{white-space:pre-wrap;word-break:break-all;font-size:13px;max-height:320px;overflow:auto;padding:12px;background:#eef3f6;color:#162b36;border-radius:10px}
</style>
'''
assert h.count('</body>')==1,'Body anchor missing'
h=h.replace('</body>',dialog+'</body>',1)
j+=r'''
// Independent safe new-member import, never invoking full-roster replacement.
(function(){
 function ready(){
  const button=document.getElementById('berlinBulkLaunch');
  const box=document.getElementById('berlinBulkDialog');
  if(!button||!box)return;
  const input=document.getElementById('berlinBulkFile');
  const preview=document.getElementById('berlinBulkPreview');
  const confirm=document.getElementById('berlinBulkConfirm');
  const close=document.getElementById('berlinBulkClose');
  const result=document.getElementById('berlinBulkResult');
  let jobId=null;
  button.addEventListener('click',()=>{jobId=null;confirm.disabled=true;result.textContent='尚未上传文件。';box.showModal()});
  close.addEventListener('click',()=>box.close());
  input.addEventListener('change',()=>{jobId=null;confirm.disabled=true;result.textContent='点击解析并预览，系统自动读取所有列。'});
  preview.addEventListener('click',async()=>{
   const file=input.files&&input.files[0];
   if(!file){result.textContent='请先选择原始Excel会员表格';return;}
   jobId=null;confirm.disabled=true;preview.disabled=true;
   result.textContent='正在检查六项数据与今日新增名单…';
   try{
    const form=new FormData();form.append('upload',file);
    const d=await api('/berlin/daily-new/preview','POST',form);
    const sample=(d.sample||[]).slice(0,8).map(x=>x.account+' ← '+(x.parent_account||'根节点')+'，姓名：'+(x.remark||'—')).join('\n');
    result.textContent='文件会员账号数：'+d.total_rows+'\n今日注册记录：'+(d.new_count+d.existing_count)+
      '\n待新增：'+d.new_count+' 位\n已建档跳过：'+d.existing_count+
      ' 位\n非今日注册跳过：'+d.old_count+' 位\n同表重复账号跳过：'+d.duplicate_count+
      ' 位\n需补建上级占位：'+d.placeholder_count+' 位'+
      '\n预计新增建仓：'+money(d.stake_cents,true)+
      '\n预计历史累计提现：'+money(d.total_withdraw_cents,true)+
      '\n识别的表头位于第 '+d.header_row+' 行'+
      '\n未知上级示例：'+(d.placeholder_examples||[]).join('、')+
      '\n预览会员：\n'+sample+'\n\n'+d.message+
      (d.valid?'\n请确认数字后再点击导入。':'\n没有需要新增的今日会员，本次无需提交。');
    jobId=d.job_id;confirm.disabled=!d.valid;
   }catch(err){result.textContent='预览失败：'+err.message;}finally{preview.disabled=false;}
  });
  confirm.addEventListener('click',async()=>{
   if(!jobId)return;
   if(!window.confirm('仅新增今天注册且尚未建档的会员，保留历史数据，确认执行吗？'))return;
   confirm.disabled=true;preview.disabled=true;
   try{
    const d=await api('/berlin/daily-new/'+encodeURIComponent(jobId)+'/confirm','POST',{});
    jobId=null;
    result.textContent='已成功增加 '+d.created+' 位今日会员；补建上级 '+d.placeholders+' 位。原会员及原资金数据未覆盖。';
    if(typeof showToast==='function')showToast('今日会员批量导入成功：'+d.created+' 位');
    await refresh();
    if(typeof syncUndoStatus==='function')await syncUndoStatus();
   }catch(err){result.textContent='导入失败：'+err.message+'\n请重新预览后提交。';jobId=null;}
   finally{preview.disabled=false;}
  });
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready);
 else ready();
})();
'''
ap.write_text(a,encoding='utf-8')
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
