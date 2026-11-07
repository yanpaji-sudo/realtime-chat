from pathlib import Path
root=Path("member-tree")
js_path=root/"static/app.js"
css_path=root/"static/style.css"
js=js_path.read_text(encoding="utf-8")
css=css_path.read_text(encoding="utf-8")

def swap_exact(s,old,new,label):
    n=s.count(old)
    if n!=1: raise RuntimeError("V32 "+label+": expected one exact anchor, found "+str(n))
    return s.replace(old,new,1)

# Native browser fullscreen displays only the selected top-layer subtree.
anchor="function attachCompactHover(node,m){"
helper="""// V32: mount compact hover details inside the fullscreen top layer.
function compactTooltipHost(node){
 const full=document.fullscreenElement;
 if(full&&full.contains(node))return full;
 const panel=fullscreenPanel();
 if(panel&&panel.classList.contains('fullscreen-fallback')&&panel.contains(node))return panel;
 return document.body;
}
"""
js=swap_exact(js,anchor,helper+anchor,"tooltip host")
old="compactTooltipEl.append(compactInfo(m));document.body.append(compactTooltipEl);moveCompactTooltip(e,node)"
new="compactTooltipEl.append(compactInfo(m));compactTooltipHost(node).append(compactTooltipEl);moveCompactTooltip(e,node)"
js=swap_exact(js,old,new,"mount inside fullscreen")
old="node.addEventListener('mousemove',e=>moveCompactTooltip(e,node));"
new="node.addEventListener('mousemove',e=>{if(!compactTooltipEl)show(e);else moveCompactTooltip(e,node)});"
js=swap_exact(js,old,new,"reopen tooltip after fullscreen transition")
old="document.addEventListener('fullscreenchange',()=>{refreshFullscreenButton();rescaleFullscreenBranch()});"
new="document.addEventListener('fullscreenchange',()=>{hideCompactTooltip();refreshFullscreenButton();rescaleFullscreenBranch()});"
js=swap_exact(js,old,new,"clean up on fullscreen transition")
css += """
/* V32: compact tooltip is a direct child of the fullscreen panel. */
.panel:fullscreen > .v28-compact-tooltip,
.panel.fullscreen-fallback > .v28-compact-tooltip {
 position:fixed!important;
 z-index:2147483647!important;
 pointer-events:none!important;
}
"""
js_path.write_text(js,encoding="utf-8")
css_path.write_text(css,encoding="utf-8")

(root/"tests/test_v32_fullscreen_hover.cjs").write_text(r'''const assert=require('node:assert/strict');
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
''',encoding="utf-8")
print("V32 applied: compact-tooltip DOM portal fix only; no API or database changes.")
