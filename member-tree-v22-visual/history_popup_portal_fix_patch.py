"""Fix V22 maximized history table hidden in transformed/clipped ancestors.

The original <details> is moved to document.body during fullscreen and restored
to its original history toolbar on exit. This makes position:fixed relative to
the real viewport, not the tree canvas/transform parent.
Presentation only. No member, money, ledger or API changes.
"""
from pathlib import Path
jp=Path('member-tree/static/app.js')
hp=Path('member-tree/static/index.html')
j=jp.read_text(encoding='utf-8')
h=hp.read_text(encoding='utf-8')
old="""function v22HistSyncMaximized(){
 const t=v22HistToolbar;
 if(!t)return;
 t.details.classList.toggle('v22-hist-maximized',v22HistMaximized);
 document.body.classList.toggle('v22-hist-page-maximized',v22HistMaximized);
 t.maximizeBtn.textContent=v22HistMaximized?'↙ 还原窗口':'⛶ 最大化预览';
 t.maximizeBtn.title=v22HistMaximized?'退出最大化（Esc）':'最大化预览历史明细表';
 t.maximizeBtn.setAttribute('aria-pressed',String(v22HistMaximized));
}"""
new="""function v22HistSyncMaximized(){
 const t=v22HistToolbar;
 if(!t)return;
 // A transformed, zoomed or overflow-hidden tree container traps position:
 // fixed children. Portal the real table to body; restore the same element.
 if(v22HistMaximized){
  if(t.details.parentElement!==document.body)document.body.appendChild(t.details);
 }else if(t.details.parentElement!==t.b){
  t.b.insertBefore(t.details,t.note);
 }
 t.details.classList.toggle('v22-hist-maximized',v22HistMaximized);
 document.body.classList.toggle('v22-hist-page-maximized',v22HistMaximized);
 t.details.setAttribute('role',v22HistMaximized?'dialog':'region');
 if(v22HistMaximized)t.details.setAttribute('aria-modal','true');
 else t.details.removeAttribute('aria-modal');
 t.maximizeBtn.textContent=v22HistMaximized?'↙ 还原窗口':'⛶ 最大化预览';
 t.maximizeBtn.title=v22HistMaximized?'退出最大化（Esc）':'最大化预览历史明细表';
 t.maximizeBtn.setAttribute('aria-pressed',String(v22HistMaximized));
}"""
assert j.count(old)==1,'V22 full-window state hook changed'
j=j.replace(old,new,1)
css=r'''
<style id="v22-historical-popup-portal-fix-css">
/* Detached from the graph and attached directly to body: true viewport layer. */
body>.v22-hist-details.v22-hist-maximized{
 position:fixed!important;
 inset:8px!important;
 z-index:2147483640!important;
 width:calc(100vw - 16px)!important;
 height:calc(100dvh - 16px)!important;
 min-height:0!important;
 max-height:calc(100dvh - 16px)!important;
 display:flex!important;
 flex-direction:column!important;
 overflow:hidden!important;
 visibility:visible!important;
 opacity:1!important;
 isolation:isolate;
 background:#fff!important;
}
body>.v22-hist-details.v22-hist-maximized[open]>.v22-hist-accounts{
 display:block!important;
 visibility:visible!important;
 opacity:1!important;
 flex:1 1 0px!important;
 min-height:0!important;
 height:0!important;
 overflow-y:scroll!important;
 overflow-x:auto!important;
 background:#fff!important;
 position:relative!important;
}
body>.v22-hist-details.v22-hist-maximized>.v22-hist-maximize-btn{
 position:absolute!important;
 right:15px!important;
 top:12px!important;
 z-index:10!important;
}
@media(max-width:640px){
 body>.v22-hist-details.v22-hist-maximized{
  inset:4px!important;
  width:calc(100vw - 8px)!important;
  height:calc(100dvh - 8px)!important;
  max-height:calc(100dvh - 8px)!important;
 }
}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count('document.body.appendChild(t.details)')==1
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print('PASS: real fullscreen popover mounted at document.body, restored to original toolbar')
