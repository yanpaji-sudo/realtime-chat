const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const js=fs.readFileSync('static/app.js','utf8');
const html=fs.readFileSync('static/index.html','utf8');
const css=fs.readFileSync('static/style.css','utf8');
const f=js.match(/function v29Position\(m\)\{[\s\S]*?\n\}/);
assert(f,'Whale alert calculator missing');
const context={};vm.createContext(context);
vm.runInContext('let positionAlarmById=null;\n'+f[0]+';this.calc=v29Position;',context);
const cases=[
 [100,120,false,0,150],
 [100,150,false,0,150],
 [100,150.01,true,.01,150],
 [100,160,true,10,150],
 [5000,7500,false,0,7500],
 [5000,8000,true,500,7500],
 [10000,16000,true,1000,15000],
 [123.45,185.17,false,0,185.17],
 [123.45,185.18,true,.01,185.17],
 [0,1000,false,0,0],
 [20000,30000,false,0,30000],
 [20000,32000,true,2000,30000]
];
for(const [stake,balance,expected,amount,limit] of cases){
 for(const direct of [0,1,5,20]){
  const result=context.calc({id:'test',stake_cents:Math.round(stake*100),
     balance_cents:Math.round(balance*100),direct_count:direct});
  assert.equal(result.active,expected,'alert '+JSON.stringify({stake,balance,direct}));
  assert.equal(result.cents,Math.round(amount*100),'minimum release '+stake);
  assert.equal(result.trigger,Math.round(limit*100),'150% boundary '+stake);
 }
}
vm.runInContext('positionAlarmById=new Map([["test",{suggest_cents:10000,started_on:"2026-11-09",remaining_days:2}]])',context);
assert.equal(context.calc({id:'test',stake_cents:10000,balance_cents:16000}).cents,1000);
assert.equal(context.calc({id:'test',stake_cents:10000,balance_cents:15000}).active,false,
 'stale server alarm must not prevent immediate clearing at 150%');
vm.runInContext('positionAlarmById=new Map()',context);
assert.equal(context.calc({id:'test',stake_cents:10000,balance_cents:16000}).active,true,
 'no cached server alarm must not hide excess current balance');
for(const marker of [
 'function openEdit(m=null)',
 "el('editStake').value=m?String(m.stake_cents/100):'10000'",
 "stake:el('editStake').value",
 '全部层级：本人余额超过建仓×150%',
 'suggest+=warn.cents',
 '150%线',
 'function academySendChat',
 '严格课程模式',
 'v33AlertPanel'
])assert(js.includes(marker),'missing existing/new function: '+marker);
assert(html.includes('min="0.01"'));
assert(html.includes('可输入任意有效正金额'));
assert(html.includes('所有层级余额超过本人建仓×150%黄色报警'));
assert(css.includes('/* Whale-only V41: YELLOW warning'));
assert(css.includes('stroke:#facc15!important'));
assert(css.includes('.v33-alarm-overdue{border-color:#dc2626!important'));
console.log('Whale V41: strict >150% browser boundaries, exact minimum release, immediate clearing, all levels, Academy OK');
