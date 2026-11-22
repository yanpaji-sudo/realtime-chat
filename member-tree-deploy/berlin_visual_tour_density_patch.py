"""Berlin SVG branch: automatic top-to-bottom survey and ranked withdrawal hotspots.

View-only: uses the already retrieved daily_withdraw_cents and branchLayout.
It does not create server endpoints or change ledger/member records.
"""
helper=r'''
function berlinRankWithdrawClusters(points,frameW,frameH,maxAreas=60){
 const sorted=points.filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y))
     .slice().sort((a,b)=>a.y-b.y||a.x-b.x);
 if(!sorted.length)return [];
 const halfW=frameW*.44,halfH=frameH*.44;
 let left=0,right=0;
 const candidates=[];
 for(const p of sorted){
  while(left<sorted.length&&sorted[left].y<p.y-halfH)left++;
  while(right<sorted.length&&sorted[right].y<=p.y+halfH)right++;
  let count=0,amount=0;
  for(let i=left;i<right;i++){
   const q=sorted[i];
   if(Math.abs(q.x-p.x)<=halfW){count++;amount+=Math.abs(q.amount||0)}
  }
  candidates.push({x:p.x,y:p.y,count,amount,account:p.account||''});
 }
 candidates.sort((a,b)=>b.count-a.count||b.amount-a.amount||a.y-b.y||a.x-b.x);
 const result=[];
 for(const c of candidates){
  if(result.some(prev=>Math.abs(prev.x-c.x)<frameW*.75&&Math.abs(prev.y-c.y)<frameH*.75))continue;
  result.push(c);
  if(result.length>=maxAreas)break;
 }
 return result;
}
let berlinVisionMode='off',berlinVisionCurrentStop=null,berlinVisionRank=0;
'''
assert j.count('function renderBranch(){')==1
j=j.replace('function renderBranch(){',helper+'\nfunction renderBranch(){',1)
# Recreated SVG hosts must never inherit a still-running animation.
anchor="function renderBranch(){\n const outer=mk('div','branch-view'"
assert j.count(anchor)==1
j=j.replace(anchor,"function renderBranch(){\n if(berlinVisionCurrentStop){berlinVisionCurrentStop();berlinVisionCurrentStop=null;}\n const outer=mk('div','branch-view'",1)

controls=r'''
 // On-screen visual modes use the same virtualized SVG viewport, with no network writes.
 let berlinFrame=0,berlinTourPaused=false,berlinClusters=[],berlinDensityScale=.45;
 const visualBar=mk('div','berlin-visual-toolbar');
 const visualTitle=mk('span','berlin-visual-title','分支巡览');
 const mkVisualButton=(txt,action)=>{
  const b=mk('button','berlin-visual-button',txt);b.type='button';
  b.onclick=e=>{e.stopPropagation();action()};visualBar.append(b);return b;
 };
 visualBar.append(visualTitle);
 const autoTourButton=mkVisualButton('▶ 自动浏览',()=>chooseVision('auto'));
 const densityButton=mkVisualButton('🔴 提现密度提醒',()=>chooseVision('density'));
 const prevAreaButton=mkVisualButton('← 上一处',()=>showArea(berlinVisionRank-1));
 const nextAreaButton=mkVisualButton('下一处 →',()=>showArea(berlinVisionRank+1));
 const pauseTourButton=mkVisualButton('⏸ 暂停',()=>toggleTourPause());
 const exitModeButton=mkVisualButton('✕ 退出模式',()=>leaveVision());
 const visualInfo=mk('span','berlin-visual-info','手动浏览');
 visualBar.append(visualInfo);
 host.append(visualBar);
 function stopVisionFrame(){
  if(berlinFrame){cancelAnimationFrame(berlinFrame);berlinFrame=0}
 }
 berlinVisionCurrentStop=stopVisionFrame;
 function updateVisionToolbar(){
  const auto=berlinVisionMode==='auto',density=berlinVisionMode==='density';
  autoTourButton.classList.toggle('is-active',auto);
  densityButton.classList.toggle('is-active',density);
  autoTourButton.setAttribute('aria-pressed',String(auto));
  densityButton.setAttribute('aria-pressed',String(density));
  prevAreaButton.hidden=!density;
  nextAreaButton.hidden=!density;
  pauseTourButton.hidden=!auto;
  exitModeButton.hidden=!(auto||density);
  pauseTourButton.textContent=berlinTourPaused?'▶ 继续':'⏸ 暂停';
  prevAreaButton.disabled=!density||berlinVisionRank<=0;
  nextAreaButton.disabled=!density||berlinVisionRank>=berlinClusters.length-1;
 }
 function leaveVision(){
  stopVisionFrame();
  berlinVisionMode='off';
  berlinTourPaused=false;
  visualInfo.textContent='手动浏览';
  updateVisionToolbar();
  persistTabView();
 }
 function chooseVision(mode){
  if(berlinVisionMode===mode){leaveVision();return}
  stopVisionFrame();
  berlinVisionMode=mode;
  berlinVisionRank=0;berlinTourPaused=false;
  // On a large tree the default initial fold hides many targets.
  // Expand in a view-only operation so clusters include all nodes.
  if(branchClosed.size){branchClosed.clear();berlinLayoutCache=null}
  if(!compactMode){
   compactMode=true;
   branchResetRequested=false;
   persistTabView();
   render(); // Recreate at compact dimensions before ranking / scanning.
   return;
  }
  if(mode==='auto')startAutoTour();else startDensitySurvey();
 }
 function startAutoTour(){
  stopVisionFrame();
  const L=getBerlinLayout();
  const w=Math.max(300,host.clientWidth||1000),h=Math.max(320,host.clientHeight||580);
  const zoom=.13; // Existing branch minimum scale, independent of membership count.
  branchTransform.scale=zoom;
  branchTransform.dx=Math.max(12,(w-L.width*zoom)/2);
  branchTransform.dy=42;
  branchViewportReady=true;branchResetRequested=false;
  const endDy=Math.min(42,h-45-L.height*zoom);
  draw();
  berlinTourPaused=false;
  visualInfo.textContent='最小化 · 由上向下 · 自动巡览';
  updateVisionToolbar();
  persistTabView();
  if(endDy>=42){
   berlinTourPaused=true;
   visualInfo.textContent='全部节点已在一屏内';
   updateVisionToolbar();return;
  }
  let previous=0;
  const step=(stamp)=>{
   if(!host.isConnected||berlinVisionMode!=='auto'){stopVisionFrame();return}
   if(berlinTourPaused){previous=stamp;berlinFrame=requestAnimationFrame(step);return}
   const delta=previous?Math.min((stamp-previous)/1000,.15):0;
   previous=stamp;
   branchTransform.dy=Math.max(endDy,branchTransform.dy-65*delta);
   apply(); // virtualization repaint throttled by the existing branch renderer.
   if(branchTransform.dy<=endDy+.01){
    stopVisionFrame();berlinTourPaused=true;
    visualInfo.textContent='已浏览到底部';
    updateVisionToolbar();persistTabView();return;
   }
   berlinFrame=requestAnimationFrame(step);
  };
  berlinFrame=requestAnimationFrame(step);
 }
 function toggleTourPause(){
  if(berlinVisionMode!=='auto')return;
  berlinTourPaused=!berlinTourPaused;
  if(!berlinTourPaused){
   // Restart from current position, not from the beginning.
   stopVisionFrame();
   const L=getBerlinLayout(),h=Math.max(320,host.clientHeight||580);
   const endDy=Math.min(42,h-45-L.height*branchTransform.scale);
   let previous=0;
   const tick=stamp=>{
    if(!host.isConnected||berlinVisionMode!=='auto'){stopVisionFrame();return}
    if(!berlinTourPaused){
     const dt=previous?Math.min((stamp-previous)/1000,.15):0;
     branchTransform.dy=Math.max(endDy,branchTransform.dy-65*dt);
     apply();
     if(branchTransform.dy<=endDy+.01){
      stopVisionFrame();berlinTourPaused=true;visualInfo.textContent='已浏览到底部';
      updateVisionToolbar();persistTabView();return;
     }
    }
    previous=stamp;berlinFrame=requestAnimationFrame(tick);
   };
   berlinFrame=requestAnimationFrame(tick);
   visualInfo.textContent='继续从上往下巡览';
  }else{
   stopVisionFrame();
   visualInfo.textContent='自动浏览已暂停';
   persistTabView();
  }
  updateVisionToolbar();
 }
 function showArea(index){
  if(berlinVisionMode!=='density'||!berlinClusters.length)return;
  berlinVisionRank=Math.max(0,Math.min(berlinClusters.length-1,index));
  const spot=berlinClusters[berlinVisionRank];
  const w=Math.max(300,host.clientWidth||1000),h=Math.max(320,host.clientHeight||580);
  branchTransform.scale=berlinDensityScale;
  branchTransform.dx=w/2-(spot.x+(compactMode?76:130))*berlinDensityScale;
  branchTransform.dy=h/2-spot.y*berlinDensityScale;
  branchViewportReady=true;branchResetRequested=false;
  draw();persistTabView();
  visualInfo.textContent='密度第 '+(berlinVisionRank+1)+' / '+berlinClusters.length+
    ' 处 · 本屏红圈约 '+spot.count+' 位';
  updateVisionToolbar();
 }
 function startDensitySurvey(){
  stopVisionFrame();
  withdrawGlowOn=true; // Density mode automatically reveals the existing red rings.
  const glowButton=el('withdrawTreeBtn');
  if(glowButton){glowButton.textContent='关闭红色光圈';glowButton.setAttribute('aria-pressed','true')}
  const L=getBerlinLayout();
  const w=Math.max(300,host.clientWidth||1000),h=Math.max(320,host.clientHeight||580);
  berlinDensityScale=Math.min(.85,Math.max(.26,h/(compactMode?1330:2380)));
  const red=shownRows.filter(m=>Number(m.daily_withdraw_cents||0)!==0)
   .map(m=>{const p=L.positions.get(m.id);return p?{x:p.x,y:p.y,amount:Number(m.daily_withdraw_cents||0),account:m.account}:null})
   .filter(Boolean);
  berlinClusters=berlinRankWithdrawClusters(red,w/berlinDensityScale,h/berlinDensityScale,60);
  berlinVisionRank=0;
  if(berlinClusters.length)showArea(0);
  else{
   visualInfo.textContent='当前范围没有当日提现红圈';
   draw();updateVisionToolbar();
  }
 }
 // Dragging/zooming manually should not compete with automatic vertical panning.
 const userInteraction=()=>{
  if(berlinVisionMode==='auto')leaveVision();
 };
 svg.addEventListener('pointerdown',userInteraction,{capture:true});
 host.addEventListener('wheel',userInteraction,{capture:true});
 updateVisionToolbar();
'''
anchor=" branchViewportControls={zoomIn:()=>zoom(1.28)"
assert j.count(anchor)==1,'branch control anchor missing'
j=j.replace(anchor,controls+anchor,1)
# Start mode after host connected and the original reset/target navigation runs.
anchor="  if(branchFocusRequested){branchFocusRequested=false;focusTarget()}\n });return outer"
assert j.count(anchor)==1,'branch first render animation anchor missing'
j=j.replace(anchor,"  if(branchFocusRequested){branchFocusRequested=false;focusTarget()}\n  if(berlinVisionMode==='auto')startAutoTour();\n  else if(berlinVisionMode==='density')startDensitySurvey();\n });return outer",1)
# Leaving branch view stops the animation and preserves user's current dataset.
render_anchor="function render(){"
assert j.count(render_anchor)==1
j=j.replace(render_anchor,"function render(){\n if(view!=='branch'&&berlinVisionCurrentStop){berlinVisionCurrentStop();berlinVisionCurrentStop=null;berlinVisionMode='off'}",1)
css=r'''
<style id="berlin-vision-css">
.branch-canvas{position:relative}
.berlin-visual-toolbar{position:absolute;top:12px;right:12px;z-index:33;
 background:rgba(16,24,29,.93);border:1px solid #58717b;border-radius:12px;
 display:flex;flex-wrap:wrap;gap:6px;align-items:center;max-width:min(92%,790px);
 padding:9px 10px;color:#e9f6f3;box-shadow:0 6px 20px #0008}
.berlin-visual-title{font-size:12px;letter-spacing:.06em;font-weight:700;
 color:#bcebd1;margin-right:4px}
.berlin-visual-button{border:1px solid #576b76;background:#263840;color:#e9f6f3;
 border-radius:7px;font-size:12px;line-height:1.3;padding:7px 9px;cursor:pointer}
.berlin-visual-button:hover{background:#36515c}
.berlin-visual-button.is-active{background:#147d64;color:white;border-color:#24b58a}
.berlin-visual-button:disabled{opacity:.38;cursor:not-allowed}
.berlin-visual-info{font-size:12px;color:#f9d3b1;white-space:nowrap}
@media(max-width:650px){
 .berlin-visual-toolbar{top:5px;right:5px;left:5px;max-width:initial;gap:4px;padding:6px}
 .berlin-visual-button{padding:5px;font-size:11px}
 .berlin-visual-info{white-space:normal}
}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count('function berlinRankWithdrawClusters(')==1
assert "if(berlinVisionMode==='auto')startAutoTour()" in j
assert "current_day()" not in helper
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
