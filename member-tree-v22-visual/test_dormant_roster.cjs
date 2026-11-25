// V22 read-only grouped dormant roster: full descendant history and aggregates.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const start=js.indexOf('let v22DormantPanel=null;');
const end=js.indexOf('\nfunction v22HistUpdateToolbar(){',start);
assert(start>0&&end>start&&end-start<18000,'Exact historical toolbar helper must be present');
const people=[
 {id:'root',account:'mainroot',parent_id:null,level:1,joined_on:'2025-01-01',group_account:'01',balance_cents:900},
 {id:'a',account:'a',parent_id:'root',level:2,joined_on:'2026-02-01',group_account:'01',balance_cents:250000,remark:'张一'},
 {id:'a1',account:'a1',parent_id:'a',level:3,joined_on:'2026-05-01',group_account:'01',balance_cents:130000},
 {id:'a2new',account:'a2new',parent_id:'a1',level:4,joined_on:'2026-11-05',group_account:'01',balance_cents:120000},
 {id:'b',account:'b',parent_id:'root',level:2,joined_on:'2026-04-01',group_account:'02',balance_cents:100000,remark:'李二'},
 {id:'c',account:'c',parent_id:'root',level:3,joined_on:'2026-05-01',group_account:'01',balance_cents:300000,remark:'王三'},
 {id:'c_old',account:'c_old',parent_id:'c',level:4,joined_on:'2026-08-24',group_account:'01',balance_cents:80000},
 {id:'d',account:'d',parent_id:'root',level:2,joined_on:'2026-08-25',group_account:'02',balance_cents:200000,remark:'边界会员'},
 {id:'e_new',account:'e_new',parent_id:'root',level:2,joined_on:'2026-08-26',group_account:'02',balance_cents:10000},
 {id:'phantom',account:'placeholder',parent_id:'root',level:2,joined_on:'2025-01-01',group_account:'03',balance_cents:999900,remark:'上级占位（待补资料）'},
];
function mk(tag,cls='',text=''){
 return {tag,cls,text,value:'',children:[],attrs:{},
  append(...x){this.children.push(...x);for(const child of x)child.parentElement=this},
  replaceChildren(...x){this.children=x},
  setAttribute(k,v){this.attrs[k]=v},
  addEventListener(k,fn){this['on'+k]=fn},
  remove(){this.removed=true;if(this.parentElement){
    const i=this.parentElement.children.indexOf(this);
    if(i>=0)this.parentElement.children.splice(i,1);
  }},
  focus(){this.focused=true}};
}
const classes=new Set(),body={
 children:[],append(x){this.children.push(x);x.parentElement=this},
 classList:{add(x){classes.add(x)},remove(x){classes.delete(x)}}
};
const env={
 members:people,mk,document:{body},selectedTreeGroup:'',
 v22HistToday:()=> '2026-11-25',money:n=>(n/100).toLocaleString('zh-CN'),
 v22HistMaximized:false,v22HistSetMaximized:()=>{},
};
vm.createContext(env);
vm.runInContext(js.slice(start,end),env);
const call=c=>vm.runInContext(c,env);
assert.strictEqual(call("v22DormantCutoff('2026-11-25')"),'2026-08-25');
assert.strictEqual(call("v22DormantCutoff('2025-05-31')"),'2025-02-28','Month-end clipping');
assert.strictEqual(call("v22DormantCutoff('2024-05-31')"),'2024-02-29','Leap-year clipping');
assert.strictEqual(call("v22DormantDays('2026-08-25','2026-11-25')"),92);
assert.strictEqual(call("v22DormantLevel(2)"),'A');
assert.strictEqual(call("v22DormantLevel(3)"),'B');
assert.strictEqual(call("v22DormantLevel(4)"),'C');
assert.strictEqual(call("v22DormantLevel(27)"),'Z');
assert.strictEqual(call("v22DormantLevel(28)"),'AA');
assert.strictEqual(call("v22DormantLevel(1)"),'总节点');
const result=Array.from(call("v22DormantAnalyze(members,'2026-11-25')"));
const ids=result.map(x=>x.id).sort();
assert.deepStrictEqual(ids,['b','c','c_old','d'],
 'New grandchild excludes older ancestors; recent joins and placeholder excluded');
const c=result.find(x=>x.id==='c');
assert.strictEqual(c.latest_descendant_join,'2026-08-24');
assert.strictEqual(c.descendant_count,1);
assert.strictEqual(c.level,'B');
assert.strictEqual(c.remark,'王三');
assert.strictEqual(c.balance_cents,300000);
assert.strictEqual(result.find(x=>x.id==='d').days,92);
assert.strictEqual(result.find(x=>x.id==='d').level,'A');
assert.strictEqual(result.find(x=>x.id==='b').group,'02');
assert.strictEqual(result.reduce((sum,x)=>sum+x.balance_cents,0),680000);
call('v22DormantOpen()');
assert.strictEqual(body.children.length,1,'Modal is mounted in document.body');
assert(classes.has('v22-dormant-body-open'));
assert(call('v22DormantPanel').table.children.length===5,'Header + 4 eligible rows');
const state=call('v22DormantPanel');
assert(state.heading.text.includes('4 人'));
assert(state.summary.text.includes('6,800'),'Overall balance shown for all groups');
assert(state.total.children[0].text.includes('6,800'),'Overall reconciliation sum');
const headers=state.table.children[0].children.map(x=>x.text);
assert.deepStrictEqual(headers.map(s=>s.split(' ')[0]),[
 '所属分组','会员备注','会员账号','层级','加入日期','躺平时间',
 '当前余额','历史下级数','最近下级新增'
]);
assert.deepStrictEqual(state.group.children.map(x=>x.value),['','01','02']);
state.group.value='02';
state.group.onchange();
assert(state.heading.text.includes('2 人'));
assert(state.summary.text.includes('3,000'),'Filter settlement should sum group 02 only');
assert(state.total.children[0].text.includes('3,000'));
assert.strictEqual(state.table.children.length,3,'Group 02 has 2 rows + header');
state.table.children[0].children[6].onclick();
assert.strictEqual(call("v22DormantSort"),'balance_cents');
assert.strictEqual(call("v22DormantDesc"),true);
assert.strictEqual(state.table.children[1].children[2].text,'d','Balance 2,000 first');
state.table.children[0].children[6].onclick();
assert.strictEqual(state.table.children[1].children[2].text,'b','Balance 1,000 first');
call('v22DormantClose()');
assert.strictEqual(body.children.length,0,'Overlay removed from body');
assert(!classes.has('v22-dormant-body-open'),'Original page scroll restored');
assert(js.includes("const dormant=mk('button','v22-hist-button v22-dormant-trigger','📋 躺平名单')"));
assert(js.includes('dormant.type=\\'button\\';dormant.onclick=v22DormantOpen;'));
assert(js.includes("b.append(label,newer,withdraw,week,month,dormant,prev,pick"));
assert(html.includes('id="v22-dormant-roster-style"'));
assert(html.includes('min-height:0;flex:1 1 0;overflow:auto;'));
assert(html.includes('.v22-dormant-total'));
console.log('PASS: true three-calendar-month cutoff/leap, indirect descendants, join-day inactivity, group filters, level A/B/C, account/remark/balance, sorting, overall settlement, modal lifecycle');
