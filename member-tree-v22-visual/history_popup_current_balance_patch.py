"""Add present-day member balance as fifth column to V22 withdrawal detail.

Shows "当前余额" directly from the existing member.balance_cents, never from
a historical withdrawal snapshot. Allows asc/desc balance sort alongside
withdrawal total and count. No API/DB writes and no financial recalculation.
"""
from pathlib import Path
jp=Path("member-tree/static/app.js")
hp=Path("member-tree/static/index.html")
j=jp.read_text(encoding="utf-8")
h=hp.read_text(encoding="utf-8")
def once(old,new):
 global j
 n=j.count(old)
 assert n==1,("V22 history list anchor mismatch",n,old[:170])
 j=j.replace(old,new,1)

old=r"""  const left=v22HistListSortField==='count'
   ? v22HistWithdrawalCount(a,frequency,amounts)
   : v22HistWithdrawalAmount(a,frequency,amounts);
  const right=v22HistListSortField==='count'
   ? v22HistWithdrawalCount(b,frequency,amounts)
   : v22HistWithdrawalAmount(b,frequency,amounts);"""
new=r"""  const left=v22HistListSortField==='count'
   ? v22HistWithdrawalCount(a,frequency,amounts)
   : v22HistListSortField==='balance' ? Number(a.balance_cents||0)
   : v22HistWithdrawalAmount(a,frequency,amounts);
  const right=v22HistListSortField==='count'
   ? v22HistWithdrawalCount(b,frequency,amounts)
   : v22HistListSortField==='balance' ? Number(b.balance_cents||0)
   : v22HistWithdrawalAmount(b,frequency,amounts);"""
once(old,new)
once("if(!['amount','count'].includes(field))return;",
     "if(!['amount','count','balance'].includes(field))return;")
once("const header=mk('div','v22-hist-list-heading'+(isWithdrawal?' v22-hist-four-columns':''));",
     "const header=mk('div','v22-hist-list-heading'+(isWithdrawal?' v22-hist-five-columns':''));")
once("for(const [key,label] of [['amount',amountTitle],['count','提现次数']]){",
     "for(const [key,label] of [['amount',amountTitle],['count','提现次数'],['balance','当前余额']]){")
once("const btn=mk('button','v22-hist-account v22-hist-account-row'+\n     (isWithdrawal?' v22-hist-four-columns':''));",
     "const btn=mk('button','v22-hist-account v22-hist-account-row'+\n     (isWithdrawal?' v22-hist-five-columns':''));")
once("if(isWithdrawal)btn.append(mk('strong','v22-hist-member-count',String(count)));",
     """if(isWithdrawal)btn.append(
    mk('strong','v22-hist-member-count',String(count)),
    mk('strong','v22-hist-member-balance',money(Number(x.balance_cents||0),true)));""")
css=r'''
<style id="v22-history-current-balance-css">
/* Current balance is a live account field, NOT a balance snapshot for the selected history period. */
.v22-hist-accounts{overflow-x:auto!important}
.v22-hist-list-heading.v22-hist-five-columns,
.v22-hist-account-row.v22-hist-five-columns{
 display:grid!important;
 grid-template-columns:minmax(95px,1.05fr) minmax(108px,1.1fr)
   minmax(125px,1fr) minmax(78px,.58fr) minmax(118px,1fr)!important;
 gap:9px!important;
 align-items:center!important;
 min-width:640px!important;
 box-sizing:border-box!important;
}
.v22-hist-member-balance{
 color:#236b53!important;
 font-size:13px!important;
 font-weight:750!important;
 text-align:right!important;
 font-variant-numeric:tabular-nums;
 white-space:nowrap;
}
.v22-hist-details.v22-hist-maximized .v22-hist-member-balance{
 font-size:14px!important;
}
.v22-hist-list-heading.v22-hist-five-columns>.v22-hist-sort-header:last-child{
 color:#236b53;
}
@media(max-width:690px){
 .v22-hist-details.v22-hist-maximized .v22-hist-list-heading.v22-hist-five-columns,
 .v22-hist-details.v22-hist-maximized .v22-hist-account-row.v22-hist-five-columns{
  min-width:640px!important;
 }
 .v22-hist-member-balance{font-size:12px!important}
}
</style>
'''
assert h.count("</body>")==1
h=h.replace("</body>",css+"</body>",1)
assert j.count("['balance','当前余额']")==1
assert j.count("v22-hist-member-balance")==1
jp.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print("PASS: V22 current account balance in history popup, five columns and numeric balance sorting")
