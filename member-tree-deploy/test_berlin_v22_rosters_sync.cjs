// Berlin review lists: pure read-only analysis from mocked member data.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const start=js.indexOf('// Berlin synchronized V22 review rosters:');
const end=js.indexOf('\nfunction berlinHistoryDateShift(value,days){',start);
assert(start>0&&end>start&&end-start<30000,'Synchronized helper must remain adjacent to calendar');
const people=[
 {id:'root',account:'root',parent_id:null,group_account:'01',joined_on:'2024-01-01',balance_cents:0},
 {id:'san',account:'san08',parent_id:'root',group_account:'08',joined_on:'2025-01-01',balance_cents:0},
 {id:'sanChild',account:'sanChild',parent_id:'san',group_account:'08',joined_on:'2026-02-01',
  balance_cents:50000,stake_cents:10000,total_withdraw_cents:5000},
 {id:'sanGrand',account:'sanGrand',parent_id:'sanChild',group_account:'08',joined_on:'2026-03-01',
  balance_cents:25000,stake_cents:50000,total_withdraw_cents:2000},
 {id:'zero',account:'zero',parent_id:'root',group_account:'02',joined_on:'2025-01-01',
  balance_cents:0,stake_cents:50000},
 {id:'zeroChild',account:'zeroChild',parent_id:'zero',group_account:'02',joined_on:'2025-06-01',
  balance_cents:40000,stake_cents:50000,total_withdraw_cents:10000},
 {id:'recentParent',account:'recentParent',parent_id:'root',group_account:'03',
  joined_on:'2025-01-01',balance_cents:90000},
 {id:'recentChild',account:'recentChild',parent_id:'recentParent',group_account:'03',
  joined_on:'2026-10-01',balance_cents:90000},
 {id:'candidate',account:'candidate',parent_id:'root',group_account:'04',
  joined_on:'2026-08-25',balance_cents:30000},
 {id:'tooYoung',account:'tooYoung',parent_id:'root',group_account:'04',
  joined_on:'2026-08-26',balance_cents:30000},
 {id:'head4',account:'head4',parent_id:'root',group_account:'05',joined_on:'2026-01-01',
  balance_cents:1500000,stake_cents:1000000,total_withdraw_cents:500000,remark:'四位直推'},
 ...[1,2,3,4].map(i=>({id:'h4'+i,account:'h4'+i,parent_id:'head4',
  group_account:'05',joined_on:'2026-03-01',balance_cents:10000,stake_cents:i*10000})),
 {id:'extra4',account:'extra4',parent_id:'h41',group_account:'05',
  joined_on:'2026-04-01',balance_cents:10000,stake_cents:20000,total_withdraw_cents:10000},
 {id:'head5',account:'head5',parent_id:'root',group_account:'06',joined_on:'2026-01-01',
  balance_cents:2000000,stake_cents:1000000,total_withdraw_cents:200000,remark:'五位直推'},
 ...[1,2,3,4,5].map(i=>({id:'h5'+i,account:'h5'+i,parent_id:'head5',
  group_account:'06',joined_on:'2026-02-01',balance_cents:10000,stake_cents:20000})),
 {id:'below5',account:'below5',parent_id:'root',group_account:'07',joined_on:'2026-01-01',
  balance_cents:1999999,stake_cents:1000000},
 ...[1,2,3,4,5].map(i=>({id:'b5'+i,account:'b5'+i,parent_id:'below5',
  group_account:'07',joined_on:'2026-02-01',balance_cents:1000,stake_cents:5000})),
 {id:'noStake',account:'noStake',parent_id:'root',group_account:'07',joined_on:'2026-01-01',
  balance_cents:3000000,stake_cents:0},
 {id:'placeholder',account:'ph',parent_id:'noStake',group_account:'07',
  joined_on:'2026-01-01',balance_cents:0,remark:'上级占位（待补资料）'}
];
const original=JSON.stringify(people);
const sandbox={members:people,dateNow:()=> '2026-11-25',TREE_GROUPS:['01','02','03','04','05','06','07','08']};
vm.createContext(sandbox);
vm.runInContext(js.slice(start,end),sandbox);
const call=src=>vm.runInContext(src,sandbox);
assert.strictEqual(call("berlinReviewCutoff('2026-11-25')"),'2026-08-25');
assert.strictEqual(call("berlinReviewCutoff('2024-05-31')"),'2024-02-29');
assert.strictEqual(call("berlinReviewAccount('san08')"),'SAN8');
assert.strictEqual(call("berlinReviewAccount('SAN008')"),'SAN8');
const flat=Array.from(call("berlinFlatlineRows('2026-11-25',members)"));
const a=flat.find(x=>x.m.account==='sanChild'),b=flat.find(x=>x.m.account==='sanGrand');
assert(a&&b,'Older SAN downstream accounts qualify when no recent descendants');
assert.strictEqual(a.label,'A','SAN direct level A');
assert.strictEqual(b.label,'B','SAN grandchild level B');
assert(!flat.find(x=>x.m.account==='san08'),'SAN group head excluded');
assert(!flat.find(x=>x.m.account==='zero'),'Zero balance excluded');
assert.strictEqual(flat.find(x=>x.m.account==='zeroChild').label,'B',
 'Unrelated zero-balance parent must NOT change its descendants tier');
assert(!flat.find(x=>x.m.account==='recentParent'),'Recent indirect downline excludes member');
assert(!flat.find(x=>x.m.account==='tooYoung'),'Must have joined at least three calendar months ago');
assert(flat.find(x=>x.m.account==='candidate'),'Exact 3-calendar-month boundary eligible');
assert.strictEqual(a.net_win_cents,5000,'Personal win/loss = stake - withdrawn');
assert.strictEqual(a.descendant_count,1,'Historical descendants count excludes self');
const loan=Array.from(call('berlinLoanRows(members)'));
const four=loan.find(x=>x.m.account==='head4'),
 five=loan.find(x=>x.m.account==='head5');
assert(four&&five,'Four and five direct cutoff both included at exact threshold');
assert.strictEqual(four.direct_count,4);
assert.strictEqual(four.target_percent,150);
assert.strictEqual(four.target_cents,1500000);
assert.strictEqual(four.umbrella_count,5,'Includes indirect descendant but excludes self');
assert.strictEqual(four.team_win_cents,610000,
 'Team win/loss is team stake - total withdrawal, with all descendants');
assert.strictEqual(five.direct_count,5);
assert.strictEqual(five.target_percent,200);
assert.strictEqual(five.target_cents,2000000);
assert.strictEqual(five.umbrella_count,5);
assert.strictEqual(five.team_win_cents,900000);
assert(!loan.find(x=>x.m.account==='below5'),'Below 200% excluded at 5 direct');
assert(!loan.find(x=>x.m.account==='noStake'),'Zero deposit excluded');
assert(!loan.find(x=>x.m.account==='ph'),'Placeholder excluded');
assert.strictEqual(JSON.stringify(people),original,'Calculations must not modify original data');
assert(js.includes('berlinFlatlineEnsure();\n berlinLoanEnsure();'));
assert(js.includes('function berlinLoanOpen()'));
assert(html.includes('id="berlin-v22-rosters-css"'));
console.log('PASS: Berlin synced V22 3-month zero-balance / SAN A-B dormancy; 150/200% 4-vs-5 direct loan; umbrella totals, signed finance, no writes');
