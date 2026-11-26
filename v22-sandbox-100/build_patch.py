"""Apply V22 test-only setup on extracted archive. Never touches official branch or storage."""
from pathlib import Path
import shutil
import ast
root=Path("member-tree")
app_path=root/"app.py"
html_path=root/"static"/"index.html"
s=app_path.read_text(encoding="utf-8")
anchor="def startup():\n    db_init()"
assert s.count(anchor)==1, "Unexpected V22 startup function; stop build"
replacement="""def startup():
    db_init()
    if os.environ.get('V22_SANDBOX') == '1':
        from sandbox_seed import seed_if_empty
        seed_if_empty(engine)"""
s=s.replace(anchor,replacement,1)
assert "/api/sandbox-status" not in s
s+="""

# Isolated test branch only. This endpoint reports synthetic test row count, never real member data.
@app.get('/api/sandbox-status')
def v22_sandbox_status():
    if os.environ.get('V22_SANDBOX') != '1':
        raise HTTPException(404)
    with engine.connect() as db:
        members = int(db.execute(text("SELECT COUNT(*) FROM members WHERE deleted=0")).scalar() or 0)
        all_members = int(db.execute(text("SELECT COUNT(*) FROM members")).scalar() or 0)
        roots = int(db.execute(text("SELECT COUNT(*) FROM members WHERE parent_id IS NULL AND deleted=0")).scalar() or 0)
    return {'sandbox': True, 'synthetic': True, 'active_members': members, 'total_members': all_members, 'roots': roots}
"""
ast.parse(s)
app_path.write_text(s,encoding="utf-8")
seed_src=Path("v22-sandbox-100/sandbox_seed.py")
assert seed_src.is_file()
shutil.copy2(seed_src,root/"sandbox_seed.py")
h=html_path.read_text(encoding="utf-8")
assert h.count("</body>")==1,"Unexpected HTML structure"
ribbon="""<div id="v22-sandbox-label" aria-label="独立测试版：100条虚拟数据" style="position:fixed;z-index:2147483000;bottom:12px;right:12px;background:#122e41f0;color:#fff;border:1px solid #57caaa;box-shadow:0 3px 16px #0006;padding:7px 12px;border-radius:9px;font-size:12px;font-weight:700;pointer-events:none">V22 独立测试版 · 100条虚拟数据</div>
"""
h=h.replace("</body>",ribbon+"</body>",1)
html_path.write_text(h,encoding="utf-8")
print("V22 isolated sandbox patch completed: seeding guard, status endpoint, visible test badge")
