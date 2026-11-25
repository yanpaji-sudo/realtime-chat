// V22 fullscreen history popup: scroll container is height bounded + visible.
const fs=require('fs'),assert=require('assert');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const head=html.indexOf('id="v22-history-scrollbar-fix-css"');
assert(head>0);
const end=html.indexOf('</style>',head);
const css=html.slice(head,end);
const block=css.match(/\.v22-hist-details\.v22-hist-maximized>\.v22-hist-accounts\s*\{([^}]*)\}/);
assert(block,'The targeted historical accounts pane selector must be present');
const st=block[1];
for(const s of ['flex:1 1 0px!important','min-height:0!important','height:0!important',
 'overflow-y:scroll!important','scrollbar-gutter:stable!important','scrollbar-width:auto!important',
 'scrollbar-color:#5485a4 #e5edf5!important'])
 assert(st.includes(s),'Missing scroll enforcement: '+s);
assert(css.includes('height:calc(100dvh - 24px)!important'));
assert(css.includes('max-height:calc(100dvh - 24px)!important'));
assert(css.includes('.v22-hist-details.v22-hist-maximized>.v22-hist-accounts::-webkit-scrollbar{'));
assert(css.includes('width:14px!important'));
assert(css.includes('::-webkit-scrollbar-thumb{'));
assert(css.includes('min-height:32px!important'));
assert(css.includes('@media(max-width:640px)'));
assert(js.includes('const maxRows=v22HistMaximized?2500:400'));
assert(js.includes('v22HistSortRows(matches,frequency,amounts)'));
assert(js.includes('v22HistSetMaximized(false)'));
assert(js.includes("ev.key==='Escape'&&v22HistMaximized"));
assert(js.includes("btn.onclick=()=>v22HistFocus(x.id)"));
assert(js.includes("class:'withdraw-red-outer'"));
console.log('PASS: fullscreen popup scroll has fixed height, bounded flex pane, visible scrollbar track/thumb, list sort and restore preserved');
