'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync(__dirname+'/../static/app.js','utf8');
const css=fs.readFileSync(__dirname+'/../static/style.css','utf8');
const start=js.indexOf('function membershipMonths('),end=js.indexOf('function showToast(',start);
assert(start>=0&&end>start);
const context={document:undefined}; vm.createContext(context); vm.runInContext(js.slice(start,end),context);
const sample=[
 {id:'root',parent_id:null,account:'01',level:1,joined_on:'2026-11-01',stake_cents:100000,balance_cents:600000,total_withdraw_cents:0,daily_withdraw_cents:0},
 {id:'b',parent_id:'root',account:'B',group_account:'01',level:2,joined_on:'2026-11-02',stake_cents:200000,balance_cents:110001,total_withdraw_cents:0,daily_withdraw_cents:10000,team_name:'青云战队'},
 {id:'c',parent_id:'root',account:'C',group_account:'01',level:2,joined_on:'2026-11-05',stake_cents:100000,balance_cents:40002,total_withdraw_cents:300000,daily_withdraw_cents:250000},
 {id:'d',parent_id:'b',account:'D',level:3,joined_on:'2026-11-05',stake_cents:300000,balance_cents:220004,total_withdraw_cents:0,daily_withdraw_cents:5000},
 {id:'e',parent_id:'d',account:'E',level:4,joined_on:'2026-11-05',stake_cents:500000,balance_cents:330006,total_withdraw_cents:0,daily_withdraw_cents:5000},
 ];
const rows=context.computeRanking(sample,'2026-11-05','total');
const B=rows.find(x=>x.account==='B'),C=rows.find(x=>x.account==='C');
assert.equal(B.teamBalance,660011,'team total balance includes self and all levels');
assert.equal(C.teamBalance,40002,'other second tier stays isolated');
assert.equal(B.layers.find(x=>x.level===4).balance,330006,'detail includes deep balance');
assert.equal(B.layers.length,3);
for (const x of ['团队总余额','ranking-fullscreen-btn','rankingFullscreenBtn','ranking-number','entry.teamBalance','amountClass(entry.score,\'profit\')']) assert(js.includes(x),'expected JS '+x);
for (const x of ['.ranking-table .ranking-number','max-height:none','ranking-fullscreen-btn','.panel:fullscreen .v12-ranking']) assert(css.includes(x),'expected CSS '+x);
assert(js.includes("'tree','branch','report','ranking'"),'fullscreen rank view supported');
assert(js.includes('cell.colSpan=10')&&js.includes('td.colSpan=10'),'new table column colspan adjusted');
console.log('V18 ranking full-depth balances, colors, numeric alignment, and fullscreen checks passed');
