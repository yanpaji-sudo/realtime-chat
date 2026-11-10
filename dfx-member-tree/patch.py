"""DFX independent display fork. Only visual labels + login count; all data formulas are retained."""
from pathlib import Path
import re
root=Path('member-tree')
assert (root/'app.py').is_file()
files=[root/'app.py',root/'static/app.js',root/'static/index.html']
# Target display words only, preserve stake_cents storage and financial calculations.
replace=[
    ('充值/建仓','总存款'),
    ('团队充值/建仓','团队总存款'),
    ('建仓资金','总存款'),
    ('建仓金额','总存款'),
    ('本人建仓','本人总存款'),
    ('团队建仓','团队总存款'),
    ('节点总建仓','节点总存款'),
    ('新增建仓','新增存款'),
    ('建仓总额','总存款金额'),
]
for p in files:
    s=p.read_text(encoding='utf-8')
    original=s
    for old,new in replace:s=s.replace(old,new)
    if p.name=='index.html':
        s=s.replace('会员树状系统 · V21实时报表与树状图','DFX数据图 · 树状统计与报表')
        s=s.replace('会员树状统计系统 · 数据报表V22版','DFX数据图 · 会员树状统计系统')
        s=s.replace('8位管理员独立登录','10位管理员独立登录')
        s=s.replace('<b>会员数据中心</b>','<b>DFX数据中心</b>')
        s=s.replace('MEMBER HIERARCHY','DFX DATA HIERARCHY')
        # Distinguish ephemeral demo from the permanent standalone DFX database.
        s=s.replace('</body>', '<div class="dfx-demo-warning" role="note">DFX临时测试站 · 数据库尚未配置持久化，请勿录入正式会员数据</div></body>')
    if p.name=='app.py':
        s=s.replace("FastAPI(title='会员树状统计系统'", "FastAPI(title='DFX会员树状统计系统'")
        # A distinct project title; do not expose DB credentials and do not connect to production.
        s+='\n@app.get("/api/dfx-status")\ndef dfx_public_status():\n    return {"site":"DFX数据图","separate_instance":True,"admin_count":10,"storage_persistent":bool(os.environ.get("DATABASE_URL"))}\n'
    assert s!=original,p.name
    p.write_text(s,encoding='utf-8')
css=root/'static/style.css'
css.write_text(css.read_text(encoding='utf-8')+'''
.dfx-demo-warning{position:fixed;bottom:0;left:0;right:0;padding:6px 10px;
background:#fff2ca;color:#694300;text-align:center;font-size:12px;font-weight:700;
border-top:1px solid #e7c16c;z-index:9000;pointer-events:none}
''',encoding='utf-8')
assert 'stake_cents' in (root/'app.py').read_text()
assert 'dfx-demo-warning' in (root/'static/index.html').read_text()
print('DFX display fork ready: independent UI, deposits label, ten admins, ephemeral safety notice')
