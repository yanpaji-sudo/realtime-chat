'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const src=fs.readFileSync(__dirname+'/../static/app.js','utf8');
const css=fs.readFileSync(__dirname+'/../static/style.css','utf8');
const html=fs.readFileSync(__dirname+'/../static/index.html','utf8');
const start=src.indexOf('function riskForMember('),end=src.indexOf('function focusRiskTreeNode(');
const ctx={TREE_GROUPS:['01','02','03','06','08']};vm.createContext(ctx);vm.runInContext(src.slice(start,end),ctx);
const data=[
{id:'01',account:'01',parent_id:null,group_account:'01',level:1,subtree_profit_cents:500,subtree_balance_cents:10000},
{id:'01B',account:'A',parent_id:'01',group_account:'01',level:2,subtree_profit_cents:-100,subtree_balance_cents:10000},
{id:'02',account:'02',parent_id:null,group_account:'02',level:1,subtree_profit_cents:2000,subtree_balance_cents:10000},
{id:'02B',account:'B',parent_id:'02',group_account:'02',level:2,subtree_profit_cents:1800,subtree_balance_cents:10000,daily_withdraw_cents:150000},
];
const ranks=ctx.riskGroupRanking(data);
assert.equal(ranks.length,5);
assert.equal(ranks[0].group,'01');assert.equal(ranks[0].risks,2);assert.equal(ranks[0].danger,1);assert.equal(ranks[0].warning,1);
assert.equal(ranks.find(x=>x.group==='02').risks,0);
for(const id of ['riskTreeBtn','withdrawTreeBtn','aiTreeBtn'])assert(html.includes(`id="${id}"`),id);
for(const id of ['toggleRiskTree','toggleWithdrawalTree','openAIEvaluation','withdraw-glow-amount','risk-banner'])assert(src.includes(id),id);
for(const selector of ['.member.withdraw-glow','.member.risk-focus','.risk-banner','.ai-eval-dialog','.branch-canvas.branch-risk-mode'])assert(css.includes(selector),selector);
console.log('V24 independent node risk grading, five-group tally and withdrawal indicator passed');
