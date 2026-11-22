"""Berlin member-batch latest-upload-wins regression (SQLite only).
Never touches an existing database or deployed financial records.
"""
import io, os, sys, uuid, tempfile, subprocess
from datetime import datetime, date, timedelta, time
from pathlib import Path
from openpyxl import Workbook
from fastapi.testclient import TestClient
from sqlalchemy import text

with tempfile.TemporaryDirectory() as directory:
    os.environ['DATABASE_URL']='sqlite:///'+directory+'/bulk_upsert_test.sqlite'
    os.environ['ENABLE_MIDNIGHT_WORKER']='0'
    sys.path.insert(0,'member-tree')
    import app as a
    a.require=lambda req,role='viewer',mutation=False:{'role':'admin','username':'bulk_test'}
    a.db_init()
    today=a.current_day()
    older=(date.fromisoformat(today)-timedelta(days=3)).isoformat()
    old_id=str(uuid.uuid4())
    untouched_id=str(uuid.uuid4())
    with a.engine.begin() as db:
        for member_id,account,stake,withdraw,balance,remark in [
            (old_id,'F123576',777700,4500,712345,'原始老会员'),
            (untouched_id,'untouched777',33300,1200,55000,'未上传保持')]:
            db.execute(text("""INSERT INTO members
                (id,account,joined_on,stake_cents,total_withdraw_cents,balance_cents,
                 daily_withdraw_cents,remark,created_at,updated_at)
                VALUES (:id,:account,:joined,:stake,:withdraw,:balance,1500,:remark,:now,:now)"""),
                {'id':member_id,'account':account,'joined':older,'stake':stake,
                 'withdraw':withdraw,'balance':balance,'remark':remark,'now':a.utc_now()})
    header=['会员id','会员账号','真实姓名','会员昵称','会员状态',
            '会员等级','会员分群','直属代理商','历史累计打针次数',
            '历史总充值','历史总提现','注册时间','其他统计']
    today_excel=datetime.combine(date.fromisoformat(today),time(10,20))
    old_excel=datetime.combine(date.fromisoformat(older),time(14,0))
    def row(id,account,name,parent,stake,withdraw,registered):
        return [id,account,name,account,'在用','1级','Default',parent,0,stake,withdraw,registered,0]
    def workbook(lines):
        book=Workbook();ws=book.active
        ws.append(['会员信息']);ws.append(header)
        for values in lines:ws.append(values)
        output=io.BytesIO();book.save(output)
        return output.getvalue()
    first=workbook([
        row(501,'user_new1','张三','F123576',10000.25,50.5,today_excel),
        row(502,'user_new2','李四','user_new1',5000,100,today_excel),
        row(503,'new_orphan','王五','unknown_parent7',0,0,today_excel),
        row(504,'F123576','新姓名','root',99999,99999,old_excel),
        row(505,'yesterday_member','旧记录','root',2000,500,old_excel),
        row(506,'user_new1','最后一行张三','F123576',11000.35,50.5,today_excel)])
    with TestClient(a.app) as client:
        def preview(content):
            r=client.post('/api/berlin/daily-new/preview',files={
               'upload':('会员信息.xlsx',content,
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
            assert r.status_code==200,r.text
            return r.json()
        def confirm(q):
            return client.post('/api/berlin/daily-new/'+q['job_id']+'/confirm',json={})
        q=preview(first)
        assert q['valid'] and q['new_count']==4 and q['updated_count']==1,q
        assert q['old_count']==2 and q['duplicate_count']==1,q
        assert q['placeholder_count']==2 and q['total_rows']==5,q
        assert q['stake_cents']==11799935,q
        assert q['total_withdraw_cents']==10064950,q
        result=confirm(q)
        assert result.status_code==200,result.text
        assert result.json()['created']==4 and result.json()['updated']==1,result.json()
        assert result.json()['placeholders']==2,result.json()
        def all_members():
            with a.engine.connect() as db:
                return {x['account']:dict(x) for x in
                    db.execute(text('SELECT id,account,parent_id,stake_cents,total_withdraw_cents,'
                                    'balance_cents,daily_withdraw_cents,remark,joined_on FROM members')).mappings().all()}
        members=all_members()
        assert len(members)==8,members
        assert members['F123576']['id']==old_id,members
        assert members['F123576']['stake_cents']==9999900,members
        assert members['F123576']['total_withdraw_cents']==9999900,members
        assert members['F123576']['balance_cents']==712345,members
        assert members['F123576']['daily_withdraw_cents']==1500,members
        assert members['F123576']['remark']=='新姓名',members
        assert members['user_new1']['remark']=='最后一行张三',members
        assert members['user_new1']['stake_cents']==1100035,members
        assert members['user_new1']['parent_id']==old_id,members
        assert members['user_new2']['parent_id']==members['user_new1']['id'],members
        assert members['new_orphan']['parent_id']==members['unknown_parent7']['id'],members
        assert members['yesterday_member']['joined_on']==older,members
        assert members['untouched777']['id']==untouched_id,members
        assert members['untouched777']['stake_cents']==33300,members
        assert members['untouched777']['balance_cents']==55000,members
        # Re-upload same document: no duplicate accounts, old rows are updatable.
        again=preview(first)
        assert again['valid'] and again['new_count']==0 and again['updated_count']==5,again
        done=confirm(again)
        assert done.status_code==200 and done.json()['updated']==5,done.text
        assert len(all_members())==8
        # Newer smaller upload: only listed member updated; omitted members unchanged.
        latest=workbook([row(999,'F123576','最后上传的名字','root',8500,200,old_excel)])
        change=preview(latest)
        assert change['new_count']==0 and change['updated_count']==1,change
        applied=confirm(change)
        assert applied.status_code==200 and applied.json()['updated']==1,applied.text
        members=all_members()
        assert members['F123576']['id']==old_id
        assert members['F123576']['stake_cents']==850000
        assert members['F123576']['total_withdraw_cents']==20000
        assert members['F123576']['remark']=='最后上传的名字'
        assert members['F123576']['balance_cents']==712345
        assert members['F123576']['daily_withdraw_cents']==1500
        assert members['user_new1']['stake_cents']==1100035
        assert members['untouched777']['stake_cents']==33300
        assert len(members)==8
        # A previously linked member cannot be given its descendant as parent.
        bad=workbook([row(1,'F123576','循环','user_new1',6000,0,old_excel)])
        q=preview(bad)
        failed=confirm(q)
        assert failed.status_code==400 and '循环' in failed.text,failed.text
        assert all_members()['F123576']['stake_cents']==850000
        assert len(all_members())==8
    subprocess.run(['node','--check','member-tree/static/app.js'],check=True)
    html=Path('member-tree/static/index.html').read_text(encoding='utf-8')
    assert 'berlinBulkLaunch' in html and 'berlinBulkDialog' in html
    assert '同账号（覆盖）' in Path('member-tree/static/app.js').read_text(encoding='utf-8')
    import inspect
    for function in ('create_member','update_member','validate_member','resolved_parent','parent_ok','validate_stake_for_level'):
        if hasattr(a,function):
            print('===SINGLE_MEMBER_'+function+'===',inspect.getsource(getattr(a,function)))
    source=Path('member-tree/static/app.js').read_text(encoding='utf-8')
    start=source.find('function openEdit(')
    end=source.find('function testDownloadBlob(',start)
    print('===EDIT_UI_SOURCE===',source[start:end] if end>start else 'missing')
    print('PASS: Berlin last-upload-wins six-field upsert, account-level last row wins, stable IDs, unlisted/financial fields safe, cycles rejected')

# View-only tests: simulation of non-overlapping red-ring hotspots.
js=Path('member-tree/static/app.js').read_text(encoding='utf-8')
html=Path('member-tree/static/index.html').read_text(encoding='utf-8')
assert 'function berlinRankWithdrawClusters(' in js
assert '▶ 自动浏览' in js and '提现密度提醒' in js
assert '下一处 →' in js and '← 上一处' in js
assert 'function startAutoTour()' in js and 'function startDensitySurvey()' in js
assert 'const zoom=.13' in js and 'requestAnimationFrame(step)' in js
assert 'daily_withdraw_cents||0' in js
assert 'berlin-visual-toolbar' in html
node_test=r"""
const fs=require('fs'),vm=require('vm');
const source=fs.readFileSync('member-tree/static/app.js','utf-8');
const from=source.indexOf('function berlinRankWithdrawClusters(');
const to=source.indexOf('\nlet berlinVisionMode=',from);
if(from<0||to<=from)throw new Error('Missing density helper boundaries');
const ctx={}; vm.runInNewContext(source.slice(from,to)+'\nthis.rank=berlinRankWithdrawClusters;',ctx);
const group=[
 {x:30,y:30,amount:50,account:'a1'},
 {x:40,y:65,amount:60,account:'a2'},
 {x:35,y:100,amount:75,account:'a3'},
 {x:55,y:120,amount:85,account:'a4'},
 {x:30,y:1100,amount:100,account:'b1'},
 {x:45,y:1140,amount:200,account:'b2'},
 {x:60,y:1180,amount:300,account:'b3'},
 {x:25,y:2200,amount:10000000,account:'c1'}];
const ranked=ctx.rank(group,420,330);
if(ranked.length!==3||ranked[0].count!==4||ranked[1].count!==3||ranked[2].count!==1){
 throw new Error('Withdrawal density ranks should be 4, 3, 1 rings not by largest amount: '+JSON.stringify(ranked))
}
if(ctx.rank([],420,330).length!==0)throw new Error('Empty data must have no hotspot');
console.log('PASS: ranked red-ring hotspots 4>3>1, non-overlapping navigation, count prioritized over withdrawal amount');
"""
subprocess.run(['node','-e',node_test],check=True)
print('PASS: minimal-scale vertical animation, density mode controls and view-only implementation present')
