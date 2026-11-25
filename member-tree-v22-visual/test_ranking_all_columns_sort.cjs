// Regression for sortable V22 second-level ranking: every field + both directions.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const coreStart=js.indexOf('function weekStart(day){');
const coreEnd=js.indexOf('function teamSummaryByNode(',coreStart);
const sortStart=js.indexOf("let v22RankingSortField='score';");
const sortEnd=js.indexOf('function renderRanking(){',sortStart);
const renderStart=sortEnd;
const renderEnd=js.indexOf('\n// Read-only left-to-right distribution',renderStart);
assert(coreStart>=0&&coreEnd>coreStart&&sortStart>coreEnd&&sortEnd>sortStart&&renderEnd>renderStart);
const ctx={};vm.createContext(ctx);
vm.runInContext(js.slice(coreStart,coreEnd),ctx);
vm.runInContext(js.slice(sortStart,sortEnd),ctx);
const raw=[
 {id:'a',account:'a2',teamName:'甲队',group:'g10',teamCount:10,newCount:2,
   dailyStake:1000,dailyWithdraw:500,score:900,teamBalance:2000,earliestJoined:'2026-11-01'},
 {id:'b',account:'a10',teamName:'乙队',group:'g2',teamCount:6,newCount:4,
   dailyStake:2000,dailyWithdraw:200,score:400,teamBalance:1000,earliestJoined:'2026-11-10'},
 {id:'c',account:'c3',teamName:'丙队',group:'g1',teamCount:20,newCount:1,
   dailyStake:1500,dailyWithdraw:1000,score:-100,teamBalance:9000,earliestJoined:'2026-10-18'},
 {id:'d',account:'d4',teamName:'丁队',group:'g3',teamCount:1,newCount:1,
   dailyStake:0,dailyWithdraw:-100,score:-200,teamBalance:5000,earliestJoined:'2026-11-25'},
];
ctx.raw=raw;ctx.rankSort='desc';
const order=()=>Array.from(vm.runInContext("v22RankingSortedRows(raw,'2026-11-25','daily').map(x=>x.id)",ctx));
const key=x=>vm.runInContext("v22RankingSortField='"+x+"'",ctx);
for(const [field,descending,ascending] of [
 ['rank',['a','b','c','d'],['d','c','b','a']],
 ['teamCount',['c','a','b','d'],['d','b','a','c']],
 ['growth',['b','a','c','d'],['c','a','b','d']],
 ['deposit',['b','c','a','d'],['d','a','c','b']],
 ['withdraw',['c','a','b','d'],['d','b','a','c']],
 ['score',['a','b','c','d'],['d','c','b','a']],
 ['balance',['c','d','a','b'],['b','a','d','c']],
 ['account',['d','c','b','a'],['a','b','c','d']],
 ['group',['a','d','b','c'],['c','b','d','a']],
]){
 key(field);ctx.rankSort='desc';
 assert.deepStrictEqual(order(),descending,field+' descending');
 ctx.rankSort='asc';
 assert.deepStrictEqual(order(),ascending,field+' ascending');
}
for(const field of ['teamName']){
 key(field);ctx.rankSort='desc';
 assert.deepStrictEqual(order(),['a','b','d','c'],'Chinese text descending');
 ctx.rankSort='asc';
 assert.deepStrictEqual(order(),['c','d','b','a'],'Chinese text ascending');
}
// Equal numeric values are deterministically ordered by original score rank.
ctx.ties=raw.map(x=>({...x,teamBalance:10000}));
key('balance');ctx.rankSort='desc';
assert.deepStrictEqual(Array.from(vm.runInContext(
 "v22RankingSortedRows(ties,'2026-11-25','daily').map(x=>x.id)",ctx)),['a','b','c','d']);
assert.deepStrictEqual(raw.map(x=>x.teamBalance),[2000,1000,9000,5000],
 'Numeric sorting must not change source amounts');

// Test actual table markup and click/keyboard interactions.
function mk(tag,cls='',text=''){
 return {tag,cls,text,children:[],attrs:{},classList:{add(){}},
  append(...xs){this.children.push(...xs)},
  setAttribute(key,val){this.attrs[key]=val}};
}
const people=[
 {id:'root',account:'root',parent_id:null,level:1,joined_on:'2026-09-01'},
 {id:'a',account:'a2',team_name:'甲队',group_account:'g10',
   parent_id:'root',level:2,joined_on:'2026-10-15',stake_cents:10000,balance_cents:250000},
 {id:'a1',account:'a1',parent_id:'a',level:3,joined_on:'2026-11-25',
   stake_cents:6000,balance_cents:8000},
 {id:'b',account:'a10',team_name:'乙队',group_account:'g2',
   parent_id:'root',level:2,joined_on:'2026-10-16',stake_cents:20000,balance_cents:800000},
 {id:'b1',account:'b1',parent_id:'b',level:3,joined_on:'2026-11-24',
   stake_cents:30000,balance_cents:500000},
 {id:'c',account:'c3',team_name:'丙队',group_account:'g1',
   parent_id:'root',level:2,joined_on:'2026-10-20',stake_cents:9000,balance_cents:1000000},
 {id:'d',account:'d4',team_name:'丁队',group_account:'g3',
   parent_id:'root',level:2,joined_on:'2026-11-25',stake_cents:1000,balance_cents:10000},
];
ctx.members=people;
ctx.businessDay='2026-11-25';ctx.dateNow=()=> '2026-11-25';
ctx.rankPeriod='daily';ctx.rankSort='desc';
ctx.rankExpanded=new Set();ctx.query='';ctx.role='viewer';
ctx.mk=mk;ctx.money=x=>String(x);ctx.amountClass=()=>'';ctx.fullscreenActive=()=>false;
ctx.toggleTreeFullscreen=()=>{};
ctx.historyCoverage={tracking_since:'2026-09-01',imported_days:[]};
ctx.v33ActiveRankingMembers=()=>[];
let renderCalls=0,lastUi=null;
ctx.render=()=>{
 renderCalls++;
 lastUi=vm.runInContext('renderRanking()',ctx);
};
vm.runInContext(js.slice(renderStart,renderEnd),ctx);
const domFind=(x,test)=>{
 if(test(x))return x;
 for(const child of x.children||[]){const res=domFind(child,test);if(res)return res;}
 return null;
};
const table=()=>domFind(lastUi,x=>x.tag==='table'&&String(x.cls).includes('ranking-table'));
const headings=()=>table().children[0].children[0].children;
const rankingRows=()=>table().children[1].children.filter(x=>x.cls!=='ranking-detail-row');
const accounts=()=>rankingRows().map(x=>x.children[2].text);
ctx.render();
assert.strictEqual(headings().length,11,'10 data columns plus actions');
const expected=['名次','团队名称','第二层账号','所属第1层','团队人数',
 '新增百分比','当日新增建仓','当日团队提现','当日团队输赢','团队总余额','操作'];
assert.deepStrictEqual(headings().map(x=>x.text),expected);
for(let i=0;i<10;i++){
 const th=headings()[i];
 assert(th.cls.includes('v22-ranking-sortable-th'),'Column '+i+' clickable');
 assert(typeof th.onclick==='function'&&typeof th.onkeydown==='function');
 assert.strictEqual(th.children[0].tag,'button','Arrow is a button');
 assert.strictEqual(typeof th.children[0].onclick,'function');
 assert.strictEqual(th.tabIndex,0,'Keyboard accessible');
 assert(th.attrs['aria-sort'],'ARIA sort status present');
}
assert.strictEqual(headings()[10].children.length,0,'Actions not sorted');
assert.strictEqual(headings()[8].children[0].text,'↓','Default profit score descending');
const startOrder=accounts();
assert.strictEqual(startOrder[0],'a10','Default existing score leaderboard preserved');
const getNames=()=>{
 const cur=rankingRows();return cur.map(x=>[x.children[2].text,x.children[9].text])
};
const byBalanceDesc=[...getNames()].sort((a,b)=>Number(b[1])-Number(a[1])).map(x=>x[0]);
headings()[9].onclick();
assert.deepStrictEqual(accounts(),byBalanceDesc,'Click balance header gives highest balance first');
assert.strictEqual(headings()[9].children[0].text,'↓');
assert.strictEqual(headings()[9].attrs['aria-sort'],'descending');
headings()[9].children[0].onclick({stopPropagation(){}});
assert.deepStrictEqual(accounts(),byBalanceDesc.slice().reverse(),'Arrow click toggles ascending');
assert.strictEqual(headings()[9].children[0].text,'↑');
assert.strictEqual(headings()[9].attrs['aria-sort'],'ascending');
const previous=renderCalls;
headings()[6].onkeydown({key:'Enter',preventDefault(){}});
assert.strictEqual(renderCalls,previous+1,'Keyboard Enter switches sorting');
assert.strictEqual(headings()[6].children[0].text,'↓');
const depRows=rankingRows().map(x=>Number(x.children[6].text));
assert.deepStrictEqual(depRows,depRows.slice().sort((a,b)=>b-a),
 'Deposits are sorted by raw numeric cents, not text formatting');
// Switching periods must preserve selected field and use its period data.
const periodTabs=domFind(lastUi,x=>x.cls==='v12-tabs');
const monthButton=periodTabs.children.find(x=>x.text==='月榜单');
monthButton.onclick();
assert.strictEqual(ctx.rankPeriod,'month');
assert.strictEqual(vm.runInContext('v22RankingSortField',ctx),'deposit');
assert(headings()[6].text.includes('本月'));
assert.strictEqual(headings()[6].children[0].text,'↓');
// Search filtering must not re-rank the underlying unfiltered scores.
ctx.query='a';ctx.render();
const shown=rankingRows();
assert(shown.every(x=>x.children[2].text.toLowerCase().includes('a')));
assert(Number(shown[0].children[0].text)>=1);
ctx.query='';
ctx.rankExpanded.add('a10');
ctx.v33ActiveRankingMembers=()=>[];
ctx.render();
const detail=table().children[1].children.find(x=>x.cls==='ranking-detail-row');
assert(detail&&detail.children[0].colSpan===11,'Existing expanded details retain colspan');
assert(js.includes("v22RankingValue(row,field,day,period,basePosition)"));
assert(js.includes("v22RankingSortBy(field)"));
assert(js.includes('v22RankingSortedRows(all,day,rankPeriod)'));
assert(html.includes('id="v22-ranking-all-sort-css"'));
console.log('PASS: 10 V22 leaderboard data columns sortable both directions, numeric cents/growth, Chinese text, arrows/keyboard, tabs, score ranking and detail preserved');
