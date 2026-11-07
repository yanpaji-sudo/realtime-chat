from pathlib import Path
root=Path('member-tree')
p=root/'static/app.js'
s=p.read_text(encoding='utf-8')
needle="  ['本人充值',money(Number(m.stake_cents||0),true)],"
replacement=needle+"\n  ['本人余额',money(Number(m.balance_cents||0),true)],"
assert s.count(needle)==1, ('personal stake row changed',s.count(needle))
s=s.replace(needle,replacement,1)
original="  if(d[0]==='本人输赢')value.classList.add(Number(m.profit_cents||0)>0?'v29-green':Number(m.profit_cents||0)<0?'v29-red':'v29-neutral');"
addition="  if(d[0]==='本人余额')value.classList.add(v29Position(m).active?'v29-red':'v29-green');\n"+original
assert s.count(original)==1, ('color binding changed',s.count(original))
s=s.replace(original,addition,1)
p.write_text(s,encoding='utf-8')
(root/'tests/test_v30_balance.cjs').write_text("""const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync('static/app.js','utf8');
assert(s.includes("['本人余额',money(Number(m.balance_cents||0),true)]"),'personal balance row');
assert(s.includes("if(d[0]==='本人余额')value.classList.add(v29Position(m).active?'v29-red':'v29-green')"),'color binding');
const f=s.match(/function v29Position\\(m\\)\\{[\\s\\S]*?\\n\\}/);
assert(f,'existing position rule found');
const context={};vm.createContext(context);vm.runInContext(f[0]+';this.position=v29Position',context);
for(const [direct,balance,isRed] of [[0,12999.99,false],[0,13000,false],[0,13000.01,true],[4,18000,true],[5,20000,false],[5,20000.01,true],[9,13001,false]]){
 const r=context.position({direct_count:direct,balance_cents:Math.round(balance*100)});
 assert.equal(r.active,isRed,'direct='+direct+', balance='+balance);
}
console.log('V30 personal balance visible and red/green threshold boundary tests passed');
""",encoding='utf-8')
print('V30 tiny UI-only patch applied, database unchanged')
