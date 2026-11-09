const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const js=fs.readFileSync('static/app.js','utf8');
const html=fs.readFileSync('static/index.html','utf8');
const css=fs.readFileSync('static/style.css','utf8');
const f=js.match(/function v29Position\(m\)\{[\s\S]*?\n\}/);
assert(f,'Whale V42 member calculator missing');
const context={};vm.createContext(context);
vm.runInContext('let positionAlarmById=null;\n'+f[0]+';this.calc=v29Position;',context);
const cases=[
 [100,120,false,0,130],
 [100,130,false,0,130],
 [100,130.01,true,.01,130],
 [100,160,true,30,130],
 [5000,6500,false,0,6500],
 [5000,7000,true,500,6500],
 [10000,13000,false,0,13000],
 [10000,18000,true,5000,13000],
 [123.45,160.48,false,0,160.48],
 [123.45,160.49,true,.01,160.48],
 [0,1000,false,0,0],
 [20000,26000,false,0,26000],
 [20000,29000,true,3000,26000]
];
for(const [stake,balance,expected,amount,limit] of cases){
 for(const direct of [0,1,5,20]){
  const result=context.calc({id:'test',stake_cents:Math.round(stake*100),
     balance_cents:Math.round(balance*100),direct_count:direct});
  assert.equal(result.active,expected,'alert '+JSON.stringify({stake,balance,direct}));
  assert.equal(result.cents,Math.round(amount*100),'minimum excess '+stake);
  assert.equal(result.trigger,Math.round(limit*100),'130% boundary '+stake);
 }
}
vm.runInContext('positionAlarmById=new Map([["test",{suggest_cents:1000000,started_on:"2026-11-09",remaining_days:2}]])',context);
assert.equal(context.calc({id:'test',stake_cents:1000000,balance_cents:1800000}).cents,500000);
assert.equal(context.calc({id:'test',stake_cents:1000000,balance_cents:1300000}).active,false,
 'old server alert should not persist after balance reaches 130%');
vm.runInContext('positionAlarmById=new Map()',context);
assert.equal(context.calc({id:'test',stake_cents:1000000,balance_cents:1800000}).active,true,
 'stale missing server state should not suppress warning');
for(const marker of [
 'function openEdit(m=null)',
 "el('editStake').value=m?String(m.stake_cents/100):'10000'",
 "stake:el('editStake').value",
 '全部层级：本人余额超过建仓×130%',
 'suggest+=warn.cents',
 '130%线',
 'function academySendChat',
 '严格课程模式',
 'v33AlertPanel'
])assert(js.includes(marker),'missing required function: '+marker);
assert(html.includes('min="0.01"'));
assert(html.includes('可输入任意有效正金额'));
assert(html.includes('所有层级余额超过本人建仓×130%黄色报警'));
assert(css.includes('/* Whale-only V42: YELLOW warning'));
assert(css.includes('stroke:#facc15!important'));
assert(css.includes('.v33-alarm-overdue{border-color:#dc2626!important'));
console.log('Whale V42: tested strict >130%, 18000-13000=5000, exact boundary, auto clear, all depths, Academy');
