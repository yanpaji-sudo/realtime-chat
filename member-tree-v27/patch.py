from pathlib import Path
root=Path("member-tree")
js_path=root/"static/app.js"
css_path=root/"static/style.css"
js=js_path.read_text(encoding="utf-8")
needle="group.append(svgEl('rect',{x:0,y:0,width:260,height:104,rx:12}));"
assert js.count(needle)==1, "branch SVG card location changed"
extra="""group.append(svgEl('rect',{x:0,y:0,width:260,height:104,rx:12}));
    // V27: Actual enlarged elliptical warning rings, not just a subtle card shadow.
    if(withdrawGlowOn&&Number(m.daily_withdraw_cents||0)!==0){
     group.append(svgEl('ellipse',{cx:130,cy:52,rx:156,ry:87,class:'withdraw-red-outer',fill:'none','aria-hidden':'true'}));
     group.append(svgEl('ellipse',{cx:130,cy:52,rx:149,ry:80,class:'withdraw-red-inner',fill:'none','aria-hidden':'true'}));
    }"""
js=js.replace(needle,extra)
changes=[
 ("⚡ 今日提现：","🔴 今日提现："),
 ("🔵 显示当日提现","🔴 显示当日提现"),
 ("蓝色光圈已显示今日有提现的会员","红色光圈已显示今日有提现的会员"),
 ("蓝色光圈：今日有提现的本人会员","红色光圈：今日有提现的本人会员"),
 ("'关闭提现光圈'","'关闭红色光圈'"),
]
for before,after in changes:
 assert js.count(before)==1,(before,js.count(before))
 js=js.replace(before,after)
js_path.write_text(js,encoding="utf-8")
css=css_path.read_text(encoding="utf-8")
assert "V27 VIVID RED WITHDRAWAL RINGS" not in css
css+="""
/* V27 VIVID RED WITHDRAWAL RINGS: intense solid red outlines plus large
   true elliptical light rings. Only nodes with nonzero own-day withdrawal get these classes. */
.branch-canvas .branch-node.branch-withdraw-glow>rect:not(.withdraw-red-outer):not(.withdraw-red-inner),
.branch-canvas.branch-risk-mode .branch-node.branch-withdraw-glow>rect:not(.withdraw-red-outer):not(.withdraw-red-inner){
 stroke:#ff002f!important;
 stroke-width:7px!important;
 filter:drop-shadow(0 0 4px #fff) drop-shadow(0 0 17px #ff002f) drop-shadow(0 0 35px #ff0000)!important;
 animation:v27-red-core 1.45s ease-in-out infinite!important;
}
.branch-canvas .branch-node.branch-withdraw-glow>ellipse.withdraw-red-outer{
 fill:none!important;
 stroke:#ff002f!important;
 stroke-width:9px!important;
 opacity:1!important;
 pointer-events:none!important;
 filter:drop-shadow(0 0 4px #fff) drop-shadow(0 0 16px #ff002f) drop-shadow(0 0 30px #f00000) drop-shadow(0 0 55px #ff1822)!important;
 animation:v27-red-ring 1.45s ease-in-out infinite!important;
}
.branch-canvas .branch-node.branch-withdraw-glow>ellipse.withdraw-red-inner{
 fill:none!important;
 stroke:#ffb9bf!important;
 stroke-width:3px!important;
 opacity:1!important;
 pointer-events:none!important;
 filter:drop-shadow(0 0 11px #ff002f)!important;
}
@keyframes v27-red-core{
 0%,100%{stroke:#ff0039;stroke-width:7px;opacity:1}
 50%{stroke:#ff5757;stroke-width:9px;opacity:1}
}
@keyframes v27-red-ring{
 0%,100%{stroke:#ff002f;stroke-width:9px;opacity:1}
 50%{stroke:#ff4242;stroke-width:12px;opacity:1}
}
.branch-canvas .branch-withdraw-badge rect{
 fill:#ec0025!important;stroke:#ffced3!important;stroke-width:2.5px!important;
 filter:drop-shadow(0 0 5px #ff002d) drop-shadow(0 0 13px #ff002f)!important;
}
.branch-canvas .branch-withdraw-badge text{
 fill:#ffffff!important;font-size:15px!important;font-weight:900!important;
}
.member.withdraw-glow{
 border:5px solid #ff002f!important;outline:5px solid #ff002f!important;
 outline-offset:5px!important;
 box-shadow:0 0 0 11px #ff003b88,0 0 29px #ff003b,0 0 60px #e70000!important;
 animation:v27-list-red 1.45s ease-in-out infinite!important;
}
@keyframes v27-list-red{
 0%,100%{box-shadow:0 0 0 11px #ff003b88,0 0 29px #ff003b,0 0 60px #e70000}
 50%{box-shadow:0 0 0 14px #ff003bd9,0 0 42px #ff003b,0 0 72px #e70000}
}
.withdraw-glow-amount{
 color:#fff!important;background:#e60022!important;border:2px solid #ffc7d0!important;
 font-size:18px!important;font-weight:900!important;
}
.branch-withdraw-cta{
 border-color:#ff2346!important;background:#fff0f2!important;color:#ba0020!important;font-weight:900!important;
}
@media(prefers-reduced-motion:reduce){
 .branch-canvas .branch-node.branch-withdraw-glow>rect,
 .branch-canvas .branch-node.branch-withdraw-glow>ellipse,
 .member.withdraw-glow {animation:none!important}
}
"""
css_path.write_text(css,encoding="utf-8")
tests=root/"tests/test_v27_red_withdrawal_ui.cjs"
tests.write_text("""const assert=require('node:assert/strict');
const fs=require('node:fs');
const js=fs.readFileSync('static/app.js','utf-8');
const css=fs.readFileSync('static/style.css','utf-8');
assert(js.includes("class:'withdraw-red-outer'"));
assert(js.includes("class:'withdraw-red-inner'"));
assert(js.includes("if(withdrawGlowOn&&Number(m.daily_withdraw_cents||0)!==0)"));
assert(js.includes("🔴 今日提现："));
assert(js.includes("🔴 显示当日提现"));
assert(css.includes('V27 VIVID RED WITHDRAWAL RINGS'));
assert(css.includes('ellipse.withdraw-red-outer'));
assert(css.includes('stroke:#ff002f!important'));
assert(css.includes('fill:#ec0025!important'));
console.log('V27 red withdrawal SVG, visual style and nonzero gating passed');
""",encoding='utf-8')
print("V27 red halo patch applied (member database untouched).")
