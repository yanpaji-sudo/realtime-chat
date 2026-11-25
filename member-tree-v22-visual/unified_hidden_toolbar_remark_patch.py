"""V22 unified hidden fullscreen toolbar + account/remark linked lookup.

Only app.js and style.css are modified. No account, authorization, financial,
database or API logic is changed. Preserve original control elements/handlers.
"""
from pathlib import Path
p=Path("member-tree/static/app.js")
cssfile=Path("member-tree/static/style.css")
s=p.read_text(encoding='utf-8')
css=cssfile.read_text(encoding='utf-8')
def once(a,b):
 global s
 n=s.count(a)
 assert n==1,("V22 toolbar/search anchor changed",n,a[:110])
 s=s.replace(a,b,1)
helper=r'''
// V22 unified toolbar, fullscreen Alt+Q toggle, and linked account/remark search.
let v22UnifiedUI=null,v22UnifiedFullscreenBefore=false;
let v22RemarkCache=null,v22RemarkCacheMembers=null,v22RemarkCacheLength=-1;
function v22RemarkByAccount(account){
 if(v22RemarkCacheMembers!==members||v22RemarkCacheLength!==members.length){
  v22RemarkCacheMembers=members;v22RemarkCacheLength=members.length;
  v22RemarkCache=new Map(members.map(m=>[String(m.account||''),String(m.remark||'')]));
 }
 return v22RemarkCache.get(String(account||''))||'';
}
function v22RemarkSearchMatches(member,raw){
 const q=String(raw||'').trim().toLocaleLowerCase();
 if(!q)return true;
 const account=String(member.account||'').toLocaleLowerCase();
 if(account.includes(q))return true;
 const note=member.remark==null?v22RemarkByAccount(member.account):String(member.remark);
 return note.toLocaleLowerCase().includes(q);
}
function v22RemarkSearchCandidates(raw,rows=members){
 const text=String(raw||'').trim(),q=text.toLocaleLowerCase();
 if(!q)return [];
 const scores=rows.filter(x=>v22RemarkSearchMatches(x,text)).map(m=>{
  const acc=String(m.account||'').toLocaleLowerCase();
  const note=String(m.remark||'').toLocaleLowerCase();
  return {m,score:acc===q?0:acc.startsWith(q)?1:note===q?2:
    note.startsWith(q)?3:acc.includes(q)?4:5};
 });
 scores.sort((a,b)=>a.score-b.score||String(a.m.account).localeCompare(String(b.m.account),'zh-CN',{numeric:true}));
 return scores.map(x=>x.m);
}
function v22RemarkSearchLocateMatches(raw,rows=members){
 const text=String(raw||'').trim(),q=text.toLocaleLowerCase();
 if(!text)return [];
 const exact=rows.filter(x=>String(x.account||'')===text);
 if(exact.length)return exact;
 const exactIgnoreCase=rows.filter(x=>String(x.account||'').toLocaleLowerCase()===q);
 if(exactIgnoreCase.length)return exactIgnoreCase;
 // No silent partial-account location; remarks may be partial but duplicates are ambiguous.
 return rows.filter(x=>String(x.remark||'').trim().toLocaleLowerCase().includes(q));
}
function v22RemarkSuggestionsHide(){
 if(v22UnifiedUI?.results)v22UnifiedUI.results.hidden=true;
}
function v22RemarkSuggestionsShow(){
 if(!v22UnifiedUI)return;
 const list=v22UnifiedUI.results,text=v22UnifiedUI.search.value.trim();
 list.replaceChildren();
 if(!text||!['branch','tree','list','table','ranking'].includes(view)){
  list.hidden=true;return;
 }
 const all=v22RemarkSearchCandidates(text);
 if(!all.length){list.hidden=true;return}
 const top=mk('div','v22-unified-result-heading','关联账号 / 会员备注 · 找到 '+all.length+' 条');
 list.append(top);
 for(const m of all.slice(0,40)){
  const b=mk('button','v22-unified-result',null);
  b.type='button';
  const id=mk('b','',String(m.account||''));
  const name=mk('span','',String(m.remark||'未填写备注'));
  b.append(id,name);
  b.addEventListener('mousedown',e=>e.preventDefault());
  b.onclick=()=>v22RemarkSearchPick(m);
  list.append(b);
 }
 if(all.length>40)list.append(mk('p','v22-unified-result-more','仅显示前40条，请输入更多字符缩小范围'));
 list.hidden=false;
}
function v22RemarkSearchPick(member){
 if(!member)return false;
 const input=el('search');
 input.value=String(member.account||'');
 input.setCustomValidity('');
 query='';v22RemarkSuggestionsHide();
 return locateBranchAccount();
}
function v22UnifiedToolbarSync(){
 if(!v22UnifiedUI)return;
 const full=fullscreenActive();
 if(full!==v22UnifiedFullscreenBefore){
  v22UnifiedFullscreenBefore=full;
  // Hide everything automatically on entering fullscreen, show toolbar when exiting.
  v22UnifiedUI.open=!full;
 }
 const ui=v22UnifiedUI;
 ui.panel.classList.toggle('v22-unified-full',full);
 ui.dock.classList.toggle('v22-unified-open',ui.open);
 ui.dock.setAttribute('aria-expanded',String(ui.open));
 ui.toggle.setAttribute('aria-expanded',String(ui.open));
 ui.toggle.textContent=ui.open?'⌃ 收起工具栏 · Alt+Q':'☰ 工具栏 · Alt+Q';
 ui.search.title='支持完整账号、部分账号或会员备注；同名时从候选列表选择';
 if(!ui.open)v22RemarkSuggestionsHide();
}
function v22UnifiedToolbarToggle(force){
 if(!v22UnifiedUI)return;
 v22UnifiedUI.open=typeof force==='boolean'?force:!v22UnifiedUI.open;
 v22UnifiedToolbarSync();
 if(v22UnifiedUI.open&&fullscreenActive())rescaleFullscreenBranch();
}
function v22UnifiedToolbarSetup(){
 if(v22UnifiedUI)return;
 const panel=document.querySelector('.panel'),
  header=panel?.querySelector('.panel-header'),
  controls=header?.querySelector('.actions'),
  search=el('search');
 if(!panel||!header||!controls||!search)return;
 const dock=mk('div','v22-unified-dock v22-unified-open');dock.id='v22UnifiedToolbar';
 const toggle=mk('button','v22-unified-toggle','⌃ 收起工具栏 · Alt+Q');
 toggle.type='button';toggle.setAttribute('aria-label','显示或隐藏快捷工具栏，快捷键 Alt+Q');
 toggle.onclick=()=>v22UnifiedToolbarToggle();
 const track=mk('div','v22-unified-track');track.id='v22UnifiedTrack';
 const holder=mk('div','v22-unified-search-holder');
 const results=mk('div','v22-unified-results');results.id='v22RemarkSearchResults';
 results.hidden=true;results.setAttribute('role','listbox');
 controls.insertBefore(holder,search);holder.append(search,results);
 dock.append(toggle,track);track.append(controls);
 panel.insertBefore(dock,header);
 v22UnifiedUI={panel,header,controls,dock,toggle,track,search,results,open:true};
 v22UnifiedFullscreenBefore=fullscreenActive();
 search.addEventListener('input',v22RemarkSuggestionsShow);
 search.addEventListener('keydown',e=>{
   if(e.key==='Escape'){v22RemarkSuggestionsHide();return}
   if(e.key==='Enter'&&view!=='branch'){
    const matches=v22RemarkSearchCandidates(search.value);
    if(matches.length===1){e.preventDefault();v22RemarkSearchPick(matches[0])}
    // Multi-match search remains filtered until the user picks the correct account.
   }
 });
 search.addEventListener('blur',()=>{
   // An explicit candidate mouse action stays clickable because mousedown prevents blur.
   v22RemarkSuggestionsHide();
 });
 document.addEventListener('keydown',e=>{
  if(e.altKey&&String(e.key).toLocaleLowerCase()==='q'&&!e.ctrlKey&&!e.metaKey&&!e.repeat
     &&!document.querySelector('dialog[open]')){
   e.preventDefault();v22UnifiedToolbarToggle();return;
  }
  if(e.key==='Escape'){
   v22RemarkSuggestionsHide();
   if(fullscreenActive()&&v22UnifiedUI?.open)v22UnifiedToolbarToggle(false);
  }
 });
 document.addEventListener('fullscreenchange',()=>v22UnifiedToolbarSync());
 v22UnifiedToolbarSync();
}
'''
once("function locateBranchAccount(){",helper+"\nfunction locateBranchAccount(){")
once("if(!searched){showToast('请输入完整会员账号，再点击「精准定位」');field.focus();return false}",
     "if(!searched){showToast('请输入会员账号或备注后搜索');field.focus();return false}")
once("const member=members.find(m=>m.account===searched);",
     """const candidates=v22RemarkSearchLocateMatches(searched);
 if(candidates.length>1){
  field.setCustomValidity('');
  v22RemarkSuggestionsShow();
  showToast('匹配到 '+candidates.length+' 位会员，请从账号和备注候选中选择');
  field.focus();return false;
 }
 const member=candidates[0];""")
once("branchSelectedAccount='';field.setCustomValidity('未找到完整账号，请检查前导0和大小写');",
     "branchSelectedAccount='';field.setCustomValidity('未找到匹配的账号或备注');")
once("showToast('未找到此完整会员账号。请输入完整账号（不是部分数字）。');",
     "showToast('未找到相应会员，请输入完整账号或备注关键字');")
once("field.setCustomValidity('');\n const index=new Map(members.map(m=>[m.id,m]));let cur=member,steps=0;",
     "field.setCustomValidity('');v22RemarkSuggestionsHide();\n const index=new Map(members.map(m=>[m.id,m]));let cur=member,steps=0;")
# Account / remark linking across existing list, table, tree and ranking.
fragment="x.account.toLowerCase().includes(query.toLowerCase())"
assert s.count(fragment)==5,("Expected five existing search sites",s.count(fragment))
s=s.replace(fragment,"v22RemarkSearchMatches(x,query)")
# Move history/loan/dormant controls into the same bar instead of a separate lower row.
import re
s,count=re.subn(r"if\(container\.parentElement&&t\.b\.parentElement!==container\.parentElement\)\s*container\.parentElement\.insertBefore\(t\.b,container\);",
    "const unified=document.getElementById('v22UnifiedTrack');\n  const target=unified||container.parentElement;\n  if(target&&t.b.parentElement!==target)target.append(t.b);",s)
assert count==1,"V22 history toolbar mount has changed"
# Placeholder responsive with search note.
once("el('search').placeholder=view==='branch'?'输入完整会员账号 · 回车精准定位':'🔎 搜索会员账号';",
     "el('search').placeholder=view==='branch'?'🔎 账号 / 备注 · 回车定位':'🔎 搜索账号或备注';")
# Setup after normal event wiring is attached and before initial login selection.
once("el('exportBtn').onclick=()=>testDownloadMembers();selectedLogin('viewer')}",
     "el('exportBtn').onclick=()=>testDownloadMembers();v22UnifiedToolbarSetup();selectedLogin('viewer')}")
# Fallback fullscreen has no fullscreenchange event, so sync after toggle.
once("refreshFullscreenButton();rescaleFullscreenBranch();\n}",
     "refreshFullscreenButton();rescaleFullscreenBranch();v22UnifiedToolbarSync();\n}")

