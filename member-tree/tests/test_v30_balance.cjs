const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
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
