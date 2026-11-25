"""Fix V22 historical withdrawal fullscreen list scrollbar visibility.

Presentation-only: explicit independently scrolling inner pane, fixed viewport
height, forced vertical scrollbar and styled track/thumb (Chrome/Firefox).
No API, database, member, or withdrawal ledger changes.
"""
from pathlib import Path
p=Path('member-tree/static/index.html')
html=p.read_text(encoding='utf-8')
assert html.count('id="v22-historical-popup-maximized-css"')==1,'Maximized popup CSS missing'
assert html.count('</body>')==1,'Expected HTML body close'

css=r'''
<style id="v22-history-scrollbar-fix-css">
/* Do not let the flex child grow to fit the full table: that suppresses the
   scrollable overflow and can make the scrollbar appear to be missing. */
.v22-hist-details.v22-hist-maximized{
 top:12px!important;
 right:12px!important;
 bottom:12px!important;
 left:12px!important;
 height:calc(100vh - 24px)!important;
 height:calc(100dvh - 24px)!important;
 min-height:0!important;
 max-height:calc(100dvh - 24px)!important;
 display:flex!important;
 flex-direction:column!important;
 overflow:hidden!important;
}
.v22-hist-details.v22-hist-maximized>.v22-hist-accounts{
 flex:1 1 0px!important;
 min-height:0!important;
 height:0!important;
 max-height:none!important;
 overflow-y:scroll!important;
 overflow-x:auto!important;
 scrollbar-width:auto!important;
 scrollbar-color:#5485a4 #e5edf5!important;
 scrollbar-gutter:stable!important;
 overscroll-behavior-y:contain;
 -webkit-overflow-scrolling:touch;
}
.v22-hist-details.v22-hist-maximized>.v22-hist-accounts::-webkit-scrollbar{
 display:block!important;
 width:14px!important;
 height:12px!important;
 background:#e5edf5!important;
}
.v22-hist-details.v22-hist-maximized>.v22-hist-accounts::-webkit-scrollbar-track{
 display:block!important;
 background:#e5edf5!important;
 border-left:1px solid #c9d9e5!important;
 border-radius:9px!important;
}
.v22-hist-details.v22-hist-maximized>.v22-hist-accounts::-webkit-scrollbar-thumb{
 display:block!important;
 background:#6795b2!important;
 border-radius:9px!important;
 border:3px solid #e5edf5!important;
 min-height:32px!important;
}
.v22-hist-details.v22-hist-maximized>.v22-hist-accounts::-webkit-scrollbar-thumb:hover{
 background:#376f95!important;
}
@media(max-width:640px){
 .v22-hist-details.v22-hist-maximized{
  top:5px!important;right:5px!important;bottom:5px!important;left:5px!important;
  height:calc(100dvh - 10px)!important;max-height:calc(100dvh - 10px)!important;
 }
 .v22-hist-details.v22-hist-maximized>.v22-hist-accounts::-webkit-scrollbar{
  width:11px!important;
 }
}
</style>
'''
html=html.replace('</body>',css+'</body>',1)
assert 'overflow-y:scroll!important' in html
assert 'flex:1 1 0px!important' in html
p.write_text(html,encoding='utf-8')
print('PASS: V22 maximized table has fixed viewport height and visible scroll track/thumb')
