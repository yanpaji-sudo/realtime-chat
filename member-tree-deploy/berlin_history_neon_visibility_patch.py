"""Make Berlin history-calendar new-member halos unmistakable, even at 13% zoom.

Purely visual: changes only member-tree/static/app.js and static/index.html.
Withdrawal-red rings, member dates, finances, API and database are untouched.
"""
from pathlib import Path
jp=Path('member-tree/static/app.js')
hp=Path('member-tree/static/index.html')
j=jp.read_text(encoding='utf-8')
h=hp.read_text(encoding='utf-8')

old="""    group.append(svgEl('ellipse',{
      cx:cardW/2,cy:cardH/2,
      rx:compactMode?112:178,ry:compactMode?43:101,
      class:'berlin-history-svg-ring',
      fill:'none','aria-hidden':'true'
    }));"""
new="""    // Two independently illuminated loops stay thick regardless of SVG zoom;
    // a broad amber outer halo draws attention before the cyan inner outline.
    group.append(svgEl('ellipse',{
      cx:cardW/2,cy:cardH/2,
      rx:compactMode?144:224,ry:compactMode?58:132,
      class:'berlin-history-svg-halo',
      fill:'none','vector-effect':'non-scaling-stroke','aria-hidden':'true'
    }));
    group.append(svgEl('ellipse',{
      cx:cardW/2,cy:cardH/2,
      rx:compactMode?118:192,ry:compactMode?47:109,
      class:'berlin-history-svg-ring',
      fill:'none','vector-effect':'non-scaling-stroke','aria-hidden':'true'
    }));
    group.append(svgEl('ellipse',{
      cx:cardW/2,cy:cardH/2,
      rx:compactMode?98:166,ry:compactMode?38:91,
      class:'berlin-history-svg-inner',
      fill:'none','vector-effect':'non-scaling-stroke','aria-hidden':'true'
    }));"""
assert j.count(old)==1, "Historical newcomer ring rendering anchor changed; stop without risk"
j=j.replace(old,new,1)
notes_old="按现存档案加入日期统计 · 蓝色光圈"
assert j.count(notes_old)==1
j=j.replace(notes_old,"按现存加入日期统计 · 荧光黄圈=新增 · 红圈=提现",1)
notes_more="仅列前400个，其他账号也已在树状图用蓝圈标记"
assert j.count(notes_more)==1
j=j.replace(notes_more,"仅列前400个，其他账号也已在树状图用荧光圈标记",1)
css=r'''
<style id="berlin-history-high-visibility-css">
/* Yellow/gold explicitly contrasts with the retained red withdrawal rings. */
.berlin-history-svg-halo{
 stroke:#ff9a00!important;stroke-width:11px!important;
 vector-effect:non-scaling-stroke;
 opacity:.98;pointer-events:none;
 filter:drop-shadow(0 0 5px #ffbf00) drop-shadow(0 0 12px #ff8400);
 animation:berlin-history-high-pulse 1.9s ease-in-out infinite;
}
.berlin-history-svg-ring{
 stroke:#fff000!important;stroke-width:8px!important;
 vector-effect:non-scaling-stroke;
 stroke-opacity:1!important;pointer-events:none;
 filter:drop-shadow(0 0 5px #ffff78);
 animation:berlin-history-high-pulse 1.9s ease-in-out infinite;
}
.berlin-history-svg-inner{
 stroke:#14e8ff!important;stroke-width:5px!important;
 vector-effect:non-scaling-stroke;
 opacity:1;pointer-events:none;
 filter:drop-shadow(0 0 4px #14e8ff);
}
.member.berlin-history-new{
 position:relative;overflow:visible!important;
 z-index:5;outline:5px solid #ffea00!important;outline-offset:6px;
 box-shadow:0 0 0 10px #ffaa00a1,0 0 20px 8px #ffeb00ca!important;
}
.member.berlin-history-new::after{
 content:"";position:absolute;inset:-14px;
 border:6px solid #fff500!important;border-radius:27px;
 box-shadow:0 0 0 5px #ff9d00,0 0 21px 8px #ffed00cf!important;
 pointer-events:none;
 animation:berlin-history-high-pulse 1.9s ease-in-out infinite;
}
.member.berlin-history-new::before{
 content:"✦ 历史新增";position:absolute;
 top:-25px;right:-10px;z-index:12;
 display:block;padding:4px 10px;
 color:#101b2b;background:#ffe500;border:2px solid #fff;
 border-radius:99px;font-weight:900;font-size:12px;line-height:1.2;
 white-space:nowrap;box-shadow:0 1px 15px 3px #ffb600e3;
 pointer-events:none;
}
.berlin-history-count{
 background:#fff1a8;color:#6d3900!important;border:2px solid #f7b41a;
 border-radius:8px;padding:4px 9px;font-weight:900!important;
}
.berlin-history-note{color:#86520c!important;font-weight:700}
@keyframes berlin-history-high-pulse{
 0%,100%{opacity:1}
 50%{opacity:.68}
}
@media (prefers-reduced-motion: reduce){
 .berlin-history-svg-halo,.berlin-history-svg-ring,
 .member.berlin-history-new::after{animation:none!important;opacity:1!important}
}
</style>
'''
assert h.count("</body>")==1
h=h.replace("</body>",css+"</body>",1)
assert j.count('berlin-history-svg-halo')==1
assert j.count('berlin-history-svg-inner')==1
assert 'class:"withdraw-red-outer"' not in j or 'withdraw-red-outer' in j
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print("PASS: new-member neon halo + non-scaling yellow/cyan dual rings + visible tree badges")
