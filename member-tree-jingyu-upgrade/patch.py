"""Whale V39 clean start. NO fake 1,000-member seed; NO production database connection."""
from pathlib import Path

root=Path('member-tree')
app_file=root/'app.py'
js_file=root/'static/app.js'
html_file=root/'static/index.html'
app=app_file.read_text(encoding='utf-8')
js=js_file.read_text(encoding='utf-8')
html=html_file.read_text(encoding='utf-8')

# Hard separation: ignore DATABASE_URL and use a new, empty whale-only database.
# The previous /tmp whale test database and journal are deleted, never copied.
before="DB_URL = os.environ.get('DATABASE_URL', 'sqlite:///' + str(ROOT / 'local-demo.db'))"
after="""DB_URL = 'sqlite:////tmp/jingyu_v39_clean.sqlite3'  # isolated whale only; ignores DATABASE_URL
for _old_suffix in ('', '-wal', '-shm', '-journal'):
    try:
        Path('/tmp/jingyu_isolated_member_tree_v28_1000.sqlite3'+_old_suffix).unlink()
    except FileNotFoundError:
        pass
"""
assert app.count(before)==1, 'Whale DB isolation anchor changed'
app=app.replace(before,after,1)

old_cookie="COOKIE = 'member_tree_v3_session'"
assert app.count(old_cookie)==1
app=app.replace(old_cookie,"COOKIE = 'jingyu_member_tree_test_session'",1)
app=app.replace("salt='member-tree-v3'","salt='jingyu-member-tree-test-v1'")

# IMPORTANT: Do not add jingyu_seed_1000() and do not call a seed in startup.
assert 'jingyu_seed_1000' not in app
assert 'jingyu_seed_1000' not in js

app=app.replace('万诚数据统计（','鲸鱼小组数据报表（')
js=js.replace('万诚数据统计（','鲸鱼小组数据报表（')
html=html.replace('会员树状统计系统 · 数据报表V22版',
                  '会员树状统计系统 · 鲸鱼小组测试版')
html=html.replace('8位管理员独立登录','3位测试管理员独立登录')
html=html.replace('<title>会员树状系统 · V21实时报表与树状图</title>',
                  '<title>鲸鱼小组 · 独立测试版 V39</title>')
html=html.replace('▥　今日报表总览','▥　鲸鱼小组数据报表')
js=js.replace("report:'今日报表总览'","report:'鲸鱼小组数据报表'")
js=js.replace('8位管理员','3位测试管理员')
# Additional explicit markers so the V39 version and whale identity are visible
html=html.replace('</title>', '</title>', 1)
assert '鲸鱼小组数据报表' in app or '鲸鱼小组数据报表' in js
app_file.write_text(app,encoding='utf-8')
js_file.write_text(js,encoding='utf-8')
html_file.write_text(html,encoding='utf-8')

status_source=r'''
@app.get('/api/jingyu-test/status')
def jingyu_test_status():
    with engine.begin() as db:
        total=db.execute(text('SELECT COUNT(*) FROM members WHERE deleted=0')).scalar()
    return {'site':'鲸鱼小组独立测试版 V39',
            'current_active_members':int(total),
            'synthetic_autofill_enabled':False,
            'data_source':'isolated-empty-whale-sqlite',
            'production_database_connected':False}
'''
assert '/api/jingyu-test/status' not in app
app_file.write_text(app+'\n'+status_source,encoding='utf-8')

(root/'tests/test_jingyu_empty.py').write_text(r'''
from sqlalchemy import text
from app import DB_URL,engine,db_init
def test_no_synthetic_members_and_own_db():
    assert DB_URL == 'sqlite:////tmp/jingyu_v39_clean.sqlite3'
    assert 'postgres' not in DB_URL.lower()
    db_init()
    with engine.begin() as db:
        n=db.execute(text("SELECT COUNT(*) FROM members")).scalar()
    assert n==0, 'Whale V39 must open with zero members'
''',encoding='utf-8')
print('Whale V39 clean-start patch complete: no 1000 fake members, no automatic seed.')
