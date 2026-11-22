"""Rebuild only the independent Berlin test payload from the formal member-tree release."""
import base64, gzip, tarfile, io, os, re
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
root = Path("member-tree")
formal = base64.b64decode(Path("/tmp/berlin_formal.b64").read_bytes())
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(formal)),mode="r:") as tar:
    tar.extractall(".", filter="data")
ap=root/"app.py"
jp=root/"static"/"app.js"
hp=root/"static"/"index.html"
a=ap.read_text()
j=jp.read_text()
h=hp.read_text()
assert a.count("def parse_legacy_full_export(payload,filename):")==1
a=a.replace("def parse_legacy_full_export(payload,filename):","def parse_formal_legacy_export(payload,filename):",1)
parser = '''
def parse_legacy_full_export(payload,filename):
    """Berlin six-column import; also accept the unmodified official format."""
    extension=os.path.splitext(filename.lower())[1]
    if extension not in ('.xlsx','.xlsm','.csv','.txt'):
        return parse_formal_legacy_export(payload,filename)
    required=('会员账号','真实姓名','隶属代理商','历史总充值','历史总提现','注册时间')
    if extension in ('.xlsx','.xlsm'):
        try:
            wb=load_workbook(io.BytesIO(payload),read_only=True,data_only=True)
            rows=wb.active.iter_rows();first=next(rows,None)
            if not first:raise ValueError('空表格')
            heads=[str(c.value or '').strip() for c in first]
            if not all(k in heads for k in required):
                wb.close();return parse_formal_legacy_export(payload,filename)
            lines=[]
            for row in rows:
                vals=[c.value for c in row]
                ix=heads.index('会员账号')
                if ix<len(row):vals[ix]=legacy_xlsx_account(row[ix])
                lines.append(vals)
            wb.close()
        except (OSError,KeyError,ValueError) as exc:raise HTTPException(400,'Excel解析失败：'+str(exc))
    else:
        try:
            try:src=payload.decode('utf-8-sig')
            except UnicodeDecodeError:src=payload.decode('gb18030')
            r=csv.reader(io.StringIO(src));heads=[v.strip() for v in next(r)]
            if not all(k in heads for k in required):
                return parse_formal_legacy_export(payload,filename)
            lines=list(r)
        except (StopIteration,csv.Error,UnicodeDecodeError) as exc:
            raise HTTPException(400,'CSV解析失败：'+str(exc))
    if len(lines)>20000:raise HTTPException(400,'最多20000条会员')
    def value(row,k):
        ix=heads.index(k)
        return row[ix] if ix<len(row) else None
    def cent3(v):
        if v is None or str(v).strip()=='':return 0
        s=str(v).replace(',','').strip()
        if not re.fullmatch(r'\\d{1,12}(?:\\.\\d{1,3})?',s):
            raise ValueError('金额应为非负数、最多3位小数')
        return int((Decimal(s)*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    output=[];seen=set()
    for num,row in enumerate(lines,2):
        if not any(str(v or '').strip() for v in row):continue
        try:
            account=legacy_account(value(row,'会员账号'))
            parent=legacy_account(value(row,'隶属代理商'))
            if parent in ('—','-','无','根节点','None','null'):parent=''
            for x in [account]+([parent] if parent else []):
                if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}',x):raise ValueError('账号格式错误')
            key=account.casefold()
            if key in seen:raise ValueError('账号重复')
            if key==parent.casefold():raise ValueError('上级不能是本人')
            seen.add(key)
            remark=str(value(row,'真实姓名') or '').strip()
            if len(remark)>20:raise ValueError('真实姓名超过20字')
            when=value(row,'注册时间')
            when=(when.isoformat(sep=' ') if isinstance(when,datetime) else
                  when.isoformat() if isinstance(when,date) else str(when or '').strip())
            joined=when[:10];valid_date(joined)
            if len(when)>10:datetime.fromisoformat(when)
            output.append({'account':account,'parent_account':parent,
              'joined_on':joined,'registered_at':when,'remark':remark,
              'stake_cents':cent3(value(row,'历史总充值')),
              'total_cents':cent3(value(row,'历史总提现')),
              'balance_cents':0,'daily_cents':0,'__berlin__':True})
        except (ValueError,HTTPException) as err:
            msg=err.detail if isinstance(err,HTTPException) else str(err)
            raise HTTPException(400,f'第{num}行：{msg}')
    if not output:raise HTTPException(400,'没有会员记录')
    by={v['account'].casefold():v for v in output}
    extra={}
    for row in output:
        p=row['parent_account'];key=p.casefold()
        if p and key not in by:
            if key not in extra:
                extra[key]={'account':p,'parent_account':'','joined_on':row['joined_on'],
                   'registered_at':row['registered_at'],'remark':'上级占位（待补资料）',
                   'stake_cents':0,'total_cents':0,'balance_cents':0,'daily_cents':0,
                   '__berlin__':True,'__placeholder__':True}
            elif row['joined_on']<extra[key]['joined_on']:
                extra[key]['joined_on']=row['joined_on']
    output.extend(extra.values())
    by={v['account'].casefold():v for v in output}
    for row in output:
        visited=set();cur=row
        while cur['parent_account']:
            key=cur['account'].casefold()
            if key in visited:raise HTTPException(400,'存在循环上级关系')
            visited.add(key);cur=by[cur['parent_account'].casefold()]
    return output

'''
assert a.count("@app.post('/api/admin/legacy/preview')")==1
a=a.replace("@app.post('/api/admin/legacy/preview')",parser+"@app.post('/api/admin/legacy/preview')",1)
a=a.replace("'roots':sum(1 for x in parsed if not x['parent_account']),",
            "'roots':sum(1 for x in parsed if not x['parent_account']), 'placeholders':sum(1 for x in parsed if x.get('__placeholder__'))," )
a=a.replace("'notice':'恢复旧版全员资料会替换当前会员及关系；不会凭空恢复旧版缺失的逐日流水或撤回记录。CSV/Excel只保留本人金额，旧表中的各层汇总不会重复导入。旧文件当日提现按本次导入的北京时间日期挂账，请核对文件是否是今日导出。'",
            "'notice':('柏林六列覆盖重建：缺失上级创建占位节点，保留每日提现、余额和历史快照。' if parsed and parsed[0].get('__berlin__') else '旧版恢复格式，执行前请备份。')")
branch = '''
        if parsed and parsed[0].get('__berlin__'):
            # Preserve IDs and historical ledgers. Non-imported accounts become inactive.
            now=utc_now()
            db.execute(text("CREATE TABLE IF NOT EXISTS member_registration_times (member_id TEXT PRIMARY KEY, registered_at TEXT NOT NULL)"))
            old=db.execute(text('SELECT id,account FROM members')).mappings().all()
            known={row['account'].casefold():row['id'] for row in old}
            for row in parsed:
                known.setdefault(row['account'].casefold(),str(uuid.uuid4()))
            existing_ids={r['id'] for r in old}
            db.execute(text('UPDATE members SET deleted=1,revision=revision+1,updated_at=:now'),{'now':now})
            for row in parsed:
                key=row['account'].casefold();mid=known[key]
                v={'i':mid,'a':row['account'],'j':row['joined_on'],'s':row['stake_cents'],
                   't':row['total_cents'],'r':row['remark'],'n':now}
                if mid in existing_ids:
                    db.execute(text("""UPDATE members SET account=:a,joined_on=:j,parent_id=NULL,
                        stake_cents=:s,total_withdraw_cents=:t,remark=:r,deleted=0,
                        revision=revision+1,updated_at=:n WHERE id=:i"""),v)
                else:
                    db.execute(text("""INSERT INTO members(id,account,joined_on,parent_id,
                        stake_cents,balance_cents,total_withdraw_cents,daily_withdraw_cents,
                        remark,created_at,updated_at)
                        VALUES (:i,:a,:j,NULL,:s,0,:t,0,:r,:n,:n)"""),v)
                db.execute(text("""INSERT INTO member_registration_times(member_id,registered_at)
                    VALUES (:i,:v) ON CONFLICT(member_id) DO UPDATE SET registered_at=excluded.registered_at"""),
                    {'i':mid,'v':row['registered_at']})
            for row in parsed:
                if row['parent_account']:
                    db.execute(text('UPDATE members SET parent_id=:p WHERE id=:i'),
                        {'i':known[row['account'].casefold()],
                         'p':known[row['parent_account'].casefold()]})
            db.execute(text('DELETE FROM import_jobs'))
            db.execute(text('DELETE FROM undo_actions'))
            db.execute(text('DELETE FROM legacy_restore_jobs'))
            audit(db,'legacy_restore',{'count':len(parsed),'previous_count':len(existing),
                     'mode':'berlin_6_columns'},actor)
            return {'ok':True,'members':len(parsed),
                    'placeholders':sum(bool(x.get('__placeholder__')) for x in parsed)}
'''
anchor="        byaccount={x['account'].casefold():str(uuid.uuid4()) for x in parsed}"
assert a.count(anchor)==1
a=a.replace(anchor,branch+anchor,1)
ap.write_text(a)
j=j.replace('导入旧版全员数据 · 一键重建会员树','一键复原树状图 · 柏林六列格式')
j=j.replace('支持老版本“导出全部CSV / 导出Excel”文件，自动识别会员、加入日期、直属上级、备注、建仓、余额、累计提现、当日提现。加密 .mtbackup 文件请使用顶部「恢复加密备份」。请不要选择只含层级合计的“逐层汇总表”。',
'''上传六列：会员账号、真实姓名、隶属代理商、历史总充值、历史总提现、注册时间。真实姓名显示为备注，充值为建仓，提现为累计提现。缺失上级自动建立占位节点。余额与每日提现通过原有功能单独上传。也兼容原正式版导出格式。''')
j=j.replace('当前正式系统会员：','当前测试系统会员：')
j=j.replace('建仓合计：${d.amounts.stake}', '占位上级：${d.placeholders||0}个\\n建仓合计：${d.amounts.stake}')
j=j.replace('即将用导出文件完整替换正式会员资料，影响所有8名管理员。','即将用六列表格覆盖柏林测试会员树，影响所有10名管理员。')
j=j.replace('8位管理员','10位管理员')
jp.write_text(j)
h=h.replace('会员树状系统 · V21实时报表与树状图','柏林树状图系统 · 免费测试版')
h=h.replace('会员树状统计系统 · 数据报表V22版','柏林树状图系统 · 测试版')
h=h.replace('会员数据中心','柏林树状图系统')
h=h.replace('8位管理员','10位管理员').replace('正式数据库','测试数据库')
hp.write_text(h)
import py_compile
py_compile.compile(str(ap),doraise=True)
(root/'BERLIN_TEST_README.txt').write_text('柏林树状图系统，来自正式版，六列导入和10管理员。\\n')
out=io.BytesIO()
with tarfile.open(fileobj=out,mode='w') as tar:
    tar.add(root,arcname='member-tree',recursive=True)
archive=base64.b64encode(gzip.compress(out.getvalue(),compresslevel=9)).decode('ascii')
Path('member-tree-deploy/payload.b64').write_text(archive)
print('Berlin test archive rebuilt from official source, chars:',len(archive))
