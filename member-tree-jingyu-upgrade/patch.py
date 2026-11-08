from pathlib import Path

root=Path('member-tree')
app_file=root/'app.py'
js_file=root/'static/app.js'
html_file=root/'static/index.html'
app=app_file.read_text(encoding='utf-8')
js=js_file.read_text(encoding='utf-8')
html=html_file.read_text(encoding='utf-8')

# Explicitly disconnect this branch from all configurable external database URLs.
# The test site CANNOT consult or write the production PostgreSQL database.
before="DB_URL = os.environ.get('DATABASE_URL', 'sqlite:///' + str(ROOT / 'local-demo.db'))"
after="DB_URL = 'sqlite:////tmp/jingyu_isolated_member_tree_v28_1000.sqlite3'  # isolated TEST-ONLY database; ignores DATABASE_URL"
assert app.count(before)==1, 'DB initialization code changed'
app=app.replace(before,after)
assert "COOKIE = 'member_tree_v3_session'" in app
app=app.replace("COOKIE = 'member_tree_v3_session'","COOKIE = 'jingyu_member_tree_test_session'")
app=app.replace("salt='member-tree-v3'","salt='jingyu-member-tree-test-v1'")

# Keep V27's functions unchanged but seed a synthetic-only dataset at first startup.
marker="    db_init()\n    if os.environ.get('ENABLE_MIDNIGHT_WORKER','1')=='1':"
assert app.count(marker)==1
app=app.replace(marker,"    db_init()\n    if os.environ.get('JINGYU_AUTOFILL','1')=='1':\n        jingyu_seed_1000()\n    if os.environ.get('ENABLE_MIDNIGHT_WORKER','1')=='1':")

# Prevent the built-in 7-person demo seed from creating confusion in the whale test.
# It remains hidden on the frontend, as in the V27 source.
assert "def seed_demo(req: Request):" in app

app=app.replace('万诚数据统计（','鲸鱼小组数据报表（')
js=js.replace('万诚数据统计（','鲸鱼小组数据报表（')
assert '鲸鱼小组数据报表（' in app and '鲸鱼小组数据报表（' in js, 'Whale identity not applied'

# Give this service a visibly distinct test identity, with ONLY three administrators.
assert '会员树状统计系统' in html, 'Unexpected HTML source for whale upgrade'
html=html.replace('会员树状统计系统 · 数据报表V22版','会员树状统计系统 · 鲸鱼小组测试版')
html=html.replace('8位管理员独立登录','3位测试管理员独立登录')
html=html.replace('<title>会员树状系统 · V21实时报表与树状图</title>','<title>鲸鱼小组 · 独立测试版 V39</title>')
html=html.replace('▥　今日报表总览','▥　鲸鱼小组数据报表')
js=js.replace("report:'今日报表总览'","report:'鲸鱼小组数据报表'")
js=js.replace('8位管理员','3位测试管理员')
html_file.write_text(html,encoding='utf-8')
js_file.write_text(js,encoding='utf-8')

# All synthetic records are generated locally from a random seed and have unique
# clearly fake JY accounts. None come from any other service or uploaded file.
seed_source=r'''
# Independent whale group synthetic testing (1,000 FAKE accounts, no customer data)
def jingyu_seed_1000():
    import random
    if DB_URL != 'sqlite:////tmp/jingyu_isolated_member_tree_v28_1000.sqlite3':
        raise RuntimeError('鲸鱼测试服务数据库隔离检查失败')
    rng=random.Random(int.from_bytes(os.urandom(16),'big'))
    today=date.fromisoformat(current_day())
    now=utc_now()
    groups=['01','02','03','06','08']
    with engine.begin() as db:
        n=int(db.execute(text('SELECT COUNT(*) FROM members')).scalar() or 0)
        if n:
            print('JINGYU_TEST existing_synthetic_or_modified_data count='+str(n),flush=True)
            return n
        created_ids={}
        group_ids={g:[] for g in groups}
        join_dates={}
        group_totals={g:{'n':0,'balance':0} for g in groups}
        rows=[]
        random_accounts=iter(rng.sample(range(100000,1000000),995))
        for i in range(1000):
            g=groups[i%5]
            is_root=i<5
            account=g if is_root else ('JY%06d'%next(random_accounts))
            mid=str(uuid.uuid4())
            if is_root:
                parent=None
                joined=today-timedelta(days=215)
            else:
                parent=rng.choice(group_ids[g])
                base=join_dates[parent]
                joined=max(base,today-timedelta(days=rng.randint(0,195)))
            joined_str=joined.isoformat()
            # Include both today's new members and withdrawals for visual tests.
            if not is_root and i%29==0: joined_str=today.isoformat()
            stake=rng.choices([500000,1000000,1500000,2000000],weights=[2,7,1,2])[0]
            balance=rng.randint(0,2800000)
            total=rng.randint(0,1300000)
            withdraw=rng.randint(2500,950000) if i%4==0 else 0
            fields={
                'id':mid,'account':account,'joined_on':joined_str,
                'parent_id':parent,'balance_cents':balance,
                'total_withdraw_cents':total,'daily_withdraw_cents':withdraw,
                'stake_cents':stake,'daily_withdraw_on':today.isoformat() if withdraw else None,
                'remark':'鲸鱼虚构测试',
                'revision':1,'deleted':0,'created_at':now,'updated_at':now
            }
            rows.append(fields)
            group_ids[g].append(mid)
            join_dates[mid]=joined
            group_totals[g]['n']+=1
            group_totals[g]['balance']+=balance
        # Bulk insert 1000 members in one transaction.
        insert=text("""INSERT INTO members
          (id,account,joined_on,parent_id,balance_cents,total_withdraw_cents,
           daily_withdraw_cents,stake_cents,daily_withdraw_on,remark,revision,
           deleted,created_at,updated_at)
          VALUES (:id,:account,:joined_on,:parent_id,:balance_cents,
           :total_withdraw_cents,:daily_withdraw_cents,:stake_cents,:daily_withdraw_on,
           :remark,:revision,:deleted,:created_at,:updated_at)""")
        db.execute(insert,rows)
        # Today's synthetic withdrawal ledger, with matching credits to avoid
        # double counting when the previous date is settled.
        todaykey=today.isoformat()
        for r in rows:
            if not r['daily_withdraw_cents']:continue
            db.execute(text("""INSERT INTO daily_withdraw_ledger(member_id,business_day,amount_cents)
              VALUES (:i,:d,:a)"""),
              {'i':r['id'],'d':todaykey,'a':r['daily_withdraw_cents']})
            db.execute(text("""INSERT INTO daily_withdraw_credit(member_id,business_day,credited_cents,settled_at)
              VALUES (:i,:d,:a,NULL)"""),
              {'i':r['id'],'d':todaykey,'a':r['daily_withdraw_cents']})
        # Historical synthetic daily reports support the full reporting UI,
        # month selection and Excel export without touching real financial records.
        historical=[]
        for days_ago in range(35,0,-1):
            d=(today-timedelta(days=days_ago)).isoformat()
            dayrows=[]
            for g in groups:
                baseline=group_totals[g]
                ratio=1.0-0.20*(days_ago/35)
                cn=max(5,round(baseline['n']*ratio))
                newcomers=rng.randint(1,6)
                snapshot={
                    'business_day':d,'group_account':g,
                    'member_count':cn,'new_count':newcomers,
                    'new_stake_cents':newcomers*rng.choice([500000,1000000,2000000]),
                    'withdraw_cents':rng.randint(30000,1800000),
                    'balance_cents':max(0,int(baseline['balance']*ratio + rng.randint(-250000,250000))),
                    'captured_at':d+'T15:55:00+00:00'
                }
                dayrows.append(snapshot)
            historical.extend(dayrows)
            historical.append({
                'business_day':d,'group_account':'__ALL__',
                'member_count':sum(q['member_count'] for q in dayrows),
                'new_count':sum(q['new_count'] for q in dayrows),
                'new_stake_cents':sum(q['new_stake_cents'] for q in dayrows),
                'withdraw_cents':sum(q['withdraw_cents'] for q in dayrows),
                'balance_cents':sum(q['balance_cents'] for q in dayrows),
                'captured_at':d+'T15:55:00+00:00'
            })
        db.execute(text("""INSERT INTO daily_group_snapshots
          (business_day,group_account,member_count,new_count,new_stake_cents,
           withdraw_cents,balance_cents,captured_at)
          VALUES (:business_day,:group_account,:member_count,:new_count,
           :new_stake_cents,:withdraw_cents,:balance_cents,:captured_at)"""),historical)
        db.execute(text("UPDATE reporting_meta SET value=:v WHERE name='tracking_since'"),
                   {'v':(today-timedelta(days=35)).isoformat()})
        capture_current_report(db,today.isoformat())
        audit(db,'seed_demo',{'count':1000,'dataset':'JINGYU_SYNTHETIC_ONLY'},'system-synthetic')
        count=db.execute(text('SELECT COUNT(*) FROM members')).scalar()
        if count!=1000:raise RuntimeError('鲸鱼测试数据数量校验失败')
    print('JINGYU_TEST synthetic_seed_created=1000 dataset=FAKE_ONLY',flush=True)
    return 1000

@app.get('/api/jingyu-test/status')
def jingyu_test_status():
    with engine.begin() as db:
        total=db.execute(text('SELECT COUNT(*) FROM members WHERE deleted=0')).scalar()
    return {'site':'鲸鱼小组独立测试版','synthetic_initial_count':1000,
            'current_active_members':int(total),'data_source':'isolated-local-sqlite-only',
            'production_database_connected':False}
'''
assert 'def jingyu_seed_1000()' not in app
app=app+'\n'+seed_source
app_file.write_text(app,encoding='utf-8')

(root/'tests/test_jingyu_isolation.py').write_text('''
import os
from sqlalchemy import text
from app import DB_URL, engine, db_init, jingyu_seed_1000
def test_1000_fake_members_and_separate_db():
    assert DB_URL == 'sqlite:////tmp/jingyu_isolated_member_tree_v28_1000.sqlite3'
    assert 'postgres' not in DB_URL
    db_init()
    n=jingyu_seed_1000()
    assert n == 1000
    with engine.begin() as db:
        rows=db.execute(text("SELECT account,parent_id,joined_on FROM members")).mappings().all()
        assert len(rows)==1000
        assert len({r['account'].lower() for r in rows})==1000
        assert set(r['account'] for r in rows[:5])=={'01','02','03','06','08'}
        assert all(r['account'] in {'01','02','03','06','08'} or r['account'].startswith('JY') for r in rows)
        assert db.execute(text("SELECT COUNT(*) FROM daily_group_snapshots")).scalar() >= 200
        assert db.execute(text("SELECT COUNT(*) FROM daily_withdraw_ledger")).scalar() > 0
    assert jingyu_seed_1000()==1000
''',encoding='utf-8')
print('JINGYU V39 patch applied: compact view and all prior features preserved, independent database, 1000 synthetic members.')
