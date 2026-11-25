"""V22 formal: simplified withdrawal list and restrained history ring styling.

Read-only presentation only. Week/month popover rows show member display name
(from existing remark field), account, and period withdrawal totals.
No day-count text in list/node SVG; frequency colors remain distinct and subtle.
The daily history popover shows name/account/day amount.
Preserves independent prior historical signup and financial ledger behavior.
"""
from pathlib import Path
jp=Path('member-tree/static/app.js')
hp=Path('member-tree/static/index.html')
j=jp.read_text(encoding='utf-8')
h=hp.read_text(encoding='utf-8')

old=r""" t.list.replaceChildren();
 for(const x of matches.slice(0,400)){
  const detail=frequency.get(x.id);
  const val=v22HistIsOverview()&&detail
   ? ' · '+detail.days+'天 · '+money(detail.amount_cents,true)
   : v22HistMode==='withdraw'?' · '+money(amounts.get(x.id)||0,true):'';
  const btn=mk('button','v22-hist-account',x.account+val);
  btn.type='button';btn.onclick=()=>v22HistFocus(x.id);
  t.list.append(btn);
 }"""
new=r""" t.list.replaceChildren();
 if(matches.length){
  const header=mk('div','v22-hist-list-heading');
  header.append(
   mk('span','','会员姓名'),
   mk('span','','会员账号'),
   mk('span','',v22HistMode==='month'?'本月提现总额':
      v22HistMode==='week'?'本周提现总额':
      v22HistMode==='withdraw'?'当日提现金额':'加入日期'));
  t.list.append(header);
 }
 for(const x of matches.slice(0,400)){
  const detail=frequency.get(x.id);
  const remark=String(x.remark||'').trim();
  const displayName=remark&&remark!=='上级占位（待补资料）'?remark:'未填写姓名';
  const amount=v22HistIsOverview()&&detail
    ? money(Number(detail.amount_cents||0),true)
    : v22HistMode==='withdraw'
      ? money(Number(amounts.get(x.id)||0),true)
      : (x.joined_on||'—');
  const btn=mk('button','v22-hist-account v22-hist-account-row');
  btn.type='button';
  btn.title='点击定位会员：'+x.account;
  btn.append(
   mk('span','v22-hist-member-name',displayName),
   mk('span','v22-hist-member-account',x.account),
   mk('strong','v22-hist-member-amount',amount));
  btn.onclick=()=>v22HistFocus(x.id);
  t.list.append(btn);
 }"""
assert j.count(old)==1,("V22 popup field layout changed",j.count(old))
j=j.replace(old,new,1)

# No frequency text on the branch SVG itself. The selected period's tier is
# still represented by a red/amber/purple outline, toned down below.
oldbadge=r"""    if(detail){
     const badge=svgEl('g',{class:'v22-hist-count-badge',
       transform:'translate('+Math.max(0,cardW-65)+',-13)'});
     badge.append(svgEl('rect',{x:0,y:0,width:65,height:27,rx:11,
       class:'v22-hist-count-badge-bg v22-hist-count-bg-'+detail.tier}));
     badge.append(svgEl('text',{x:32,y:18,'text-anchor':'middle',
       class:'v22-hist-count-label'},String(detail.days)+'天'));
     group.append(badge);
    }"""
assert j.count(oldbadge)==1,("V22 historic SVg day badge block changed",j.count(oldbadge))
j=j.replace(oldbadge,"    // Ring color is enough: no day-count badge obscuring the member node.",1)
oldtip=r"""group.append(svgEl('title',{},v22HistSelected()+
     (joined?' 新增会员 ':' 历史提现 ')+m.account+
     (detail?' · '+detail.days+'天提现 · 累计 '+money(detail.amount_cents,true):'')));"""
newtip=r"""group.append(svgEl('title',{},v22HistSelected()+
     (joined?' 新增会员 ':' 历史提现 ')+m.account+
     (detail?' · 提现总额 '+money(detail.amount_cents,true):'')));"""
assert j.count(oldtip)==1,('V22 node title changed',j.count(oldtip))
j=j.replace(oldtip,newtip,1)

# Clear all 'N days withdrawal' pseudo badges in the standard tree.
# Retain its tier-based color and hidden day metadata (needed for no UI display? no).
oldmeta=r"""   if(detail)card.dataset.v22HistDays=String(detail.days);
   else delete card.dataset.v22HistDays;"""
assert j.count(oldmeta)==1,'V22 history frequency metadata changed'
j=j.replace(oldmeta,"   delete card.dataset.v22HistDays;",1)

# Remove "days" from member list only. The color legend still explains
# what red/orange/purple mean, but the cards no longer carry count labels.
css=r'''
<style id="v22-history-compact-soft-css">
/* Compact three-column list instead of the old multi-pill day badges. */
.v22-hist-accounts{
 width:min(680px,92vw)!important;
 min-width:min(380px,92vw)!important;
 max-height:min(380px,58vh)!important;
 display:block!important;
 padding:8px!important;
 box-sizing:border-box!important;
}
.v22-hist-list-heading,.v22-hist-account-row{
 display:grid!important;
 grid-template-columns:minmax(82px,1fr) minmax(95px,1.18fr) minmax(104px,1fr);
 align-items:center;
 gap:10px;
 width:100%;
 box-sizing:border-box;
 text-align:left;
}
.v22-hist-list-heading{
 padding:6px 10px 8px;
 border-bottom:1px solid #cbd5e1;
 color:#586575;font-weight:750;font-size:12px;
}
.v22-hist-account-row{
 margin:3px 0!important;
 padding:8px 10px!important;
 border:1px solid #e0e7ef!important;
 background:#fff!important;
 box-shadow:none!important;
 border-radius:6px!important;
 font-size:13px!important;
}
.v22-hist-account-row:hover{background:#f1f7fc!important;border-color:#b3cada!important}
.v22-hist-member-name,.v22-hist-member-account{
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.v22-hist-member-name{color:#344054;font-weight:700}
.v22-hist-member-account{color:#25618a}
.v22-hist-member-amount{
 color:#b13243;white-space:nowrap;
 font-size:13px;font-weight:700;text-align:right;
 font-variant-numeric:tabular-nums;
}
.v22-hist-list-heading>span:last-child{text-align:right}
/* Soft, static historical rings: visible at a glance without bright neon. */
.v22-hist-ring-gold{stroke:#d7ab48!important;stroke-width:4px!important;filter:none!important;animation:none!important;opacity:.93}
.v22-hist-ring-yellow{stroke:#f4da64!important;stroke-width:3px!important;filter:none!important;animation:none!important;opacity:.92}
.v22-hist-ring-cyan{stroke:#67b9c8!important;stroke-width:2px!important;filter:none!important;animation:none!important;opacity:.85}
.v22-hist-ring-crimson{stroke:#dc606c!important;stroke-width:4px!important;filter:none!important;animation:none!important;opacity:.93}
.v22-hist-ring-red{stroke:#f3a0a9!important;stroke-width:3px!important;filter:none!important;animation:none!important;opacity:.91}
.v22-hist-ring-pink{stroke:#fbd1d8!important;stroke-width:2px!important;filter:none!important;animation:none!important;opacity:.87}
.branch-node.v22-hist-frequency-mid .v22-hist-ring-crimson,
.branch-node.v22-hist-frequency-mid .v22-hist-ring-red,
.branch-node.v22-hist-frequency-mid .v22-hist-ring-pink{stroke:#dc983a!important;filter:none!important}
.branch-node.v22-hist-frequency-mid .v22-hist-ring-red{stroke:#f4c47b!important}
.branch-node.v22-hist-frequency-high .v22-hist-ring-crimson,
.branch-node.v22-hist-frequency-high .v22-hist-ring-red,
.branch-node.v22-hist-frequency-high .v22-hist-ring-pink{stroke:#9569c7!important;filter:none!important}
.branch-node.v22-hist-frequency-high .v22-hist-ring-red{stroke:#c3a8e3!important}
.member.v22-hist-new,.member.v22-hist-withdraw{
 outline-width:2px!important;
 outline-offset:3px!important;
 box-shadow:0 0 0 2px #b9c9d180!important;
}
.member.v22-hist-new{outline-color:#cbaa36!important}
.member.v22-hist-withdraw{outline-color:#d56876!important}
.member.v22-hist-withdraw.v22-hist-frequency-mid{
 outline-color:#d6a34a!important;box-shadow:0 0 0 2px #ddbd7a8c!important}
.member.v22-hist-withdraw.v22-hist-frequency-high{
 outline-color:#9772cf!important;box-shadow:0 0 0 2px #b9a1d68c!important}
.member.v22-hist-new::after,.member.v22-hist-withdraw::after{
 inset:-6px!important;border-width:2px!important;box-shadow:none!important;
 animation:none!important;opacity:.9!important;
}
.member.v22-hist-new::after{border-color:#d0b14a!important}
.member.v22-hist-withdraw::after{border-color:#df6879!important}
.member.v22-hist-withdraw.v22-hist-frequency-mid::after{
 border-color:#d6a34a!important;box-shadow:none!important}
.member.v22-hist-withdraw.v22-hist-frequency-high::after{
 border-color:#9772cf!important;box-shadow:none!important}
.member.v22-hist-new::before,.member.v22-hist-withdraw::before{
 display:none!important;content:none!important;
}
@media(max-width:550px){
 .v22-hist-list-heading,.v22-hist-account-row{
  grid-template-columns:minmax(70px,1fr) minmax(75px,1fr) minmax(90px,1fr);
  gap:5px;font-size:12px!important;
 }
 .v22-hist-list-heading{padding:6px}
 .v22-hist-account-row{padding:7px 6px!important}
 .v22-hist-member-amount{font-size:12px}
}
@media(prefers-reduced-motion:reduce){
 .v22-hist-ring-gold,.v22-hist-ring-yellow,.v22-hist-ring-cyan,
 .v22-hist-ring-crimson,.v22-hist-ring-red,.v22-hist-ring-pink{
  animation:none!important
 }
}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count("v22-hist-member-name")==1
assert j.count("v22-hist-count-badge'")==0
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print('PASS: V22 historical withdrawal lists now show remark/name+account+total; subtle static tier rings and no day count badges')
