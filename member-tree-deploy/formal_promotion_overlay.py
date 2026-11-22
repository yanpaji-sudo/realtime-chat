"""Promote Berlin test functionality onto the official member tree, preserving official UI/roster settings.

Runs only in the GitHub Actions build context, on files extracted from the test release.
The existing formal data store, secrets, and environment are never copied or modified.
"""
from pathlib import Path
from datetime import datetime, timezone
import base64, gzip, tarfile, io, re, py_compile

root=Path("member-tree")
ap=root/"app.py"
jp=root/"static"/"app.js"
hp=root/"static"/"index.html"
academy=root/"academy.py"
src=base64.b64decode(Path("/tmp/formal_payload.b64").read_bytes())
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(src)),mode="r:") as ft:
    original_index=ft.extractfile("member-tree/static/index.html").read()
    original_academy=ft.extractfile("member-tree/academy.py").read()
    original_app=ft.extractfile("member-tree/app.py").read().decode("utf-8")
    original_js=ft.extractfile("member-tree/static/app.js").read().decode("utf-8")

a=ap.read_text(encoding="utf-8")
j=jp.read_text(encoding="utf-8")
assert "def parse_legacy_full_export(payload,filename)" in a
assert "member_registration_times" in a
assert "berlin_incremental_6_columns" in a
assert "def _berlin_sample_due" in a
assert "berlinRefreshBusy" in j
assert "一键识别并填写" in j or "一键识别" in j
assert "const TREE_GROUPS=['daili01','daili02','daili05'];" in j

# Keep the existing five formal groups 01, 02, 03, 06 and 08.
j=j.replace("const TREE_GROUPS=['daili01','daili02','daili05'];",
            "const TREE_GROUPS=['01','02','03','06','08'];",1)
agent_root = """function berlinGroupMemberIds(group){
 const root=members.find(m=>String(m.account).toLowerCase()===String(group).toLowerCase());
 return root?tableNodeIds(root.account):new Set();
}
function berlinMemberGroup(member){
 const path=String(member.group_path||member.account).split(' / ');
 return TREE_GROUPS.find(g=>path.includes(g))||'';
}"""
formal_group = """function berlinGroupMemberIds(group){
 return new Set(members.filter(m=>String(m.group_account||m.account)===String(group)).map(m=>m.id));
}
function berlinMemberGroup(member){
 return String(member.group_account||member.account||'');
}"""
assert j.count(agent_root)==1, "New Berlin group source changed; refuse to publish"
j=j.replace(agent_root,formal_group,1)

# Restore official branding, labels and report name while keeping new business functionality.
j=j.replace("柏林数据统计","万诚数据统计").replace("柏林学院","磐石AI学院")
j=j.replace("柏林树状图系统","会员树状统计系统")
j=j.replace("柏林测试版","正式版").replace("柏林六列","六列")
j=j.replace("当前测试系统会员","当前正式系统会员")
j=j.replace("测试数据库","正式数据库")
j=j.replace("三组节点风险评估","五组节点风险评估")
j=j.replace("三组按节点","五组按节点")
j=j.replace("三组实时","五组实时")
j=j.replace("10位管理员","8位管理员")
j=j.replace("10名管理员","8名管理员")
j=j.replace("柏林","正式")
a=a.replace("柏林数据统计","万诚数据统计").replace("柏林学院","磐石AI学院")
a=a.replace("柏林六列","六列")
j=j.replace("约每10秒刷新","约每45秒刷新")
j=j.replace("约10秒刷新","约45秒刷新")
assert "const TREE_GROUPS=['01','02','03','06','08'];" in j
assert "function berlinGroupMemberIds(group)" in j
assert "function shownTreeMembers(rows=members)" in j

# Existing login/admin credentials and UI remain exactly as the prior formal release.
hp.write_bytes(original_index)
academy.write_bytes(original_academy)
ap.write_text(a,encoding="utf-8")
jp.write_text(j,encoding="utf-8")
test_readme=root/"BERLIN_TEST_README.txt"
if test_readme.exists():test_readme.unlink()
(root/"FORMAL_PROMOTION_NOTE.txt").write_text(
 "Formal performance and six-column importer upgrade; source from Berlin test.\n"
 "Existing formal member records, five group settings, session/password environment,"
 " and academy content are retained.\n",encoding="utf-8")

# Core data/session semantics are unchanged across the promoted release.
for field in ("SESSION_SECRET", "ADMIN_USERS_JSON", "DATABASE_URL", "daily_withdraw_credit", "daily_business_closes"):
    assert field in a and field in original_app, field
assert "柏林树状图系统" not in j and "柏林数据统计" not in a
py_compile.compile(str(ap),doraise=True)

out=io.BytesIO()
with tarfile.open(fileobj=out,mode="w") as t:
    t.add(root,arcname="member-tree",recursive=True)
release=base64.b64encode(gzip.compress(out.getvalue(),compresslevel=9,mtime=0)).decode("ascii")
Path("member-tree-deploy/payload.b64").write_text(release)
print("Formal source promoted; released encoded chars:",len(release))
