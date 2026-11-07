from pathlib import Path
root=Path('member-tree')
js=(root/'static/app.js').read_text(encoding='utf-8')
v29=root/'tests/test_v29_position_alert.cjs'
s=v29.read_text(encoding='utf-8')
replacements={
 "stake===500000?700000:(Number(m.direct_count||0)>=5?2000000:1300000)": "const trigger=stake===500000?750000:stake<=1000000?1500000",
 "Math.max(0,balance-threshold)": "Math.max(0,balance-target)",
 "suggest+=v29Position(x).cents": "suggest+=warn.cents",
}
for old,new in replacements.items():
    if old in s:s=s.replace(old,new)
v29.write_text(s,encoding='utf-8')
(root/'tests/test_v30_balance.cjs').write_text(r'''const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync('static/app.js','utf8');
assert(s.includes("['本人余额',money(Number(m.balance_cents||0),true)]"),'personal balance row');
assert(s.includes("if(d[0]==='本人余额')value.classList.add(v29Position(m).active?'v29-red':'v29-green')"),'color binding');
const f=s.match(/function v29Position\(m\)\{[\s\S]*?\n\}/);
assert(f,'position rule found');
const c={};vm.createContext(c);
vm.runInContext('let positionAlarmById=null;\n'+f[0]+';this.position=v29Position',c);
for(const [stake,direct,balance,isRed] of [
 [5000,0,7500,false],[5000,0,7500.01,true],[5000,7,8200,true],
 [10000,0,15000,false],[10000,4,15000.01,true],
 [10000,5,15000,false],[10000,7,15000.01,true],
 [3000,1,15000,false],[3000,1,15000.01,true],
 [16000,5,20000,false],[16000,5,20000.01,true]
]){
 const got=c.position({stake_cents:Math.round(stake*100),direct_count:direct,balance_cents:Math.round(balance*100)});
 assert.equal(got.active,isRed,'stake '+stake+' direct '+direct+' balance '+balance);
}
console.log('V30 compact personal balance color uses current V33 warning rule, 11 boundaries passed');
''',encoding='utf-8')
(root/'tests/test_v31_stake_threshold.cjs').write_text(r'''const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync('static/app.js','utf8');
const f=s.match(/function v29Position\(m\)\{[\s\S]*?\n\}/);
assert(f,'position rule missing');
const c={};vm.createContext(c);
vm.runInContext('let positionAlarmById=null;\n'+f[0]+';this.check=v29Position',c);
const cases=[
 [5000,0,7500,7500,7000,500,false],
 [5000,0,7500.01,7500,7000,750.01,true],
 [5000,5,9000,7500,7000,2000,true],
 [10000,0,15000,15000,13000,2000,false],
 [10000,0,16000,15000,13000,3000,true],
 [10000,6,15001,15000,13000,2001,true],
 [3000,0,15000,15000,13000,2000,false],
 [3000,0,15001,15000,13000,2001,true],
 [20000,0,13001,13000,13000,1,true],
 [20000,5,20000,20000,20000,0,false],
 [20000,5,21000,20000,20000,1000,true]
];
for(const [stake,direct,balance,trigger,target,amount,active] of cases){
 const r=c.check({stake_cents:stake*100,direct_count:direct,balance_cents:Math.round(balance*100)});
 assert.equal(r.trigger,trigger*100,'trigger stake '+stake);
 assert.equal(r.threshold,target*100,'target stake '+stake);
 assert.equal(r.cents,Math.round(amount*100),'suggestion stake '+stake);
 assert.equal(r.active,active,'glow stake '+stake);
}
assert(s.includes('const live=positionAlarmById&&positionAlarmById.get(m.id)'));
assert(s.includes('const active=positionAlarmById!==null?Boolean(live)'));
assert(s.includes("if(d[0]==='本人余额')value.classList.add(v29Position(m).active?'v29-red':'v29-green')"));
assert(s.includes('suggest+=warn.cents'));
console.log('V31/V33 warning trigger differs from target, historical alert status and payout suggestions pass');
''',encoding='utf-8')
print('V33 upgraded regression tests to warning-trigger vs suggestion target semantics.')
