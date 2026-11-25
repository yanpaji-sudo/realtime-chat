// V22 ranking regression: exact requested formulas and 11-column leaderboard.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const start=js.indexOf('function weekStart(day){');
const end=js.indexOf('function teamSummaryByNode(',start);
assert(start>0&&end>start);
const src=js.slice(start,end);
const team=[
 {id:'root',account:'mainroot',parent_id:null,level:1,joined_on:'2026-09-15',balance_cents:100},
 {id:'a',account:'TeamA',parent_id:'root',level:2,joined_on:'2026-11-01',balance_cents:1000,stake_cents:100000},
 {id:'a1',account:'a1',parent_id:'a',level:3,joined_on:'2026-11-25',balance_cents:200,stake_cents:20000},
 {id:'a2',account:'a2',parent_id:'a',level:3,joined_on:'2026-11-24',balance_cents:300,stake_cents:30000},
 {id:'a3',account:'a3',parent_id:'a2',level:4,joined_on:'2026-10-20',balance_cents:400,stake_cents:40000},
 {id:'b',account:'TeamB',parent_id:'root',level:2,joined_on:'2026-11-24',stake_cents:10000},
 {id:'b1',account:'b1',parent_id:'b',level:3,joined_on:'2026-11-25',stake_cents:11000},
 {id:'solo',account:'TeamSolo',parent_id:'root',level:2,joined_on:'2026-11-25',stake_cents:10000},
];
const day='2026-11-25';
const ctx={};vm.createContext(ctx);vm.runInContext(src,ctx);
const call=(period,account)=>vm.runInContext("computeRanking(team,day,'"+period+"').find(x=>x.account==='"+account+"')",
 Object.assign(ctx,{team,day}));
const percentage=(period,account)=>vm.runInContext("v22RankGrowthPercent(computeRanking(team,day,'"+period+"').find(x=>x.account==='"+account+"'),day,'"+period+"')",ctx);
const approx=(x,expect)=>assert(Math.abs(x-expect)<1e-9,(x+" != "+expect));
let a=call('daily','TeamA');
assert.strictEqual(a.teamCount,4);assert.strictEqual(a.newCount,1);
assert.strictEqual(a.earliestJoined,'2026-10-20','Earliest is from entire second-level subtree, not global root');
approx(percentage('daily','TeamA'),100/3);
a=call('week','TeamA');
assert.strictEqual(a.newCount,2);
approx(percentage('week','TeamA'),100*2/2/7);
a=call('month','TeamA');
assert.strictEqual(a.newCount,3);
approx(percentage('month','TeamA'),100*3/1/30);
a=call('total','TeamA');
assert.strictEqual(a.newCount,4);
approx(percentage('total','TeamA'),100/3/36);
assert.strictEqual(vm.runInContext("v22RankGrowthText(computeRanking(team,day,'total').find(x=>x.account==='TeamA'),day,'total')",ctx),'0.93%');
assert.strictEqual(percentage('week','TeamB'),null,'No prior team in week => undefined');
assert.strictEqual(percentage('month','TeamB'),null,'No prior team in month => undefined');
approx(percentage('daily','TeamB'),100);
assert.strictEqual(percentage('daily','TeamSolo'),null);
assert.strictEqual(percentage('total','TeamSolo'),null,'One-person team has no total growth baseline');
assert.strictEqual(vm.runInContext("v22RankGrowthText({teamCount:2,newCount:2,earliestJoined:'2026-11-25'},day,'total')",ctx),'—');
assert.strictEqual(vm.runInContext("v22RankGrowthText({teamCount:4,newCount:0,earliestJoined:'2026-11-01'},day,'daily')",ctx),'0.00%');
for(const bad of ['2026-02-30','2026-12-01','bad'])assert.strictEqual(vm.runInContext(
 "v22RankGrowthText({teamCount:4,newCount:4,earliestJoined:'"+bad+"'},day,'total')",ctx),'—');
// Existing score sorting must be unaffected; still descending team score.
assert.deepStrictEqual(Array.from(vm.runInContext("computeRanking(team,day,'total').map(x=>x.account)",ctx)),['TeamA','TeamB','TeamSolo']);

// Render the actual leaderboard in a deterministic fake DOM.
function mk(tag,cls='',text=''){
 return {tag,cls,text,children:[],attrs:{},classList:{add(){}},
  append(...items){this.children.push(...items)},
  setAttribute(k,v){this.attrs[k]=v}};
}
const rstart=js.indexOf('function renderRanking(){');
const rend=js.indexOf('\n// Read-only left-to-right distribution',rstart);
assert(rstart>0&&rend>rstart);
const renderCode=js.slice(rstart,rend);
Object.assign(ctx,{
 members:team,businessDay:day,dateNow:()=>day,rankPeriod:'daily',
 rankSort:'desc',rankExpanded:new Set(),query:'',role:'viewer',mk,
 money:(v)=>String(v),amountClass:()=>'',fullscreenActive:()=>false,
 toggleTreeFullscreen:()=>{},periodStart:()=>day,
 historyCoverage:{tracking_since:'2026-09-01',imported_days:[]}
});
vm.runInContext(renderCode,ctx);
const render=period=>{
 ctx.rankPeriod=period;
 return vm.runInContext('renderRanking()',ctx);
};
const find=(root,predicate)=>{
 if(predicate(root))return root;
 for(const c of root.children||[]){const hit=find(c,predicate);if(hit)return hit;}
 return null;
};
for(const period of ['daily','week','month','total']){
 const root=render(period);
 const table=find(root,x=>x.tag==='table'&&String(x.cls).includes('ranking-table'));
 assert(table,'Team leaderboard table exists');
 const th=table.children[0].children[0].children;
 assert.strictEqual(th.length,11,'Header includes exactly one extra column');
 assert.strictEqual(th[5].text,'新增百分比');
 const tr=table.children[1].children[0];
 assert.strictEqual(tr.children.length,11,'Each row has 11 values including detail controls');
 const top=call(period,'TeamA');
 assert.strictEqual(tr.children[5].text,vm.runInContext(
  "v22RankGrowthText(computeRanking(team,day,'"+period+"').find(x=>x.account==='TeamA'),day,'"+period+"')",ctx));
 assert(tr.children[5].cls.includes('v22-ranking-growth'));
 assert(tr.children[5].title?.includes('÷'));
 assert.strictEqual(tr.children[4].text,'4','Team count still in original column');
 assert.strictEqual(tr.children[6].text,String(top.dailyStake),'Original deposit shifted, not altered');
 assert.strictEqual(tr.children[7].text,String(top.dailyWithdraw),'Withdrawal preserved');
 assert.strictEqual(tr.children[8].text,String(top.score),'Net score preserved');
 assert.strictEqual(tr.children[9].text,String(top.teamBalance),'Total balance preserved');
}
// Expanded detail row colspan must match new 11-column parent table.
ctx.rankPeriod='daily';ctx.rankExpanded.add('TeamA');
ctx.v33ActiveRankingMembers=()=>[];
const withExpanded=render('daily');
const tab=find(withExpanded,x=>x.tag==='table'&&String(x.cls).includes('ranking-table'));
const body=tab.children[1];
assert.strictEqual(body.children[1].children[0].colSpan,11);
assert(js.includes("td.colSpan=11;tr.append(td);body.append(tr)"));
assert(html.includes('id="v22-team-ranking-growth-css"'));
assert(html.includes('min-width:112px'));
console.log('PASS: V22 daily/week/month/total exact growth percent, earliest joined member, zero divisor, 11-column display, existing money/score and expanded detail preserved');
