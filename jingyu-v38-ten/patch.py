"""Whale ONLY: isolate V38 from production and replace 1000 fake users with 10.
Target: jingyu-whale-member-tree-v27-test Render service only.
The production V38 payload is unpacked by the separate CI workflow.
No external db, user data import, auth migration or member table reset on production.
"""
from pathlib import Path
root=Path('member-tree')
app_file=root/'app.py'
js_file=root/'static/app.js'
html_file=root/'static/index.html'
app=app_file.read_text(encoding='utf8')
js=js_file.read_text(encoding='utf8')
html=html_file.read_text(encoding='utf8')

old_db="DB_URL = os.environ.get('DATABASE_URL', 'sqlite:///' + str(ROOT / 'local-demo.db'))"
new_db="""DB_URL = 'sqlite:////tmp/jingyu_v38_only_ten.sqlite3'  # WHALE LOCAL TEST DB, never DATABASE_URL
# The obsolete thousand-record synthetic dataset is removed from this test
# service's local /tmp storage on the next start. Never delete production files.
for _suffix in ('', '-wal', '-shm', '-journal'):
    try:
        Path('/tmp/jingyu_isolated_member_tree_v28_1000.sqlite3'+_suffix).unlink()
    except FileNotFoundError:
        pass
"""
assert app.count(old_db)==1, ('V38 database anchor changed',app.count(old_db))
app=app.replace(old_db,new_db,1)
assert "COOKIE = 'member_tree_v3_session'" in app
app=app.replace("COOKIE = 'member_tree_v3_session'",
                "COOKIE = 'jingyu_member_tree_test_session'",1)
app=app.replace("salt='member-tree-v3'","salt='jingyu-member-tree-test-v1'")
# The built-in demo is not auto-seeded. Only isolated, deterministic synthetic
# JY rows below are generated when the whale database starts empty.
assert "jingyu_seed_1000" not in app
before="    db_init()\n    if os.environ.get('ENABLE_MIDNIGHT_WORKER','1')=='1':"
after="    db_init()\n    jingyu_seed_ten()\n    if os.environ.get('ENABLE_MIDNIGHT_WORKER','1')=='1':"
assert app.count(before)==1,('startup db_init anchor changed',app.count(before))
app=app.replace(before,after,1)

app=app.replace('万诚数据统计（','鲸鱼小组数据报表（')
js=js.replace('万诚数据统计（','鲸鱼小组数据报表（')
html=html.replace('会员树状统计系统 · 数据报表V22版','会员树状统计系统 · 鲸鱼小组测试版')
html=html.replace('8位管理员独立登录','3位测试管理员独立登录')
html=html.replace('<title>会员树状系统 · V21实时报表与树状图</title>',
                  '<title>鲸鱼小组 · 独立测试版 V38</title>')
html=html.replace('▥　今日报表总览','▥　鲸鱼小组数据报表')
js=js.replace("report:'今日报表总览'","report:'鲸鱼小组数据报表'")
js=js.replace('8位管理员','3位测试管理员')
assert 'data-view="academy"' in html, 'V38 AI Academy nav missing'
assert 'v33AlertPanel' in js, 'V33 position alert queue missing'
assert 'function v29Position(' in js, 'position warning status missing'
assert '严格课程模式' in js, 'V38 course-based AI tutor missing'
app_file.write_text(app,encoding='utf8')
js_file.write_text(js,encoding='utf8')
html_file.write_text(html,encoding='utf8')

extra=r'''
# WHALE TEST: exactly ten fake members (5 group roots + 5 children) on clean start.
def jingyu_seed_ten():
    if DB_URL != 'sqlite:////tmp/jingyu_v38_only_ten.sqlite3':
        raise RuntimeError('Whale test database isolation guard failed')
    from datetime import timedelta
    today=date.fromisoformat(current_day())
    now=utc_now()
    spec=[
        ('01',None,1000000,1800000,0,210),
        ('02',None,500000,850000,0,180),
        ('03',None,1000000,700000,0,150),
        ('06',None,1000000,2200000,0,120),
        ('08',None,1000000,1250000,0,90),
        ('JY000001','01',1000000,2100000,45000,60),
        ('JY000002','02',500000,450000,0,35),
        ('JY000003','03',1000000,1600000,100000,21),
        ('JY000004','06',1000000,1300000,0,7),
        ('JY000005','08',500000,800000,25000,0)
    ]
    with engine.begin() as db:
        existing=int(db.execute(text('SELECT COUNT(*) FROM members')).scalar() or 0)
        if existing:
            # Manual edits persist across test-service restarts; no hourly
            # regeneration or automatic erasure of member edits.
            print('JINGYU_EXISTING_TEST_MEMBERS='+str(existing),flush=True)
            return existing
        from uuid import uuid5, NAMESPACE_DNS
        ids={account:str(uuid5(NAMESPACE_DNS,'whale-jingyu-v38-fake-'+account))
             for account,_,_,_,_,_ in spec}
        values=[]
        for account,parent,stake,balance,daily,days in spec:
            values.append({
                'id':ids[account],'account':account,
                'joined_on':(today-timedelta(days=days)).isoformat(),
                'parent_id':ids[parent] if parent else None,
                'balance_cents':balance,
                'total_withdraw_cents':daily*2,
                'daily_withdraw_cents':daily,
                'stake_cents':stake,
                'daily_withdraw_on':today.isoformat() if daily else None,
                'remark':'鲸鱼小组虚拟测试（非真实会员）',
                'revision':1,'deleted':0,'created_at':now,'updated_at':now
            })
        db.execute(text("""INSERT INTO members
          (id,account,joined_on,parent_id,balance_cents,total_withdraw_cents,
           daily_withdraw_cents,stake_cents,daily_withdraw_on,remark,revision,
           deleted,created_at,updated_at)
          VALUES (:id,:account,:joined_on,:parent_id,:balance_cents,
           :total_withdraw_cents,:daily_withdraw_cents,:stake_cents,
           :daily_withdraw_on,:remark,:revision,:deleted,:created_at,:updated_at)"""),
            values)
        # Match today's synthetic withdrawal ledger to avoid double counting.
        for row in values:
            if not row['daily_withdraw_cents']:continue
            db.execute(text("""INSERT INTO daily_withdraw_ledger
                (member_id,business_day,amount_cents) VALUES (:m,:d,:a)"""),
                {'m':row['id'],'d':today.isoformat(),'a':row['daily_withdraw_cents']})
            db.execute(text("""INSERT INTO daily_withdraw_credit
                (member_id,business_day,credited_cents,settled_at)
                VALUES (:m,:d,:a,NULL)"""),
                {'m':row['id'],'d':today.isoformat(),'a':row['daily_withdraw_cents']})
        total=int(db.execute(text('SELECT COUNT(*) FROM members WHERE deleted=0')).scalar())
        if total!=10:raise RuntimeError('Whale synthetic seed MUST contain 10 active rows')
    print('JINGYU_TEST_FAKE_SEED=10;PRODUCTION_DB=DISCONNECTED',flush=True)
    return 10

@app.get('/api/jingyu-test/status')
def jingyu_test_status():
    with engine.connect() as db:
        active=int(db.execute(text('SELECT COUNT(*) FROM members WHERE deleted=0')).scalar() or 0)
        total=int(db.execute(text('SELECT COUNT(*) FROM members')).scalar() or 0)
    return {'site':'鲸鱼小组独立测试版 V38',
            'synthetic_original_count':1000,'active_members':active,
            'stored_members':total,'synthetic_seed_size':10,
            'isolated_test_database':True,
            'production_database_connected':False,
            'academy_enabled':True,
            'position_alert_enabled':True}
'''
assert '/api/jingyu-test/status' not in app
app_file.write_text(app+'\n'+extra,encoding='utf8')
(root/'tests/test_jingyu_ten.py').write_text(r'''
from pathlib import Path
from sqlalchemy import text
from app import DB_URL,engine,db_init,jingyu_seed_ten
def test_ten_members_stake_warning_and_isolated_database():
    assert DB_URL=='sqlite:////tmp/jingyu_v38_only_ten.sqlite3'
    assert 'DATABASE_URL' not in DB_URL
    db_init()
    n=jingyu_seed_ten()
    assert n==10
    with engine.connect() as db:
        r=db.execute(text('SELECT account,parent_id,stake_cents,balance_cents FROM members WHERE deleted=0')).mappings().all()
        assert len(r)==10
        assert set(x['account'] for x in r)=={'01','02','03','06','08'} | {'JY%06d'%i for i in range(1,6)}
        assert sum(x['parent_id'] is None for x in r)==5
        assert any(x['balance_cents']>1500000 and x['stake_cents']==1000000 for x in r)
        assert any(x['balance_cents']>750000 and x['stake_cents']==500000 for x in r)
    assert jingyu_seed_ten()==10
''',encoding='utf8')
print('鲸鱼 V38 专属升级：仅10条虚拟会员，压仓提醒和AI学院保留，正式数据库完全隔离')
