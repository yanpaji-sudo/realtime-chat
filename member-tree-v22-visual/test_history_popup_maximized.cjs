// Verify historical popup fullscreen/restore keyboard and sortable table preservation.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const start=js.indexOf('let v22HistMaximized=false;');
const end=js.indexOf('function v22HistSortBy(field)',start);
assert(start>0&&end>start&&end-start<3000,
 'Maximized controls must be present once inside history-helper script');
const handlers={};let updates=0,focused=0;
const classList=()=>{
 const set=new Set();
 return {set,toggle(cls,v){
  const yes=typeof v==='boolean'?v:!set.has(cls);
  yes?set.add(cls):set.delete(cls);
  return yes;
 },contains:cls=>set.has(cls)};
};
const details={
 open:false,classList:classList(),listeners:{},
 addEventListener(name,cb){this.listeners[name]=cb}
};
const maximizeBtn={
 textContent:'⛶ 最大化预览',
 attrs:{},setAttribute(k,v){this.attrs[k]=v},
 focus(){focused++}
};
const doc={
 body:{classList:classList()},
 addEventListener(name,cb){handlers[name]=cb}
};
const ctx={
 document:doc,
 v22HistUpdateToolbar:()=>{updates++},
 t:{details,maximizeBtn}
};
vm.createContext(ctx);
vm.runInContext('let v22HistToolbar=null;\n'+js.slice(start,end),ctx);
const run=(text)=>vm.runInContext(text,ctx);
run('v22HistToolbar=t');
assert.strictEqual(run('v22HistMaximized'),false);
run('v22HistSetMaximized(true)');
assert.strictEqual(run('v22HistMaximized'),true);
assert.strictEqual(details.open,true,'Expanding opens the details popup');
assert(details.classList.contains('v22-hist-maximized'),'Full-size class applied');
assert(doc.body.classList.contains('v22-hist-page-maximized'),'Body scrolling should be suppressed');
assert(maximizeBtn.textContent.includes('还原'));
assert.strictEqual(maximizeBtn.attrs['aria-pressed'],'true');
assert.strictEqual(updates,1,'List should redraw with larger page size');
run('v22HistSetMaximized(false)');
assert.strictEqual(run('v22HistMaximized'),false);
assert(!details.classList.contains('v22-hist-maximized'),'Restore returns normal dropdown');
assert(!doc.body.classList.contains('v22-hist-page-maximized'),'Restore frees page scroll');
assert(maximizeBtn.textContent.includes('最大化'));
assert.strictEqual(maximizeBtn.attrs['aria-pressed'],'false');
run('v22HistSetMaximized(true)');
let prevented=0;
handlers.keydown({key:'Escape',preventDefault(){prevented++}});
assert.strictEqual(prevented,1);
assert.strictEqual(run('v22HistMaximized'),false,'Escape exits full preview');
assert.strictEqual(focused,1,'Escape returns keyboard focus to control');
handlers.keydown({key:'Enter',preventDefault(){prevented++}});
assert.strictEqual(prevented,1,'Unrelated key should not be intercepted');
// Source checks for integration with original history toolbar and sort.
assert(js.includes("const maximizeBtn=mk('button','v22-hist-maximize-btn','⛶ 最大化预览')"));
assert(js.includes('maximizeBtn.onclick=ev=>'));
assert(js.includes("details.addEventListener('toggle',"));
assert(js.includes("if(!details.open&&v22HistMaximized)v22HistSetMaximized(false)"));
assert(js.includes("const maxRows=v22HistMaximized?2500:400"));
assert(js.includes('sortedMatches.slice(0,maxRows)'));
assert(js.includes('v22HistSortBy(key)'));
assert(js.includes('v22HistSortRows(matches,frequency,amounts)'));
assert(js.includes('btn.onclick=()=>v22HistFocus(x.id)'));
assert(js.includes("if(!matches.length&&v22HistMaximized)v22HistSetMaximized(false,false)"));
assert(js.includes("if(!on){\n  if(v22HistMaximized)v22HistSetMaximized(false,false);"));
assert(html.includes('id="v22-historical-popup-maximized-css"'));
assert(html.includes('position:fixed!important;inset:12px!important'));
assert(html.includes('z-index:2147483000!important'));
assert(html.includes('overflow:auto!important'));
assert(html.includes('position:sticky!important'));
assert(html.includes('body.v22-hist-page-maximized'));
assert(!js.includes('fetch(')||js.includes("'/history/withdrawals"),
 'Maximize must not introduce network requests');
console.log('PASS: maximize/restore, keyboard Escape, focus, scroll, sticky header, normal popup unchanged, sorting and member navigation retained');
