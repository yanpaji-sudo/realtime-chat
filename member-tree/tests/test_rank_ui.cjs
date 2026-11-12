const fs=require('fs');const vm=require('vm');const assert=require('assert');
const src=fs.readFileSync(__dirname+'/../static/app.js','utf8');
const start=src.indexOf('function membershipMonths('),end=src.indexOf('function showToast(',start);
assert(start>=0&&end>start);
const ctx={};vm.createContext(ctx);vm.runInContext(src.slice(start,end),ctx);
const rows=[
{id:'a',parent_id:null,account:'A',group_account:'A',joined_on:'2026-11-05',level:1,stake_cents:1000000,daily_withdraw_cents:100000},
{id:'b',parent_id:'a',account:'B',group_account:'A',joined_on:'2026-10-01',level:2,stake_cents:500000,daily_withdraw_cents:10000},
{id:'c',parent_id:'a',account:'C',group_account:'A',joined_on:'2026-10-02',level:2,stake_cents:500000,daily_withdraw_cents:200000},
{id:'d',parent_id:'b',account:'D',group_account:'A',joined_on:'2026-11-05',level:3,stake_cents:500000,daily_withdraw_cents:10000},
{id:'e',parent_id:'d',account:'E',group_account:'A',joined_on:'2026-11-05',level:4,stake_cents:1000000,daily_withdraw_cents:0},
{id:'f',parent_id:'c',account:'F',group_account:'A',joined_on:'2026-11-04',level:3,stake_cents:1000000,daily_withdraw_cents:10000},
{id:'z',parent_id:null,account:'Z',group_account:'Z',joined_on:'2026-10-01',level:1,stake_cents:500000,daily_withdraw_cents:0},
{id:'z2',parent_id:'z',account:'Z2',group_account:'Z',joined_on:'2026-11-05',level:2,stake_cents:500000,daily_withdraw_cents:0}
];
let result=ctx.computeRanking(rows,'2026-11-05');
assert.deepEqual(Array.from(result.map(x=>x.account)),['B','Z2','C']);
assert.equal(result[0].dailyStake,1500000);assert.equal(result[0].dailyWithdraw,20000);assert.equal(result[0].score,1480000);
assert.equal(result[0].newCount,2);assert.equal(result[0].teamCount,3);
assert.equal(result[1].score,500000);assert.equal(result[2].score,-210000);
assert(result.every(x=>x.account!=='A'&&x.account!=='D'));
let next=ctx.computeRanking(rows.map(x=>({...x,daily_withdraw_cents:0})),'2026-11-06');
assert(next.every(x=>x.score===0));
assert.equal(ctx.membershipMonths('2026-11-05','2026-11-05'),0);
assert.equal(ctx.membershipMonths('2026-10-05','2026-11-05'),1);
assert.equal(ctx.membershipMonths('2026-05-05','2026-11-05'),6);
assert.equal(ctx.membershipMonths('2024-01-01','2026-11-05'),6);
assert.equal(ctx.membershipMonths('2026-10-20','2026-11-05'),0);
console.log('rank UI rules OK');
