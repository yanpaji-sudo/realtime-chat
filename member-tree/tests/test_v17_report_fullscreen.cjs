const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(__dirname+'/../static/app.js','utf8');
const css=fs.readFileSync(__dirname+'/../static/style.css','utf8');
for(const token of ["['tree','branch','report','ranking'].includes(view)", "'⛶ 报表最大化'", "reportFullscreenBtn", "filter.append(mWrap,gWrap,order,prevDay,nextDay,currentLabel,excel,maxBtn)"]){
 assert(src.includes(token),`V17 report fullscreen missing ${token}`);
}
assert(css.includes('.panel:fullscreen .report-table'), 'full-screen table adaptation missing');
assert(css.includes('.panel.fullscreen-fallback .report-page'), 'fallback report fullscreen missing');
const script=src.slice(src.indexOf('let branchFullscreenReflow=null;'),src.indexOf('function showToast('));
const buttons={treeFullscreenBtn:{textContent:'',setAttribute(n,v){this[n]=v}},reportFullscreenBtn:{textContent:'',setAttribute(n,v){this[n]=v}}};
const classes=new Set();
const panel={classList:{contains:x=>classes.has(x),add:x=>classes.add(x),remove:x=>classes.delete(x)},requestFullscreen:async()=>{document.fullscreenElement=panel}};
const events={};
const document={fullscreenElement:null,querySelector:s=>s==='.panel'?panel:null,addEventListener:(n,f)=>events[n]=f,exitFullscreen:async()=>{document.fullscreenElement=null},activeElement:{tagName:'BODY'}};
const window={addEventListener:()=>{}};
let view='report', toast='';
const context={document,window,view,el:id=>buttons[id],showToast:s=>toast=s,requestAnimationFrame:f=>f()};
vm.createContext(context); vm.runInContext(script,context);
(async()=>{
 assert.equal(context.fullscreenActive(),false);
 await context.toggleTreeFullscreen();
 assert.equal(context.fullscreenActive(),true);
 assert.equal(buttons.treeFullscreenBtn.textContent,'⛶ 退出全屏');
 assert.equal(buttons.reportFullscreenBtn['aria-pressed'],'true');
 await context.toggleTreeFullscreen(); assert.equal(context.fullscreenActive(),false);
 delete panel.requestFullscreen;
 await context.toggleTreeFullscreen(); assert.equal(classes.has('fullscreen-fallback'),true);
 events.keydown({key:'Escape'}); assert.equal(classes.has('fullscreen-fallback'),false);
 context.view='list'; await context.toggleTreeFullscreen(); assert.equal(context.fullscreenActive(),false);
 console.log('V17 report native/fallback fullscreen and Esc tested');
})().catch(e=>{console.error(e);process.exitCode=1});
