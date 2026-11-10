"""Add DFX teams 05 and 09 everywhere group IDs are explicitly enumerated.
No changes to members, amounts, auth, databases, import/export formats, or formulas.
"""
from pathlib import Path

root=Path("member-tree")
backend=root/"app.py"
jsfile=root/"static/app.js"
htmlfile=root/"static/index.html"
py=backend.read_text(encoding="utf-8")
js=jsfile.read_text(encoding="utf-8")
html=htmlfile.read_text(encoding="utf-8")

def once(haystack, old, new, tag):
    matches=haystack.count(old)
    assert matches==1, f"{tag}: expected one exact anchor, found {matches}"
    return haystack.replace(old,new,1)

py=once(py,"REPORT_GROUPS=('01','02','03','06','08')",
        "REPORT_GROUPS=('01','02','03','05','06','08','09')","report definitions")
py=once(py,"fix['group_account'] not in ('01','02','03','06','08')",
        "fix['group_account'] not in ('01','02','03','05','06','08','09')","restore historical manual correction")

js=once(js,"const TREE_GROUPS=['01','02','03','06','08'];",
        "const TREE_GROUPS=['01','02','03','05','06','08','09'];","tree group switcher and risk summary")
js=once(js,"if(['01','02','03','06','08'].includes(r.group_account)",
        "if(TREE_GROUPS.includes(r.group_account)","daily report edit button")
js=once(js,"['03','03组：本月逐日'],['06','06组：本月逐日'],['08','08组：本月逐日']",
        "['03','03组：本月逐日'],['05','05组：本月逐日'],['06','06组：本月逐日'],['08','08组：本月逐日'],['09','09组：本月逐日']","monthly report dropdown")
html=once(html,'<option value="03">03小组</option><option value="06">06小组</option>',
        '<option value="03">03小组</option><option value="05">05小组</option><option value="06">06小组</option>',"top tree selector 05")
html=once(html,'<option value="08">08小组</option>',
        '<option value="08">08小组</option><option value="09">09小组</option>',"top tree selector 09")

assert "DFX数据图" in html
assert "总存款" in js
assert "10位管理员独立登录" in html
assert "def dfx_public_status():" in py
assert "'stake_cents'" in py
for p,txt in [(backend,py),(jsfile,js),(htmlfile,html)]:
    p.write_text(txt,encoding="utf-8")
print("DFX GROUPS OK:",("01","02","03","05","06","08","09"))
