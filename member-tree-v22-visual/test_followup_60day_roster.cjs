// 2026 Aug-onward 60-day no-direct-referral follow-up roster, display-only.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const css=fs.readFileSync('member-tree/static/style.css','utf8');
const begin=js.indexOf('// Follow-up list, members joined since Aug 2026');
const finish=js.indexOf('\nfunction v22HistUpdateToolbar(){',begin);
assert(begin>=0&&finish>begin&&finish-begin<19000,'Follow-up helper inserted exactly once');
const members=[
 {id:'root',account:'root',parent_id:null,level:1,joined_on:'2025-01-01',group_account:'01',balance_cents:0},
 {id:'aug',account:'aug1',remark:'张先生 江苏',parent_id:'root',level:2,group_account:'01',
  joined_on:'2026-08-01',balance_cents:0,stake_cents:100000,total_withdraw_cents:30000},
 {id:'aug2',account:'aug2',remark:'李经理',parent_id:'root',level:2,group_account:'02',
  joined_on:'2026-08-20',balance_cents:230000,stake_cents:100000,total_withdraw_cents:120000},
 {id:'edge61',account:'edge61',remark:'边界61天',parent_id:'root',level:2,group_account:'01',
  joined_on:'2026-09-26',balance_cents:3333,stake_cents:5000,total_withdraw_cents:0},
 {id:'edge60',account:'edge60',remark:'边界60天',parent_id:'root',level:2,group_account:'01',
  joined_on:'2026-09-27',balance_cents:5555},
 {id:'old',account:'july31',remark:'过早加入',parent_id:'root',level:2,group_account:'02',
  joined_on:'2026-07-31',balance_cents:10000},
 {id:'new',account:'october',parent_id:'root',level:2,group_account:'02',
  joined_on:'2026-10-12',balance_cents:10000},
 {id:'has',account:'haschild',parent_id:'root',level:2,group_account:'03',
  joined_on:'2026-08-04',balance_cents:400000},
 {id:'child',account:'realchild',parent_id:'has',level:3,group_account:'03',
  joined_on:'2026-08-25',balance_cents:10000},
 {id:'delParent',account:'deletedchildparent',parent_id:'root',level:2,group_account:'02',
  joined_on:'2026-08-09',balance_cents:80000},
 {id:'del',account:'gone',parent_id:'delParent',level:3,deleted:true,group_account:'02',
  joined_on:'2026-08-31',balance_cents:0},
 {id:'dummyParent',account:'dummyParent',parent_id:'root',level:2,group_account:'02',
  joined_on:'2026-08-10',balance_cents:80000},
 {id:'dummy',account:'placeholder',parent_id:'dummyParent',level:3,
  remark:'上级占位（待补资料）',group_account:'02',joined_on:'2026-09-01',balance_cents:0},
 {id:'san',account:'san08',parent_id:'root',level:2,group_account:'08',
  joined_on:'2026-08-01',balance_cents:0},
 {id:'sanChild',account:'sanChild',parent_id:'san',level:3,group_account:'08',
  joined_on:'2026-08-01',balance_cents:1000}
];
const snapshot=JSON.stringify(members);
function el(tag,cls='',text=''){
 const e={tag,cls,text,children:[],value:'',hidden:false,attrs:{},classList:{add(){},remove(){}},
  replaceChildren(...kids){this.children=kids;for(const k of kids){if(k)k.parentElement=this}},
  append(...kids){this.children.push(...kids);for(const k of kids){if(k)k.parentElement=this}},
  setAttribute(k,v){this.attrs[k]=v},
  addEventListener(k,handler){this['on'+k]=handler},
  focus(){this.focused=true},
  remove(){this.removed=true;const parent=this.parentElement;if(parent){
    const i=parent.children.indexOf(this);if(i>=0)parent.children.splice(i,1)
  }}
 };
 return e;
}
const body=el('body');
const env={members,mk:el,document:{body},v22HistToday:()=> '2026-11-26',
  v22HistMaximized:false,v22DormantPanel:null,v22LoanPanel:null,
  TREE_GROUPS:['01','02','03','08'],selectedTreeGroup:'',
  money:v=>String(v),v22DormantDate:day=>{
    if(!/^\d{4}-\d{2}-\d{2}$/.test(String(day)))return null;
    const d=new Date(day+'T00:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===day?d:null;
  },v22DormantDisplayLevel:m=>m.level===3?'A':m.level===2?'A':'总节点',
  V22_DORMANT_EXCLUDED_ACCOUNTS:new Set(['SAN1','SAN2','SAN5','SAN6','SAN8']),
  v22DormantAccountKey:a=>String(a||'').toUpperCase().replace(/^SAN0+([1-9]\d*)$/,'SAN$1')
};
vm.createContext(env);
vm.runInContext(js.slice(begin,finish),env);
const call=code=>vm.runInContext(code,env);
assert.strictEqual(call("v22FollowDays('2026-09-27','2026-11-26')"),60);
assert.strictEqual(call("v22FollowDays('2026-09-26','2026-11-26')"),61);
assert.strictEqual(call("v22FollowDays('2026-11-27','2026-11-26')"),null);
const rows=Array.from(call("v22FollowAnalyze(members,'2026-11-26')"));
const byAccount=new Map(rows.map(x=>[x.account,x]));
assert(byAccount.has('aug1'),'August 1 account included');
assert(byAccount.has('aug2'),'August 20 account included');
assert(byAccount.has('edge61'),'61 day boundary included');
assert(!byAccount.has('edge60'),'Exactly 60 days not included');
assert(!byAccount.has('july31'),'Pre-August date excluded');
assert(!byAccount.has('october'),'New October account excluded');
assert(!byAccount.has('haschild'),'Already referred a direct subordinate');
assert(!byAccount.has('san08'),'Excluded structural SAN group account');
assert(byAccount.has('sanChild'),'SAN descendant without direct referrals remains eligible');
assert(byAccount.has('deletedchildparent'),'Deleted referral must not count as valid');
assert(byAccount.has('dummyParent'),'Placeholder referral must not count');
assert.strictEqual(byAccount.get('aug1').days,117);
assert.strictEqual(byAccount.get('aug1').balance_cents,0,'No generic zero-balance filtering requested for this follow-up list');
assert.strictEqual(byAccount.get('aug1').remark,'张先生 江苏');
assert.strictEqual(byAccount.get('aug1').net_win_cents,70000);
assert.strictEqual(byAccount.get('aug2').net_win_cents,-20000);
assert.strictEqual(JSON.stringify(members),snapshot,'Read-only follower calculation never modifies membership records');
call('v22FollowOpen()');
assert.strictEqual(body.children.length,1,'Opens a single overlay');
const view=call('v22FollowPanel');
assert(view.heading.textContent.includes('人'),'Summary shows count');
assert.strictEqual(view.table.children.length,1+rows.length,'Header plus one row per member');
assert(view.summary.textContent.includes('余额合计'),'Summarizes current balance');
const header=view.table.children[0].children.map(x=>x.text.replace(/\s[↓↑↕]$/,''));
assert.deepStrictEqual(header,['所属分组','会员备注','会员账号','层级','加入日期','未裂变天数','直属裂变人数','当前余额','本人输赢']);
view.group.value='01';view.group.onchange();
assert(view.heading.textContent.includes('2 人'),'Group 01 filtered to Aug1 and 61-day member');
view.group.value='';view.group.onchange();
assert(view.heading.textContent.includes(rows.length+' 人'),'All-groups option works after selecting a group');
view.keyword.value='江苏';view.keyword.oninput();
assert(view.heading.textContent.includes('1 人'),'Search by note works');
view.keyword.value='';view.keyword.oninput();
view.table.children[0].children[5].onclick();
assert.strictEqual(call('v22FollowSort'),'days');
assert.strictEqual(call('v22FollowDesc'),false);
call('v22FollowClose()');
assert.strictEqual(body.children.length,0);
assert.strictEqual(JSON.stringify(members),snapshot);
assert(js.includes("const follow=mk('button','v22-hist-button v22-follow-trigger','📌 跟进名单')"));
assert(js.includes('b.append(label,newer,withdraw,week,month,dormant,loan,follow,prev,pick'));
assert(js.includes("document.getElementById('v22UnifiedTrack')"),'Unified Alt+Q dock remains');
assert(css.includes('.v22-follow-trigger')&&css.includes('.v22-follow-overlay'));
console.log('PASS: V22 August+ >60-day zero-direct-growth follow-up list: eligibility boundaries, notes, group, balance, pagination and no writes');
