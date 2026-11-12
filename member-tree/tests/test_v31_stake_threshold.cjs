const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync('static/app.js','utf8');
const f=s.match(/function v29Position\(m\)\{[\s\S]*?\n\}/);
assert(f,'position rule missing');
const c={};vm.createContext(c);
vm.runInContext('let positionAlarmById=null;\n'+f[0]+';this.check=v29Position',c);
const cases=[
 [5000,0,7500,7500,7000,500,false],
 [5000,0,7500.01,7500,7000,500.01,true],
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
