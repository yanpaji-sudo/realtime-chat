"""V22 leaderboard: click-to-sort every displayed data column.

Uses integer team counts, raw cent amounts and unrounded growth rates.
The original score ranking, daily/weekly/monthly/total calculation, expanded
detail and persistent database remain unchanged.
"""
from pathlib import Path
p=Path('member-tree/static/app.js')
hp=Path('member-tree/static/index.html')
j=p.read_text(encoding='utf-8')
h=hp.read_text(encoding='utf-8')
def once(before,after):
    global j
    assert j.count(before)==1,('ranking code changed',j.count(before),before[:160])
    j=j.replace(before,after,1)

helper=r'''
// Derived display order only: no effects on member finance or data storage.
let v22RankingSortField='score';
function v22RankingValue(row,field,day,period,basePosition){
 switch(field){
  case 'rank':return -(basePosition.get(row.id)||0);
  case 'teamName':return row.teamName||'（未命名）';
  case 'account':return row.account||'';
  case 'group':return row.group||'';
  case 'teamCount':return Number(row.teamCount||0);
  case 'growth':return v22RankGrowthPercent(row,day,period);
  case 'deposit':return Number(row.dailyStake||0);
  case 'withdraw':return Number(row.dailyWithdraw||0);
  case 'score':return Number(row.score||0);
  case 'balance':return Number(row.teamBalance||0);
  default:return Number(row.score||0);
 }
}
function v22RankingSortedRows(rows,day,period){
 const positions=new Map(rows.map((row,i)=>[row.id,i+1]));
 const sign=rankSort==='asc'?1:-1;
 return rows.slice().sort((a,b)=>{
  const x=v22RankingValue(a,v22RankingSortField,day,period,positions);
  const y=v22RankingValue(b,v22RankingSortField,day,period,positions);
  const xEmpty=x==null||(typeof x==='number'&&!Number.isFinite(x));
  const yEmpty=y==null||(typeof y==='number'&&!Number.isFinite(y));
  // Undefined growth is always placed last for either sorting direction.
  if(xEmpty||yEmpty){
   if(xEmpty!==yEmpty)return xEmpty?1:-1;
   return positions.get(a.id)-positions.get(b.id);
  }
  const primary=typeof x==='string'
   ?String(x).localeCompare(String(y),'zh-CN',{numeric:true,sensitivity:'base'})
   :x-y;
  return primary?primary*sign:positions.get(a.id)-positions.get(b.id);
 });
}
function v22RankingSortBy(field){
 if(v22RankingSortField===field)rankSort=rankSort==='desc'?'asc':'desc';
 else{v22RankingSortField=field;rankSort='desc'}
 render();
}
'''
once("function renderRanking(){",helper+"\nfunction renderRanking(){")
once(""" const day=businessDay||dateNow(),all=computeRanking(members,day,rankPeriod);
 const ordered=rankSort==='asc'?all.slice().reverse():all;
 const filtered=ordered.filter(x=>!query||x.account.toLowerCase().includes(query.toLowerCase()));""",
""" const day=businessDay||dateNow(),all=computeRanking(members,day,rankPeriod);
 const ordered=v22RankingSortedRows(all,day,rankPeriod);
 const sortedPosition=new Map(ordered.map((entry,i)=>[entry.id,i+1]));
 const filtered=ordered.filter(x=>!query||x.account.toLowerCase().includes(query.toLowerCase()));""")
begin=" ['名次','团队名称','第二层账号','所属第1层','团队人数','新增百分比',"
end=".forEach(x=>tr.append(mk('th','',x)));"
assert j.count(begin)==1
start=j.index(begin)
finish=j.index(end,start)+len(end)
assert finish-start<370
heading=r""" const columnDefs=[
  ['rank','名次'],['teamName','团队名称'],['account','第二层账号'],
  ['group','所属第1层'],['teamCount','团队人数'],
  ['growth','新增百分比'],['deposit',prefix+'新增建仓'],
  ['withdraw',prefix+'团队提现'],['score',prefix+'团队输赢'],
  ['balance','团队总余额']
 ];
 for(const [field,title] of columnDefs){
  const selected=v22RankingSortField===field;
  const arrow=selected?(rankSort==='desc'?'↓':'↑'):'↕';
  const th=mk('th','v22-ranking-sortable-th'+(selected?' v22-ranking-sort-active':''),title);
  th.title='点击按'+title+'排序（再次点击切换升序或降序）';
  th.tabIndex=0;
  th.setAttribute('aria-sort',selected?(rankSort==='desc'?'descending':'ascending'):'none');
  const toggle=()=>v22RankingSortBy(field);
  th.onclick=toggle;
  th.onkeydown=event=>{
   if(event.key==='Enter'||event.key===' '){event.preventDefault();toggle()}
  };
  const button=mk('button','v22-ranking-sort-arrow',arrow);
  button.type='button';
  button.title=th.title;
  button.setAttribute('aria-label','按'+title+'排序，'+(selected?(rankSort==='desc'?'当前从高到低':'当前从低到高'):'点击从高到低'));
  button.onclick=event=>{event?.stopPropagation?.();toggle()};
  th.append(button);
  tr.append(th);
 }
 tr.append(mk('th','','操作'));"""
j=j[:start]+heading+j[finish:]
once("String(rankSort==='desc'?all.findIndex(x=>x.account===entry.account)+1:all.length-all.findIndex(x=>x.account===entry.account))",
     "String(sortedPosition.get(entry.id)||i+1)")
css=r'''
<style id="v22-ranking-all-sort-css">
.ranking-table th.v22-ranking-sortable-th{
 cursor:pointer!important;
 user-select:none!important;
 white-space:nowrap!important;
 vertical-align:middle!important;
 min-width:68px;
}
.ranking-table th.v22-ranking-sortable-th:hover{
 background:#e7f2fd!important;
 color:#174b77!important;
}
.ranking-table th.v22-ranking-sort-active{
 background:#e3f0ff!important;
 color:#075985!important;
}
.ranking-table th.v22-ranking-sortable-th:focus-visible{
 outline:2px solid #428ec7!important;
 outline-offset:-2px!important;
}
.ranking-table .v22-ranking-sort-arrow{
 appearance:none;
 display:inline-block;
 margin-left:5px;
 min-width:19px;
 padding:2px 3px;
 background:transparent;
 border:1px solid transparent;
 border-radius:4px;
 color:#668da8;
 font-weight:900;
 font-size:13px;
 line-height:1.1;
 cursor:pointer;
 vertical-align:middle;
}
.ranking-table th.v22-ranking-sort-active .v22-ranking-sort-arrow{
 color:#0872ad;
 background:#c8e2f6;
 border-color:#9bbbd3;
}
.ranking-table .v22-ranking-sort-arrow:hover,
.ranking-table .v22-ranking-sort-arrow:focus-visible{
 color:#005b96;
 background:#d8ecfc;
 outline:1px solid #85b5d5;
}
</style>
'''
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count("function v22RankingSortedRows(")==1
assert j.count("function v22RankingSortBy(")==1
assert j.count("v22-ranking-sort-arrow")==1
assert j.count("const sortedPosition=new Map(")==1
p.write_text(j,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print('PASS: V22 every team-ranking data column click-sorts raw values, with numeric/text/growth asc/desc')
