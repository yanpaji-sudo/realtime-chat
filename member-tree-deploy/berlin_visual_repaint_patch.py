"""Repair Berlin automatic SVG scan redraw and preserve scan position across refreshes.
Browser-only: no finance, member or backend code changes.
"""
from pathlib import Path
jp=Path('member-tree/static/app.js')
j=jp.read_text(encoding='utf-8')
def once(a,b):
 global j
 assert j.count(a)==1,(a[:100],j.count(a))
 j=j.replace(a,b,1)

# During every animation frame previous code canceled and rescheduled repaint.
# When the renderer has more than 800 members this meant draw() NEVER ran.
once("if(shownRows.length>800){clearTimeout(berlinPaintTimeout);berlinPaintTimeout=setTimeout(()=>{if(host.isConnected)draw()},90)}",
     "if(shownRows.length>550&&!berlinPaintTimeout){berlinPaintTimeout=setTimeout(()=>{berlinPaintTimeout=null;if(host.isConnected)draw()},110)}")
# Keep progress when periodic data refresh replaces the SVG.
once("let berlinVisionMode='off',berlinVisionCurrentStop=null,berlinVisionRank=0;",
     "let berlinVisionMode='off',berlinVisionCurrentStop=null,berlinVisionRank=0,berlinVisionTourResumeDy=null;")
once("berlinVisionMode='mode'","berlinVisionMode='mode'") if False else None
once("berlinVisionRank=0;berlinTourPaused=false;",
     "berlinVisionRank=0;berlinTourPaused=false;berlinVisionTourResumeDy=null;")
once("berlinVisionMode='off';\n  berlinTourPaused=false;",
     "berlinVisionMode='off';berlinVisionTourResumeDy=null;\n  berlinTourPaused=false;")
once("const endDy=Math.min(42,h-45-L.height*zoom);\n  draw();",
     "const endDy=Math.min(42,h-45-L.height*zoom);\n  if(berlinVisionTourResumeDy!==null)branchTransform.dy=Math.max(endDy,Math.min(42,berlinVisionTourResumeDy));\n  draw();")
once("branchTransform.dy=Math.max(endDy,branchTransform.dy-65*delta);\n   apply();",
     "branchTransform.dy=Math.max(endDy,branchTransform.dy-65*delta);\n   berlinVisionTourResumeDy=branchTransform.dy;\n   apply();")
once("branchTransform.dy=Math.max(endDy,branchTransform.dy-65*dt);\n     apply();",
     "branchTransform.dy=Math.max(endDy,branchTransform.dy-65*dt);\n     berlinVisionTourResumeDy=branchTransform.dy;\n     apply();")
assert "berlinPaintTimeout=setTimeout" in j
assert "berlinVisionTourResumeDy=branchTransform.dy" in j
jp.write_text(j,encoding='utf-8')
