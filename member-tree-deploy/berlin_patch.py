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
from decimal import ROUND_HALF_UP

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
assert a.count('万诚数据统计') == 1
a=a.replace('万诚数据统计','柏林数据统计')
ap.write_text(a)
j=j.replace('导入旧版全员数据 · 一键重建会员树','一键复原树状图 · 柏林六列格式')
j=j.replace('支持老版本“导出全部CSV / 导出Excel”文件，自动识别会员、加入日期、直属上级、备注、建仓、余额、累计提现、当日提现。加密 .mtbackup 文件请使用顶部「恢复加密备份」。请不要选择只含层级合计的“逐层汇总表”。',
'''上传六列：会员账号、真实姓名、隶属代理商、历史总充值、历史总提现、注册时间。真实姓名显示为备注，充值为建仓，提现为累计提现。缺失上级自动建立占位节点。余额与每日提现通过原有功能单独上传。也兼容原正式版导出格式。''')
j=j.replace('当前正式系统会员：','当前测试系统会员：')
j=j.replace('建仓合计：${d.amounts.stake}', '占位上级：${d.placeholders||0}个\\n建仓合计：${d.amounts.stake}')
j=j.replace('即将用导出文件完整替换正式会员资料，影响所有8名管理员。','即将用六列表格覆盖柏林测试会员树，影响所有10名管理员。')
j=j.replace('8位管理员','10位管理员')
assert j.count('万诚数据统计') == 1
assert j.count('磐石AI学院') >= 1
assert j.count('磐石 AI 学院') == 1
j=j.replace('万诚数据统计','柏林数据统计')
j=j.replace('磐石AI学院','柏林学院')
j=j.replace('磐石 AI 学院','柏林学院')
j=j.replace('你好，我是磐石AI话术导师','你好，我是柏林学院话术导师')
jp.write_text(j)
h=h.replace('会员树状系统 · V21实时报表与树状图','柏林树状图系统 · 免费测试版')
h=h.replace('会员树状统计系统 · 数据报表V22版','柏林树状图系统 · 测试版')
h=h.replace('会员数据中心','柏林树状图系统')
h=h.replace('8位管理员','10位管理员').replace('正式数据库','测试数据库')
assert '磐石AI学院' in h
h=h.replace('磐石AI学院','柏林学院')
hp.write_text(h)
academy_file=root/'academy.py'
academy_src=academy_file.read_text()
assert '【磐石AI学院·课程专属话术导师】' in academy_src
academy_src=academy_src.replace('【磐石AI学院·课程专属话术导师】','【柏林学院·课程专属话术导师】')
academy_file.write_text(academy_src)
# Berlin group view and append-only six-column importer (tested separately).
# The UTF-8 source is a gzipped, base64-encoded release-build patch.
exec(compile(gzip.decompress(base64.b64decode('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')).decode('utf-8'), 'berlin_incremental_group_patch.py', 'exec'))
# Six-column header auto-detection with explicit field errors; only Berlin test.
exec(compile(gzip.decompress(base64.b64decode('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')).decode('utf-8'), 'berlin_import_fix.py', 'exec'))
# Fix incorrectly declared XLSX dimensions, e.g. dimension=A1 while actual cells occupy A1:F5438.
# Read-only openpyxl otherwise silently truncates every row to the first column.
_dimension_old="for ws in wb.worksheets:"+chr(10)+"                    for n,cells in enumerate(ws.iter_rows(max_row=30,values_only=True),1):"
_dimension_new="for ws in wb.worksheets:"+chr(10)+"                    ws.reset_dimensions()  # Ignore defective XML dimension tags from exporters."+chr(10)+"                    for n,cells in enumerate(ws.iter_rows(max_row=30,values_only=True),1):"
assert a.count(_dimension_old)==1, "Dimension-scanning location must be unique"
a=a.replace(_dimension_old,_dimension_new,1)
# Original historical deposits sometimes contain a negative settlement adjustment.
# Permit signed historical deposit values only, without zeroing or changing data.
_slash=chr(92)
_money_old="        if not re.fullmatch(r'"+_slash+"d{1,12}(?:"+_slash+"."+_slash+"d{1,3})?',s):"
_money_new="        if not re.fullmatch(r'-?"+_slash+"d{1,12}(?:"+_slash+"."+_slash+"d{1,3})?' if field=='充值' else r'"+_slash+"d{1,12}(?:"+_slash+"."+_slash+"d{1,3})?',s):"
assert a.count(_money_old)==1, "Historical recharge validation location must be unique"
a=a.replace(_money_old,_money_new,1)
assert "ws.reset_dimensions()" in a
assert "field=='充值'" in a
# The amount checker must know which column is being validated.
# Recharge adjustments can be signed, historical withdrawals cannot.
assert a.count("    def cent3(v):")==1
a=a.replace("    def cent3(v):","    def cent3(v,field='充值'):",1)
assert a.count("cent3(value(row,'历史总提现'))")==1
a=a.replace("cent3(value(row,'历史总提现'))",
            "cent3(value(row,'历史总提现'),'提现')",1)
assert "def cent3(v,field='充值')" in a
assert "cent3(value(row,'历史总提现'),'提现')" in a
ap.write_text(a)
# Berlin-specific slash-separated one-click paste: member, join date, demographic note, skip phone.
exec(compile(gzip.decompress(base64.b64decode('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')).decode('utf-8'), 'berlin_smart_paste_patch.py', 'exec'))
# Berlin test-only performance fix. Kept separate from the formal branch.
exec(compile(Path('member-tree-deploy/berlin_perf_patch.py').read_text(encoding='utf-8'),'berlin_perf_patch.py','exec'))
# Browser performance v2: bound DOM/SVG nodes for 10k-member paid Berlin service.
exec(compile(gzip.decompress(base64.b64decode('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')).decode('utf-8'),'berlin_browser_perf_v2.py','exec'))
# Preserve exact account lookup across all member records without rendering 10k options.
_table_lookup_old="berlinTablePage=1;render()};filter.append(range);"
_table_lookup_new="berlinTablePage=1;render()};filter.append(range);const jump=mk('input','filter-select');jump.placeholder='输入完整会员账号查看其全部下级';jump.value=tableScope;const locate=()=>{const target=members.find(m=>m.account.toLowerCase()===jump.value.trim().toLowerCase());if(!target){showToast('未找到完整会员账号');return}tableScope=target.account;berlinTablePage=1;render()};jump.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();locate()}};filter.append(jump);const go=mk('button','button','定位账号');go.onclick=locate;filter.append(go);"
assert j.count(_table_lookup_old)==1, 'Missing scoped lookup after pagination upgrade'
j=j.replace(_table_lookup_old,_table_lookup_new,1)
# Berlin paid-production API compression + conditional 304, no dataset/schema edits.
exec(compile(gzip.decompress(base64.b64decode('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')).decode('utf-8'),'berlin_network_perf_v3.py','exec'))
# Berlin is now running on dedicated paid Render compute and Postgres.
# Correct the public-facing edition label only; no database/admin/business changes.
formal_html=hp.read_text(encoding='utf-8')
formal_js=jp.read_text(encoding='utf-8')
assert '柏林树状图系统 · 免费测试版' in formal_html or '柏林树状图系统 · 测试版' in formal_html, 'Old edition label not present'
formal_html=formal_html.replace('柏林树状图系统 · 免费测试版','柏林树状图系统 · 正式版').replace('柏林树状图系统 · 测试版','柏林树状图系统 · 正式版')
formal_html=formal_html.replace('测试数据库','正式数据库').replace('免费测试版','正式版')
formal_js=formal_js.replace('当前测试系统会员：','当前正式系统会员：')
formal_js=formal_js.replace('柏林测试会员树','柏林会员树')
formal_js=formal_js.replace('免费测试版','正式版')
assert '免费测试版' not in formal_html and '柏林树状图系统 · 测试版' not in formal_html
assert '柏林树状图系统 · 正式版' in formal_html
hp.write_text(formal_html,encoding='utf-8')
jp.write_text(formal_js,encoding='utf-8')
exec(compile(Path('member-tree-deploy/berlin_full_replace_import_patch.py').read_text(encoding='utf-8'),'berlin_full_replace_import_patch.py','exec'))
# Berlin financial import (balance / daily withdrawal only): signed, rounded cents.
exec(compile(Path('member-tree-deploy/berlin_balance_daily_money_patch.py').read_text(encoding='utf-8'),'berlin_balance_daily_money_patch.py','exec'))
# De-duplicate repeat accounts within a single six-column roster before full overwrite.
exec(compile(Path('member-tree-deploy/berlin_six_column_dedupe_patch.py').read_text(encoding='utf-8'),'berlin_six_column_dedupe_patch.py','exec'))
# Signed cash-flow withdrawals: immediate daily/cumulative net changes, idempotent per day.
exec(compile(Path('member-tree-deploy/berlin_signed_withdrawal_realtime_patch.py').read_text(encoding='utf-8'),'berlin_signed_withdrawal_realtime_patch.py','exec'))
# Berlin add-on only: daily recharge snapshots; midnight supplemental credit.
exec(compile(Path('member-tree-deploy/berlin_daily_recharge_patch.py').read_text(encoding='utf-8'),'berlin_daily_recharge_patch.py','exec'))
# Berlin finance raw exports: three-line description / account / amount events.
exec(compile(Path('member-tree-deploy/berlin_three_line_cashflow_patch.py').read_text(encoding='utf-8'),'berlin_three_line_cashflow_patch.py','exec'))
# Berlin extra cashflow layouts: amount / memo / account and amount / account.
exec(compile(Path('member-tree-deploy/berlin_reverse_cashflow_patch.py').read_text(encoding='utf-8'),'berlin_reverse_cashflow_patch.py','exec'))
# Recognize pasted recharge/withdrawal triplets even when the import screen starts in combined mode.
exec(compile(Path('member-tree-deploy/berlin_auto_cashflow_mode_patch.py').read_text(encoding='utf-8'),'berlin_auto_cashflow_mode_patch.py','exec'))
# Incremental daily new member import: auto-read complete Excel with no roster deletion.
exec(compile(Path('member-tree-deploy/berlin_bulk_new_members_patch.py').read_text(encoding='utf-8'),'berlin_bulk_new_members_patch.py','exec'))
# For duplicate accounts, six imported fields now use the last uploaded file (upsert).
exec(compile(Path('member-tree-deploy/berlin_bulk_latest_wins_patch.py').read_text(encoding='utf-8'),'berlin_bulk_latest_wins_patch.py','exec'))
# Berlin presentation-only tour and local withdrawal ring-density ranking.
exec(compile(Path('member-tree-deploy/berlin_visual_tour_density_patch.py').read_text(encoding='utf-8'),'berlin_visual_tour_density_patch.py','exec'))
# Single-member plus-button now upserts existing account safely, preserving balances and history.
exec(compile(Path('member-tree-deploy/berlin_single_member_upsert_patch.py').read_text(encoding='utf-8'),'berlin_single_member_upsert_patch.py','exec'))
# Fix endless debounce hiding nodes during continuous automatic tours.
exec(compile(Path('member-tree-deploy/berlin_visual_repaint_patch.py').read_text(encoding='utf-8'),'berlin_visual_repaint_patch.py','exec'))
# Smart-paste and single-member parent matching ignore ASCII case; retain original member spelling.
exec(compile(Path('member-tree-deploy/berlin_case_insensitive_member_patch.py').read_text(encoding='utf-8'),'berlin_case_insensitive_member_patch.py','exec'))
# Allow 0 initial capital in the single member add/edit dialog and backend validation.
exec(compile(Path('member-tree-deploy/berlin_zero_stake_patch.py').read_text(encoding='utf-8'),'berlin_zero_stake_patch.py','exec'))
import py_compile
py_compile.compile(str(ap),doraise=True)
(root/'BERLIN_TEST_README.txt').write_text('柏林树状图系统，来自正式版，六列导入和10管理员。\\n')
out=io.BytesIO()
with tarfile.open(fileobj=out,mode='w') as tar:
    tar.add(root,arcname='member-tree',recursive=True)
archive=base64.b64encode(gzip.compress(out.getvalue(),compresslevel=9)).decode('ascii')
Path('member-tree-deploy/payload.b64').write_text(archive)
print('Berlin test archive rebuilt from official source, chars:',len(archive))
