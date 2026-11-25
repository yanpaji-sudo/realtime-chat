// Test actual V22 popup DOM generation and user-click sort handlers (no DB).
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const start=js.indexOf('let v22HistListSortField=');
const end=js.indexOf('function v22HistIsOverview(){',start);
assert(start>0&&end>start);
const listStart=js.indexOf(' t.list.replaceChildren();',end);
const listEnd=js.indexOf(' if(matches.length>maxRows)',listStart);
assert(listStart>0&&listEnd>listStart&&listEnd-listStart<5200,
 'Must test real popup rendering fragment');
function mk(tag,cls='',text=''){
 return {tag,cls,text,children:[],attrs:{},
  append(...items){this.children.push(...items)},
  replaceChildren(){this.children=[]},
  setAttribute(key,value){this.attrs[key]=value}};
}
let touched=false;
const people=[
 {id:'a',account:'wlb841216',remark:'王女士',joined_on:'2026-11-13',balance_cents:508000},
 {id:'b',account:'beiying007',remark:'',joined_on:'2026-11-14',balance_cents:1200000},
 {id:'c',account:'abc12',remark:'测试姓名',joined_on:'2026-11-15',balance_cents:75000}
];
const details=new Map([
 ['a',{days:1,tier:'low',amount_cents:1007000}],
 ['b',{days:3,tier:'mid',amount_cents:467600}],
 ['c',{days:2,tier:'mid',amount_cents:1300000}]
]);
const context={
 v22HistMode:'month',matches:people,
 frequency:details,amounts:new Map(),
 t:{list:mk('div')},mk,
 v22HistIsOverview(){return this.v22HistMode==='week'||this.v22HistMode==='month'},
 money:(cents)=>Number(cents/100).toLocaleString('en-US',{minimumFractionDigits:0,maximumFractionDigits:2}),
 document:{addEventListener:()=>{},body:{classList:{toggle:()=>{}}}},
 v22HistFocus:()=>{touched=true}
};
// Prefer lexical closure over host 'this' for the helper's globals.
vm.createContext(context);
vm.runInContext(js.slice(start,end),context);
vm.runInContext("function v22HistIsOverview(){return v22HistMode==='week'||v22HistMode==='month'}",context);
vm.runInContext("function v22HistUpdateToolbar(){renderList()}",context);
vm.runInContext("function renderList(){"+js.slice(listStart,listEnd)+"}",context);
const render=()=>vm.runInContext("renderList()",context);
const items=()=>context.t.list.children.slice(1);
const order=()=>items().map(x=>x.children[1].text);
const header=()=>context.t.list.children[0];
const sort=(key)=>{const i=key==='amount'?2:key==='count'?3:4;header().children[i].onclick()};
const checks=[
 [2,'本月提现总额'],[3,'提现次数'],[4,'当前余额']
];
render();
assert.strictEqual(header().children.length,5,'Withdrawal list has 5 columns');
assert.strictEqual(header().children[0].text,'会员姓名');
assert.strictEqual(header().children[1].text,'会员账号');
for(const [i,label] of checks)assert(header().children[i].text.startsWith(label),header().children[i].text);
assert(header().children[2].cls.includes('active'));
assert.strictEqual(header().children[2].attrs['aria-pressed'],'true');
assert.deepStrictEqual(order(),['abc12','wlb841216','beiying007'],
 'Default amount descending');
assert.strictEqual(items()[1].children[0].text,'王女士');
assert.strictEqual(items()[1].children[2].text,'10,070');
assert.strictEqual(items()[1].children[3].text,'1');
assert.strictEqual(items()[1].children[4].text,'5,080');
assert.strictEqual(items()[2].children[0].text,'未填写姓名');
assert.strictEqual(items()[2].children[2].text,'4,676');
assert.strictEqual(items()[2].children[3].text,'3');
assert.strictEqual(items()[2].children[4].text,'12,000');
items()[0].onclick();assert(touched,'Row click should still focus a member');
touched=false;
sort('count');assert.deepStrictEqual(order(),['beiying007','abc12','wlb841216']);
assert(header().children[3].text.includes('↓'),'Count high-to-low arrow');
assert(!touched,'Sorting should not focus a member or mutate data');
sort('count');assert.deepStrictEqual(order(),['wlb841216','abc12','beiying007']);
assert(header().children[3].text.includes('↑'),'Count low-to-high arrow');
sort('amount');assert.deepStrictEqual(order(),['abc12','wlb841216','beiying007']);
sort('amount');assert.deepStrictEqual(order(),['beiying007','wlb841216','abc12']);
assert(header().children[2].text.includes('↑'));
sort('balance');assert.deepStrictEqual(order(),['beiying007','wlb841216','abc12']);
assert(header().children[4].text.includes('↓'));
sort('balance');assert.deepStrictEqual(order(),['abc12','wlb841216','beiying007']);
assert(header().children[4].text.includes('↑'));
sort('amount');
assert.deepStrictEqual(people.map(x=>x.account),['wlb841216','beiying007','abc12'],
 'List sorting must not change member tree order or stored amounts');
context.v22HistMode='week';render();
assert(header().children[2].text.includes('本周提现总额'));
assert.strictEqual(header().children.length,5);
context.v22HistMode='withdraw';context.amounts=new Map([['a',-2500],['b',120000],['c',40000]]);
render();assert.strictEqual(header().children[2].text.startsWith('当日提现金额'),true);
assert.strictEqual(items().find(x=>x.children[1].text==='wlb841216').children[3].text,'0',
 'Daily negative return is not a withdrawal count');
assert.strictEqual(items().find(x=>x.children[1].text==='beiying007').children[3].text,'1');
context.v22HistMode='new';render();
assert.strictEqual(header().children.length,3,'Signup date list is unaffected');
assert.strictEqual(header().children[2].text,'加入日期');
assert.strictEqual(items()[0].children.length,3);
assert(js.includes('v22HistOneRing')||js.includes('v22-hist-one-withdraw-ring'));
assert(js.includes("class:joined?'v22-hist-one-new-ring':'v22-hist-one-withdraw-ring'"));
assert(!js.includes('group.append(outer,mid,inner)'), 'No 3 nested SVG ellipses');
assert(!js.includes("class:'v22-hist-ring-crimson'"), 'Old outer ring removed');
assert(!js.includes("class:'v22-hist-ring-red'"), 'Old middle ring removed');
assert(!js.includes("class:'v22-hist-ring-pink'"), 'Old inner ring removed');
assert(html.includes('#v22-one-ring-sortable-history-css')||
 html.includes('id="v22-one-ring-sortable-history-css"'));
assert(html.includes('display:none!important;'));
assert(html.includes('.v22-hist-one-withdraw-ring{'));
assert(html.includes('stroke:#e95668'));
assert(html.includes('rx:compactMode?94:156')===false,'SVG geometry belongs in JS only');
assert(js.includes("class:'withdraw-red-outer'"),'Original current-day red ring must remain');
console.log('PASS: V22 single historical ring, 5 columns including current balance, three independently sortable numeric columns and original daily/newcomer modes');
