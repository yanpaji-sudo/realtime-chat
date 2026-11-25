// Test the actual popup rendering fragment and soft historical-ring CSS offline.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
const start=js.indexOf(' t.list.replaceChildren();');
const end=js.indexOf(' if(matches.length>400)',start);
assert(start>0&&end>start&&end-start<2200,'Popup renderer range must be identified exactly');
const snippet=js.slice(start,end);
function make(tag,cls='',text=''){
 return {
  tag,cls,text,children:[],append(...xs){this.children.push(...xs)},
  replaceChildren(){this.children=[]}
 };
}
function run(mode,rows,details,recordAmounts={}){
 const list=make('div');
 let clicked=null;
 const context={
  t:{list},
  matches:rows,
  frequency:new Map(Object.entries(details)),
  amounts:new Map(Object.entries(recordAmounts)),
  v22HistMode:mode,
  v22HistIsOverview:()=>mode==='week'||mode==='month',
  mk:make,
  money:(cents)=>Number(cents/100).toLocaleString('en-US',{maximumFractionDigits:2,minimumFractionDigits:0}),
  v22HistFocus:(id)=>{clicked=id}
 };
 vm.runInNewContext(snippet,context);
 return {list,clicked:()=>clicked};
}
const people=[
 {id:'one',account:'wlb841216',remark:'王女士',joined_on:'2026-11-13'},
 {id:'two',account:'beiying007',remark:'',joined_on:'2026-11-14'},
 {id:'three',account:'abc12',remark:'测试姓名',joined_on:'2026-11-15'}
];
for(const mode of ['week','month']){
 const r=run(mode,people,{
  one:{days:3,tier:'mid',amount_cents:1007000},
  two:{days:2,tier:'mid',amount_cents:467600},
  three:{days:1,tier:'low',amount_cents:200001}
 });
 assert.strictEqual(r.list.children.length,4);
 const header=r.list.children[0];
 assert.strictEqual(header.children[0].text,'会员姓名');
 assert.strictEqual(header.children[1].text,'会员账号');
 assert.strictEqual(header.children[2].text,mode==='month'?'本月提现总额':'本周提现总额');
 const first=r.list.children[1];
 assert.strictEqual(first.children[0].text,'王女士');
 assert.strictEqual(first.children[1].text,'wlb841216');
 assert.strictEqual(first.children[2].text,'10,070');
 assert(!first.children.some(x=>String(x.text).includes('天')));
 first.onclick();assert.strictEqual(r.clicked(),'one');
 const fallback=r.list.children[2];
 assert.strictEqual(fallback.children[0].text,'未填写姓名');
 assert.strictEqual(fallback.children[1].text,'beiying007');
 assert.strictEqual(fallback.children[2].text,'4,676');
}
const daily=run('withdraw',people.slice(0,1),{}, {one:123456});
assert.strictEqual(daily.list.children[0].children[2].text,'当日提现金额');
assert.strictEqual(daily.list.children[1].children[2].text,'1,234.56');
const newer=run('new',people.slice(0,1),{});
assert.strictEqual(newer.list.children[0].children[2].text,'加入日期');
assert.strictEqual(newer.list.children[1].children[2].text,'2026-11-13');
assert(!js.includes("class:'v22-hist-count-badge'"), 'SVG should not show days badge');
assert(!js.includes("card.dataset.v22HistDays=String(detail.days)"), 'HTML card should not expose count metadata');
assert(js.includes('v22HistFrequency()'), 'Data filtering by withdrawal frequency preserved');
assert(js.includes('v22HistIsOverview()'), 'Week/month modes preserved');
assert(html.includes('v22-history-compact-soft-css'));
assert(html.includes('v22-hist-member-account'));
assert(html.includes('.v22-hist-ring-crimson{stroke:#dc606c!important;stroke-width:4px!important;filter:none!important;animation:none!important'));
assert(html.includes('.member.v22-hist-new::before,.member.v22-hist-withdraw::before{'));
assert(html.includes('display:none!important;content:none!important'));
assert(html.includes('stroke:#9569c7!important'), 'Purple tier still visually distinguished');
assert(html.includes('stroke:#dc983a!important'), 'Orange tier still visually distinguished');
console.log('PASS: name/remark + account + week/month amount rows, daily amount, blank name fallback, no day badges, subtle static red/amber/purple rings');
