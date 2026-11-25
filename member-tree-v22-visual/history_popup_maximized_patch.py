"""V22 withdrawal/history popup maximize and restore, presentation-only.

Adds ⛶ 最大化预览 within the currently sortable history popup. It can fill
almost the entire browser viewport without replacing the member tree. Existing
sort, row-focus, filters and financial records stay unchanged. Escape restores.
"""
from pathlib import Path
jp=Path('member-tree/static/app.js')
hp=Path('member-tree/static/index.html')
j=jp.read_text(encoding='utf-8')
h=hp.read_text(encoding='utf-8')
def once(old,new):
    global j
    n=j.count(old)
    assert n==1, ('V22 expected exact UI marker',n,old[:145])
    j=j.replace(old,new,1)

anchor="function v22HistSortBy(field){"
helper=r'''
let v22HistMaximized=false;
function v22HistSyncMaximized(){
 const t=v22HistToolbar;
 if(!t)return;
 t.details.classList.toggle('v22-hist-maximized',v22HistMaximized);
 document.body.classList.toggle('v22-hist-page-maximized',v22HistMaximized);
 t.maximizeBtn.textContent=v22HistMaximized?'↙ 还原窗口':'⛶ 最大化预览';
 t.maximizeBtn.title=v22HistMaximized?'退出最大化（Esc）':'最大化预览历史明细表';
 t.maximizeBtn.setAttribute('aria-pressed',String(v22HistMaximized));
}
function v22HistSetMaximized(next,update=true){
 if(!v22HistToolbar)return;
 v22HistMaximized=Boolean(next);
 if(v22HistMaximized)v22HistToolbar.details.open=true;
 v22HistSyncMaximized();
 if(update)v22HistUpdateToolbar();
}
document.addEventListener('keydown',ev=>{
 if(ev.key==='Escape'&&v22HistMaximized){
  ev.preventDefault();
  v22HistSetMaximized(false);
  v22HistToolbar?.maximizeBtn?.focus();
 }
});
'''
once(anchor,helper+"\n"+anchor)

once("""  const summary=mk('summary','','查看账号');
  const list=mk('div','v22-hist-accounts');
  details.append(summary,list);""",
 """  const summary=mk('summary','','查看账号');
  const maximizeBtn=mk('button','v22-hist-maximize-btn','⛶ 最大化预览');
  maximizeBtn.type='button';
  maximizeBtn.title='最大化预览历史明细表';
  maximizeBtn.setAttribute('aria-label','最大化或还原历史提现明细表');
  maximizeBtn.setAttribute('aria-pressed','false');
  maximizeBtn.onclick=ev=>{
   ev?.preventDefault?.();
   ev?.stopPropagation?.();
   v22HistSetMaximized(!v22HistMaximized);
  };
  details.addEventListener('toggle',()=>{
   if(!details.open&&v22HistMaximized)v22HistSetMaximized(false);
  });
  const list=mk('div','v22-hist-accounts');
  details.append(summary,maximizeBtn,list);""")

once("v22HistToolbar={b,newer,withdraw,week,month,prev,pick,next,yesterday,today,info,details,list,note};",
     "v22HistToolbar={b,newer,withdraw,week,month,prev,pick,next,yesterday,today,info,details,list,note,maximizeBtn};")

once(""" t.b.hidden=!on;
 if(!on)return;""",
 """ t.b.hidden=!on;
 if(!on){
  if(v22HistMaximized)v22HistSetMaximized(false,false);
  return;
 }""")
once(""" t.details.hidden=!matches.length;
 t.details.querySelector('summary').textContent='查看 '+matches.length+' 个账号';""",
 """ if(!matches.length&&v22HistMaximized)v22HistSetMaximized(false,false);
 t.details.hidden=!matches.length;
 t.details.querySelector('summary').textContent='查看 '+matches.length+' 个账号';
 v22HistSyncMaximized();""")
once(" for(const x of sortedMatches.slice(0,400)){",
     """ const maxRows=v22HistMaximized?2500:400;
 for(const x of sortedMatches.slice(0,maxRows)){""")
once(" if(matches.length>400)t.list.append(mk('span','v22-hist-note','仅列出前400位；所有命中会员都已标记'));",
     " if(matches.length>maxRows)t.list.append(mk('span','v22-hist-note','当前显示前'+maxRows+'位；其他会员仍可通过缩小筛选范围查看'));")

# Make the whole panel stable when showing many rows and sticky table headers
# while preserving its original popover behavior in the normal state.
css=r'''
<style id="v22-historical-popup-maximized-css">
/* In the normal dropdown place the maximizer next to the "查看账号" summary. */
.v22-hist-details{position:relative}
.v22-hist-maximize-btn{
 display:inline-flex;align-items:center;justify-content:center;
 margin-left:9px;padding:5px 9px;border-radius:7px;
 border:1px solid #8bb9ce;background:#edf7ff;color:#164e6c;
 cursor:pointer;font-size:12px;font-weight:800;line-height:1.25;
 white-space:nowrap;
}
.v22-hist-maximize-btn:hover,.v22-hist-maximize-btn:focus-visible{
 background:#d9efff;outline:2px solid #9fcfe9;
}
body.v22-hist-page-maximized{overflow:hidden!important}
/* Fixed pane independent of scroll position, with space for a header. */
.v22-hist-details.v22-hist-maximized{
 position:fixed!important;inset:12px!important;
 width:auto!important;max-width:none!important;height:auto!important;
 z-index:2147483000!important;display:flex!important;flex-direction:column;
 box-sizing:border-box!important;overflow:hidden!important;
 background:#fff!important;border:1px solid #9db6c7!important;
 border-radius:13px!important;box-shadow:0 0 0 100vmax #0008,0 20px 60px #071b2b88!important;
 color:#243746!important;
}
.v22-hist-details.v22-hist-maximized>summary{
 display:block!important;flex:0 0 auto!important;list-style:none;
 font-weight:900;font-size:17px!important;color:#163a55!important;
 padding:18px 140px 16px 22px!important;cursor:default!important;
 background:#f1f7fc!important;border-bottom:1px solid #d0e0ed!important;
}
.v22-hist-details.v22-hist-maximized>summary::-webkit-details-marker{display:none}
.v22-hist-details.v22-hist-maximized>.v22-hist-maximize-btn{
 position:absolute!important;right:17px;top:14px;z-index:5!important;
 margin:0!important;padding:8px 12px!important;
 font-size:13px!important;background:#fff!important;border:1px solid #8db1c7!important;
}
.v22-hist-details.v22-hist-maximized>.v22-hist-accounts{
 position:relative!important;top:auto!important;right:auto!important;left:auto!important;
 display:block!important;min-width:0!important;width:100%!important;
 max-width:none!important;max-height:none!important;height:auto!important;
 flex:1 1 0!important;overflow:auto!important;
 margin:0!important;padding:14px 22px!important;
 box-sizing:border-box!important;background:#fff!important;
 border:0!important;border-radius:0!important;box-shadow:none!important;
 scrollbar-gutter:stable;
}
.v22-hist-details.v22-hist-maximized .v22-hist-list-heading{
 position:sticky!important;top:-14px!important;z-index:4!important;
 background:#edf4fb!important;padding:14px 14px!important;
 font-size:14px!important;border-bottom:2px solid #a4becc!important;
 box-sizing:border-box!important;
}
.v22-hist-details.v22-hist-maximized .v22-hist-account-row{
 padding:12px 14px!important;margin:4px 0!important;
 font-size:14px!important;min-height:45px;
}
.v22-hist-details.v22-hist-maximized .v22-hist-member-amount,
.v22-hist-details.v22-hist-maximized .v22-hist-member-count{
 font-size:14px!important;
}
.v22-hist-details.v22-hist-maximized .v22-hist-sort-header{font-size:14px!important}
@media(max-width:640px){
 .v22-hist-details.v22-hist-maximized{inset:5px!important}
 .v22-hist-details.v22-hist-maximized>summary{padding:14px 92px 14px 10px!important;font-size:14px!important}
 .v22-hist-details.v22-hist-maximized>.v22-hist-maximize-btn{
  top:9px!important;right:8px!important;padding:6px!important;font-size:11px!important
 }
 .v22-hist-details.v22-hist-maximized>.v22-hist-accounts{padding:8px!important}
 .v22-hist-details.v22-hist-maximized .v22-hist-list-heading{top:-8px!important;padding:10px 4px!important}
 .v22-hist-details.v22-hist-maximized .v22-hist-account-row{padding:8px 4px!important;font-size:11px!important}
 .v22-hist-details.v22-hist-maximized .v22-hist-sort-header{font-size:11px!important}
 .v22-hist-details.v22-hist-maximized .v22-hist-member-amount,
 .v22-hist-details.v22-hist-maximized .v22-hist-member-count{font-size:11px!important}
}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert 'v22HistSetMaximized(' in j
assert j.count("v22-hist-maximize-btn")==1
assert j.count("maxRows=v22HistMaximized?2500:400")==1
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print('PASS: V22 full-window history list, restore/Escape, scrollable rows and preserved clickable sort')
