"""V22 Free-server view-only SVG performance repair and two巡览 modes.

Apply to the exact production archive's original JS + HTML.
No backend, SQL, credentials, roster, or transaction changes.
"""
from pathlib import Path
jpath=Path('member-tree/static/app.js')
hpath=Path('member-tree/static/index.html')
j=jpath.read_text(encoding='utf-8')
h=hpath.read_text(encoding='utf-8')
def once(old,new):
    global j
    count=j.count(old)
    assert count==1,(f'V22 visual source changed: expected one anchor, got {count}',old[:100])
    j=j.replace(old,new,1)

helper=r"""
// V22 visual-only navigation: count red withdrawal rings in a fixed viewport.
function v22RankWithdrawalAreas(points,screenW,screenH){
 const sorted=points.filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)).slice()
  .sort((a,b)=>a.y-b.y||a.x-b.x);
 if(!sorted.length)return [];
 const windowX=screenW*.45,windowY=screenH*.45;
 let start=0,end=0;
 const buckets=[];
 for(const p of sorted){
  while(start<sorted.length&&sorted[start].y<p.y-windowY)start++;
  while(end<sorted.length&&sorted[end].y<=p.y+windowY)end++;
  let count=0,amount=0;
  for(let k=start;k<end;k++){
   const q=sorted[k];
   if(Math.abs(p.x-q.x)>windowX)continue;
   count++;amount+=Math.abs(q.amount||0);
  }
  buckets.push({x:p.x,y:p.y,count,amount});
 }
 buckets.sort((a,b)=>b.count-a.count||b.amount-a.amount||a.y-b.y||a.x-b.x);
 const distinct=[];
 for(const x of buckets){
  if(distinct.some(p=>Math.abs(p.x-x.x)<=screenW*.72&&Math.abs(p.y-x.y)<=screenH*.72))continue;
  distinct.push(x);
  if(distinct.length>=60)break;
 }
 return distinct;
}
let v22VisionMode='off',v22VisionStop=null,v22VisionIndex=0,v22TourResumeY=null;
"""
once("function renderBranch(){",helper+"\nfunction renderBranch(){\n if(v22VisionStop){v22VisionStop();v22VisionStop=null;}")
old=""" const shownRows=teamFocusId?teamExportRows(teamFocusId):shownTreeMembers();"""
new=""" const shownRows=teamFocusId?teamExportRows(teamFocusId):shownTreeMembers();
 // 10k+ nodes previously built an entire SVG in every redraw, freezing on scroll.
 // Cache a single layout per mounted canvas, paint only in-view nodes and edges.
 let cachedLayout=null,paintTimer=null,visionFrame=0;
 const getLayout=()=>cachedLayout||(cachedLayout=branchLayout(shownRows,branchClosed));
 const isVirtual=shownRows.length>550;
 const parentIds=new Set(shownRows.map(x=>x.parent_id).filter(Boolean));
"""
once(old,new)
old=""" function draw(){
  const L=branchLayout(shownRows,branchClosed);const cardW=compactMode?152:260,cardH=compactMode?44:104;svg.setAttribute('viewBox',\`0 0 \${Math.max(300,host.clientWidth||1100)} \${Math.max(320,host.clientHeight||590)}\`);viewport.replaceChildren();"""
new=""" function draw(){
  if(!host.isConnected)return;
  const L=getLayout(),cardW=compactMode?152:260,cardH=compactMode?44:104;
  const W=Math.max(300,host.clientWidth||1100),H=Math.max(320,host.clientHeight||590),s=branchTransform.scale;
  const margin=180;
  const visible=p=>!isVirtual||(p&&(p.x+cardW)*s+branchTransform.dx>=-margin&&
   p.x*s+branchTransform.dx<=W+margin&&(p.y+cardH/2)*s+branchTransform.dy>=-margin&&
   (p.y-cardH/2)*s+branchTransform.dy<=H+margin);
  svg.setAttribute('viewBox',\`0 0 \${W} \${H}\`);viewport.replaceChildren();"""
once(old,new)
old="""  for(const [a,b]of L.edges){const p=L.positions.get(a),q=L.positions.get(b),start=p.x+cardW,end=q.x;
   const d="""
new="""  for(const [a,b]of L.edges){const p=L.positions.get(a),q=L.positions.get(b);
   if(isVirtual&&!visible(p)&&!visible(q))continue;
   const start=p.x+cardW,end=q.x;
   const d="""
once(old,new)
once("const highlight=branchSelectedAccount,day=businessDay||dateNow(),parentIds=new Set(shownRows.map(x=>x.parent_id).filter(Boolean));",
     "const highlight=branchSelectedAccount,day=businessDay||dateNow();")
once("for(const m of shownRows){const pos=L.positions.get(m.id);if(!pos)continue;",
     "for(const m of shownRows){const pos=L.positions.get(m.id);if(!pos||!visible(pos))continue;")
once("function fold(){branchClosed.has(m.id)?branchClosed.delete(m.id):branchClosed.add(m.id);draw();persistTabView()}",
     "function fold(){branchClosed.has(m.id)?branchClosed.delete(m.id):branchClosed.add(m.id);cachedLayout=null;draw();persistTabView()}")
once("function apply(){viewport.setAttribute('transform',\`translate(\${branchTransform.dx},\${branchTransform.dy}) scale(\${branchTransform.scale})\`)}",
     """function apply(){
  viewport.setAttribute('transform',\`translate(\${branchTransform.dx},\${branchTransform.dy}) scale(\${branchTransform.scale})\`);
  if(isVirtual&&!paintTimer){
   paintTimer=setTimeout(()=>{paintTimer=null;if(host.isConnected)draw()},110);
  }
 }""")
once("function reset(){const L=branchLayout(shownRows,branchClosed);",
     "function reset(){const L=getLayout();")
once("const layout=branchLayout(shownRows,branchClosed),p=layout.positions.get(selected.id);",
     "const layout=getLayout(),p=layout.positions.get(selected.id);")
once("expand:()=>{branchClosed.clear();reset()}",
     "expand:()=>{branchClosed.clear();cachedLayout=null;reset()}")

vision=r"""
 // Mode controls are local to each SVG host; no mutations or API calls.
 let surveyPaused=false,surveyAreas=[],surveyScale=.42;
 const bar=mk('div','v22-visual-toolbar');
 const label=mk('span','v22-visual-label','分支巡视');
 bar.append(label);
 const visualButton=(caption,handler)=>{
  const b=mk('button','v22-visual-button',caption);
  b.type='button';b.onclick=ev=>{ev.preventDefault();ev.stopPropagation();handler()};
  bar.append(b);return b;
 };
 const autoBtn=visualButton('▶ 自动巡视',()=>changeVision('auto'));
 const densityBtn=visualButton('🔴 爆红密度',()=>changeVision('density'));
 const prevBtn=visualButton('← 上一处',()=>showSurvey(v22VisionIndex-1));
 const nextBtn=visualButton('下一处 →',()=>showSurvey(v22VisionIndex+1));
 const pauseBtn=visualButton('⏸ 暂停',()=>{surveyPaused=!surveyPaused;updateBar()});
 const exitBtn=visualButton('✕ 退出',()=>exitVision());
 const summary=mk('span','v22-visual-summary','可拖拽和滚轮缩放');
 bar.append(summary);host.append(bar);
 function stopFrames(){
  if(visionFrame)cancelAnimationFrame(visionFrame);
  visionFrame=0;
  if(paintTimer)clearTimeout(paintTimer);
  paintTimer=null;
 }
 v22VisionStop=stopFrames;
 function updateBar(){
  const auto=v22VisionMode==='auto',density=v22VisionMode==='density';
  autoBtn.classList.toggle('active',auto);densityBtn.classList.toggle('active',density);
  autoBtn.setAttribute('aria-pressed',String(auto));
  densityBtn.setAttribute('aria-pressed',String(density));
  prevBtn.hidden=nextBtn.hidden=!density;
  pauseBtn.hidden=!auto;exitBtn.hidden=!(auto||density);
  pauseBtn.textContent=surveyPaused?'▶ 继续':'⏸ 暂停';
  prevBtn.disabled=!density||v22VisionIndex===0;
  nextBtn.disabled=!density||v22VisionIndex>=surveyAreas.length-1;
 }
 function exitVision(){
  stopFrames();v22VisionMode='off';v22TourResumeY=null;
  surveyPaused=false;summary.textContent='可拖拽和滚轮缩放';
  updateBar();persistTabView();
 }
 function changeVision(mode){
  if(mode===v22VisionMode){exitVision();return}
  stopFrames();v22VisionMode=mode;v22VisionIndex=0;v22TourResumeY=null;
  surveyPaused=false;
  if(branchClosed.size){branchClosed.clear();cachedLayout=null}
  // Compact cards keep the viewport usable when scanning a very large tree.
  if(!compactMode){
   compactMode=true;persistTabView();render();return;
  }
  if(mode==='auto')startTour();else startDensity();
 }
 function startTour(){
  stopFrames();
  const L=getLayout(),W=Math.max(300,host.clientWidth||1000),H=Math.max(320,host.clientHeight||580);
  const scale=.13;
  const upper=45,lower=Math.min(upper,H-55-L.height*scale);
  branchTransform.scale=scale;
  branchTransform.dx=Math.max(12,(W-L.width*scale)/2);
  branchTransform.dy=v22TourResumeY===null?upper:Math.max(lower,Math.min(upper,v22TourResumeY));
  branchViewportReady=true;branchResetRequested=false;
  draw();updateBar();summary.textContent='最小比例 · 自上向下巡视';
  if(lower>=upper-.1){summary.textContent='整棵树已显示在一屏内';return}
  let last=0;
  function step(now){
   if(!host.isConnected||v22VisionMode!=='auto'){stopFrames();return}
   const dt=last?Math.min(.2,(now-last)/1000):0;
   last=now;
   if(!surveyPaused){
    branchTransform.dy=Math.max(lower,branchTransform.dy-75*dt);
    v22TourResumeY=branchTransform.dy;
    apply(); // Visible SVG nodes are repainted as the viewport moves.
    if(branchTransform.dy<=lower+.1){
     summary.textContent='巡视到底部';
     surveyPaused=true;updateBar();
     stopFrames();persistTabView();return;
    }
   }
   visionFrame=requestAnimationFrame(step);
  }
  visionFrame=requestAnimationFrame(step);
 }
 function showSurvey(index){
  if(v22VisionMode!=='density'||!surveyAreas.length)return;
  v22VisionIndex=Math.max(0,Math.min(surveyAreas.length-1,index));
  const pos=surveyAreas[v22VisionIndex];
  const W=Math.max(300,host.clientWidth||1000),H=Math.max(320,host.clientHeight||580);
  branchTransform.scale=surveyScale;
  branchTransform.dx=W/2-pos.x*surveyScale;
  branchTransform.dy=H/2-pos.y*surveyScale;
  branchViewportReady=true;branchResetRequested=false;
  draw();persistTabView();
  summary.textContent='密度第 '+(v22VisionIndex+1)+' / '+surveyAreas.length+
   ' 处 · 本屏红圈 '+pos.count+' 个';
  updateBar();
 }
 function startDensity(){
  stopFrames();withdrawGlowOn=true;
  const ctrl=el('withdrawTreeBtn');
  if(ctrl){ctrl.textContent='关闭红色光圈';ctrl.setAttribute('aria-pressed','true')}
  const L=getLayout();
  const W=Math.max(300,host.clientWidth||1000),H=Math.max(320,host.clientHeight||580);
  surveyScale=Math.max(.28,Math.min(.85,H/1350));
  const red=shownRows.filter(x=>Number(x.daily_withdraw_cents||0)!==0)
   .map(x=>{const p=L.positions.get(x.id);
     return p?{x:p.x+(compactMode?76:130),y:p.y,amount:Number(x.daily_withdraw_cents||0)}:null})
   .filter(Boolean);
  surveyAreas=v22RankWithdrawalAreas(red,W/surveyScale,H/surveyScale);
  if(surveyAreas.length)showSurvey(Math.min(v22VisionIndex,surveyAreas.length-1));
  else{summary.textContent='目前没有当日提现红圈';draw();updateBar()}
 }
 // Manual interaction wins over automatic scanning.
 svg.addEventListener('pointerdown',()=>{if(v22VisionMode==='auto')exitVision()},{capture:true});
 host.addEventListener('wheel',()=>{if(v22VisionMode==='auto')exitVision()},{capture:true});
 updateBar();
"""
once(" branchViewportControls={zoomIn:()=>zoom(1.28)",vision+"\n branchViewportControls={zoomIn:()=>zoom(1.28)")
once("  if(branchFocusRequested){branchFocusRequested=false;focusTarget()}\n });return outer",
     "  if(branchFocusRequested){branchFocusRequested=false;focusTarget()}\n  if(v22VisionMode==='auto')startTour();\n  else if(v22VisionMode==='density')startDensity();\n });return outer")
# Any tab changes cancel the rAF loop instead of animating a detached SVG.
once("function render(){if(!role)return;",
     "function render(){if(view!=='branch'&&v22VisionStop){v22VisionStop();v22VisionStop=null;v22VisionMode='off';v22TourResumeY=null}if(!role)return;")

css=r"""
<style id="v22-visual-performance">
.branch-canvas{position:relative}
.v22-visual-toolbar{position:absolute;top:10px;right:10px;z-index:34;
 background:rgba(14,23,29,.94);border:1px solid #566a70;border-radius:11px;
 color:#e6f3ef;display:flex;align-items:center;flex-wrap:wrap;gap:5px;
 max-width:min(96%,800px);padding:8px;box-shadow:0 6px 18px #0008}
.v22-visual-label{color:#b4efd7;font-size:12px;font-weight:700;padding-right:5px}
.v22-visual-button{font-size:12px;line-height:1.35;cursor:pointer;border:1px solid #637983;
 border-radius:7px;background:#243842;color:#f5fbfb;padding:7px 9px}
.v22-visual-button:hover{background:#395361}
.v22-visual-button.active{background:#16765f;border-color:#26b587}
.v22-visual-button:disabled{opacity:.4;cursor:not-allowed}
.v22-visual-summary{font-size:12px;color:#ffdcac}
@media(max-width:700px){.v22-visual-toolbar{top:4px;left:4px;right:4px;max-width:none}
 .v22-visual-button{padding:5px;font-size:11px}}
</style>
"""
assert h.count("</body>")==1
h=h.replace("</body>",css+"</body>",1)
assert "v22RankWithdrawalAreas" in j
assert "function startTour()" in j and "function startDensity()" in j
assert "if(!pos||!visible(pos))continue" in j
assert j.count("function renderBranch(){")==1
jpath.write_text(j,encoding='utf-8')
hpath.write_text(h,encoding='utf-8')
print("V22 view-only patch:",len(j),"JS chars, original production backend untouched")
