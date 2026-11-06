from pathlib import Path
root=Path("member-tree")
p=root/"static/app.js"; js=p.read_text()
h=root/"static/index.html"; html=h.read_text()
c=root/"static/style.css"; css=c.read_text()
def rep(s,a,b,label):
 n=s.count(a)
 if n!=1:raise RuntimeError(label+" expected once, found "+str(n))
 return s.replace(a,b,1)

js=rep(js,"const savedTabView=restoreTabView();","const savedTabView=restoreTabView();\nlet compactMode=Boolean(savedTabView.compactMode);","state")
js=rep(js,"JSON.stringify({group:selectedTreeGroup,treeVertical,branchVertical,","JSON.stringify({group:selectedTreeGroup,treeVertical,branchVertical,compactMode,","persist")
helper="""
// V28 read-only compact hover popover; preserves all original member fields.
let compactTooltipEl=null;
function hideCompactTooltip(){if(compactTooltipEl){compactTooltipEl.remove();compactTooltipEl=null}}
function compactInfo(m){
 const wrap=mk('div','v28-pop-body');
 wrap.append(mk('h3','v28-pop-title',m.account+' · 全部个人和团队数据'));
 const facts=mk('div','v28-pop-facts');
 const parent=members.find(x=>x.id===m.parent_id);
 for(const entry of [['会员账号',m.account],['加入日期',m.joined_on||'—'],
 ['所在层级','第'+(m.level||1)+'层'],['所属小组',m.group_account||'—'],
 ['上级账号',parent?parent.account:'根节点'],['备注',m.remark||'无'],
 ['直属下级',m.direct_count||0],['全部下级',m.descendant_count||0]]){
 facts.append(mk('span','',entry[0]),mk('b','',String(entry[1])));
 }
 wrap.append(facts);
 const day=businessDay||dateNow(),children=new Map();
 for(const x of members){const a=children.get(x.parent_id)||[];a.push(x);children.set(x.parent_id,a)}
 const direct=children.get(m.id)||[],todo=[m],seen=new Set();
 let newCount=0;
 while(todo.length){const x=todo.pop();if(seen.has(x.id))continue;seen.add(x.id);
  if(x.joined_on===day)newCount++;
  for(const y of children.get(x.id)||[])todo.push(y)}
 wrap.append(mk('p','v28-pop-new','今日新增：本人 '+(m.joined_on===day?1:0)+' · 直属 '+direct.filter(x=>x.joined_on===day).length+' · 团队 '+newCount));
 const tbl=mk('table','v28-pop-table'),head=mk('tr');
 for(const k of ['指标','本人','直属汇总','团队所有层级'])head.append(mk('th','',k));
 tbl.append(head);
 for(const spec of [
 ['建仓资金','stake_cents','direct_stake_cents','subtree_stake_cents'],
 ['当前余额','balance_cents','direct_balance_cents','subtree_balance_cents'],
 ['累计提现','total_withdraw_cents','direct_total_withdraw_cents','subtree_total_withdraw_cents'],
 ['当日提现','daily_withdraw_cents','direct_daily_withdraw_cents','subtree_daily_withdraw_cents'],
 ['输赢（建仓－总提现）','profit_cents','direct_profit_cents','subtree_profit_cents']
 ]){
  const row=mk('tr');row.append(mk('td','',spec[0]));
  for(const key of spec.slice(1))row.append(mk('td','',money(Number(m[key]||0),true)));
  tbl.append(row)
 }
 wrap.append(tbl);
 const risk=riskForMember(m);
 wrap.append(mk('p','v28-pop-risk','团队风险：'+risk.label+'，收益/余额 '+(risk.pct===null?'不可计算':risk.pct.toFixed(2)+'%')));
 wrap.append(mk('small','v28-pop-help','完整编辑和逐层导出请切换回完整版；分支图点击会员可打开详细页面。'));
 return wrap;
}
function moveCompactTooltip(e,node){
 if(!compactTooltipEl)return;
 const r=node.getBoundingClientRect(),w=compactTooltipEl.offsetWidth||420,h=compactTooltipEl.offsetHeight||330;
 const x=e&&Number.isFinite(e.clientX)?e.clientX:r.right;
 const y=e&&Number.isFinite(e.clientY)?e.clientY:r.top;
 let left=x+12,top=y+12;
 if(left+w>window.innerWidth-8)left=x-w-14;
 if(top+h>window.innerHeight-8)top=y-h-14;
 compactTooltipEl.style.left=Math.max(7,Math.min(Math.max(7,window.innerWidth-w-7),left))+'px';
 compactTooltipEl.style.top=Math.max(7,Math.min(Math.max(7,window.innerHeight-h-7),top))+'px';
}
function attachCompactHover(node,m){
 const show=e=>{hideCompactTooltip();compactTooltipEl=mk('div','v28-compact-tooltip');compactTooltipEl.setAttribute('role','tooltip');compactTooltipEl.append(compactInfo(m));document.body.append(compactTooltipEl);moveCompactTooltip(e,node)};
 node.addEventListener('mouseenter',show);
 node.addEventListener('mousemove',e=>moveCompactTooltip(e,node));
 node.addEventListener('mouseleave',hideCompactTooltip);
 node.addEventListener('focus',()=>show(null));
 node.addEventListener('blur',hideCompactTooltip);
}
function toggleCompactTree(){
 compactMode=!compactMode;hideCompactTooltip();
 branchViewportReady=false;branchResetRequested=true;
 persistTabView();render();
 showToast(compactMode?'简洁版已开启：悬停会员可查看全部个人与团队数据':'已恢复完整版');
}
"""
js=rep(js,"function nodeCard(x,isRoot,newByNode,day,summaryByNode){",helper+"\nfunction nodeCard(x,isRoot,newByNode,day,summaryByNode){","helpers")
tiny="""if(compactMode&&view==='tree'){
  card.classList.add('v28-member-mini');card.tabIndex=0;card.title='';
  card.append(mk('b','v28-mini-account',x.account),mk('small','v28-mini-date',x.joined_on||'—'));
  if(x.direct_count){
   const btn=mk('button','v28-mini-fold',collapsed.has(x.id)&&!query?'+':'−');
   btn.type='button';btn.title=collapsed.has(x.id)?'展开下级':'收起下级';btn.setAttribute('aria-label',btn.title);
   btn.onclick=e=>{e.stopPropagation();collapsed.has(x.id)?collapsed.delete(x.id):collapsed.add(x.id);hideCompactTooltip();persistTabView();render()};
   card.append(btn);
  }
  attachCompactHover(card,x);li.append(card);return li
 }
 const head=mk('div','member-top'),iden=mk('div','account');"""
js=rep(js,"const head=mk('div','member-top'),iden=mk('div','account');",tiny,"dom tiny")
js=rep(js,"'tree-main'+(riskMode?' tree-risk-mode':'')","'tree-main'+(riskMode?' tree-risk-mode':'')+(compactMode?' v28-compact':'')","tree class")
js=rep(js,"const positions=new Map();let nextLeaf=0,maxDepth=0;","const positions=new Map();let nextLeaf=0,maxDepth=0;const gapY=compactMode?64:139,gapX=compactMode?186:368,offsetX=compactMode?20:52,offsetY=compactMode?40:72;","layout")
js=rep(js,"y=nextLeaf*139+72;nextLeaf++","y=nextLeaf*gapY+offsetY;nextLeaf++","leaf y")
js=rep(js,"nextLeaf++*139+72","nextLeaf++*gapY+offsetY","fallback y")
js=rep(js,"x:depth*368+52","x:depth*gapX+offsetX","node x")
js=rep(js,"width:Math.max(720,(maxDepth+1)*368+150),height:Math.max(350,nextLeaf*139+150)","width:Math.max(320,(maxDepth+1)*gapX+(compactMode?35:150)),height:Math.max(220,nextLeaf*gapY+(compactMode?50:150))","layout size")
js=rep(js,"const outer=mk('div','branch-view');","const outer=mk('div','branch-view'+(compactMode?' v28-compact':''));","branch wrapper")
js=rep(js,"const host=mk('div','branch-canvas'+(riskMode?' branch-risk-mode':''));","const host=mk('div','branch-canvas'+(riskMode?' branch-risk-mode':'')+(compactMode?' v28-branch-compact':''));","branch host")
js=rep(js,"const L=branchLayout(shownRows,branchClosed);svg.setAttribute('viewBox',","const L=branchLayout(shownRows,branchClosed);const cardW=compactMode?152:260,cardH=compactMode?44:104;svg.setAttribute('viewBox',","card size")
js=rep(js,"start=p.x+260,end=q.x","start=p.x+cardW,end=q.x","edges")
js=rep(js,"const d=","const bend=compactMode?17:65;const d=","edge bend declaration") if False else js
# Change Bézier spacing only at its source; retain the existing template literal.
js=rep(js,"start+65","start+(compactMode?17:65)","edge bend 1")
js=rep(js,"end-65","end-(compactMode?17:65)","edge bend 2")
js=rep(js,"pos.y-52","pos.y-cardH/2","node center")
js=rep(js,"group.append(svgEl('rect',{x:0,y:0,width:260,height:104,rx:12}));","group.append(svgEl('rect',{x:0,y:0,width:cardW,height:cardH,rx:compactMode?7:12}));if(compactMode)attachCompactHover(group,m);","tiny rect")
js=rep(js,"cx:130,cy:52,rx:156,ry:87","cx:cardW/2,cy:cardH/2,rx:compactMode?94:156,ry:compactMode?34:87","outer ring")
js=rep(js,"cx:130,cy:52,rx:149,ry:80","cx:cardW/2,cy:cardH/2,rx:compactMode?88:149,ry:compactMode?29:80","inner ring")
anchor="group.append(svgEl('text',{x:13,y:18,class:'branch-date'}"
prepend="""if(compactMode){
     group.append(svgEl('text',{x:8,y:16,class:'branch-name v28-mini-name'},m.account.length>19?m.account.slice(0,18)+'…':m.account));
     group.append(svgEl('text',{x:8,y:34,class:'branch-date v28-mini-joined'},m.joined_on||'—'));
    }else{
    group.append(svgEl('text',{x:13,y:18,class:'branch-date'}"""
js=rep(js,anchor,prepend,"tiny text start")
js=rep(js,"if(withdrawGlowOn&&Number(m.daily_withdraw_cents||0)!==0){\n     const amount=svgEl","}\n    if(!compactMode&&withdrawGlowOn&&Number(m.daily_withdraw_cents||0)!==0){\n     const amount=svgEl","tiny text end hide badge")
js=rep(js,"if(role==='admin'){\n     const editor=svgEl","if(!compactMode&&role==='admin'){\n     const editor=svgEl","hide edit")
js=rep(js,"cx:260,cy:51,r:12,class:'branch-toggle'","cx:cardW,cy:cardH/2,r:compactMode?8:12,class:'branch-toggle'","fold circle")
js=rep(js,"x:260,y:57,'text-anchor':'middle',class:'branch-toggle-label'","x:cardW,y:cardH/2+(compactMode?3:6),'text-anchor':'middle',class:'branch-toggle-label'","fold label")
js=rep(js,"(w-48)/310","(w-48)/(compactMode?200:310)","focus width")
js=rep(js,"(h-50)/170","(h-50)/(compactMode?95:170)","focus height")
js=rep(js,"(p.x+130)","(p.x+(compactMode?76:130))","focus center")
js=rep(js,"el('aiTreeBtn').classList.toggle('hidden',!['tree','branch'].includes(view));","el('aiTreeBtn').classList.toggle('hidden',!['tree','branch'].includes(view));el('compactTreeBtn').classList.toggle('hidden',!['tree','branch'].includes(view));el('compactTreeBtn').textContent=compactMode?'▣ 完整版':'▦ 简洁版';el('compactTreeBtn').setAttribute('aria-pressed',String(compactMode));","button state")
js=rep(js,"const preserveScrollX=c.scrollLeft,preserveScrollY=c.scrollTop;","hideCompactTooltip();const preserveScrollX=c.scrollLeft,preserveScrollY=c.scrollTop;","cleanup")
js=rep(js,"el('withdrawTreeBtn').onclick=toggleWithdrawalTree;","el('withdrawTreeBtn').onclick=toggleWithdrawalTree;el('compactTreeBtn').onclick=toggleCompactTree;","button click")
p.write_text(js)
html=rep(html,'<button class="button hidden" type="button" id="aiTreeBtn"','<button class="button hidden v28-compact-switch" type="button" id="compactTreeBtn" aria-pressed="false" title="简洁版只显示会员账号和加入日期，悬停看完整个人与团队信息">▦ 简洁版</button><button class="button hidden" type="button" id="aiTreeBtn"',"HTML button")
h.write_text(html)
css+="""
/* V28 visual-only compact view. Full mode remains unchanged. */
.v28-compact-switch{background:#eaf3ff!important;border:1px solid #2b67c8!important;color:#1754aa!important;font-weight:900!important}
.v28-compact-switch[aria-pressed=true]{background:#1d4ed8!important;color:#fff!important}
.tree-main.v28-compact .tree{min-width:0!important;width:max-content;padding-left:0!important}
.tree-main.v28-compact .tree ul{padding-left:25px!important;margin-left:0!important}
.tree-main.v28-compact .tree li{margin:4px 0!important;padding-left:14px!important}
.tree-main.v28-compact .member.v28-member-mini{
 box-sizing:border-box!important;display:flex!important;flex-direction:column!important;justify-content:center!important;
 width:156px!important;min-width:156px!important;max-width:156px!important;
 height:42px!important;min-height:42px!important;margin:0!important;
 padding:4px 17px 4px 7px!important;border-radius:7px!important;gap:0!important;
 line-height:1.2!important;position:relative;
}
.v28-member-mini .v28-mini-account{display:block;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.v28-member-mini .v28-mini-date{display:block;font-size:10px;opacity:.9;white-space:nowrap}
.v28-member-mini .v28-mini-fold{position:absolute;top:10px;right:-8px;width:19px;height:19px;padding:0;line-height:16px;border-radius:50%;background:#fff;color:#1e4d85;border:1px solid #8faecf;font-size:15px;font-weight:900;z-index:1}
.tree-main.v28-compact .member.v28-member-mini:hover{outline:2px solid #eeb33c!important;outline-offset:2px}
.branch-canvas.v28-branch-compact .branch-node .v28-mini-name{font-size:12.4px!important;font-weight:900!important}
.branch-canvas.v28-branch-compact .branch-node .v28-mini-joined{font-size:10.5px!important;font-weight:700!important}
.branch-canvas.v28-branch-compact .branch-node>rect{filter:drop-shadow(0 1px 2px #0005)}
.branch-canvas.v28-branch-compact .branch-toggle-label{font-size:12px!important}
.v28-compact-tooltip{position:fixed;z-index:999999;pointer-events:none;
 width:max-content;min-width:min(320px,calc(100vw - 14px));max-width:min(450px,calc(100vw - 14px));
 max-height:min(535px,calc(100vh - 14px));overflow:auto;
 color:#16334c;background:#fff;border:2px solid #2865b1;border-radius:11px;
 box-shadow:0 12px 42px #001c3680;padding:12px;
 font:12px/1.4 -apple-system,BlinkMacSystemFont,'Microsoft Yahei',Arial,sans-serif}
.v28-pop-body{display:grid;gap:8px}
.v28-pop-title{font-size:15px;font-weight:900;color:#17457a;margin:0;padding-bottom:5px;border-bottom:1px solid #dde6f2}
.v28-pop-facts{display:grid;grid-template-columns:75px minmax(0,1fr);gap:3px 10px}
.v28-pop-facts span{color:#697f95}.v28-pop-facts b{overflow-wrap:anywhere}
.v28-pop-new,.v28-pop-risk{margin:0;padding:6px 8px;background:#f1f7ff;border-radius:6px;font-weight:800}
.v28-pop-table{border-collapse:collapse;width:100%;font-size:11px}
.v28-pop-table th,.v28-pop-table td{border:1px solid #dbe5f0;padding:5px;text-align:right;font-variant-numeric:tabular-nums}
.v28-pop-table th:first-child,.v28-pop-table td:first-child{text-align:left;white-space:nowrap}
.v28-pop-table th{background:#eaf2ff;font-weight:900}
.v28-pop-help{font-size:10px;color:#6b7b8e}
"""
c.write_text(css)
(root/"tests/test_v28_compact.cjs").write_text("""
const assert=require('node:assert/strict'),fs=require('node:fs');
const js=fs.readFileSync('static/app.js','utf8'),css=fs.readFileSync('static/style.css','utf8'),html=fs.readFileSync('static/index.html','utf8');
assert(html.includes('id="compactTreeBtn"'));
assert(js.includes("el('compactTreeBtn').onclick=toggleCompactTree"));
assert(js.includes("let compactMode=Boolean(savedTabView.compactMode)"));
assert(js.includes("if(compactMode&&view==='tree')"));
assert(js.includes("const gapY=compactMode?64:139,gapX=compactMode?186:368"));
assert(js.includes("attachCompactHover(group,m)"));
for(const k of ['direct_balance_cents','subtree_balance_cents','direct_stake_cents','subtree_stake_cents','direct_total_withdraw_cents','subtree_total_withdraw_cents','direct_daily_withdraw_cents','subtree_daily_withdraw_cents','direct_profit_cents','subtree_profit_cents'])assert(js.includes(k),k);
assert(css.includes('.v28-compact-tooltip'));assert(css.includes('.v28-member-mini'));
console.log('V28 compact tree, dense branch map, hover full team data tests passed');
""")
print('V28 frontend-only patch applied.')
