const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const js=fs.readFileSync('static/app.js','utf8');
const html=fs.readFileSync('static/index.html','utf8');
const css=fs.readFileSync('static/style.css','utf8');
const f=js.match(/function v29Position\(m\)\{[\s\S]*?\n\}/);
assert(f,'Individual V40 alert calculator missing');
const context={};
vm.createContext(context);
vm.runInContext('let positionAlarmById=null;\n'+f[0]+';this.calc=v29Position;',context);
const cases=[
 [100,120,false,0,130],
 [100,130,true,100,130],
 [100,140,true,100,130],
 [5000,6499.99,false,0,6500],
 [5000,6500,true,5000,6500],
 [10000,14000,true,10000,13000],
 [123.45,160.48,false,0,160.49],
 [123.45,160.49,true,123.45,160.49],
 [0,1000,false,0,0],
 [20000,26000,true,20000,26000]
];
for(const [stake,balance,expected,amount,trigger] of cases){
 for(const direct of [0,1,5,20]){
  const result=context.calc({
   id:'test',stake_cents:Math.round(stake*100),
   balance_cents:Math.round(balance*100),direct_count:direct
  });
  assert.equal(result.active,expected,'alert '+JSON.stringify({stake,balance,direct}));
  assert.equal(result.cents,Math.round(amount*100),'suggestion stake '+stake);
  assert.equal(result.trigger,Math.round(trigger*100),'trigger stake '+stake);
 }
}
vm.runInContext('positionAlarmById=new Map([["test",{suggest_cents:10000,started_on:"2026-11-09",remaining_days:2}]])',context);
const live=context.calc({id:'test',stake_cents:10000,balance_cents:14000});
assert.equal(live.active,true);
assert.equal(live.cents,10000);
vm.runInContext('positionAlarmById=new Map()',context);
assert.equal(context.calc({id:'test',stake_cents:10000,balance_cents:14000}).active,false);
for(const marker of [
 'function openEdit(m=null)',
 "el('editStake').value=m?String(m.stake_cents/100):'10000'",
 "stake:el('editStake').value",
 '全部层级：本人余额≥本人建仓×130%',
 'suggest+=warn.cents',
 '130%线',
 'function academySendChat',
 '严格课程模式',
 'v33AlertPanel'
])assert(js.includes(marker),'missing existing or new function: '+marker);
assert(html.includes('min="0.01"'),'manual positive stake input disabled');
assert(html.includes('可输入任意有效正金额'),'manual free stake editor disabled');
assert(html.includes('所有层级按本人建仓金额×130%黄色报警'),'html hover description not updated');
assert(css.includes('/* Whale-only V40: YELLOW warning'));
assert(css.includes('stroke:#facc15!important'));
assert(css.includes('.v33-alarm-overdue{border-color:#dc2626!important'));
console.log('Whale V40: 40 130% browser boundary cases, all-level stake input, yellow badges, overdue red and AI Academy passed');
