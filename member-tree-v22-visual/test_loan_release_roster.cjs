// V22 discharge-eligibility roster: 150% for fewer than five DIRECT children,
// 200% for five or more. Team data from descendants, display only.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const start=js.indexOf('let v22LoanPanel=null,');
const end=js.indexOf('\nfunction v22HistUpdateToolbar(){',start);
assert(start>0&&end>start&&end-start<28000,'Loan helper must be present once on history toolbar');
const people=[
 {id:'root',account:'main',parent_id:null,group_account:'01',balance_cents:100,stake_cents:100,total_withdraw_cents:0},
 {id:'a',account:'a',parent_id:'root',group_account:'01',remark:'负责人A',balance_cents:15000,stake_cents:10000,total_withdraw_cents:2000},
 ...[1,2,3,4].map(i=>({id:'a'+i,account:'a'+i,parent_id:'a',group_account:'01',
    balance_cents:100,stake_cents:i*1000,total_withdraw_cents:i===1?6000:0})),
 {id:'a11',account:'a11',parent_id:'a1',group_account:'01',balance_cents:100,stake_cents:4000,total_withdraw_cents:0},
 {id:'b',account:'b',parent_id:'root',group_account:'02',remark:'负责人B',balance_cents:19999,stake_cents:10000,total_withdraw_cents:0},
 ...[1,2,3,4,5].map(i=>({id:'b'+i,account:'b'+i,parent_id:'b',group_account:'02',balance_cents:50,stake_cents:500,total_withdraw_cents:0})),
 {id:'c',account:'c',parent_id:'root',group_account:'03',remark:'负责人C',balance_cents:20000,stake_cents:10000,total_withdraw_cents:3000},
 ...[1,2,3,4,5].map(i=>({id:'c'+i,account:'c'+i,parent_id:'c',group_account:'03',balance_cents:50,stake_cents:500,total_withdraw_cents:0})),
 {id:'d',account:'d',parent_id:'root',group_account:'04',balance_cents:20000,stake_cents:0,total_withdraw_cents:0},
 {id:'e',account:'e',parent_id:'root',group_account:'04',balance_cents:14999,stake_cents:10000,total_withdraw_cents:0},
 {id:'f',account:'f',parent_id:'root',group_account:'04',balance_cents:0,stake_cents:10000,total_withdraw_cents:0},
 {id:'g',account:'g',parent_id:'root',group_account:'05',remark:'最后一位',balance_cents:15001,stake_cents:10000,total_withdraw_cents:20000},
 {id:'p',account:'placeholder',parent_id:'g',group_account:'05',remark:'上级占位（待补资料）',balance_cents:0,stake_cents:0,total_withdraw_cents:0}
];
function mk(tag,cls='',text=''){
 return {tag,cls,text,value:'',children:[],attrs:{},
  append(...kids){this.children.push(...kids);for(const kid of kids)kid.parentElement=this},
  replaceChildren(...kids){this.children=kids},
  setAttribute(k,v){this.attrs[k]=v},
  addEventListener(k,fn){this['on'+k]=fn},
  remove(){this.removed=true;if(this.parentElement){
   const idx=this.parentElement.children.indexOf(this);
   if(idx>=0)this.parentElement.children.splice(idx,1)
  }},
  focus(){this.focused=true}};
}
const classNames=new Set(),body={children:[],
 append(x){this.children.push(x);x.parentElement=this},
 classList:{add(x){classNames.add(x)},remove(x){classNames.delete(x)}}
};
const calls={writes:0},env={
 members:people,mk,document:{body},selectedTreeGroup:'',TREE_GROUPS:['01','02','03','04','05','06'],
 v22HistMaximized:false,v22HistSetMaximized:()=>{},v22DormantPanel:null,v22DormantClose:()=>{},
 money:n=>(n/100).toLocaleString('zh-CN',{maximumFractionDigits:2}),
};
vm.createContext(env);
vm.runInContext(js.slice(start,end),env);
const call=x=>vm.runInContext(x,env);
const before=JSON.stringify(people);
const data=call('v22LoanAnalyze(members)');
const eligible=Array.from(data.eligible).map(x=>({...x})); // copy across contexts
const accounts=eligible.map(x=>x.account).sort();
assert.deepStrictEqual(accounts,['a','c','g'],'Only 150% under five and 200% at five, all with stake>0');
const a=eligible.find(x=>x.account==='a'),c=eligible.find(x=>x.account==='c'),
  g=eligible.find(x=>x.account==='g');
assert.strictEqual(a.required_percent,150);
assert.strictEqual(a.required_cents,15000);
assert.strictEqual(a.direct_count,4);
assert.strictEqual(a.umbrella_count,5,'Indirect descendant counted, own account excluded');
assert.strictEqual(a.team_win_cents,16000,'Team total from personal stake and all children minus withdrawals');
assert.strictEqual(a.remark,'负责人A');
assert.strictEqual(c.required_percent,200);
assert.strictEqual(c.direct_count,5);
assert.strictEqual(c.required_cents,20000);
assert.strictEqual(c.team_win_cents,9500);
assert.strictEqual(g.required_percent,150);
assert.strictEqual(g.team_win_cents,-10000,'Team can have an overall loss');
assert.strictEqual(g.umbrella_count,0,'Placeholder does not count as real downline');
assert.strictEqual(g.ratio,150.01);
assert(!eligible.some(x=>['b','d','e','f'].includes(x.account)),
  'Below 200%, no deposits, below 150%, or zero balance do not qualify');
assert.strictEqual(JSON.stringify(people),before,'No writes or modifications of underlying membership data');
call('v22LoanOpen()');
assert.strictEqual(body.children.length,1);
assert(classNames.has('v22-loan-body-open'));
let panel=call('v22LoanPanel');
assert(panel.heading.textContent.includes('3 人'));
assert(panel.summary.textContent.includes('500'),'Eligible balances displayed in summary');
assert.strictEqual(panel.table.children.length,4,'Header + three eligible records');
const headers=panel.table.children[0].children.map(x=>x.text.split(' ')[0]);
assert.deepStrictEqual(headers,['所属分组','会员备注','会员账号','直属下级','伞下总人数',
 '建仓资金','当前仓位余额','适用标准','达标余额','伞下整体输赢','余额/建仓比例']);
assert(panel.table.children.some(x=>x.children?.[2]?.text==='g'&&
 x.children[9].cls==='v22-loan-loss'),'Negative team total marked red');
assert.deepStrictEqual(panel.group.children.map(x=>x.value),['','01','02','03','04','05','06']);
panel.group.value='02';panel.group.onchange();
assert(panel.heading.textContent.includes('0 人'),'Group with no eligible account remains selectable');
assert(panel.table.children.length===1);
panel.group.value='03';panel.group.onchange();
assert(panel.heading.textContent.includes('1 人'));
assert(panel.summary.textContent.includes('200'),'Group current balance sum matches single candidate');
panel.table.children[0].children[9].onclick();
assert.strictEqual(call('v22LoanSort'),'team_win_cents');
panel.group.value='';panel.group.onchange();
assert.strictEqual(panel.table.children[1].children[2].text,'a',
 'Team win/loss sorts signed numeric descending');
call('v22LoanClose()');
assert.strictEqual(body.children.length,0);
assert(!classNames.has('v22-loan-body-open'));
assert(js.includes("const loan=mk('button','v22-hist-button v22-loan-trigger','💰 放款名单')"));
assert(js.includes("b.append(label,newer,withdraw,week,month,dormant,loan,prev,pick") ||
       js.includes("b.append(label,newer,withdraw,week,month,dormant,loan,follow,prev,pick"),
       "Existing dormant and loan buttons remain, optionally with follow-up button");
assert(html.includes('id="v22-loan-roster-style"'));
assert.strictEqual(JSON.stringify(people),before,'Opening and filtering display must not change financial fields');
console.log('PASS: V22 read-only release eligibility 150% (<5 direct), 200% (>=5 direct), all descendants and signed P/L, accounts/notes/current balance/group filters/finance unchanged');
