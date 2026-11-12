const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(__dirname+'/../static/app.js','utf8');
const part=src.slice(src.indexOf('function amountClass('),src.indexOf('function showToast('));
const ctx={};vm.createContext(ctx);vm.runInContext(part,ctx);
const color=(n,type)=>ctx.amountClass(n,type);
assert.equal(color(0,'daily'),'amount-black');
assert.equal(color(100,'daily'),'amount-red');
assert.equal(color(-100,'daily'),'amount-red');
assert.equal(color(100,'profit'),'amount-green');
assert.equal(color(-100,'profit'),'amount-red');
assert.equal(color(0,'profit'),'amount-black');
assert.equal(color(100,'normal'),'amount-black');
assert.equal(color(-100,'normal'),'amount-red');
const rows=[
 {id:'A',parent_id:null,account:'A',joined_on:'2026-02-01',level:1},
 {id:'B',parent_id:'A',account:'B',joined_on:'2026-11-05',level:2},
 {id:'C',parent_id:'A',account:'C',joined_on:'2026-10-01',level:2},
 {id:'D',parent_id:'B',account:'D',joined_on:'2026-11-05',level:3},
 {id:'E',parent_id:'D',account:'E',joined_on:'2026-11-05',level:4},
 {id:'F',parent_id:'C',account:'F',joined_on:'2026-11-04',level:3},
];
let by=ctx.todaysNewByNode(rows,'2026-11-05');
assert.equal(by.get('A').total,3); // root includes every generation, exactly once
assert.equal(by.get('A').byLevel.get(2),1);
assert.equal(by.get('A').byLevel.get(3),1);
assert.equal(by.get('A').byLevel.get(4),1);
assert.equal(by.get('B').total,3);
assert.equal(by.get('B').own,1);
assert.equal(by.get('C').total,0);
assert.equal(by.get('D').total,2);
assert.equal(by.get('E').total,1);
by=ctx.todaysNewByNode(rows,'2026-11-06');
assert([...by.values()].every(v=>v.total===0)); // after midnight no older new-signup highlight
assert.equal(ctx.membershipMonths('2026-05-05','2026-11-05'),6);
console.log('V7 display: colors, depth totals, tomorrow rollover OK');
