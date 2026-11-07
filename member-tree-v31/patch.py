from pathlib import Path
root=Path("member-tree")
p=root/"static/app.js"
js=p.read_text(encoding="utf-8")
before="""function v29Position(m){
 const threshold=(Number(m.direct_count||0)>=5?20000:13000)*100;
 const cents=Math.max(0,Number(m.balance_cents||0)-threshold);
 return {active:Number.isFinite(cents)&&cents>0,cents,threshold};
}"""
after="""function v29Position(m){
 // V31: stake exactly 5,000 uses the 7,000 balance threshold for all direct counts.
 // Stakes below 5,000 (and other stake amounts) retain the 10,000-stake
 // rule: 13,000 (<5 direct), 20,000 (>=5 direct).
 // All amounts are cents. Display only; this does not execute payouts.
 const stake=Number(m.stake_cents||0);
 const threshold=stake===500000?700000:(Number(m.direct_count||0)>=5?2000000:1300000);
 const balance=Number(m.balance_cents||0);
 const cents=Number.isFinite(balance)?Math.max(0,balance-threshold):0;
 return {active:cents>0,cents,threshold};
}"""
assert js.count(before)==1, "V31 original position rule changed"
js=js.replace(before,after,1)
old="showToast(positionAlarmOn?'仓位告警已开启：直属不足5人余额超过13000；直属至少5人余额超过20000':'仓位告警已关闭');"
new="showToast(positionAlarmOn?'仓位告警已开启：5000仓位告警线7000；其他仓位按直属人数分档13000或20000':'仓位告警已关闭');"
assert js.count(old)==1, "V31 toggle description changed"
js=js.replace(old,new,1)
p.write_text(js,encoding="utf-8")
t=root/"tests/test_v29_position_alert.cjs"
ss=t.read_text(encoding="utf-8")
anchor='assert(js.includes("(Number(m.direct_count||0)>=5?20000:13000)*100"));'
replacement='assert(js.includes("stake===500000?700000:(Number(m.direct_count||0)>=5?2000000:1300000)"));'
assert ss.count(anchor)==1, "V29 legacy test anchor changed"
ss=ss.replace(anchor,replacement,1)
old_balance_check="assert(js.includes('Number(m.balance_cents||0)-threshold'));"
new_balance_check="assert(js.includes('Math.max(0,balance-threshold)'));"
assert ss.count(old_balance_check)==1, "V29 balance test anchor changed"
ss=ss.replace(old_balance_check,new_balance_check,1)
t.write_text(ss,encoding="utf-8")
(root/"tests/test_v31_stake_threshold.cjs").write_text(r'''const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync('static/app.js','utf8');
const f=s.match(/function v29Position\(m\)\{[\s\S]*?\n\}/);
assert(f,'position rule function missing');
const sandbox={};
vm.createContext(sandbox);
vm.runInContext(f[0]+';this.check=v29Position',sandbox);
const cases=[
  [5000,0,7000,7000,0,false],
  [5000,0,7000.01,7000,0.01,true],
  [5000,4,12000,7000,5000,true],
  [5000,5,7000,7000,0,false],
  [5000,7,18000,7000,11000,true],
  [10000,0,13000,13000,0,false],
  [10000,4,13000.01,13000,0.01,true],
  [10000,4,18000,13000,5000,true],
  [10000,5,20000,20000,0,false],
  [10000,5,20000.01,20000,0.01,true],
  [0,0,13000,13000,0,false],
  [3000,0,13100,13000,100,true],
  [4999,4,12999,13000,0,false],
  [4999,5,18000,20000,0,false],
  [4000,6,21500,20000,1500,true],
  [15000,4,13001,13000,1,true],
  [20000,5,21000,20000,1000,true],
];
for(const [stake,direct,balance,threshold,amount,active] of cases){
  const got=sandbox.check({
    stake_cents:Math.round(stake*100),
    direct_count:direct,
    balance_cents:Math.round(balance*100)
  });
  const desc='stake='+stake+' direct='+direct;
  assert.equal(got.threshold,Math.round(threshold*100),'threshold '+desc);
  assert.equal(got.cents,Math.round(amount*100),'suggestion '+desc);
  assert.equal(got.active,active,'alert '+desc);
}
assert(s.includes("if(d[0]==='本人余额')value.classList.add(v29Position(m).active?'v29-red':'v29-green')"),'own balance color uses shared threshold');
assert(s.includes('suggest+=v29Position(x).cents'),'team aggregate suggestion uses shared threshold');
assert(s.includes('const warn=v29Position(m)'),'SVG rings use shared threshold');
console.log('V31 threshold, alert, suggested amount and coloring: 17 cases passed');
''',encoding="utf-8")
print('V31 applied: only frontend position-threshold logic and tests changed.')
