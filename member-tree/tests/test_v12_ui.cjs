const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(__dirname+'/../static/app.js','utf8');
const a=src.indexOf('function weekStart('),b=src.indexOf('function showToast(',a);
assert(a>0&&b>a);
const ctx={amountClass:(v,t)=> v<0?'amount-red':v>0?'amount-green':'amount-black'};
vm.createContext(ctx);vm.runInContext(src.slice(a,b),ctx);
// The Friday stays in the Monday-starting calendar week.
assert.equal(ctx.weekStart('2026-11-06'),'2026-11-02');
assert.equal(ctx.periodStart('2026-11-06','month'),'2026-11-01');
const rows=[
{id:'a',parent_id:null,account:'A',group_account:'A',joined_on:'2026-11-01',level:1,stake_cents:1000000,total_withdraw_cents:0},
{id:'b',parent_id:'a',account:'B',group_account:'A',joined_on:'2026-11-02',level:2,stake_cents:500000,total_withdraw_cents:30000,daily_withdraw_cents:20000,week_withdraw_cents:30000,month_withdraw_cents:30000,balance_cents:1500000},
{id:'c',parent_id:'b',account:'C',group_account:'A',joined_on:'2026-11-05',level:3,stake_cents:500000,total_withdraw_cents:5000,daily_withdraw_cents:0,week_withdraw_cents:5000,month_withdraw_cents:5000,balance_cents:1000000},
{id:'d',parent_id:'c',account:'D',group_account:'A',joined_on:'2026-11-06',level:4,stake_cents:500000,total_withdraw_cents:0,daily_withdraw_cents:0,week_withdraw_cents:0,month_withdraw_cents:0,balance_cents:500000},
{id:'e',parent_id:'d',account:'E',group_account:'A',joined_on:'2026-11-06',level:5,stake_cents:500000,total_withdraw_cents:0,daily_withdraw_cents:0,week_withdraw_cents:0,month_withdraw_cents:0,balance_cents:2000000}
];
const w=ctx.computeRanking(rows,'2026-11-06','week');
assert.equal(w.length,1);
assert.equal(w[0].account,'B');
assert.equal(w[0].dailyStake,2000000);
assert.equal(w[0].dailyWithdraw,35000);
assert.equal(w[0].score,1965000);
assert.equal(w[0].layers.length,4); // levels 2,3,4,5
assert.equal(w[0].layers[3].level,5);
assert.equal(ctx.computeRanking(rows,'2026-11-06','daily')[0].dailyStake,1000000);
assert.equal(ctx.computeRanking(rows,'2026-11-06','total')[0].dailyWithdraw,35000);
const summaries=ctx.teamSummaryByNode(rows,'2026-11-06');
assert.equal(summaries.get('b').count,4);
assert.equal(summaries.get('b').todayCount,2);
assert.equal(summaries.get('b').monthCount,4);
assert.equal(summaries.get('b').balance,5000000);
assert.equal(ctx.summaryTone(1200000,1300000,false,true),'amount-green');
assert.equal(ctx.summaryTone(1400000,1300000,false,true),'amount-red');
assert.equal(ctx.summaryTone(1.5,1.5,true),'amount-black');
assert.equal(ctx.summaryTone(0,1.5,true),'amount-black');
console.log('V12 week/month/deep layers and all-node team metrics passed');
