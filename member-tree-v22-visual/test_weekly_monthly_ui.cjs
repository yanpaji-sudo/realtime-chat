// Independent week/month display regression: no browser or production DB.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const start=js.indexOf("let v22HistMode='new'");
const end=js.indexOf("\nfunction renderBranch(){",start);
assert(start>0&&end>start);
const members=[
 {id:'root',account:'root',joined_on:'2026-10-01',parent_id:null},
 {id:'alice',account:'alice',joined_on:'2026-11-23',parent_id:'root'},
 {id:'bob',account:'bob',joined_on:'2026-11-24',parent_id:'root'},
 {id:'carol',account:'carol',joined_on:'2026-11-24',parent_id:'alice'},
 {id:'dave',account:'dave',joined_on:'2026-11-05',parent_id:'root'},
];
let calls=[],requests=[],visible=members,renders=0;
const week={
 mode:'week',day:'2026-11-25',start_day:'2026-11-23',end_day:'2026-11-25',
 recorded:true,recorded_days:2,expected_days:3,missing_days:1,
 members:[
  {id:'alice',account:'alice',days:2,tier:'mid',amount_cents:140000},
  {id:'bob',account:'bob',days:1,tier:'low',amount_cents:25000}],
 count:2
};
const month={
 mode:'month',day:'2026-11-25',start_day:'2026-11-01',end_day:'2026-11-25',
 recorded:true,recorded_days:19,expected_days:25,missing_days:6,
 members:[
  {id:'alice',account:'alice',days:5,tier:'high',amount_cents:700000},
  {id:'bob',account:'bob',days:1,tier:'low',amount_cents:25000},
  {id:'carol',account:'carol',days:3,tier:'mid',amount_cents:57000}],
 count:3
};
const sandbox={
 dateNow:()=> '2026-11-25',businessDay:'2026-11-25',
 members,historyCoverage:{tracking_since:'2026-10-01'},
 view:'branch',teamFocusId:null,
 shownTreeMembers:()=>visible,teamExportRows:()=>visible,
 render:()=>{renders++},
 requestAnimationFrame:(cb)=>cb(),document:{querySelectorAll:()=>[],addEventListener:()=>{},body:{classList:{toggle:()=>{}}}},
 el:()=>null,money:v=>String(v/100),
 calls,api:async(path)=>{requests.push(path);return path.includes('mode=week')?week:month}
};
vm.createContext(sandbox);
vm.runInContext(js.slice(start,end),sandbox);
const run=code=>vm.runInContext(code,sandbox);
run("v22HistBranch={reveal:(id)=>calls.push(id)}");
run("v22HistUpdateToolbar=()=>{}");
(async()=>{
 assert.strictEqual(run("v22HistShift('2026-12-31',1)"),'2027-01-01');
 assert.strictEqual(run("v22HistStep('2026-11-25',-1)"),'2026-11-24');
 await run("v22HistChange('week','2026-11-25')");
 assert.strictEqual(run('v22HistIsOverview()'),true);
 assert.strictEqual(run('v22HistIsWithdrawMode()'),true);
 assert.strictEqual(run("v22HistStep('2026-11-25',-1)"),'2026-11-18');
 assert.strictEqual(run("v22HistStep('2026-11-25',1)"),'2026-12-02');
 assert(requests.at(-1).includes('mode=week&day=2026-11-25'));
 assert.strictEqual(run('v22HistMatches().length'),2);
 assert.strictEqual(run("v22HistFrequency().get('alice').days"),2);
 assert.strictEqual(run("v22HistFrequency().get('alice').tier"),'mid');
 assert.strictEqual(calls.at(-1),'alice');
 await run("v22HistChange('month','2026-11-25')");
 assert(requests.at(-1).includes('mode=month&day=2026-11-25'));
 assert.strictEqual(run("v22HistStep('2026-11-25',-1)"),'2026-10-01');
 assert.strictEqual(run('v22HistMatches().length'),3);
 assert.strictEqual(run("v22HistFrequency().get('alice').days"),5);
 assert.strictEqual(run("v22HistFrequency().get('alice').tier"),'high');
 assert.strictEqual(run("v22HistFrequency().get('carol').tier"),'mid');
 assert.strictEqual(run("v22HistFrequency().get('bob').tier"),'low');
 const limited=[members[0],members[1]];visible=limited;
 assert.strictEqual(run('v22HistMatches().length'),1,'Group view scope must narrow counts');
 visible=members;
 // A period without any recorded data must NOT show live withdrawals.
 month.recorded=false;month.members=[];month.count=0;
 await run("v22HistChange('month','2026-11-25')");
 assert.strictEqual(run('v22HistMatches().length'),0);
 assert.strictEqual(run('v22HistFrequency().size'),0);
 month.recorded=true;month.members=[{id:'alice',days:5,amount_cents:700000,tier:'high'}];
 await run("v22HistChange('month','2026-11-25')");
 sandbox.view='tree';sandbox.collapsed=new Set(['root','alice']);
 await run("v22HistChange('month','2026-11-25')");
 assert(renders>0,'Main tree should re-render when changing history');
 assert.strictEqual(sandbox.collapsed.has('root'),false);
 await run("v22HistChange('new','2026-11-24')");
 assert.strictEqual(run('v22HistIsOverview()'),false);
 assert.strictEqual(run('v22HistFrequency().size'),0);
 assert.strictEqual(run('v22HistMatches().length'),2);
 for(const txt of ['🟠 本周提现总览','🟣 本月提现总览',
   "'v22-hist-frequency-'+detail.tier",
   'v22-hist-account-row','v22HistStep',
   'v22HistIsWithdrawMode()'])assert(js.includes(txt),txt);
 for(const txt of ['v22-withdraw-frequency-css','#ff9b15','#a54aff',
   'attr(data-v22-hist-days)','v22-hist-count-bg-high'])assert(html.includes(txt),txt);
 assert(js.includes("if(v22HistMode==='new'){"),
   'Historical week/month should hide current-day red rings');
 assert(js.includes("'vector-effect':'non-scaling-stroke'"));
 assert(!js.includes("class:'v22-hist-count-badge'"),'Day count SVG badge is intentionally removed');
 assert(js.includes('startDensity()'));
 console.log('PASS: week/month modes, day vs week vs month stepping, 1/2-3/4+ tiers, empty periods, scoped tree, anchored badges, no live-day contamination');
})().catch(err=>{console.error(err);process.exit(1)});
