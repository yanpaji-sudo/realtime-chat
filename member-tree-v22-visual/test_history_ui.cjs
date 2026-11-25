// V22 date calendar: historical newcomers and selected-day withdrawal rings.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const begin=js.indexOf("let v22HistMode='new'");
const end=js.indexOf('\nfunction renderBranch(){',begin);
assert(begin>0&&end>begin);
const members=[
 {id:'root',account:'root',parent_id:null,joined_on:'2026-11-01'},
 {id:'alice',account:'alice',parent_id:'root',joined_on:'2026-11-23'},
 {id:'bob',account:'bob',parent_id:'alice',joined_on:'2026-11-24'},
 {id:'carol',account:'carol',parent_id:'root',joined_on:'2026-11-24'},
 {id:'placeholder',account:'oldroot',parent_id:null,
  joined_on:'2026-11-24',remark:'上级占位（待补资料）'},
];
let calls=[],renderCalls=0,visible=members,reply={
 day:'2026-11-24',recorded:true,members:[
  {id:'alice',account:'alice',amount_cents:50000},
  {id:'bob',account:'bob',amount_cents:-1200}],
 count:2
};
const sandbox={
 dateNow:()=> '2026-11-25',
 businessDay:'2026-11-25',
 members,historyCoverage:{tracking_since:'2026-11-01'},
 view:'branch',teamFocusId:null,
 shownTreeMembers:()=>visible,teamExportRows:()=>visible,
 api:async()=>reply,
 render:()=>{renderCalls++},calls,
 requestAnimationFrame:(cb)=>cb(),document:{querySelectorAll:()=>[]},
 el:()=>null,money:(n)=>String(n/100),
};
vm.createContext(sandbox);
vm.runInContext(js.slice(begin,end),sandbox);
const evalJs=code=>vm.runInContext(code,sandbox);
evalJs("v22HistBranch={reveal:(id)=>calls.push(id)}");
evalJs("v22HistUpdateToolbar=()=>{}");
(async()=>{
 assert.strictEqual(evalJs("v22HistShift('2026-11-01',-1)"),'2026-10-31');
 assert.strictEqual(evalJs("v22HistShift('2026-12-31',1)"),'2027-01-01');
 assert.strictEqual(evalJs("v22HistShift('2026-02-30',0)"),null);
 assert.strictEqual(evalJs("v22HistMatches().length"),0);
 await evalJs("v22HistChange('new','2026-11-24')");
 assert.strictEqual(evalJs('v22HistSelected()'),'2026-11-24');
 assert.deepStrictEqual(Array.from(evalJs('v22HistMatches()'),x=>x.account),['bob','carol']);
 assert.strictEqual(calls.at(-1),'bob','Branch viewport should center first newcomer');
 assert.strictEqual(renderCalls,0,'Branch overlay should not rebuild whole UI');
 await evalJs("v22HistChange('withdraw','2026-11-24')");
 assert.strictEqual(evalJs('v22HistMode'),'withdraw');
 assert.deepStrictEqual(Array.from(evalJs('v22HistMatches()'),x=>x.account),['alice','bob']);
 assert.strictEqual(evalJs("v22HistAmounts().get('alice')"),50000);
 assert.strictEqual(evalJs("v22HistAmounts().get('bob')"),-1200);
 assert.strictEqual(calls.at(-1),'alice');
 reply={day:'2026-11-23',recorded:false,members:[],count:0};
 await evalJs("v22HistChange('withdraw','2026-11-23')");
 assert.strictEqual(evalJs('v22HistMatches().length'),0,
  'Unrecorded day MUST NOT use current-day withdrawal amounts');
 assert.strictEqual(evalJs('v22HistResult.recorded'),false);
 await evalJs("v22HistChange('withdraw','2026-11-26')");
 assert.strictEqual(evalJs('v22HistSelected()'),'2026-11-23',
  'Future date should not be selectable');
 let closed=new Set(['root','alice']);
 sandbox.testCollapsed=closed;
 evalJs("v22HistUnfold(['bob'],testCollapsed)");
 assert.strictEqual(closed.size,0,'Newcomer ancestor branch should unfold');
 visible=[members[0],members[1]];
 assert.strictEqual(evalJs('v22HistMatches().length'),0,
  'Group-scoped rows must not show unrelated historical withdrawals');
 sandbox.view='tree';
 sandbox.collapsed=new Set(['root','alice']);
 await evalJs("v22HistChange('new','2026-11-23')");
 assert.strictEqual(renderCalls>0,true,'Standard tree should render newly selected day');
 assert.strictEqual(sandbox.collapsed.has('root'),false);
 for(const part of ['v22HistoryCalendar','✨ 历史新增','🔴 历史提现',
  '前一天','后一天','昨天','今天'])assert(js.includes(part),part);
 for(const part of ['v22-hist-one-new-ring','v22-hist-one-withdraw-ring',
  "'vector-effect':'non-scaling-stroke'"])assert(js.includes(part),part);
 assert(js.includes("v22HistMode==='new'&&Number(m.daily_withdraw_cents||0)!==0"),
  'Do not contaminate yesterday history with live today red rings');
 assert(js.includes("v22HistIsWithdrawMode()?Number(historyAmounts.get(x.id)||0)"),
  'Withdrawal density must use selected historical day');
 assert(html.includes('v22-historical-browse-css'));
 assert(html.includes('outline:5px solid #ffea00'));
 assert(html.includes('outline:5px solid #ff1645'));
 assert(html.includes('prefers-reduced-motion'));
 console.log('PASS: historical calendar previous/next, one ring per node, previous-day ledger, missing-date protection and original live red overlays');
})().catch(err=>{console.error(err);process.exit(1)});
