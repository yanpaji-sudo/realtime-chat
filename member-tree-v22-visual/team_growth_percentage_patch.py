"""V22 ranking: four period-specific team signup percentage formulas.

Daily  = new / (total - new)
Week   = new / (total - new) / 7
Month  = new / (total - new) / 30
Total  = 1 / (total - 1) / elapsed days since first member joined this team

All rates displayed as percent with 2 decimals, safely '—' for missing base.
This is a read-only frontend patch: no financial, DB, API or score changes.
"""
from pathlib import Path
p=Path('member-tree/static/app.js')
hp=Path('member-tree/static/index.html')
j=p.read_text(encoding='utf-8')
h=hp.read_text(encoding='utf-8')

def once(a,b):
    global j
    n=j.count(a)
    assert n==1,("ranking anchor differs from V22 version",n,a[:135])
    j=j.replace(a,b,1)

helper=r'''
function v22RankGrowthPercent(team,day,period){
 const n=Number(team.teamCount||0),adds=Number(team.newCount||0);
 if(!Number.isFinite(n)||n<=0||!Number.isFinite(adds)||adds<0||adds>n)return null;
 if(period==='total'){
  if(n<=1)return null;
  const joined=String(team.earliestJoined||'').slice(0,10);
  if(!/^\d{4}-\d{2}-\d{2}$/.test(joined)||!/^\d{4}-\d{2}-\d{2}$/.test(day))return null;
  const start=new Date(joined+'T00:00:00Z');
  const today=new Date(day+'T00:00:00Z');
  if(Number.isNaN(start.getTime())||Number.isNaN(today.getTime())||
      start.toISOString().slice(0,10)!==joined||today.toISOString().slice(0,10)!==day)return null;
  const days=Math.round((today.getTime()-start.getTime())/86400000);
  return days>0?100/(n-1)/days:null;
 }
 const prior=n-adds;
 if(prior<=0)return null;
 const divisor=period==='week'?7:period==='month'?30:1;
 return 100*adds/prior/divisor;
}
function v22RankGrowthText(team,day,period){
 const pct=v22RankGrowthPercent(team,day,period);
 return pct===null||!Number.isFinite(pct)?'—':pct.toFixed(2)+'%';
}
'''
once("function computeRanking(rows,day,period='daily'){",helper+"\nfunction computeRanking(rows,day,period='daily'){")

once("""  return [r.id,{deposit,withdraw,newCount,count:1,balance:Number(r.balance_cents||0),layers:new Map([[level,{count:1,deposit,withdraw,balance:Number(r.balance_cents||0)}]])}];""",
"""  const joined=String(r.joined_on||'').slice(0,10);
  return [r.id,{deposit,withdraw,newCount,count:1,balance:Number(r.balance_cents||0),
    earliestJoined:/^\d{4}-\d{2}-\d{2}$/.test(joined)?joined:'',
    layers:new Map([[level,{count:1,deposit,withdraw,balance:Number(r.balance_cents||0)}]])}];""")

once("""  parent.deposit+=mine.deposit;parent.withdraw+=mine.withdraw;parent.newCount+=mine.newCount;parent.count+=mine.count;parent.balance+=mine.balance;""",
"""  parent.deposit+=mine.deposit;parent.withdraw+=mine.withdraw;parent.newCount+=mine.newCount;parent.count+=mine.count;parent.balance+=mine.balance;
  if(mine.earliestJoined&&(!parent.earliestJoined||mine.earliestJoined<parent.earliestJoined))
   parent.earliestJoined=mine.earliestJoined;""")

once("""return {id:r.id,account:r.account,teamName:r.team_name||'',group:r.group_account||'',teamCount:t.count,newCount:t.newCount,
          dailyStake:""",
"""return {id:r.id,account:r.account,teamName:r.team_name||'',group:r.group_account||'',teamCount:t.count,newCount:t.newCount,
          earliestJoined:t.earliestJoined,dailyStake:""")

once("""['名次','团队名称','第二层账号','所属第1层','团队人数',""",
"""['名次','团队名称','第二层账号','所属第1层','团队人数','新增百分比',""")

once("""entry.group,String(entry.teamCount),money(entry.dailyStake,true),money(entry.dailyWithdraw,true),(entry.score>0?'+':'')+money(entry.score,true),money(entry.teamBalance,true)];""",
"""entry.group,String(entry.teamCount),v22RankGrowthText(entry,day,rankPeriod),
   money(entry.dailyStake,true),money(entry.dailyWithdraw,true),
   (entry.score>0?'+':'')+money(entry.score,true),money(entry.teamBalance,true)];""")

old=r"""   if(k===5)cls+=' '+(entry.dailyStake>0?'amount-green':entry.dailyStake<0?'amount-red':'amount-black');
   if(k===6)cls+=' '+amountClass(entry.dailyWithdraw,'daily');
   if(k===7)cls+=' '+amountClass(entry.score,'profit');
   if(k===8)cls+=' '+amountClass(entry.teamBalance);
   const td=mk('td',cls.trim(),v);if(k===2)td.classList.add('account-cell');tr.append(td)"""
new=r"""   if(k===5)cls+=' v22-ranking-growth'+(v==='—'?' amount-black':' amount-green');
   if(k===6)cls+=' '+(entry.dailyStake>0?'amount-green':entry.dailyStake<0?'amount-red':'amount-black');
   if(k===7)cls+=' '+amountClass(entry.dailyWithdraw,'daily');
   if(k===8)cls+=' '+amountClass(entry.score,'profit');
   if(k===9)cls+=' '+amountClass(entry.teamBalance);
   const td=mk('td',cls.trim(),v);
   if(k===2)td.classList.add('account-cell');
   if(k===5)td.title=rankPeriod==='total'
      ? '1÷（团队总人数－1）÷该团队首位成员加入至今的天数'
      : rankPeriod==='week'?'本周新增人数÷（团队总人数－本周新增人数）÷7'
      : rankPeriod==='month'?'本月新增人数÷（团队总人数－本月新增人数）÷30'
      : '当日新增人数÷（团队总人数－当日新增人数）';
   tr.append(td)"""
once(old,new)
once("cell.colSpan=10;", "cell.colSpan=11;")
once("td.colSpan=10;tr.append(td);body.append(tr)", "td.colSpan=11;tr.append(td);body.append(tr)")

note="周榜按北京时间周一至周日、月榜按自然月；原系统没有的历史提现明细不会被推测补齐。"
assert j.count(note)==1
j=j.replace(note,
  "新增百分比：当日＝新增÷（团队人数－当日新增）；本周＝新增÷（团队人数－本周新增）÷7；本月＝新增÷（团队人数－本月新增）÷30；总榜＝1÷（团队人数－1）÷本团队首位会员加入至今的天数。无历史基数或不足一天显示“—”。"+note,1)

css=r'''
<style id="v22-team-ranking-growth-css">
.ranking-table th:nth-child(6),.ranking-table td.v22-ranking-growth{
 min-width:112px;
 white-space:nowrap;
 text-align:right;
 font-variant-numeric:tabular-nums;
}
.ranking-table td.v22-ranking-growth{font-weight:800}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count("function v22RankGrowthPercent(")==1
assert j.count("v22RankGrowthText(entry,day,rankPeriod)")==1
assert j.count("cell.colSpan=11")==1
p.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print('PASS: all four requested ranking growth percent formulas added with earliest team join date')
