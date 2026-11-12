const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync('static/app.js','utf8');
const css=fs.readFileSync('static/style.css','utf8');
assert(s.includes("new Map(Object.entries(d.position_alerts||{}))"));
assert(s.includes("positionAlarmOn)host.append(v33AlertPanel(shownRows))"));
assert(s.includes("positionAlarmOn)outer.append(v33AlertPanel(shownTreeMembers()))"));
assert(s.includes('over?'+'' )===false||s.includes('已超期'));
assert(s.includes("suggest+=warn.cents"));
assert(css.includes('.v33-alarm-sidebar'));
const a=s.indexOf('function v33ActiveRankingMembers('),b=s.indexOf('function renderRanking(){',a);
assert(a>0&&b>a);
const part=s.slice(a,b);
const sandbox={};
vm.createContext(sandbox);
vm.runInContext(
 "const periodAmounts=(m,day,period)=>({deposit:period==='week'&&m.newFlag?m.stake_cents:0,withdraw:m.week_withdraw_cents||0});\n"+
 part+"\nthis.filter=v33ActiveRankingMembers;",sandbox);
const rows=[
 {id:'one',account:'leader',parent_id:null,level:2,stake_cents:1000,newFlag:false,week_withdraw_cents:0},
 {id:'two',account:'deposit',parent_id:'one',level:3,stake_cents:1000,newFlag:true,week_withdraw_cents:0},
 {id:'three',account:'withdraw',parent_id:'two',level:4,stake_cents:1000,newFlag:false,week_withdraw_cents:200},
 {id:'four',account:'inactive',parent_id:'two',level:4,stake_cents:1000,newFlag:false,week_withdraw_cents:0},
 {id:'five',account:'other-team',parent_id:null,level:2,stake_cents:1000,newFlag:true,week_withdraw_cents:300}
];
assert.deepEqual(Array.from(sandbox.filter({id:'one'},rows,'2026-11-08','week'),x=>x.member.account),['deposit','withdraw']);
console.log('V33 ranking detailed member filter and alert list state tests passed');
