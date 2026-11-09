"""Apply formal-only export features. Keep all existing data and formulas unchanged."""
from pathlib import Path

root=Path('member-tree')
backend=root/'app.py'
s=backend.read_text(encoding='utf-8')
anchor="@app.get('/api/export.xlsx')"
assert s.count(anchor)==1, 'Excel endpoint insertion anchor changed'
s=s.replace(anchor,Path('member-tree-team-export/endpoint.pyfrag').read_text(encoding='utf-8')+'\n'+anchor,1)
backend.write_text(s,encoding='utf-8')

jfile=root/'static/app.js'
js=jfile.read_text(encoding='utf-8')
def replace_once(old,new):
    global js
    assert js.count(old)==1, ('JS anchor changed',old[:90],js.count(old))
    js=js.replace(old,new,1)

replace_once('let branchViewportControls=null;',
             "let branchViewportControls=null;\nlet teamFocusId=null,teamFocusRestoreGroup=''; // view-only\n")
replace_once('function compactInfo(m){',
    Path('member-tree-team-export/frontend.jsfrag').read_text(encoding='utf-8')+'\nfunction compactInfo(m){')
replace_once("wrap.append(mk('h3','v28-pop-title',m.account+' · 个人与团队数据'));",
"""const header=mk('div','v42-team-head'),heading=mk('h3','v28-pop-title',m.account+' · 个人与团队数据'),buttons=mk('div','v42-team-buttons');
 const only=mk('button','v42-team-button','▤');only.type='button';only.title='仅看本团队架构';only.setAttribute('aria-label','仅看本团队架构');
 only.onclick=e=>{e.stopPropagation();e.preventDefault();teamOnlyShow(m.id)};
 buttons.append(only);
 if(role==='admin'){
  const down=mk('button','v42-team-button','⇩');down.type='button';down.title='导出本团队数据';down.setAttribute('aria-label','导出本团队数据');
  down.onclick=e=>{e.stopPropagation();e.preventDefault();teamExportDialog(m.id)};
  buttons.append(down);
 }
 header.append(heading,buttons);wrap.append(header);""")
replace_once("node.addEventListener('mouseleave',hideCompactTooltip);\n node.addEventListener('focus',()=>show(null));\n node.addEventListener('blur',hideCompactTooltip);",
"""node.addEventListener('mouseleave',()=>setTimeout(()=>{if(compactTooltipEl&&!compactTooltipEl.matches(':hover'))hideCompactTooltip()},260));
 node.addEventListener('focus',()=>show(null));
 node.addEventListener('blur',()=>setTimeout(()=>{if(compactTooltipEl&&!compactTooltipEl.matches(':hover'))hideCompactTooltip()},260));""")
replace_once("const shownRows=shownTreeMembers();\n if(positionAlarmOn)host.append(v33AlertPanel(shownRows));",
"""const shownRows=teamFocusId?teamExportRows(teamFocusId):shownTreeMembers();
 if(teamFocusId){
  const owner=members.find(x=>x.id===teamFocusId);
  const bar=mk('div','v42-focus-bar');
  bar.append(mk('b','','独立团队架构：'+(owner?.account||'')+'（共'+shownRows.length+'人）'));
  const back=mk('button','v42-team-back','↩ 返回完整架构');
  back.onclick=teamOnlyClear;bar.append(back);outer.prepend(bar);
 }
 if(positionAlarmOn)host.append(v33AlertPanel(shownRows));""")
replace_once("function selectTreeGroup(group){",
    "function selectTreeGroup(group){\n teamFocusId=null;teamFocusRestoreGroup='';")
replace_once("root.append(top);root.append(branchAgeLegend());",
"""const only=mk('button','button','▤ 仅看本团队');only.onclick=()=>teamOnlyShow(m.id);top.append(only);
 if(role==='admin'){const down=mk('button','button','⇩ 导出本团队');down.onclick=()=>teamExportDialog(m.id);top.append(down)}
 root.append(top);root.append(branchAgeLegend());""")
jfile.write_text(js,encoding='utf-8')

css=root/'static/style.css'
css.write_text(css.read_text(encoding='utf-8')+"""
/* Formal V42 - functional, clickable actions at the two marked header positions. */
.v28-compact-tooltip{pointer-events:auto!important}
.v42-team-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;padding-bottom:5px;border-bottom:1px solid #dce7f3}
.v42-team-head .v28-pop-title{flex:1;min-width:0;border:0;padding:0;line-height:1.45}
.v42-team-buttons{display:flex;gap:7px;flex:none}
.v42-team-button{height:31px;width:35px;padding:0;background:#ecf5ff;border:1px solid #9abadd;border-radius:7px;color:#18528b;font-size:19px;font-weight:900;cursor:pointer}
.v42-team-button:hover,.v42-team-button:focus-visible{background:#d3e8ff;outline:2px solid #72aaf2;outline-offset:1px}
.v42-focus-bar{display:flex;justify-content:space-between;gap:9px;align-items:center;flex-wrap:wrap;padding:10px 12px;background:#ecf5ff;border:1px solid #aac6e4;color:#1a4b7b;border-radius:9px}
.v42-team-back{padding:8px 13px;background:white;border:1px solid #91b5d7;border-radius:7px;cursor:pointer;color:#16487a;font-weight:bold}
.v42-export-dialog{width:min(440px,calc(100vw - 28px));padding:22px;border:1px solid #b3c7dd;border-radius:13px;box-shadow:0 25px 70px #152e4777}
.v42-export-dialog::backdrop{background:#13233e91}
.v42-export-dialog h3{margin:0 0 8px;color:#174b7e}
.v42-export-dialog p{font-size:13px;line-height:1.6;color:#57718c}
.v42-export-choice{display:block;width:100%;margin:8px 0;padding:12px;text-align:left;color:#174b7e;background:#f2f7fe;border:1px solid #c6d9ef;border-radius:7px;cursor:pointer;font-weight:bold}
.v42-export-choice:hover{background:#dbeeff}
.v42-export-cancel{display:block;margin:13px 0 0 auto;padding:8px 14px;border:0;border-radius:7px;color:#3c516b;cursor:pointer}
""",encoding='utf-8')
print('Formal production team-only view and exports integrated without schema/data changes')
