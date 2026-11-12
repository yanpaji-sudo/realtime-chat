const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const js=fs.readFileSync('static/app.js','utf8');
const css=fs.readFileSync('static/style.css','utf8');
assert(js.includes("compactTooltipHost(node).append(compactTooltipEl)"));
assert(js.includes("document.addEventListener('fullscreenchange',()=>{hideCompactTooltip();"));
assert(js.includes("if(!compactTooltipEl)show(e);else moveCompactTooltip(e,node)"));
assert(css.includes('.panel:fullscreen > .v28-compact-tooltip'));
const start=js.indexOf('function compactTooltipHost(node){');
const end=js.indexOf('function toggleCompactTree(){',start);
assert(start>=0&&end>start,'missing fullscreen tooltip implementation');
const full=js.slice(start,end);
const events={};
const member={account:'test-member'};
const node={
  getBoundingClientRect(){return {left:100,right:220,top:80,bottom:124}},
  addEventListener(kind,callback){events[kind]=callback}
};
const panel={
  contains(x){return x===node},
  fallback:false,
  classList:{contains(x){return x==='fullscreen-fallback'&&panel.fallback}},
  append(el){el.parent='panel'}
};
const body={append(el){el.parent='body'}};
const doc={fullscreenElement:null,body};
const fakeMk=()=>({
  setAttribute(){},append(){},remove(){},style:{},
  get offsetWidth(){return 375},get offsetHeight(){return 350}
});
const ctx={
 document:doc,window:{innerWidth:1200,innerHeight:700},
 fullscreenPanel:()=>panel,
 mk:fakeMk
};
vm.createContext(ctx);
vm.runInContext(
 "let compactTooltipEl=null;\n"+
 "function hideCompactTooltip(){if(compactTooltipEl){compactTooltipEl.remove();compactTooltipEl=null}}\n"+
 "function compactInfo(){return {}}\n"+
 "function moveCompactTooltip(){}\n"+
 full+
 "this.getTip=()=>compactTooltipEl;\nthis.attach=attachCompactHover;\n",
 ctx
);
ctx.attach(node,member);
events.mouseenter({clientX:130,clientY:110});
assert.equal(ctx.getTip().parent,'body');
events.mouseleave();
doc.fullscreenElement=panel;
events.mouseenter({clientX:130,clientY:110});
assert.equal(ctx.getTip().parent,'panel');
events.mouseleave();
events.mousemove({clientX:130,clientY:110});
assert.equal(ctx.getTip().parent,'panel');
events.mouseleave();
doc.fullscreenElement=null;
panel.fallback=true;
events.mousemove({clientX:130,clientY:110});
assert.equal(ctx.getTip().parent,'panel');
events.mouseleave();
panel.fallback=false;
events.mouseenter({clientX:130,clientY:110});
assert.equal(ctx.getTip().parent,'body');
console.log('V32 hover works in regular, native fullscreen, fallback fullscreen and mousemove transitions');
