"""V22: replace overlapping historical rings with ONE clear red ring; sortable list.

Only changes static/app.js and static/index.html. Does not modify backend,
member names, withdrawal ledger, cash balances or business-day snapshots.

Weekly/monthly historical frequency = distinct positive withdrawal days in
the daily snapshot ledger. Expose the numeric day count in an additional
column and sort by either amount or count, ascending/descending.
"""
from pathlib import Path

jp=Path('member-tree/static/app.js')
hp=Path('member-tree/static/index.html')
j=jp.read_text(encoding='utf-8')
h=hp.read_text(encoding='utf-8')

def once(old,new):
    global j
    assert j.count(old)==1,("V22 code insertion anchor changed",j.count(old),old[:145])
    j=j.replace(old,new,1)

# 1. Dynamic sorting: do not mutate original tree order or backend records.
anchor="function v22HistIsOverview(){return v22HistMode==='week'||v22HistMode==='month'}"
sorter=r'''
let v22HistListSortField='amount',v22HistListSortDesc=true;
function v22HistWithdrawalAmount(x,frequency,amounts){
 const detail=frequency.get(x.id);
 return v22HistIsOverview()
  ? Number(detail?.amount_cents||0)
  : Number(amounts.get(x.id)||0);
}
function v22HistWithdrawalCount(x,frequency,amounts){
 const detail=frequency.get(x.id);
 return v22HistIsOverview()
  ? Number(detail?.days||0)
  : Number(amounts.get(x.id)||0)>0?1:0;
}
function v22HistSortRows(rows,frequency,amounts){
 if(v22HistMode==='new')return rows.slice();
 return rows.slice().sort((a,b)=>{
  const left=v22HistListSortField==='count'
   ? v22HistWithdrawalCount(a,frequency,amounts)
   : v22HistWithdrawalAmount(a,frequency,amounts);
  const right=v22HistListSortField==='count'
   ? v22HistWithdrawalCount(b,frequency,amounts)
   : v22HistWithdrawalAmount(b,frequency,amounts);
  return left===right?String(a.account||'').localeCompare(String(b.account||'')):
   v22HistListSortDesc?right-left:left-right;
 });
}
function v22HistSortBy(field){
 if(!['amount','count'].includes(field))return;
 if(v22HistListSortField===field)v22HistListSortDesc=!v22HistListSortDesc;
 else{v22HistListSortField=field;v22HistListSortDesc=true}
 v22HistUpdateToolbar();
}
'''
once(anchor,sorter+"\n"+anchor)

# 2. Keep historical newcomer date row 3 columns. For historical
# withdraw, week and month, show 4 columns with clickable sort headings.
old=r""" t.list.replaceChildren();
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
new=r""" t.list.replaceChildren();
 const isWithdrawal=v22HistMode!=='new';
 const sortedMatches=v22HistSortRows(matches,frequency,amounts);
 if(matches.length){
  const header=mk('div','v22-hist-list-heading'+(isWithdrawal?' v22-hist-four-columns':''));
  header.append(mk('span','','会员姓名'),mk('span','','会员账号'));
  if(isWithdrawal){
   const amountTitle=v22HistMode==='month'?'本月提现总额':
      v22HistMode==='week'?'本周提现总额':'当日提现金额';
   for(const [key,label] of [['amount',amountTitle],['count','提现次数']]){
    const selected=v22HistListSortField===key;
    const sort=mk('button','v22-hist-sort-header'+(selected?' active':''),
      label+(selected?(v22HistListSortDesc?' ↓':' ↑'):' ↕'));
    sort.type='button';
    sort.title='点击按'+label+(selected?'切换升序／降序':'从高到低排序');
    sort.setAttribute('aria-label',sort.title);
    sort.setAttribute('aria-pressed',String(selected));
    sort.onclick=()=>v22HistSortBy(key);
    header.append(sort);
   }
  }else header.append(mk('span','','加入日期'));
  t.list.append(header);
 }
 for(const x of sortedMatches.slice(0,400)){
  const remark=String(x.remark||'').trim();
  const displayName=remark&&remark!=='上级占位（待补资料）'?remark:'未填写姓名';
  const amount=isWithdrawal
   ? money(v22HistWithdrawalAmount(x,frequency,amounts),true)
   : (x.joined_on||'—');
  const count=isWithdrawal?v22HistWithdrawalCount(x,frequency,amounts):null;
  const btn=mk('button','v22-hist-account v22-hist-account-row'+
     (isWithdrawal?' v22-hist-four-columns':''));
  btn.type='button';btn.title='点击定位会员：'+x.account;
  btn.append(
   mk('span','v22-hist-member-name',displayName),
   mk('span','v22-hist-member-account',x.account),
   mk('strong','v22-hist-member-amount',amount));
  if(isWithdrawal)btn.append(mk('strong','v22-hist-member-count',String(count)));
  btn.onclick=()=>v22HistFocus(x.id);
  t.list.append(btn);
 }"""
once(old,new)

# 3. Exactly one appropriately sized ellipse, placed near each card like the
# existing "今日提现" V27 alert. Drop multiple oversized history ellipses.
old=r"""    const cx=cardW/2,cy=cardH/2;
    const outer=svgEl('ellipse',{
      cx,cy,rx:compactMode?144:225,ry:compactMode?58:134,
      class:joined?'v22-hist-ring-gold':'v22-hist-ring-crimson',
      'vector-effect':'non-scaling-stroke',fill:'none','aria-hidden':'true'
    });
    const mid=svgEl('ellipse',{
      cx,cy,rx:compactMode?117:192,ry:compactMode?46:107,
      class:joined?'v22-hist-ring-yellow':'v22-hist-ring-red',
      'vector-effect':'non-scaling-stroke',fill:'none','aria-hidden':'true'
    });
    const inner=svgEl('ellipse',{
      cx,cy,rx:compactMode?99:166,ry:compactMode?38:90,
      class:joined?'v22-hist-ring-cyan':'v22-hist-ring-pink',
      'vector-effect':'non-scaling-stroke',fill:'none','aria-hidden':'true'
    });
    group.append(outer,mid,inner);"""
new=r"""    // One circle only, sized like today's withdrawal ring. Historical
    // withdrawals are always red regardless of frequency; count is in list.
    group.append(svgEl('ellipse',{
      cx:cardW/2,cy:cardH/2,
      rx:compactMode?94:156,ry:compactMode?34:87,
      class:joined?'v22-hist-one-new-ring':'v22-hist-one-withdraw-ring',
      'vector-effect':'non-scaling-stroke',fill:'none','aria-hidden':'true'
    }));"""
once(old,new)

# Retain tree risk and "today's withdrawal" rings, but history only one ring.
# Prevent CSS extra pseudo-ring on the HTML member view.
once("note='红色双层光圈＝该日提现流水'+(returns?'；含 '+returns+' 条负数回流':'');",
     "note='红色单圈＝该日提现流水'+(returns?'；含 '+returns+' 条负数回流':'');")
once("note='黄蓝双层光圈＝该日新增；普通红圈仍为今日提现';",
     "note='黄色单圈＝该日新增；普通红圈仍为今日提现';")
old_legend="红圈=1天 · 橙圈=2—3天 · 紫圈=4天以上 ｜ 已记录 "
assert j.count(old_legend)==1
j=j.replace(old_legend,"红圈＝该段时间内有提现（圈色不区分次数） ｜ 已记录 ",1)

# Override old per-frequency palette without tampering with ledger logic.
css=r'''
<style id="v22-one-ring-sortable-history-css">
/* One outer ring per historical member, no overlap or aggressive animation.
   Matches the V27 today's withdrawal ellipse proportions. */
.v22-hist-one-withdraw-ring{
 stroke:#e95668!important;
 stroke-width:4px!important;
 opacity:.98!important;
 filter:drop-shadow(0 0 3px #ff657080)!important;
 animation:none!important;
 pointer-events:none;
}
.v22-hist-one-new-ring{
 stroke:#e7c649!important;
 stroke-width:3.5px!important;
 opacity:.96!important;
 filter:drop-shadow(0 0 2px #f2d45780)!important;
 animation:none!important;
 pointer-events:none;
}
/* Only one outline in the HTML tree; remove its old ::after extra halo. */
.member.v22-hist-withdraw::after,.member.v22-hist-new::after{
 display:none!important;
 content:none!important;
}
.member.v22-hist-withdraw,.member.v22-hist-new{
 box-shadow:none!important;
 outline-width:3px!important;
 outline-offset:4px!important;
}
.member.v22-hist-withdraw,.member.v22-hist-withdraw.v22-hist-frequency-low,
.member.v22-hist-withdraw.v22-hist-frequency-mid,
.member.v22-hist-withdraw.v22-hist-frequency-high{
 outline-color:#e95668!important;
 box-shadow:none!important;
}
.member.v22-hist-new{outline-color:#e7c649!important}
/* 4-column sortable ledger; date-only newcomer list stays 3 columns. */
.v22-hist-accounts{width:min(760px,96vw)!important;max-height:min(410px,65vh)!important}
.v22-hist-list-heading.v22-hist-four-columns,
.v22-hist-account-row.v22-hist-four-columns{
 grid-template-columns:minmax(84px,1fr) minmax(90px,1.18fr)
 minmax(112px,1.08fr) minmax(60px,.64fr)!important;
}
.v22-hist-sort-header{
 background:transparent;
 border:0;
 font-size:12px;
 font-weight:700;
 color:#536579;
 text-align:right;
 white-space:nowrap;
 padding:5px 1px;
 cursor:pointer;
 border-radius:4px;
}
.v22-hist-sort-header.active{color:#b13243}
.v22-hist-sort-header:hover,.v22-hist-sort-header:focus-visible{
 color:#075985;background:#e4f1fa;outline:1px solid #afd2e5;
}
.v22-hist-member-count{font-size:13px;font-weight:700;text-align:right;color:#66478b;
 font-variant-numeric:tabular-nums}
@media(max-width:570px){
 .v22-hist-list-heading.v22-hist-four-columns,
 .v22-hist-account-row.v22-hist-four-columns{
  grid-template-columns:minmax(62px,1fr) minmax(68px,1.1fr)
   minmax(75px,1.05fr) minmax(42px,.55fr)!important;
  gap:3px!important;font-size:11px!important;
 }
 .v22-hist-sort-header,.v22-hist-member-count{font-size:11px!important}
}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count('function v22HistSortRows(')==1
assert j.count("class:joined?'v22-hist-one-new-ring':'v22-hist-one-withdraw-ring'")==1
assert "group.append(outer,mid,inner)" not in j
assert "v22-hist-sort-header" in j
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print("PASS: V22 one bright red ring, 4-column sortable withdrawal history, finance untouched")
