'use strict';
const el=id=>document.getElementById(id);
let historyCoverage={},rankPeriod='daily',rankExpanded=new Set();
// V21 view-only toggles; no writes to member records.
let riskMode=false,riskFocusId='',withdrawGlowOn=false,treeVertical=false,branchVertical=false;
let positionAlarmOn=false;
let positionAlarmById=null;
const TREE_GROUPS=['01','02','03','06','08'];
const VIEW_STATE_KEY='member-tree-v22-tab-viewport';
function restoreTabView(){try{const v=JSON.parse(sessionStorage.getItem(VIEW_STATE_KEY)||'{}');return v&&typeof v==='object'?v:{}}catch(_){return {}}}
const savedTabView=restoreTabView();
let compactMode=Boolean(savedTabView.compactMode);
let selectedTreeGroup=TREE_GROUPS.includes(savedTabView.group)?savedTabView.group:'',
    branchFocusRequested=false,
    branchViewportReady=false,
    branchResetRequested=false;
treeVertical=false;branchVertical=false;
function persistTabView(){
 try{sessionStorage.setItem(VIEW_STATE_KEY,JSON.stringify({group:selectedTreeGroup,treeVertical,branchVertical,compactMode,
    zoom:branchTransform,branchClosed:[...branchClosed],collapsed:[...collapsed]}))}catch(_){}
}
function shownTreeMembers(rows=members){return selectedTreeGroup?rows.filter(r=>String(r.group_account||r.account)===selectedTreeGroup):rows}
function selectTreeGroup(group){
 teamFocusId=null;teamFocusRestoreGroup='';
 selectedTreeGroup=TREE_GROUPS.includes(group)?group:'';
 // Changing visible group is an explicit request to fit the new diagram.
 branchViewportReady=false;branchResetRequested=true;
 branchSelectedAccount='';riskFocusId='';query='';el('search').value='';
 persistTabView();render();
 showToast(selectedTreeGroup?`正在查看 ${selectedTreeGroup} 小组，其他分组已隐藏`:'正在查看所有小组');
}

let role=null,csrf='',members=[],total={},view='branch',query='',branchSelectedAccount='',collapsed=new Set(Array.isArray(savedTabView.collapsed)?savedTabView.collapsed:[]),editId=null,previewJob=null,importMode='both',toastTimer=null,tableScope='',tableGroup='',tableMetric='self',rankSort='desc',businessDay='',lastDisplayDay='',branchClosed=new Set(Array.isArray(savedTabView.branchClosed)?savedTabView.branchClosed:[]),branchTransform=(savedTabView.zoom&&Number.isFinite(savedTabView.zoom.scale)&&savedTabView.zoom.scale>=.13&&savedTabView.zoom.scale<=3.8&&Number.isFinite(savedTabView.zoom.dx)&&Number.isFinite(savedTabView.zoom.dy))?savedTabView.zoom:{scale:1,dx:0,dy:0},detailId=null,restoreChosenFile=null;
branchViewportReady=Boolean(savedTabView.zoom&&Number.isFinite(savedTabView.zoom.scale));
let branchViewportControls=null;
let teamFocusId=null,teamFocusRestoreGroup=''; // view-only

const url='/api';
function money(c,integer=false){return (Number(c||0)/100).toLocaleString('zh-CN',{minimumFractionDigits:0,maximumFractionDigits:0})}
// V7 is a presentation-only upgrade; financial figures stay in the existing database.
function amountClass(c,type='normal'){
 const n=Number(c||0);
 if(n===0)return 'amount-black';
 if(type==='daily')return 'amount-red'; // every non-zero daily withdrawal is red
 if(type==='profit')return n>0?'amount-green':'amount-red';
 return n<0?'amount-red':'amount-black';
}
function setAmount(id,c,integer=false,type='normal'){
 const e=el(id);e.textContent=money(c,integer);
 e.classList.remove('amount-red','amount-black','amount-green');e.classList.add(amountClass(c,type));
}
// Counts new sign-ups by their *absolute visible tree level*, for each ancestor node.
// Only derives totals from already-loaded read-only member records; no database writes.
function todaysNewByNode(rows,day){
 const byId=new Map(rows.map(r=>[r.id,r]));
 const result=new Map(rows.map(r=>[r.id,{total:0,own:0,byLevel:new Map()}]));
 for(const newcomer of rows){
  if(String(newcomer.joined_on)!==day)continue;
  let current=newcomer,visited=new Set();
  while(current&&!visited.has(current.id)){
   visited.add(current.id);
   const summary=result.get(current.id);if(!summary)break;
   summary.total++;
   if(current.id===newcomer.id)summary.own++;
   const level=Number(newcomer.level||1);
   summary.byLevel.set(level,(summary.byLevel.get(level)||0)+1);
   current=byId.get(current.parent_id);
  }
 }
 return result;
}
function newBadge(x,byId,day,summaryByNode){
 const v=byId.get(x.id)||{total:0,own:0,byLevel:new Map()};
 const stats=summaryByNode&&summaryByNode.get(x.id)||{count:1,balance:0,stake:0,withdraw:0,monthCount:0,todayCount:0};
 const shell=mk('div','today-new-summary v12-summary'+(v.total?' has-new':' no-new'));
 const main=mk('div','today-new-head');
 main.append(mk('span','today-new-label','今日新增'),mk('strong','today-new-number',String(v.total)),mk('span','today-new-unit','人'));
 if(v.own)main.append(mk('span','today-self-tag','本人今日加入'));
 shell.append(main);
 const newStake=mk('div','today-new-stake',`今日新增存款：${money(stats.todayStake||0,true)}`);
 const todayWithdraw=Number(stats.todayWithdraw||0),todayProfit=Number(stats.todayStake||0)-todayWithdraw;
 const withdrawalLine=mk('div','today-new-withdraw',`今日新增提现：${money(todayWithdraw,true)}`);
 const profitLine=mk('div','today-new-profit '+amountClass(todayProfit,'profit'),
  `今日输赢：${todayProfit>0?'+':''}${money(todayProfit,true)}${todayProfit>0?' · 给力':todayProfit<0?' · 你要努力了':''}`);
 main.append(newStake,withdrawalLine,profitLine);
 const avg=stats.count?stats.balance/stats.count:0;
 const profit=stats.stake-stats.withdraw;
 const dayPct=stats.count?stats.todayCount/stats.count*100:0;
 const monthPct=stats.count?stats.monthCount/stats.count*100:0;
 const entries=[
  {title:'本月团队新增人数',value:`${stats.monthCount} 人`,tone:'amount-black'},
  {title:'团队平均余额',value:money(avg),tone:summaryTone(avg,1300000,false,true),alert:avg>1300000?'💣 炸弹来喽':''},
  {title:'团队输赢',value:(profit>0?'+':'')+money(profit),tone:amountClass(profit,'profit'),alert:profit<1000000?'你生病了吗':''},
  {title:'当日裂变比例',value:Math.round(dayPct)+'%',tone:summaryTone(dayPct,1.5,true),alert:dayPct<1.5?(Number(x.low_fission_streak||1)>1?`你已经连续${x.low_fission_streak}天拖油瓶了哦 😢`:'拖油瓶'):''},
  {title:'本月裂变比例',value:Math.round(monthPct)+'%',tone:summaryTone(monthPct,1.5*Number(day.slice(-2)),false),alert:monthPct<1.5*Number(day.slice(-2))?`再接再厉，你需再增长 ${Math.round(1.5*Number(day.slice(-2))-monthPct)}% 😮`:''}
 ];
 const bar=mk('div','v12-kpis');
 for(const entry of entries){
  const item=mk('div','v12-kpi');item.append(mk('span','v12-label',entry.title));
  item.append(mk('strong','v12-value '+entry.tone,entry.value));
  if(entry.alert)item.append(mk('span','v12-alert',entry.alert));
  bar.append(item);
 }
 shell.append(bar);
 const detail=mk('div','today-new-levels');
 if(v.total){for(const [level,count] of [...v.byLevel].sort((a,b)=>a[0]-b[0])){
  detail.append(mk('span','today-level-chip',`第${level}层 ${count}人`));
 }}else detail.append(mk('span','today-no-desc','当日暂无新增'));
 shell.append(detail);
 return shell;
}

function dateNow(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
function membershipMonths(joinedOn,asOf=dateNow()){
 const a=String(joinedOn||'').split('-').map(Number),b=String(asOf||'').split('-').map(Number);
 if(a.length!==3||b.length!==3||a.some(x=>!Number.isFinite(x))||b.some(x=>!Number.isFinite(x)))return 0;
 const full=(b[0]-a[0])*12+b[1]-a[1]-(b[2]<a[2]?1:0);
 return Math.max(0,Math.min(6,full));
}
function weekStart(day){
 const d=new Date(`${day}T12:00:00Z`);
 d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));
 return d.toISOString().slice(0,10);
}
function periodStart(day,period){return period==='week'?weekStart(day):period==='month'?day.slice(0,7)+'-01':period==='total'?'0000-01-01':day}
function periodAmounts(row,day,period){
 const start=periodStart(day,period),joined=String(row.joined_on||'');
 const deposit=(period==='total'||(joined>=start&&joined<=day))?Number(row.stake_cents||0):0;
 const withdrawals=period==='total'?Number(row.total_withdraw_cents||0):
   period==='week'?Number(row.week_withdraw_cents||0):
   period==='month'?Number(row.month_withdraw_cents||0):Number(row.daily_withdraw_cents||0);
 return {deposit,withdraw:withdrawals,newCount:period==='total'?1:(joined>=start&&joined<=day?1:0)};
}
function computeRanking(rows,day,period='daily'){
 const tree=new Map(rows.map(r=>{
  const {deposit,withdraw,newCount}=periodAmounts(r,day,period),level=Number(r.level||1);
  return [r.id,{deposit,withdraw,newCount,count:1,balance:Number(r.balance_cents||0),layers:new Map([[level,{count:1,deposit,withdraw,balance:Number(r.balance_cents||0)}]])}];
 }));
 const ordered=rows.slice().sort((a,b)=>Number(b.level||0)-Number(a.level||0));
 for(const x of ordered){
  const mine=tree.get(x.id),parent=tree.get(x.parent_id);
  if(!parent)continue;
  parent.deposit+=mine.deposit;parent.withdraw+=mine.withdraw;parent.newCount+=mine.newCount;parent.count+=mine.count;parent.balance+=mine.balance;
  for(const [level,item] of mine.layers){
   const sum=parent.layers.get(level)||{count:0,deposit:0,withdraw:0,balance:0};
   sum.count+=item.count;sum.deposit+=item.deposit;sum.withdraw+=item.withdraw;sum.balance+=item.balance;
   parent.layers.set(level,sum);
  }
 }
 return rows.filter(r=>Number(r.level)===2).map(r=>{
  const t=tree.get(r.id);
  return {id:r.id,account:r.account,teamName:r.team_name||'',group:r.group_account||'',teamCount:t.count,newCount:t.newCount,
          dailyStake:t.deposit,dailyWithdraw:t.withdraw,score:t.deposit-t.withdraw,teamBalance:t.balance,
          layers:[...t.layers].sort((a,b)=>a[0]-b[0]).map(([level,item])=>({
           level,count:item.count,deposit:item.deposit,withdraw:item.withdraw,score:item.deposit-item.withdraw,balance:item.balance
          }))};
 }).sort((a,b)=>b.score-a.score||b.dailyStake-a.dailyStake||a.dailyWithdraw-b.dailyWithdraw||a.account.localeCompare(b.account,'zh-CN'));
}
function teamSummaryByNode(rows,day){
 const map=new Map(rows.map(r=>[r.id,{
  count:1,balance:Number(r.balance_cents||0),
  stake:Number(r.stake_cents||0),withdraw:Number(r.total_withdraw_cents||0),
  todayCount:String(r.joined_on)===day?1:0,
  todayStake:String(r.joined_on)===day?Number(r.stake_cents||0):0,
  todayWithdraw:Number(r.daily_withdraw_cents||0),
  monthCount:String(r.joined_on||'').slice(0,7)===day.slice(0,7)?1:0
 }]));
 for(const x of rows.slice().sort((a,b)=>Number(b.level||0)-Number(a.level||0))){
  const a=map.get(x.id),parent=map.get(x.parent_id);if(!parent)continue;
  for(const key of Object.keys(a))parent[key]+=a[key];
 }
 return map;
}
function summaryTone(value,threshold,zeroBlack=false,inverse=false){
 if(value===threshold||(zeroBlack&&value===0))return 'amount-black';
 return (value>threshold)!==inverse?'amount-green':'amount-red';
}


// V14 fullscreen only affects rendering. Alt+Enter toggles; Escape exits.
let branchFullscreenReflow=null;
function fullscreenPanel(){return document.querySelector('.panel')}
function fullscreenActive(){const p=fullscreenPanel();return Boolean(p&&(document.fullscreenElement===p||p.classList.contains('fullscreen-fallback')))}
function rescaleFullscreenBranch(){if(typeof branchFullscreenReflow==='function')requestAnimationFrame(()=>requestAnimationFrame(()=>branchFullscreenReflow&&branchFullscreenReflow()))}
function refreshFullscreenButton(){const active=fullscreenActive();const label=active?'⛶ 退出全屏':view==='report'?'⛶ 报表最大化':view==='ranking'?'⛶ 排行榜最大化':'⛶ 全屏显示';for(const id of ['treeFullscreenBtn','reportFullscreenBtn','rankingFullscreenBtn']){const b=el(id);if(!b)continue;b.textContent=label;b.setAttribute('aria-pressed',String(active))}}
async function toggleTreeFullscreen(){
 if(!['tree','branch','report','ranking'].includes(view)){showToast('请先进入会员树状图、分支分布图、今日报表总览或团队排行榜');return}
 const p=fullscreenPanel();if(!p)return;
 if(document.fullscreenElement===p){try{await document.exitFullscreen()}catch(err){showToast('退出全屏失败：'+err.message)}}
 else if(p.classList.contains('fullscreen-fallback'))p.classList.remove('fullscreen-fallback');
 else{try{if(!p.requestFullscreen)throw new Error('浏览器不支持');await p.requestFullscreen()}catch(e){p.classList.add('fullscreen-fallback');showToast('已使用兼容全屏模式，按 Esc 退出')}}
 refreshFullscreenButton();rescaleFullscreenBranch();
}
if(typeof document!=='undefined')document.addEventListener('fullscreenchange',()=>{hideCompactTooltip();refreshFullscreenButton();rescaleFullscreenBranch()});
if(typeof window!=='undefined')window.addEventListener('resize',()=>{if(fullscreenActive())rescaleFullscreenBranch()});
if(typeof document!=='undefined')document.addEventListener('keydown',e=>{
 if(e.key==='Escape'&&fullscreenPanel()?.classList.contains('fullscreen-fallback')){fullscreenPanel().classList.remove('fullscreen-fallback');refreshFullscreenButton();rescaleFullscreenBranch();return}
 if(e.altKey&&e.key==='Enter'&&!e.ctrlKey&&!e.metaKey&&!document.querySelector('dialog[open]')&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)){
  if(['tree','branch','report','ranking'].includes(view)){e.preventDefault();toggleTreeFullscreen()}
 }
});

function showToast(s){const x=el('toast');x.textContent=s;x.classList.remove('hidden');clearTimeout(toastTimer);toastTimer=setTimeout(()=>x.classList.add('hidden'),4500)}
async function api(path,method='GET',body=null){const opt={method,credentials:'same-origin',headers:{}};if(method!=='GET')opt.headers['X-CSRF-Token']=csrf;if(body instanceof FormData)opt.body=body;else if(body!==null){opt.body=JSON.stringify(body);opt.headers['Content-Type']='application/json'}const resp=await fetch(url+path,opt);const d=await resp.json().catch(()=>({}));if(!resp.ok)throw Error(d.detail||`服务器返回${resp.status}`);return d}
function mk(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
function message(s){el('content').replaceChildren(mk('p','empty',s))}
function setRole(r,c,username=''){role=r;csrf=c||'';el('loginView').classList.toggle('hidden',!!r);el('app').classList.toggle('hidden',!r);document.querySelectorAll('.admin-only').forEach(x=>x.classList.toggle('hidden',r!=='admin'));el('roleLabel').textContent=r==='admin'?'管理员 '+(username||'已登录'):'内部成员查看';el('sessionLabel').textContent=r==='admin'?'管理员 · '+(username||'已登录'):'只读查看模式'}
async function login(){el('loginError').textContent='';try{const r=await api('/login','POST',{role:el('loginView').dataset.role||'viewer',username:el('loginUsername').value.trim(),password:el('loginPassword').value});el('loginPassword').value='';setRole(r.role,r.csrf,r.username);await refresh();showToast('登录成功，已连接共享会员系统')}catch(e){el('loginError').textContent=e.message}}
function selectedLogin(mode){el('loginView').dataset.role=mode;el('adminTab').classList.toggle('selected',mode==='admin');el('viewerTab').classList.toggle('selected',mode==='viewer');el('loginUsernameWrap').classList.toggle('hidden',mode!=='admin');(mode==='admin'?el('loginUsername'):el('loginPassword')).focus()}
async function logout(){try{await api('/logout','POST',{})}catch(e){}academyClearChat();setRole(null,null);members=[];selectedLogin('viewer')}
function index(){return new Map(members.map(m=>[m.id,m]))}
function descendants(){const m=index();let graph=new Map();for(const row of members){if(!graph.has(row.parent_id))graph.set(row.parent_id,[]);graph.get(row.parent_id).push(row)}return {m,graph}}
function getShown(){if(!query)return null;const ids=new Set(), {m}=descendants();for(const x of members){if(x.account.toLowerCase().includes(query.toLowerCase())){let n=x,seen=new Set();while(n&&!seen.has(n.id)){ids.add(n.id);seen.add(n.id);n=m.get(n.parent_id)}}}return ids}
function metric(title,self,direct,sum,isDaily=false){const box=mk('div','metric');box.append(mk('label','',title));const type=isDaily?'daily':title.startsWith('输赢')?'profit':'normal';for(const [name,val,cls] of [['本人',self,'self'],['直推',direct,'direct'],['团队总计',sum,'sum']]){const line=mk('div',cls);line.append(mk('span','',name),mk('b',amountClass(val,type),money(val,title.includes('提现'))));box.append(line)}return box} 

// V28 read-only compact hover popover; preserves all original member fields.
let compactTooltipEl=null;
function hideCompactTooltip(){if(compactTooltipEl){compactTooltipEl.remove();compactTooltipEl=null}}

// V29: view-only alert based on OWN balance and number of direct referrals.
function v29Position(m){
 // V33 thresholds are in cents; status comes from the shared database.
 const stake=Number(m.stake_cents||0),direct=Number(m.direct_count||0);
 const trigger=stake===500000?750000:stake<=1000000?1500000:(direct>=5?2000000:1300000);
 const target=stake===500000?700000:stake<=1000000?1300000:trigger;
 const clear=stake===500000?750000:target;
 const balance=Number(m.balance_cents||0);
 const live=positionAlarmById&&positionAlarmById.get(m.id);
 const active=positionAlarmById!==null?Boolean(live):(Number.isFinite(balance)&&balance>trigger);
 const cents=live?Number(live.suggest_cents||0):Number.isFinite(balance)?Math.max(0,balance-target):0;
 return {active,cents,threshold:target,trigger,clear,
         started_on:live?.started_on||'',overdue_days:Number(live?.overdue_days||0),
         remaining_days:Number(live?.remaining_days||3)};
}
function togglePositionAlarm(){
 positionAlarmOn=!positionAlarmOn;
 hideCompactTooltip();
 render();
 showToast(positionAlarmOn?'仓位告警已开启：5000仓位余额超过7500、10000仓位超过15000显示光圈；余额达到解除线自动清除':'仓位告警已关闭');
}
function v29TeamStats(m){
 const count=Math.max(1,Number(m.descendant_count||0)+1);
 const teamBalance=Number(m.subtree_balance_cents||0);
 const downCount=Number(m.descendant_count||0);
 const downAvg=downCount>0?(teamBalance-Number(m.balance_cents||0))/downCount:0;
 const dayParts=String(businessDay||dateNow()).split('-').map(Number);
 const joinParts=String(m.joined_on||'').split('-').map(Number);
 const fullMonths=(dayParts[0]-joinParts[0])*12+(dayParts[1]-joinParts[1])-(dayParts[2]<joinParts[2]?1:0);
 const months=Number.isFinite(fullMonths)?Math.max(0,fullMonths):0;
 const quota=Math.max(1,months);
 const children=new Map();
 for(const x of members){
  const kids=children.get(x.parent_id)||[];
  kids.push(x);
  children.set(x.parent_id,kids);
 }
 const pending=[m],seen=new Set();
 let suggest=0;
 while(pending.length){
  const x=pending.pop();
  if(seen.has(x.id))continue;
  seen.add(x.id);
  const warn=v29Position(x);if(warn.active)suggest+=warn.cents;
  for(const y of children.get(x.id)||[])pending.push(y);
 }
 return {count,teamBalance,average:teamBalance/count,downAvg,months,quota,qualified:count>=quota,suggest};
}



/* Formal branch: team-only lens and two-format exports. Uses existing member array; no state writes. */
function teamExportRows(id){
 const root=members.find(m=>m.id===id);
 if(!root)return [];
 const ids=tableNodeIds(root.account);
 return members.filter(m=>ids&&ids.has(m.id));
}
function teamOnlyShow(id){
 const root=members.find(m=>m.id===id);
 if(!root){showToast('会员不存在');return}
 hideCompactTooltip();
 teamFocusRestoreGroup=selectedTreeGroup;
 teamFocusId=id;
 selectedTreeGroup='';
 view='branch';
 query='';el('search').value='';
 branchSelectedAccount='';
 branchClosed.clear();
 branchViewportReady=false;branchResetRequested=true;
 render();
 showToast('当前仅查看 '+root.account+' 及全部下级，点击返回完整架构即可恢复');
}
function teamOnlyClear(){
 teamFocusId=null;
 selectedTreeGroup=teamFocusRestoreGroup;
 teamFocusRestoreGroup='';
 branchSelectedAccount='';
 branchViewportReady=false;branchResetRequested=true;
 view='branch';render();
}
function teamExportFilename(account,label,ext){
 return String(account).replace(/[^A-Za-z0-9_\u4e00-\u9fa5-]/g,'_')+'_'+label+'_'+dateNow()+'.'+ext;
}
async function teamExcelDownload(id){
 if(role!=='admin')throw Error('只有管理员能导出团队数据');
 const root=members.find(m=>m.id===id);
 if(!root)throw Error('会员不存在');
 const res=await fetch('/api/export/team.xlsx?account='+encodeURIComponent(root.account),{credentials:'same-origin'});
 if(!res.ok)throw Error('Excel导出失败：HTTP '+res.status);
 const blob=await res.blob();
 const url=URL.createObjectURL(blob),a=document.createElement('a');
 a.href=url;a.download=teamExportFilename(root.account,'团队数据','xlsx');
 document.body.append(a);a.click();a.remove();
 setTimeout(()=>URL.revokeObjectURL(url),45000);
}
async function teamPictureDownload(id,all=true){
 if(role!=='admin')throw Error('只有管理员能导出团队数据');
 const root=members.find(m=>m.id===id);
 if(!root)throw Error('会员不存在');
 const rows=teamExportRows(id);
 if(!rows.length)throw Error('本团队暂无会员');
 // Compute a full, independent tree layout; never change the visible page.
 const priorCompact=compactMode;
 let layout;
 try{compactMode=false;layout=branchLayout(rows,all?new Set():branchClosed)}
 finally{compactMode=priorCompact}
 const paperW=2600,paperH=2250,canvasScale=2,cardW=290,cardH=112;
 const wholeW=Math.ceil(layout.width+80),wholeH=Math.ceil(layout.height+120);
 const nx=Math.ceil(wholeW/paperW),ny=Math.ceil(wholeH/paperH),pages=nx*ny;
 if(pages>100)throw Error('该团队结构过大，高清图片超过100张，请选择较小的节点或使用Excel');
 function label(s,max){const v=String(s??'');return v.length>max?v.slice(0,max-1)+'…':v}
 for(let ty=0;ty<ny;ty++){
  for(let tx=0;tx<nx;tx++){
   const bx=tx*paperW,by=ty*paperH,w=Math.min(paperW,wholeW-bx),h=Math.min(paperH,wholeH-by);
   const canvas=document.createElement('canvas');canvas.width=w*canvasScale;canvas.height=(h+90)*canvasScale;
   const c=canvas.getContext('2d');
   if(!c)throw Error('浏览器不支持图片导出');
   c.scale(canvasScale,canvasScale);
   c.fillStyle='#fff';c.fillRect(0,0,w,h+90);
   c.fillStyle='#17375e';c.fillRect(0,0,w,78);
   c.font='bold 22px Microsoft YaHei, sans-serif';c.fillStyle='white';
   c.fillText(label(root.account,35)+' · 团队树状架构',22,32);
   c.font='13px Microsoft YaHei, sans-serif';c.fillStyle='#dbeafa';
   c.fillText('团队人数 '+rows.length+' | '+dateNow()+' | 高清分片 '+(ty*nx+tx+1)+'/'+pages,22,56);
   c.save();
   c.beginPath();c.rect(0,78,w,h+12);c.clip();
   c.translate(28-bx,104-by);
   c.lineWidth=2;c.strokeStyle='#9bb5d3';
   for(const edge of layout.edges){
    const a=layout.positions.get(edge[0]),b=layout.positions.get(edge[1]);if(!a||!b)continue;
    const x1=a.x+cardW,x2=b.x,y1=a.y,y2=b.y;
    if(Math.max(x1,x2)<bx-330||Math.min(x1,x2)>bx+w+330||
       Math.max(y1,y2)<by-160||Math.min(y1,y2)>by+h+160)continue;
    c.beginPath();c.moveTo(x1,y1);c.bezierCurveTo(x1+30,y1,x2-30,y2,x2,y2);c.stroke();
   }
   for(const member of rows){
    const loc=layout.positions.get(member.id);if(!loc)continue;
    const x=loc.x,y=loc.y-cardH/2;
    if(x+cardW<bx-30||x>bx+w||y+cardH<by-45||y>by+h+45)continue;
    c.fillStyle='#f2f7fc';c.strokeStyle='#5c88b6';c.lineWidth=1.6;
    c.beginPath();c.roundRect(x,y,cardW,cardH,8);c.fill();c.stroke();
    c.font='bold 14px Microsoft YaHei, sans-serif';c.fillStyle='#164371';
    c.fillText(label(member.account,25),x+10,y+20);
    c.font='12px Microsoft YaHei, sans-serif';c.fillStyle='#526782';
    c.fillText('加入日期 '+String(member.joined_on||'—'),x+10,y+38);
    c.fillStyle='#087c46';c.fillText('充值 '+money(member.stake_cents,true),x+10,y+59);
    c.fillStyle='#c62828';c.fillText('提现 '+money(member.total_withdraw_cents,true),x+148,y+59);
    c.fillStyle='#364c66';c.fillText('余额 '+money(member.balance_cents,true),x+10,y+79);
    const profit=Number(member.profit_cents||0);
    c.fillStyle=profit>0?'#087c46':profit<0?'#c62828':'#364c66';
    c.fillText('输赢 '+money(profit,true),x+148,y+79);
    c.fillStyle='#526782';c.fillText('备注 '+label(member.remark||'—',24),x+10,y+98);
   }
   c.restore();
   const file=teamExportFilename(root.account,all?'完整团队架构':'当前团队架构','png')
     .replace(/\.png$/, (pages>1?'_'+(ty*nx+tx+1)+'of'+pages:'')+'.png');
   const blob=await new Promise((resolve,reject)=>canvas.toBlob(x=>x?resolve(x):reject(new Error('无法编码PNG图片')),'image/png'));
   const url=URL.createObjectURL(blob),a=document.createElement('a');
   a.href=url;a.download=file;document.body.append(a);a.click();a.remove();
   setTimeout(()=>URL.revokeObjectURL(url),45000);
   if(pages>1)await new Promise(resolve=>setTimeout(resolve,180));
  }
 }
}
function teamExportDialog(id){
 if(role!=='admin'){showToast('只有管理员允许导出团队');return}
 const root=members.find(m=>m.id===id);
 if(!root){showToast('会员不存在');return}
 hideCompactTooltip();
 const dialog=mk('dialog','v42-export-dialog');
 dialog.append(mk('h3','','导出 '+root.account+' 的团队数据'));
 dialog.append(mk('p','','范围包含该会员及所有下级。Excel第一张表为团队汇总，明细按加入时间升序。'));
 async function go(mode){
  dialog.close();
  try{
   if(mode==='excel'||mode==='all')await teamExcelDownload(id);
   if(mode==='png'||mode==='visible'||mode==='all')await teamPictureDownload(id,mode!=='visible');
   showToast('团队文件已开始导出，请查看下载列表');
  }catch(err){showToast('导出失败：'+String(err?.message||err))}
 }
 const options=[['▥ 导出完整树状图 · 高清PNG','png'],
 ['▤ 导出当前展开图 · PNG','visible'],
 ['▦ 导出团队Excel · 汇总/明细/层级','excel'],
 ['↓ 同时导出PNG和Excel','all']];
 for(const pair of options){
  const b=mk('button','v42-export-choice',pair[0]);
  b.type='button';b.onclick=()=>go(pair[1]);dialog.append(b);
 }
 const cancel=mk('button','v42-export-cancel','取消');
 cancel.type='button';cancel.onclick=()=>dialog.close();dialog.append(cancel);
 dialog.addEventListener('close',()=>dialog.remove());
 document.body.append(dialog);dialog.showModal();
}

function compactInfo(m){
 const stats=v29TeamStats(m),wrap=mk('div','v28-pop-body');
 const header=mk('div','v42-team-head'),headTitle=mk('h3','v28-pop-title',m.account+' · 个人与团队数据'),buttons=mk('div','v42-team-buttons');
 const only=mk('button','v42-team-button','▤');only.type='button';only.title='仅看本团队架构';only.setAttribute('aria-label','仅看本团队架构');
 only.onclick=e=>{e.stopPropagation();e.preventDefault();teamOnlyShow(m.id)};
 buttons.append(only);
 if(role==='admin'){
  const down=mk('button','v42-team-button','⇩');down.type='button';down.title='导出本团队数据';down.setAttribute('aria-label','导出本团队数据');
  down.onclick=e=>{e.stopPropagation();e.preventDefault();teamExportDialog(m.id)};
  buttons.append(down);
 }
 header.append(headTitle,buttons);wrap.append(header);
 const facts=mk('div','v28-pop-facts');
 const details=[
  ['备注信息',m.remark||'无'],
  ['会员账号',m.account],
  ['加入日期',m.joined_on||'—'],
  ['本人充值',money(Number(m.stake_cents||0),true)],
  ['本人余额',money(Number(m.balance_cents||0),true)],
  ['本人总提现',money(Number(m.total_withdraw_cents||0),true)],
  ['本人输赢',money(Number(m.profit_cents||0),true)],
  ['直属人数',String(m.direct_count||0)],
  ['全部下级',String(m.descendant_count||0)],
  ['下级平均余额',money(stats.downAvg,true)]
 ];
 for(const d of details){
  facts.append(mk('span','',d[0]));
  const value=mk('b','',d[1]);
  if(d[0]==='本人余额')value.classList.add(v29Position(m).active?'v29-red':'v29-green');
  if(d[0]==='本人输赢')value.classList.add(Number(m.profit_cents||0)>0?'v29-green':Number(m.profit_cents||0)<0?'v29-red':'v29-neutral');
  facts.append(value);
 }
 wrap.append(facts);
 const table=mk('table','v28-pop-table'),heading=mk('tr');
 heading.append(mk('th','','团队指标（含本人）'),mk('th','','汇总数值'));
 table.append(heading);
 const rows=[
  ['团队充值',Number(m.subtree_stake_cents||0),'v29-green'],
  ['团队总提现',Number(m.subtree_total_withdraw_cents||0),'v29-red'],
  ['团队余额',stats.teamBalance,stats.average>13000*100?'v29-red':'v29-green'],
  ['团队平均余额',stats.average,stats.average>13000*100?'v29-red':'v29-green'],
  ['团队总人数',stats.count,stats.qualified?'v29-green':'v29-red'],
  ['团队输赢',Number(m.subtree_profit_cents||0),Number(m.subtree_profit_cents||0)>0?'v29-green':Number(m.subtree_profit_cents||0)<0?'v29-red':'v29-neutral']
 ];
 for(const [label,value,cls] of rows){
  const tr=mk('tr');tr.append(mk('td','',label));
  const printed=label==='团队总人数'?(String(value)+'人（满'+stats.months+'月 / 目标≥'+stats.quota+'人）'):money(value,true);
  tr.append(mk('td',cls,printed));table.append(tr);
 }
 wrap.append(table);
 const risk=riskForMember(m);
 const foot=mk('div','v29-risk-footer');
 foot.append(mk('span','','团队风险：平均余额 '+money(stats.average,true)+' · 团队建议放款 '+money(stats.suggest,true)+' · 收益/余额 '));
 foot.append(mk('strong','v29-grade-'+risk.grade,risk.pct===null?'—':risk.pct.toFixed(1)+'%'));
 wrap.append(foot);
 wrap.append(mk('small','v28-pop-help','团队建议放款按未解除告警成员各自仓位的目标余额计算；仅为规则提示，不执行放款。'));
 return wrap;
}
function moveCompactTooltip(e,node){
 if(!compactTooltipEl)return;
 const r=node.getBoundingClientRect(),w=compactTooltipEl.offsetWidth||420,h=compactTooltipEl.offsetHeight||330;
 const x=e&&Number.isFinite(e.clientX)?e.clientX:r.right;
 const y=e&&Number.isFinite(e.clientY)?e.clientY:r.top;
 let left=x+12,top=y+12;
 if(left+w>window.innerWidth-8)left=x-w-14;
 if(top+h>window.innerHeight-8)top=y-h-14;
 compactTooltipEl.style.left=Math.max(7,Math.min(Math.max(7,window.innerWidth-w-7),left))+'px';
 compactTooltipEl.style.top=Math.max(7,Math.min(Math.max(7,window.innerHeight-h-7),top))+'px';
}
// V32: mount compact hover details inside the fullscreen top layer.
function compactTooltipHost(node){
 const full=document.fullscreenElement;
 if(full&&full.contains(node))return full;
 const panel=fullscreenPanel();
 if(panel&&panel.classList.contains('fullscreen-fallback')&&panel.contains(node))return panel;
 return document.body;
}
function attachCompactHover(node,m){
 const show=e=>{hideCompactTooltip();compactTooltipEl=mk('div','v28-compact-tooltip');compactTooltipEl.setAttribute('role','tooltip');compactTooltipEl.append(compactInfo(m));compactTooltipHost(node).append(compactTooltipEl);moveCompactTooltip(e,node)};
 node.addEventListener('mouseenter',show);
 node.addEventListener('mousemove',e=>{if(!compactTooltipEl)show(e);else moveCompactTooltip(e,node)});
 node.addEventListener('mouseleave',()=>{if(typeof setTimeout==='function'&&compactTooltipEl?.querySelector?.('.v42-team-buttons'))setTimeout(()=>{if(compactTooltipEl&&!compactTooltipEl.matches(':hover'))hideCompactTooltip()},260);else hideCompactTooltip()});
 node.addEventListener('focus',()=>show(null));
 node.addEventListener('blur',()=>{if(typeof setTimeout==='function'&&compactTooltipEl?.querySelector?.('.v42-team-buttons'))setTimeout(()=>{if(compactTooltipEl&&!compactTooltipEl.matches(':hover'))hideCompactTooltip()},260);else hideCompactTooltip()});
}
function toggleCompactTree(){
 compactMode=!compactMode;hideCompactTooltip();
 branchViewportReady=false;branchResetRequested=true;
 persistTabView();render();
 showToast(compactMode?'简洁版已开启：悬停会员可查看全部个人与团队数据':'已恢复完整版');
}

function nodeCard(x,isRoot,newByNode,day,summaryByNode){const li=mk('li'),age=membershipMonths(x.joined_on,day),isNew=String(x.joined_on)===day;
 const ownWithdraw=Number(x.daily_withdraw_cents||0),glow=withdrawGlowOn&&ownWithdraw!==0;
 const card=mk('div','member age-'+age+(riskMode?' risk-grade-'+riskForMember(x).grade:'')+(isRoot?' root':'')+(isNew?' joined-today':'')+(query&&x.account.toLowerCase().includes(query.toLowerCase())?' matched':'')+(glow?' withdraw-glow':'')+(riskFocusId===x.id&&riskMode?' risk-focus':''));
 if(positionAlarmOn){
  const notice=v29Position(x);
  if(notice.active){
   card.classList.add('v29-position-alert');
   const label=mk('span','v29-position-label','建议放款 '+money(notice.cents,true));
   card.append(label);
  }
 }
 card.dataset.memberId=x.id;card.title=isNew?'今日加入：绿色背景与蓝色边框；北京时间零点后自动恢复入会时长对应颜色':age===0?'加入不足1个月':`加入已满${age}个月${age===6?'（6个月及以上）':''}`;if(compactMode&&view==='tree'){
  card.classList.add('v28-member-mini');card.tabIndex=0;card.title='';
  card.append(mk('b','v28-mini-account',x.account),mk('small','v28-mini-date',x.joined_on||'—'));
  if(x.direct_count){
   const btn=mk('button','v28-mini-fold',collapsed.has(x.id)&&!query?'+':'−');
   btn.type='button';btn.title=collapsed.has(x.id)?'展开下级':'收起下级';btn.setAttribute('aria-label',btn.title);
   btn.onclick=e=>{e.stopPropagation();collapsed.has(x.id)?collapsed.delete(x.id):collapsed.add(x.id);hideCompactTooltip();persistTabView();render()};
   card.append(btn);
  }
  attachCompactHover(card,x);li.append(card);return li
 }
 const head=mk('div','member-top'),iden=mk('div','account');iden.append(mk('span','avatar','会'));const top=mk('div','member-details'),title=mk('div','member-title');title.append(mk('b','',x.account),mk('span','level-tag',`第${x.level||1}层`),mk('span','remark-tag',`备注：${x.remark||'无'}`));top.append(title,mk('small','',`加入日期：${x.joined_on}`));
 if(glow)top.append(mk('div','withdraw-glow-amount',`今日提现 ${money(ownWithdraw,true)}`));
 iden.append(top);head.append(iden);const ops=mk('div','nodeactions');ops.append(mk('span','count',`直属 ${x.direct_count} · 全部下级 ${x.descendant_count}`));if(x.direct_count){const btn=mk('button','tiny',collapsed.has(x.id)&&!query?'＋ 展开':'－ 收起');btn.onclick=()=>{collapsed.has(x.id)?collapsed.delete(x.id):collapsed.add(x.id);persistTabView();render()};ops.append(btn)}{const btn=mk('button','tiny export-layers','导出逐层表格');btn.onclick=()=>downloadLayers(x.account);ops.append(btn)}if(role==='admin'){const edit=mk('button','tiny','编辑');edit.onclick=()=>openEdit(x);ops.append(edit)}head.append(ops);card.append(head);card.append(newBadge(x,newByNode,day,summaryByNode));const grid=mk('div','metricrow');grid.append(
 metric('建仓资金',x.stake_cents,x.direct_stake_cents,x.subtree_stake_cents),
 metric('当前余额',x.balance_cents,x.direct_balance_cents,x.subtree_balance_cents),
 metric('累计总提现',x.total_withdraw_cents,x.direct_total_withdraw_cents,x.subtree_total_withdraw_cents),
 metric('当日提现',x.daily_withdraw_cents,x.direct_daily_withdraw_cents,x.subtree_daily_withdraw_cents,true),
 metric('输赢（建仓－总提现）',x.profit_cents,x.direct_profit_cents,x.subtree_profit_cents));card.append(grid);li.append(card);return li}
// V24 visual-only risk comparison: ratios are based on recorded subtree amounts,
// not an audit of profitability, liquidity or real-world financial safety.
// Four mutually exclusive bands resolve overlapping descriptions: loss, 0-10%, 10-20%, 20%+.
function riskForMember(row){
 const balance=Number(row.subtree_balance_cents||0),profit=Number(row.subtree_profit_cents||0);
 if(!Number.isFinite(balance)||!Number.isFinite(profit)||balance<=0)return {grade:'unknown',label:'余额为0／无法评估',pct:null,balance,profit};
 const ratio=profit/balance;
 const grade=ratio<0?'danger':ratio<.10?'warning':ratio<.20?'improve':'healthy';
 const label={danger:'深红 · 团队亏损',warning:'淡红 · 盈利低于10%',improve:'淡绿 · 盈利10%—20%',healthy:'深绿 · 盈利达到20%'}[grade];
 return {grade,label,pct:ratio*100,balance,profit};
}
function riskGroupRanking(rows=members){
 const groups=new Map(TREE_GROUPS.map(group=>[group,{group,count:0,risks:0,danger:0,warning:0,improve:0,healthy:0,unknown:0,nodes:[]}]));
 for(const m of rows){
  const group=String(m.group_account||m.account||'');
  const bucket=groups.get(group);if(!bucket)continue;
  const r=riskForMember(m);bucket.count++;bucket[r.grade]++;
  if(r.grade==='danger'||r.grade==='warning')bucket.risks++;
  bucket.nodes.push({id:m.id,account:m.account,level:m.level||1,...r});
 }
 return [...groups.values()].sort((a,b)=>b.risks-a.risks||b.danger-a.danger||a.group.localeCompare(b.group,'zh-CN'));
}
function focusRiskTreeNode(id){
 const member=members.find(r=>r.id===id);if(!member)return;
 if(selectedTreeGroup&&member.group_account!==selectedTreeGroup)selectedTreeGroup='';
 riskFocusId=id;collapsed.clear();branchClosed.clear();query='';el('search').value='';
 if(view==='branch'){
  branchSelectedAccount=member.account;
  branchFocusRequested=true;branchViewportReady=false;branchResetRequested=true;
 }else branchSelectedAccount='';
 persistTabView();render();
 if(view==='tree')setTimeout(()=>{
  const node=[...document.querySelectorAll('.member[data-member-id]')].find(n=>n.dataset.memberId===id);
  if(node)node.scrollIntoView({behavior:'smooth',block:'center',inline:'center'});
 },100);
}
function toggleRiskTree(){
 riskMode=!riskMode;riskFocusId='';
 if(!riskMode)branchSelectedAccount='';
 render();
 showToast(riskMode?'已按每个节点本人及全部下级的团队余额与团队收益独立着色；点击组别可展开风险明细。':'已恢复入会时间七色卡');
}
function toggleWithdrawalTree(){
 withdrawGlowOn=!withdrawGlowOn;
 if(withdrawGlowOn)collapsed.clear();
 persistTabView();render();showToast(withdrawGlowOn?'红色光圈已显示今日有提现的会员':'已关闭提现光圈');
}
function riskBanner(){
 const box=mk('section','risk-banner v24-risk-banner');box.setAttribute('role','region');box.setAttribute('aria-label','五组按节点独立收益余额比评估');
 const head=mk('div','risk-panel-header');head.append(mk('strong','','五组节点风险评估（实时）'));
 const hide=mk('button','tiny','收起');hide.type='button';hide.onclick=toggleRiskTree;head.append(hide);box.append(head);
 box.append(mk('p','risk-meaning','深红：亏损｜淡红：收益／余额＜10%｜淡绿：10%—＜20%｜深绿：≥20%；余额为0单列。按节点团队汇总，不是实际财务风险评级。'));
 const line=mk('div','risk-chip-row risk-groups');
 for(const g of riskGroupRanking()){
  const details=document.createElement('details');details.className='risk-group-detail';
  if(selectedTreeGroup===g.group)details.open=true;
  const summary=document.createElement('summary');summary.className='risk-chip';
  summary.append(mk('strong','',`${g.group}组：风险 ${g.risks}/${g.count}`));
  summary.append(mk('span','',`深红${g.danger} · 淡红${g.warning} · 待核对${g.unknown}`));
  details.append(summary);
  const list=mk('div','risk-node-list');
  const affected=g.nodes.filter(n=>n.grade==='danger'||n.grade==='warning').sort((a,b)=>(a.pct??-999)-(b.pct??-999));
  if(affected.length===0)list.append(mk('p','risk-empty','没有深红或淡红节点'));
  for(const n of affected){
   const btn=mk('button',`risk-node-row risk-${n.grade}`,`${n.account}（第${n.level}层）· ${n.label} · ${n.pct===null?'—':n.pct.toFixed(1)+'%'} · 余额 ${money(n.balance,true)} · 收益 ${money(n.profit,true)}`);
   btn.type='button';btn.onclick=()=>focusRiskTreeNode(n.id);list.append(btn);
  }
  details.append(list);line.append(details);
 }
 box.append(line);return box;
}
// V33: compact left-column review queue, one line per active warning.
function v33AlertPanel(visibleRows){
 const box=mk('aside','v33-alarm-sidebar');
 box.setAttribute('role','region');
 box.setAttribute('aria-label','待处理仓位告警人员名单');
 const visible=new Set(visibleRows.map(x=>x.id));
 const ranked=members.filter(x=>visible.has(x.id)&&v29Position(x).active).map(x=>({member:x,alert:v29Position(x)}));
 ranked.sort((a,b)=>b.alert.overdue_days-a.alert.overdue_days||b.alert.cents-a.alert.cents||a.member.account.localeCompare(b.member.account));
 const title=mk('div','v33-alarm-heading');
 title.append(mk('strong','','待处理仓位告警 · '+ranked.length+'人'));
 const hide=mk('button','tiny','收起');
 hide.type='button';hide.onclick=togglePositionAlarm;title.append(hide);box.append(title);
 const hint=mk('p','v33-alarm-tip','告警后3天内处理；余额降至解除线自动移出。列表只供核对，不自动放款。');
 box.append(hint);
 const list=mk('div','v33-alarm-list');
 if(!ranked.length)list.append(mk('p','v33-alarm-empty','当前没有待处理的仓位告警'));
 for(const entry of ranked){
  const m=entry.member,w=entry.alert;
  const over=w.overdue_days>0;
  const btn=mk('button','v33-alarm-person'+(over?' v33-alarm-overdue':''),'');
  btn.type='button';btn.title='定位会员 '+m.account;
  btn.append(mk('b','v33-alarm-account',m.account));
  btn.append(mk('span','','仓位 '+money(m.stake_cents,true)+' · 余额 '+money(m.balance_cents,true)));
  btn.append(mk('strong','v33-alarm-amount','建议放款 '+money(w.cents,true)));
  btn.append(mk('small','v33-alarm-time'+(over?' overdue':''),
   over?'已超期'+w.overdue_days+'天':('剩余'+w.remaining_days+'天 · 告警日 '+(w.started_on||'今日'))));
  btn.onclick=()=>{
    if(view!=='branch')view='branch';
    if(selectedTreeGroup&&selectedTreeGroup!==m.group_account)selectedTreeGroup=m.group_account||'';
    branchClosed.clear();
    branchSelectedAccount=m.account;
    branchFocusRequested=true;branchViewportReady=false;branchResetRequested=true;
    persistTabView();render();
  };
  list.append(btn);
 }
 box.append(list);return box;
}

function renderTree(){const {m,graph}=descendants(),visible=getShown(),groupVisible=new Set(shownTreeMembers().map(r=>r.id));const day=businessDay||dateNow(),newByNode=todaysNewByNode(members,day),summaryByNode=teamSummaryByNode(members,day);
 const outer=mk('div','tree-main'+(riskMode?' tree-risk-mode':'')+(compactMode?' v28-compact':''));
 if(riskMode)outer.append(riskBanner());
 if(positionAlarmOn)outer.append(v33AlertPanel(shownTreeMembers()));
 if(withdrawGlowOn)outer.append(mk('p','withdraw-notice',`红色光圈：今日有提现的本人会员 · 共 ${shownTreeMembers().filter(x=>Number(x.daily_withdraw_cents||0)!==0).length} 位（点击按钮可关闭）`));
 const tree=mk('ul','tree'+(treeVertical?' vertical-tree':'')),roots=members.filter(x=>groupVisible.has(x.id)&&(!x.parent_id||!groupVisible.has(x.parent_id)));const seen=new Set();function walk(x,level){if(seen.has(x.id)||!groupVisible.has(x.id)||visible&&!visible.has(x.id))return null;seen.add(x.id);const li=nodeCard(x,level===0,newByNode,day,summaryByNode);if(!collapsed.has(x.id)||query){const children=graph.get(x.id)||[];const sub=mk('ul');for(const k of children){const child=walk(k,level+1);if(child)sub.append(child)}if(sub.childNodes.length)li.append(sub)}return li}for(const root of roots){const li=walk(root,0);if(li)tree.append(li)}outer.append(tree);return outer}
function renderList(){const wrap=mk('div','simple-list'),header=mk('div','itemrow head');['会员账号','加入日期','层级','备注','建仓资金','余额','总提现','当日提现','本人输赢','操作'].forEach(x=>header.append(mk('span','',x)));wrap.append(header);for(const r of members.filter(x=>!query||x.account.toLowerCase().includes(query.toLowerCase()))){const row=mk('div','itemrow');const cells=[r.account,r.joined_on,`第${r.level||1}层`,r.remark||'—',money(r.stake_cents),money(r.balance_cents),money(r.total_withdraw_cents,true),money(r.daily_withdraw_cents,true),money(r.profit_cents)];cells.forEach((x,i)=>row.append(mk(i===0?'b':'span',i>=4?amountClass([r.stake_cents,r.balance_cents,r.total_withdraw_cents,r.daily_withdraw_cents,r.profit_cents][i-4],i===7?'daily':i===8?'profit':'normal'):'',x)));const actions=mk('div','row-actions'),exportBtn=mk('button','tiny export-layers','逐层导出');exportBtn.onclick=()=>downloadLayers(r.account);actions.append(exportBtn);if(role==='admin'){const b=mk('button','tiny','编辑');b.onclick=()=>openEdit(r);actions.append(b)}row.append(actions);wrap.append(row)}return wrap}
function downloadNode(account){if(role!=='admin')return;testDownloadMembers(account)}
function downloadLayers(account){if(!role)return;testDownloadLayers(account)}
function groupFor(x){return x.group_account||x.account}
function tableNodeIds(rootAccount){if(!rootAccount)return null;const root=members.find(m=>m.account===rootAccount);if(!root)return new Set();const selected=new Set([root.id]);let changed=true;while(changed){changed=false;for(const r of members){if(r.parent_id&&selected.has(r.parent_id)&&!selected.has(r.id)){selected.add(r.id);changed=true}}}return selected}
function renderDataTable(){
  const wrap=mk('div','table-data'),toolbar=mk('div','table-toolbar');
  const label=mk('div','table-intro');label.append(mk('b','', '会员节点表格数据'),mk('small','', '选择本人／直属一层／全部层级，快速查看对应金额；每行保留所属分组和直属上级。'));wrap.append(label);
  const filter=mk('div','table-filters');
  const gp=mk('select','filter-select');gp.append(new Option('全部分组',''));const groups=[...new Set(members.map(x=>groupFor(x)))].sort();groups.forEach(g=>gp.append(new Option('分组：'+g,g)));gp.value=tableGroup;gp.onchange=()=>{tableGroup=gp.value;tableScope='';render()};filter.append(gp);
  const range=mk('select','filter-select');range.append(new Option('全部会员',''));members.slice().sort((a,b)=>a.account.localeCompare(b.account,'zh-CN')).forEach(x=>range.append(new Option('仅看节点 '+x.account+' 及所有下级',x.account)));range.value=tableScope;range.onchange=()=>{tableScope=range.value;render()};filter.append(range);
  const metricMode=mk('select','filter-select');[['self','本人数据'],['direct','直属一层数据'],['subtree','节点全部层级数据']].forEach(x=>metricMode.append(new Option(x[1],x[0])));metricMode.value=tableMetric;metricMode.onchange=()=>{tableMetric=metricMode.value;render()};filter.append(metricMode);
  if(tableScope){const exportLayers=mk('button','button','导出选中节点逐层表格');exportLayers.onclick=()=>downloadLayers(tableScope);filter.append(exportLayers)}if(role==='admin'){const exportAll=mk('button','button','导出全部会员明细');exportAll.onclick=()=>{if(tableScope)downloadNode(tableScope);else testDownloadMembers()};filter.append(exportAll)}
  wrap.append(filter);
  const scoped=tableNodeIds(tableScope), rows=members.filter(x=>(!query||x.account.toLowerCase().includes(query.toLowerCase()))&&(!tableGroup||groupFor(x)===tableGroup)&&(!scoped||scoped.has(x.id)));
  const status=mk('p','table-status',`当前显示 ${rows.length} / ${members.length} 位会员 · 统计口径：${tableMetric==='self'?'本人':tableMetric==='direct'?'直推':'本人和所有下级'}`);wrap.append(status);
  const shell=mk('div','table-scroll'),table=mk('table','member-table'),thead=mk('thead'),theadRow=mk('tr');
  ['会员账号','所在分组','直属上级','加入日期','层级','备注','直属人数','团队下级','建仓资金','余额','总提现','当日提现','输赢','节点操作'].forEach(v=>theadRow.append(mk('th','',v)));
  thead.append(theadRow);table.append(thead);
  const tbody=mk('tbody');const prefix=tableMetric==='self'?'':tableMetric+'_';
  rows.forEach(x=>{const tr=mk('tr');const cells=[x.account,groupFor(x),x.parent_account||'—',x.joined_on,String(x.level||1),x.remark||'—',String(x.direct_count),String(x.descendant_count),money(x[prefix+'stake_cents']),money(x[prefix+'balance_cents']),money(x[prefix+'total_withdraw_cents'],true),money(x[prefix+'daily_withdraw_cents'],true),money(x[prefix+'profit_cents'])];cells.forEach((v,i)=>{const values=[x[prefix+'stake_cents'],x[prefix+'balance_cents'],x[prefix+'total_withdraw_cents'],x[prefix+'daily_withdraw_cents'],x[prefix+'profit_cents']];const td=mk('td',i>=8?'money-cell '+amountClass(values[i-8],i===11?'daily':i===12?'profit':'normal'):'',v);if(i===0)td.classList.add('account-cell');tr.append(td)});const action=mk('td','actions-cell');const browse=mk('button','tiny','查看节点');browse.onclick=()=>{tableScope=x.account;query='';el('search').value='';render()};action.append(browse);{const ex=mk('button','tiny export-layers','逐层导出');ex.onclick=()=>downloadLayers(x.account);action.append(ex)}tr.append(action);tbody.append(tr)});
  if(rows.length===0){const tr=mk('tr'),td=mk('td','empty','没有符合筛选条件的会员');td.colSpan=14;tr.append(td);tbody.append(tr)}
  table.append(tbody);shell.append(table);wrap.append(shell);
  const foot=mk('p','table-footnote','所属分组为该会员向上追溯到的最顶层根账号；直属一层统计不包含节点本人。逐层导出仅含本人数据，下面按第1层、第2层……分别汇总各层人数和金额，不列出下级个人明细。');wrap.append(foot);
  return wrap
}
function v33ActiveRankingMembers(entry,rows,day,period){
 const byParent=new Map();
 for(const member of rows){
  const items=byParent.get(member.parent_id)||[];
  items.push(member);byParent.set(member.parent_id,items);
 }
 const selected=[],todo=[entry.id],seen=new Set();
 const index=new Map(rows.map(m=>[m.id,m]));
 while(todo.length){
  const id=todo.pop();
  if(seen.has(id))continue;
  seen.add(id);
  const m=index.get(id);
  if(!m)continue;
  const amount=periodAmounts(m,day,period);
  if(amount.deposit!==0||amount.withdraw!==0){
   selected.push({member:m,deposit:amount.deposit,withdraw:amount.withdraw,score:amount.deposit-amount.withdraw});
  }
  for(const child of byParent.get(id)||[])todo.push(child.id);
 }
 selected.sort((a,b)=>Number(a.member.level||0)-Number(b.member.level||0)||b.deposit-a.deposit||b.withdraw-a.withdraw||a.member.account.localeCompare(b.member.account));
 return selected;
}

function renderRanking(){
 const day=businessDay||dateNow(),all=computeRanking(members,day,rankPeriod);
 const ordered=rankSort==='asc'?all.slice().reverse():all;
 const filtered=ordered.filter(x=>!query||x.account.toLowerCase().includes(query.toLowerCase()));
 const root=mk('div','ranking v12-ranking');
 const header=mk('div','ranking-header');
 header.append(mk('div','ranking-title','🏆 团队排行榜'));
 const tabs=mk('div','v12-tabs');
 for(const [p,title] of [['daily','当日榜单'],['week','周榜单'],['month','月榜单'],['total','总榜单']]){
  const b=mk('button','button'+(rankPeriod===p?' selected':''),title);
  b.onclick=()=>{rankPeriod=p;rankExpanded.clear();render()};tabs.append(b);
 }
 header.append(tabs);
 header.append(mk('p','ranking-note','排行榜统计整个团队；点击「详细」仅列出本期有充值或提现的会员账号，零活动会员不列出。'));
 const switcher=mk('div','ranking-switch');for(const [mode,label] of [['desc','从高到低'],['asc','从低到高']]){
  const btn=mk('button','button'+(rankSort===mode?' selected':''),label);
  btn.onclick=()=>{rankSort=mode;render()};switcher.append(btn);
 }
 header.append(switcher);
 const maximize=mk('button','button ranking-fullscreen-btn',fullscreenActive()?'⛶ 退出全屏':'⛶ 排行榜最大化');
 maximize.id='rankingFullscreenBtn';maximize.type='button';maximize.title='最大化排行榜，Alt+Enter 切换，Esc 退出';maximize.setAttribute('aria-pressed',String(fullscreenActive()));maximize.onclick=toggleTreeFullscreen;
 header.append(maximize);root.append(header);
 if(rankPeriod==='week'||rankPeriod==='month'){
  const start=periodStart(day,rankPeriod),since=historyCoverage.tracking_since||day;
  const required=[];let cursor=new Date(start+'T12:00:00Z'),end=new Date(day+'T12:00:00Z');
  while(cursor<=end){required.push(cursor.toISOString().slice(0,10));cursor.setUTCDate(cursor.getUTCDate()+1)}
  const recorded=new Set(historyCoverage.imported_days||[]),missing=required.filter(d=>!recorded.has(d));
  if(since>start||missing.length){
   root.append(mk('p','v12-coverage-warning',`⚠ ${rankPeriod==='week'?'本周':'本月'}提现历史可能不完整：数据从 ${since} 起跟踪；本统计期 ${missing.length} 天没有完整的每日提现上传记录。缺失日期不推算，榜单仅供参考。`));
  }else root.append(mk('p','v12-coverage-ok','本统计期已有逐日提现上传记录。'));
 }
 const shell=mk('div','table-scroll'),table=mk('table','member-table ranking-table'),thead=mk('thead'),tr=mk('tr');
 const prefix=rankPeriod==='daily'?'当日':rankPeriod==='week'?'本周':rankPeriod==='month'?'本月':'累计';
 ['名次','团队名称','第二层账号','所属第1层','团队人数',`${prefix}新增建仓`,`${prefix}团队提现`,`${prefix}团队输赢`,'团队总余额','操作'].forEach(x=>tr.append(mk('th','',x)));
 thead.append(tr);table.append(thead);const body=mk('tbody');
 filtered.forEach((entry,i)=>{
  const tr=mk('tr');
  const vals=[String(rankSort==='desc'?all.findIndex(x=>x.account===entry.account)+1:all.length-all.findIndex(x=>x.account===entry.account)),entry.teamName||'（未命名）',entry.account,entry.group,String(entry.teamCount),money(entry.dailyStake,true),money(entry.dailyWithdraw,true),(entry.score>0?'+':'')+money(entry.score,true),money(entry.teamBalance,true)];
  vals.forEach((v,k)=>{
   let cls=k===0||k>=4?'ranking-number':'';
   if(k===5)cls+=' '+(entry.dailyStake>0?'amount-green':entry.dailyStake<0?'amount-red':'amount-black');
   if(k===6)cls+=' '+amountClass(entry.dailyWithdraw,'daily');
   if(k===7)cls+=' '+amountClass(entry.score,'profit');
   if(k===8)cls+=' '+amountClass(entry.teamBalance);
   const td=mk('td',cls.trim(),v);if(k===2)td.classList.add('account-cell');tr.append(td)});
  const td=mk('td','ranking-actions');const open=rankExpanded.has(entry.account);
  const btn=mk('button','tiny v12-detail-toggle',open?'收起详细':'详细');
  btn.onclick=()=>{open?rankExpanded.delete(entry.account):rankExpanded.add(entry.account);render()};td.append(btn);if(role==='admin'){const rename=mk('button','tiny','改队名');rename.onclick=async()=>{const name=prompt('填写第2层团队名称（最多20字；留空表示清除）：',entry.teamName);if(name===null)return;try{await api('/admin/team-name/'+encodeURIComponent(entry.id),'POST',{name:name.trim()});await refresh();showToast('团队名称已保存')}catch(e){showToast(e.message)}};td.append(rename)}tr.append(td);body.append(tr);
     if(open){
    const detailRow=mk('tr','ranking-detail-row'),cell=mk('td','ranking-detail-cell');cell.colSpan=10;
    const active=v33ActiveRankingMembers(entry,members,day,rankPeriod);
    cell.append(mk('b','','本期有充值或提现的会员明细（'+active.length+'人）'));
    const subt=mk('table','v12-layer-table'),th=mk('tr');
    ['会员账号','所属层级','备注',prefix+'充值',prefix+'提现',prefix+'输赢','本人余额'].forEach(z=>th.append(mk('th','',z)));
    subt.append(th);
    for(const entry of active){
     const m=entry.member,rt=mk('tr');
     const values=[m.account,'第'+m.level+'层',m.remark||'—',
       money(entry.deposit,true),money(entry.withdraw,true),
       (entry.score>0?'+':'')+money(entry.score,true),money(m.balance_cents,true)];
     values.forEach((value,k)=>{
      const cls=k===3?(entry.deposit>0?'amount-green':'amount-black'):
                k===4?amountClass(entry.withdraw,'daily'):
                k===5?amountClass(entry.score,'profit'):k===6?amountClass(m.balance_cents):'';
      rt.append(mk('td',cls,value));
     });
     subt.append(rt);
    }
    if(!active.length){
     const tr=mk('tr'),td=mk('td','empty','本期该团队没有充值或提现记录');
     td.colSpan=7;tr.append(td);subt.append(tr);
    }
    cell.append(subt);detailRow.append(cell);body.append(detailRow);
   }
 });
 if(!filtered.length){const tr=mk('tr'),td=mk('td','empty',all.length?'没有符合搜索条件的第2层会员':'暂无第2层会员');td.colSpan=10;tr.append(td);body.append(tr)}
 table.append(body);shell.append(table);root.append(shell);
 root.append(mk('p','ranking-note',`口径：${prefix}榜＝本统计期新会员建仓－本统计期团队提现，均包含该第2层账号及全部下级；总榜＝累计建仓－累计提现。周榜按北京时间周一至周日、月榜按自然月；原系统没有的历史提现明细不会被推测补齐。`));
 return root;
}

// Read-only left-to-right distribution map derived from the same /api/tree records.
// Only display state changes when zooming, panning or folding a branch.
function svgEl(tag, attrs={}, txt){
 const x=document.createElementNS('http://www.w3.org/2000/svg',tag);
 for(const [k,v] of Object.entries(attrs))x.setAttribute(k,String(v));
 if(txt!==undefined)x.textContent=String(txt);return x;
}
function branchLayout(rows,folded,vertical=false){
 const byId=new Map(rows.map(r=>[r.id,r]));
 const children=new Map(rows.map(r=>[r.id,[]]));
 const roots=[];
 for(const r of rows){const parent=children.get(r.parent_id);if(parent)parent.push(r);else roots.push(r)}
 const positions=new Map();let nextLeaf=0,maxDepth=0;const gapY=compactMode?64:139,gapX=compactMode?186:368,offsetX=compactMode?20:52,offsetY=compactMode?40:72;
 function place(r,depth,stack){
  if(stack.has(r.id))return;const here=new Set(stack);here.add(r.id);
  const visible=folded.has(r.id)?[]:children.get(r.id)||[];
  const first=nextLeaf;
  for(const c of visible)place(c,depth+1,here);
  let y;
  if(nextLeaf===first){y=nextLeaf*gapY+offsetY;nextLeaf++}
  else{const ys=visible.filter(x=>positions.has(x.id)).map(x=>positions.get(x.id).y);
    y=ys.length?(Math.min(...ys)+Math.max(...ys))/2:nextLeaf++*gapY+offsetY}
  positions.set(r.id,{x:depth*gapX+offsetX,y,depth});maxDepth=Math.max(maxDepth,depth)
 }
 for(const r of roots)place(r,0,new Set());
 const edges=[];for(const r of rows){if(!positions.has(r.id)||!positions.has(r.parent_id)||folded.has(r.parent_id))continue;edges.push([r.parent_id,r.id])}
 
 return {positions,edges,width:Math.max(320,(maxDepth+1)*gapX+(compactMode?35:150)),height:Math.max(220,nextLeaf*gapY+(compactMode?50:150)),roots:roots.length};
}
function branchAgeLegend(){const div=mk('div','branch-age-legend');div.append(mk('b','','入会时间：'));div.append(mk('span','swatch joined-today','今日新增（绿色蓝框）'));for(const [i,label] of [[0,'未满1个月'],[1,'满1个月'],[2,'满2个月'],[3,'满3个月'],[4,'满4—5个月'],[6,'满6个月以上']]){div.append(mk('span','swatch age-'+i,label))}return div}
function branchMemberDetail(id){const m=members.find(x=>x.id===id);if(!m){showToast('会员不存在，请刷新');return}detailId=m.id;view='detail';query='';el('search').value='';render();document.querySelector('.panel')?.scrollIntoView({behavior:'smooth',block:'start'})}
function renderMemberDetail(){const root=mk('div','member-detail'),m=members.find(x=>x.id===detailId);if(!m){root.append(mk('p','empty','没有找到该会员'));return root}const top=mk('div','member-detail-intro');const back=mk('button','button','← 返回分支概览图');back.onclick=()=>{view='branch';render()};top.append(back,mk('h3','',`会员 ${m.account} · 详细概览`));if(role==='admin'){const edit=mk('button','button','✎ 直接修改备注');edit.onclick=()=>quickEditRemark(m);top.append(edit)}const only=mk('button','button','▤ 仅看本团队');only.onclick=()=>teamOnlyShow(m.id);top.append(only);
 if(role==='admin'){const down=mk('button','button','⇩ 导出本团队');down.onclick=()=>teamExportDialog(m.id);top.append(down)}
 root.append(top);root.append(branchAgeLegend());const tree=mk('ul','tree'),day=businessDay||dateNow();tree.append(nodeCard(m,!m.parent_id,todaysNewByNode(members,day),day,teamSummaryByNode(members,day)));root.append(tree);const direct=members.filter(x=>x.parent_id===m.id);if(direct.length){root.append(mk('h3','','直属下级（点击继续查看详情）'));const links=mk('div','members-links');for(const child of direct){const btn=mk('button','button',child.account+'  ·  '+money(child.stake_cents,true));btn.onclick=()=>branchMemberDetail(child.id);links.append(btn)}root.append(links)}return root}
function quickEditRemark(m){if(role!=='admin'){showToast('仅测试管理员可修改备注');return}const found=members.find(x=>x.id===m.id);if(!found){showToast('会员已不存在');return}el('remarkAccount').textContent=`会员：${found.account} ｜ 加入：${found.joined_on} ｜ 建仓：${money(found.stake_cents,true)}`;el('remarkDialog').dataset.memberId=found.id;el('quickRemark').value=found.remark||'';el('remarkError').textContent='';el('remarkDialog').showModal();el('quickRemark').focus()}
async function saveQuickRemark(e){e.preventDefault();const m=members.find(x=>x.id===el('remarkDialog').dataset.memberId);if(!m){el('remarkError').textContent='该会员已不存在';return}const note=el('quickRemark').value.trim();if([...note].length>20){el('remarkError').textContent='备注最多20字';return}const parent=members.find(x=>x.id===m.parent_id)?.account||null;const payload={account:m.account,joined_on:m.joined_on,parent_account:parent,stake:m.stake_cents/100,total_withdraw:(m.total_withdraw_cents/100).toFixed(2),remark:note,expected_revision:m.revision};try{await api('/members/'+encodeURIComponent(m.id),'PUT',payload);el('remarkDialog').close();await refresh();await syncUndoStatus();showToast('备注已更新（可撤回）')}catch(err){el('remarkError').textContent=err.message}}
function locateBranchAccount(){
 const field=el('search');const searched=field.value.trim();
 if(!searched){showToast('请输入完整会员账号，再点击「精准定位」');field.focus();return false}
 const member=members.find(m=>m.account===searched);
 if(!member){
  branchSelectedAccount='';field.setCustomValidity('未找到完整账号，请检查前导0和大小写');
  showToast('未找到此完整会员账号。请输入完整账号（不是部分数字）。');
  if(view==='branch')render();field.focus();return false
 }
 field.setCustomValidity('');
 const index=new Map(members.map(m=>[m.id,m]));let cur=member,steps=0;
 while(cur&&cur.parent_id&&steps++<members.length){branchClosed.delete(cur.parent_id);cur=index.get(cur.parent_id)}
 if(selectedTreeGroup&&member.group_account!==selectedTreeGroup)selectedTreeGroup=member.group_account&&TREE_GROUPS.includes(member.group_account)?member.group_account:'';
 branchSelectedAccount=member.account;branchFocusRequested=true;branchViewportReady=false;branchResetRequested=true;view='branch';persistTabView();render();
 showToast('已精准定位：'+member.account+'，黄色节点位于屏幕中心');
 return true
}
// V23: on-demand read-only five-group comparison. This is a transparent rule-based analysis, not an external AI model.
function evaluateAllGroups(){
 const day=businessDay||dateNow(),summaries=TREE_GROUPS.map(g=>{
  const rows=members.filter(m=>String(m.group_account||m.account)===g);
  const newRows=rows.filter(m=>String(m.joined_on)===day);
  const count=rows.length,newCount=newRows.length,newStake=newRows.reduce((a,m)=>a+Number(m.stake_cents||0),0);
  const withdrawal=rows.reduce((a,m)=>a+Number(m.daily_withdraw_cents||0),0);
  const balance=rows.reduce((a,m)=>a+Number(m.balance_cents||0),0);
  const older=rows.filter(m=>membershipMonths(m.joined_on,day)>=4).length;
  const withdrawn=rows.filter(m=>Number(m.daily_withdraw_cents||0)!==0).length;
  return {group:g,rows,count,newCount,newStake,withdrawal,balance,older,withdrawn,
   avg:count?balance/count:null,rate:count?newCount/count*100:null,profit:newStake-withdrawal};
 });
 const active=summaries.filter(g=>g.count>0),meanRate=active.length?active.reduce((a,g)=>a+g.rate,0)/active.length:0;
 return {day,summaries,meanRate};
}
function openAIEvaluation(){
 const {day,summaries,meanRate}=evaluateAllGroups();
 const dialog=document.createElement('dialog');dialog.className='ai-eval-dialog';
 const header=mk('div','ai-eval-head'),heading=mk('div');heading.append(mk('h2','','五组 AI评估 · 数据对比'),mk('small','','依据当前已录入数据作规则分析，不调用外部模型、不修改会员数据。'));
 const close=mk('button','tiny','✕ 关闭');close.type='button';close.onclick=()=>dialog.close();header.append(heading,close);dialog.append(header);
 const body=mk('div','ai-eval-body');body.append(mk('p','ai-eval-disclaimer',`统计日期：${day}（北京时间） · 对比 01 / 02 / 03 / 06 / 08 · 今日数据随上传变化。缺少前日快照时不推断历史趋势。`));
 if(!summaries.some(x=>x.count)){body.append(mk('p','empty','暂无可评估会员。先添加各组会员并上传余额、提现数据。'))}
 for(const x of summaries){
  const card=mk('section','ai-eval-card');const title=mk('h3','',`${x.group}小组 · ${x.count}人`);card.append(title);
  if(!x.count){card.append(mk('p','','暂无会员记录，不能判断增长或余额表现。建议先核实该组数据是否已经导入。'));body.append(card);continue}
  const metrics=mk('div','ai-eval-metrics');
  for(const [name,val] of [['今日新增',`${x.newCount}人（${x.rate.toFixed(1)}%）`],['新增建仓',money(x.newStake,true)],['今日提现',money(x.withdrawal,true)],['今日输赢',money(x.profit,true)],['团队余额',money(x.balance,true)],['人均余额',money(x.avg,true)]]){
   const b=mk('div','ai-eval-metric');b.append(mk('small','',name),mk('b','',val));metrics.append(b)
  }card.append(metrics);
  const notes=[];
  if(x.rate<1.5)notes.push(`今日新增占比 ${x.rate.toFixed(1)}%，低于1.5%参考线；先抽查近期入会记录、统计口径及真实推广转化，再决定改进措施。`);
  else notes.push(`今日新增占比 ${x.rate.toFixed(1)}%，达到1.5%参考线；仍需持续观察，不代表未来会保持。`);
  if(x.rate<meanRate)notes.push(`低于五个有会员小组的平均新增占比 ${meanRate.toFixed(1)}%，建议核对新会员登记时间及渠道反馈。`);
  if(x.profit<0)notes.push('今日新增建仓低于今日提现：请抽样核对提现批次、账号匹配和当日最后一次上传；这是收支差额，不应直接认定经营亏损。');
  else notes.push('今日新增建仓与提现的差额为非负，注意它不等同于扣除费用后的真实利润。');
  if(x.avg<1300000)notes.push(`人均余额 ${money(x.avg,true)}，低于13,000参考值；建议抽查低余额记录及是否有重复/漏导入账号。`);
  if(x.older>0)notes.push(`入会满4个月及以上 ${x.older}/${x.count} 人：可分层核对较早入会会员的余额和近期活跃情况。年龄色卡不等于风险分级；风险评估模式使用独立的团队收益/余额比。`);
  const sample=Math.min(5,Math.max(1,Math.ceil(x.count*.1)));
  notes.push(`建议每轮抽样约 ${sample} 位会员，优先覆盖当日新增、当日提现非零与较早入会三类；查看账号、加入日期、上下级和最后上传记录是否一致。`);
  const list=mk('ul','ai-eval-notes');notes.forEach(t=>list.append(mk('li','',t)));card.append(list);body.append(card)
 }
 dialog.append(body);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
}
function renderBranch(){
 const outer=mk('div','branch-view'+(compactMode?' v28-compact':''));
 // Controls and heading live in the single compact panel toolbar; do not duplicate them above the canvas.
 const host=mk('div','branch-canvas'+(riskMode?' branch-risk-mode':'')+(compactMode?' v28-branch-compact':''));host.tabIndex=0;host.setAttribute('aria-label','可拖动缩放的会员分支概览图，点击会员可查看详情');
 const svg=svgEl('svg',{class:'branch-svg',preserveAspectRatio:'xMidYMid meet'});
 const viewport=svgEl('g');svg.append(viewport);host.append(svg);if(riskMode)host.append(riskBanner());outer.append(host);
 const shownRows=teamFocusId?teamExportRows(teamFocusId):shownTreeMembers();
 if(teamFocusId){
  const owner=members.find(x=>x.id===teamFocusId);
  const bar=mk('div','v42-focus-bar');
  bar.append(mk('b','','独立团队架构：'+(owner?.account||'')+'（共'+shownRows.length+'人）'));
  const back=mk('button','v42-team-back','↩ 返回完整架构');
  back.onclick=teamOnlyClear;bar.append(back);outer.prepend(bar);
 }
 if(positionAlarmOn)host.append(v33AlertPanel(shownRows));
 function draw(){
  const L=branchLayout(shownRows,branchClosed);const cardW=compactMode?152:260,cardH=compactMode?44:104;svg.setAttribute('viewBox',`0 0 ${Math.max(300,host.clientWidth||1100)} ${Math.max(320,host.clientHeight||590)}`);viewport.replaceChildren();
  for(const [a,b]of L.edges){const p=L.positions.get(a),q=L.positions.get(b),start=p.x+cardW,end=q.x;
   const d=`M ${start} ${p.y} C ${start+(compactMode?17:65)} ${p.y}, ${end-(compactMode?17:65)} ${q.y}, ${end} ${q.y}`;
   viewport.append(svgEl('path',{class:'branch-line',d}))}
  const highlight=branchSelectedAccount,day=businessDay||dateNow(),parentIds=new Set(shownRows.map(x=>x.parent_id).filter(Boolean));
  for(const m of shownRows){const pos=L.positions.get(m.id);if(!pos)continue;
   const isNew=String(m.joined_on)===day,age=membershipMonths(m.joined_on,day),kids=parentIds.has(m.id);
   const group=svgEl('g',{class:`branch-node branch-age-${age}${riskMode?' branch-risk-'+riskForMember(m).grade:''}${isNew?' branch-today':''}${highlight&&m.account===highlight?' branch-match branch-target':''}${withdrawGlowOn&&Number(m.daily_withdraw_cents||0)!==0?' branch-withdraw-glow':''}${riskMode&&m.id===riskFocusId?' branch-risk-focus':''}`,transform:`translate(${pos.x},${pos.y-cardH/2})`,role:'button',tabindex:'0','aria-label':`查看${m.account}的详细概览`});
   group.append(svgEl('rect',{x:0,y:0,width:cardW,height:cardH,rx:compactMode?7:12}));if(compactMode)attachCompactHover(group,m);
    if(positionAlarmOn){
     const warn=v29Position(m);
     if(warn.active){
      group.classList.add('branch-position-alarm');
      group.append(svgEl('ellipse',{cx:cardW/2,cy:cardH/2,rx:cardW/2+9,ry:cardH/2+7,class:'v29-position-ring',fill:'none','aria-hidden':'true'}));
      const alertLabel=svgEl('g',{class:'v29-position-svg-badge','aria-label':'建议放款 '+money(warn.cents,true)});
      const textVal='建议放款 '+money(warn.cents,true);
      const badgeWidth=Math.min(cardW,Math.max(118,textVal.length*10+16));
      alertLabel.append(svgEl('rect',{x:0,y:-24,width:badgeWidth,height:21,rx:5}));
      alertLabel.append(svgEl('text',{x:6,y:-9},textVal));
      group.append(alertLabel);
     }
    }

    // V27: Actual enlarged elliptical warning rings, not just a subtle card shadow.
    if(withdrawGlowOn&&Number(m.daily_withdraw_cents||0)!==0){
     group.append(svgEl('ellipse',{cx:cardW/2,cy:cardH/2,rx:compactMode?94:156,ry:compactMode?34:87,class:'withdraw-red-outer',fill:'none','aria-hidden':'true'}));
     group.append(svgEl('ellipse',{cx:cardW/2,cy:cardH/2,rx:compactMode?88:149,ry:compactMode?29:80,class:'withdraw-red-inner',fill:'none','aria-hidden':'true'}));
    }
   if(riskMode){const r=riskForMember(m);group.append(svgEl('title',{},`${r.label}；团队余额 ${money(r.balance,true)}，团队收益 ${money(r.profit,true)}，占比 ${r.pct===null?'不可计算':r.pct.toFixed(1)+'%'}`))}
   if(compactMode){
     group.append(svgEl('text',{x:8,y:16,class:'branch-name v28-mini-name'},m.account.length>19?m.account.slice(0,18)+'…':m.account));
     group.append(svgEl('text',{x:8,y:34,class:'branch-date v28-mini-joined'},m.joined_on||'—'));
    }else{
    group.append(svgEl('text',{x:13,y:18,class:'branch-date'},m.joined_on||'未填写加入日期'));
   group.append(svgEl('text',{x:13,y:42,class:'branch-name'},m.account.length>23?m.account.slice(0,22)+'…':m.account));
   group.append(svgEl('text',{x:13,y:62,class:'branch-stake'},`本人建仓：${money(m.stake_cents,true)}`));
   const note=String(m.remark||'无备注');group.append(svgEl('text',{x:13,y:83,class:'branch-remark'},`备注：${note.length>12?note.slice(0,12)+'…':note}`));
   }
   if(!compactMode&&withdrawGlowOn&&Number(m.daily_withdraw_cents||0)!==0){
    const amount=svgEl('g',{class:'branch-withdraw-badge','aria-label':`今日提现 ${money(m.daily_withdraw_cents,true)}`});
    amount.append(svgEl('rect',{x:7,y:-27,width:244,height:23,rx:6}));
    amount.append(svgEl('text',{x:14,y:-11},`🔴 今日提现：${money(m.daily_withdraw_cents,true)}`));group.append(amount);
   }
   if(!compactMode&&role==='admin'){
    const editor=svgEl('g',{class:'branch-editbtn',role:'button',tabindex:'0','aria-label':'修改'+m.account+'的备注'});
    editor.append(svgEl('rect',{x:175,y:70,width:70,height:25,rx:7}));editor.append(svgEl('text',{x:210,y:87,'text-anchor':'middle'},'✎ 改备注'));
    editor.addEventListener('click',e=>{e.stopPropagation();if(!host.dataset.dragging)quickEditRemark(m)});
    editor.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();quickEditRemark(m)}});
    group.append(editor)
   }
   if(kids){const toggle=svgEl('g',{class:'branch-expand',role:'button',tabindex:'0','aria-label':'展开或折叠'+m.account+'的下级'});
    toggle.append(svgEl('circle',{cx:cardW,cy:cardH/2,r:compactMode?8:12,class:'branch-toggle'}));toggle.append(svgEl('text',{x:cardW,y:cardH/2+(compactMode?3:6),'text-anchor':'middle',class:'branch-toggle-label'},branchClosed.has(m.id)?'+':'−'));
    function fold(){branchClosed.has(m.id)?branchClosed.delete(m.id):branchClosed.add(m.id);draw();persistTabView()}
    toggle.addEventListener('click',e=>{e.stopPropagation();if(!host.dataset.dragging)fold()});toggle.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.stopPropagation();e.preventDefault();fold()}});group.append(toggle)}
   group.addEventListener('click',e=>{e.stopPropagation();if(!host.dataset.dragging)branchMemberDetail(m.id)});
   group.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target===group){e.preventDefault();branchMemberDetail(m.id)}});
   viewport.append(group)
  }
  viewport.setAttribute('transform',`translate(${branchTransform.dx},${branchTransform.dy}) scale(${branchTransform.scale})`);
  outer.dataset.height=String(L.height)
 }
 function apply(){viewport.setAttribute('transform',`translate(${branchTransform.dx},${branchTransform.dy}) scale(${branchTransform.scale})`)}
 function reset(){const L=branchLayout(shownRows,branchClosed);const w=Math.max(300,host.clientWidth),h=Math.max(320,host.clientHeight);
  branchTransform.scale=Math.max(.16,Math.min(1.35,Math.min((w-55)/L.width,(h-45)/L.height)));
  branchTransform.dx=Math.max(15,(w-L.width*branchTransform.scale)/2);
  branchTransform.dy=Math.max(15,(h-L.height*branchTransform.scale)/2);branchViewportReady=true;branchResetRequested=false;draw();persistTabView()}
 function zoom(factor,px=host.clientWidth/2,py=host.clientHeight/2){const before=branchTransform.scale,next=Math.max(.13,Math.min(3.8,before*factor));branchTransform.dx=px-(px-branchTransform.dx)*next/before;branchTransform.dy=py-(py-branchTransform.dy)*next/before;branchTransform.scale=next;apply();persistTabView()}
 function focusTarget(){
  if(!branchSelectedAccount)return false;
  const selected=members.find(x=>x.account===branchSelectedAccount);
  if(!selected)return false;
  const layout=branchLayout(shownRows,branchClosed),p=layout.positions.get(selected.id);
  if(!p)return false;
  const w=Math.max(300,host.clientWidth),h=Math.max(320,host.clientHeight);
  const scale=Math.min(1.35,Math.max(.78,Math.min((w-48)/(compactMode?200:310),(h-50)/(compactMode?95:170))));
  branchTransform.scale=scale;
  branchTransform.dx=w/2-(p.x+(compactMode?76:130))*scale;
  branchTransform.dy=h/2-p.y*scale;
  branchViewportReady=true;branchResetRequested=false;apply();persistTabView();
  host.scrollIntoView({behavior:'smooth',block:'center'});
  return true
 }
 branchViewportControls={zoomIn:()=>zoom(1.28),zoomOut:()=>zoom(.78),fit:reset,expand:()=>{branchClosed.clear();reset()}};
 host.addEventListener('wheel',e=>{e.preventDefault();const b=host.getBoundingClientRect();zoom(e.deltaY<0?1.12:.88,e.clientX-b.left,e.clientY-b.top)},{passive:false});
 let drag=null;
 svg.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,dx:branchTransform.dx,dy:branchTransform.dy};if(e.target===svg)svg.setPointerCapture(e.pointerId)});
 svg.addEventListener('pointermove',e=>{if(!drag)return;const ax=e.clientX-drag.x,ay=e.clientY-drag.y;if(Math.abs(ax)+Math.abs(ay)>5)host.dataset.dragging='1';branchTransform.dx=drag.dx+ax;branchTransform.dy=drag.dy+ay;apply();persistTabView()});
 svg.addEventListener('pointerup',()=>{drag=null;setTimeout(()=>delete host.dataset.dragging,0)});
 svg.addEventListener('pointercancel',()=>{drag=null;delete host.dataset.dragging});
 host.addEventListener('keydown',e=>{if(e.key==='+'||e.key==='=')zoom(1.2);else if(e.key==='-')zoom(.8);else if(e.key==='0')reset()});
 branchFullscreenReflow=()=>{if(host.isConnected)draw()};
 requestAnimationFrame(()=>{
  if(!host.isConnected)return;
  if(branchResetRequested||!branchViewportReady)reset();else draw();
  if(branchFocusRequested){branchFocusRequested=false;focusTarget()}
 });return outer
}

const EVENT_LABEL={legacy_restore:'从旧版恢复会员资料',create:'新增会员',update:'编辑会员',delete:'删除会员',import:'批量导入',undo:'撤回操作',seed_demo:'导入演示会员',login:'管理员登录',logout:'管理员退出'};
function summarizeLog(log){const d=log.detail||{};
 if(log.event==='update'){const before=d.before||{},after=d.after||{};const fields=[['account','账号'],['parent','直属上级'],['stake','建仓'],['total','总提现'],['remark','备注']];
  const changes=fields.filter(([k])=>String(before[k]??'')!==String(after[k]??'')).map(([k,name])=>`${name}：${String(before[k]??'—')} → ${String(after[k]??'—')}`);
  return changes.join('；')||'会员资料修改'}
 if(log.event==='create')return `账号：${d.account||'—'}；备注：${d.remark||'无'}`;
 if(log.event==='delete')return `账号：${d.account||'—'}`;
 if(log.event==='import')return `模式：${d.mode||'—'}；匹配：${d.matched||0}位；提现变化：${money(d.withdraw_delta_cents||0,true)}`;
 if(log.event==='undo')return `${d.label||'最近一次操作'}；影响${d.affected||0}条`;
 if(log.event==='seed_demo')return `演示会员：${d.count||0}位`;
 return '—'
}
function renderAdminLogs(){const root=mk('div','audit-wrap');root.append(mk('h3','','管理员操作日志'));
 root.append(mk('p','audit-note','仅管理员可查看。记录操作时间、账号、类型和修改摘要；日志只追加，不会因撤回操作而删除。'));
 const head=mk('div','audit-toolbar');const filter=mk('input','search');filter.placeholder='搜索管理员、账号、操作内容';
 const reload=mk('button','button','↻ 刷新日志');head.append(filter,reload);root.append(head);
 const tableWrap=mk('div','table-scroll');const table=mk('table','member-table audit-table');const thead=mk('thead'),tr=mk('tr');
 ['时间（北京时间）','管理员','操作类型','内容'].forEach(h=>tr.append(mk('th','',h)));thead.append(tr);table.append(thead);
 const tbody=mk('tbody');tbody.append(mk('tr','',''));table.append(tbody);tableWrap.append(table);root.append(tableWrap);
 const fmt=t=>{try{return new Date(t).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}catch(e){return t||''}};
 async function load(){tbody.replaceChildren();const l=mk('tr');const cell=mk('td','empty','正在获取操作日志…');cell.colSpan=4;l.append(cell);tbody.append(l);
  try{const data=await api('/admin/logs?limit=200');const rows=data.logs||[];
    function fill(){const search=filter.value.trim().toLowerCase();tbody.replaceChildren();let count=0;
     for(const log of rows){const value=[log.operator,log.event,JSON.stringify(log.detail||{})].join(' ').toLowerCase();if(search&&!value.includes(search))continue;
      count++;const r=mk('tr');r.append(mk('td','',fmt(log.created_at)),mk('td','',log.operator||'系统'),mk('td','',EVENT_LABEL[log.event]||log.event),mk('td','audit-detail',summarizeLog(log)));tbody.append(r)}
     if(!count){const r=mk('tr'),cell=mk('td','empty','没有匹配的操作日志');cell.colSpan=4;r.append(cell);tbody.append(r)}}
    filter.oninput=fill;fill();
  }catch(e){tbody.replaceChildren();const r=mk('tr'),cell=mk('td','empty','读取失败：'+e.message);cell.colSpan=4;r.append(cell);tbody.append(r)}}
 reload.onclick=load;load();return root
}
async function syncUndoStatus(){if(role!=='admin')return;const btn=el('undoButton');if(!btn)return;
 try{const x=await api('/admin/undo/status');btn.disabled=!x.can_undo;btn.title=x.can_undo?`可撤回：${x.label}`:x.reason;btn.dataset.actionId=x.action_id||'';btn.dataset.actionLabel=x.label||''}
 catch(e){btn.disabled=true;btn.title='暂时无法查询撤回状态：'+e.message}}
async function undoPrevious(){const btn=el('undoButton');if(btn.disabled)return;
 const id=btn.dataset.actionId,desc=btn.dataset.actionLabel||'最近一次操作';
 if(!id||!confirm(`确定撤回你最近一次的修改「${desc}」吗？\n仅撤回最近的管理员数据操作，并保留操作日志。`))return;
 try{const d=await api('/admin/undo','POST',{action_id:id});showToast('已撤回：'+d.undone);await refresh();if(view==='logs')render();await syncUndoStatus()}
 catch(e){showToast('撤回失败：'+e.message);await syncUndoStatus()}}

function renderHelp(){const d=mk('div','help');d.innerHTML=`<h3>会员树状统计 · 正式版使用说明</h3><p><b>本页面使用服务器共享会员库，8位管理员可协同更新。请每次重要操作前导出加密备份。</b></p>
<p>五项财务数据：建仓资金、余额、总提现、当日提现、输赢。其中输赢＝建仓资金－总提现；正数代表建仓金额大于累计提现，负数代表累计提现超过建仓金额。该口径不包含当前余额，不等同于最终投资盈亏。</p>
<ol><li>新增会员：填写会员账号、加入日期、上级账号（可搜索选择）、建仓资金5000或10000元、历史累计总提现。</li>
<li>节点卡片的每项金额分成三行：<b>本人</b>、<b>直属一层</b>（仅第一层下级，不含本人）、<b>节点总计</b>（本人＋所有下级所有层级）。</li>
<li>余额与当日提现分别按照完整会员账号粘贴或上传；缺失会员的选中字段按0处理。可一次上传三列“会员账号 余额 当日提现”。</li>
<li><b>每日提现最后一次上传为准：</b>同日多次上传只是更新当日快照；待当天结束、下次系统执行跨日结算时才一次性计入累计总提现。北京时间零点后“当日提现”重置显示为0，历史累计保留。</li>
<li>上传时先点“预览核对”，核对会员数、置零数及总提现预计变化，再点“确认批量更新”。上传过程为完整事务，失败不会修改一半。</li>
<li>层级从每个根节点的第1层开始向下递增；备注由管理员填写，最多20个字。</li><li>管理员账号独立分配，支持测试人员各自使用本机数据；同一会员被其他管理员更新时会提示先刷新，防止覆盖。</li><li>金额颜色规则：当日提现有金额则红色、为0则黑色；输赢正数绿色、负数红色、为0黑色；其他金额正数和0黑色、负数红色。提现显示整数，数据库原始金额不变。</li><li>今天加入的会员节点淡绿色提醒；北京时间次日0点后分支图自动恢复按入会月龄从淡红到深红的6档颜色。满1、2、3、4、5、6个月逐档加深。每个节点的今日新增包括本人和全部后代，详细列出新增来自哪一层。</li><li>第二层团队排行榜：只列出每个根节点的直属会员（第2层），将该会员本人及全部层级下属的当日新增建仓减去当日提现作为排名依据。按北京时间每日0点更新，支持升序和降序。</li><li>分支概览图：由本机上下级关系从左到右绘制，展示加入日期、账号、建仓金额、备注；点击会员进入单人详细汇总，管理员可直接修改备注并记入日志；展开、收起、缩放不会修改数据。</li><li>管理员操作日志仅管理员可查看，包含操作者、时间、操作类型、内容摘要；撤回会额外记一条日志，历史不会被删除。</li><li>管理员「撤回上一步」只允许撤回本人最近一次创建、编辑、删除、批量导入或演示导入。若另一管理员已提交新的修改，或数据发生冲突，则拒绝撤回；撤回后会员版本号仍然递增，避免覆盖他人的旧窗口数据。</li><li>每个会员卡片和表格行均有「逐层导出」，导出本人一行，随后为第1层、第2层直到最深层的汇总（人数、建仓、余额、总提现、当日提现和输赢），不包含下级逐人明细。普通查看成员也可导出这些授权查看的汇总。</li><li>「一键加密备份」采用 AES-256-GCM 与 PBKDF2-SHA256，必须设置至少8位密码，备份包含完整会员、资金、关系和日志。上传 .mtbackup 后输入原密码才能完整恢复本机测试数据。恢复会覆盖当前本机测试数据，请先另做备份。</li><li>总提现仍允许管理员手动修改，用来校正历史累计；请谨慎使用并定期备份。数据仅供授权内部人员查看。</li><li>表格数据菜单可按账号搜索、按所在分组筛选、切换本人／直属一层／节点全部层级统计。每个会员均可导出本人及下级按层级汇总的Excel表格（仅汇总，不显示下级逐人明细）。</li></ol>
<div class="alert">注意：导入的是“当天累计提现快照”，不是每一笔新增提现流水。同日上传两次相同数据不会重复添加。需要把会员账号列设为文本，保留前导0。</div>`;return d}

let legacyPendingJob=null;
function legacyRestorePanel(){
 const div=mk('div','');div.id='legacyRestorePane';
 const title=mk('h3','','📦 导入旧版全员数据 · 一键重建会员树');
 const help=mk('p','', '支持老版本“导出全部CSV / 导出Excel”文件，自动识别会员、加入日期、直属上级、备注、建仓、余额、累计提现、当日提现。加密 .mtbackup 文件请使用顶部「恢复加密备份」。请不要选择只含层级合计的“逐层汇总表”。');
 const input=mk('input');input.type='file';input.accept='.csv,.xlsx,.xlsm,.txt';input.id='legacyFile';
 const buttons=mk('div','import-controls'),previewBtn=mk('button','button primary','① 上传文件，预览核对');previewBtn.type='button';
 const confirmBtn=mk('button','button primary','② 确认恢复会员资料');confirmBtn.type='button';confirmBtn.disabled=true;
 const result=mk('div','preview','未选择文件。注意：此操作不同于“批量更新余额”，它会完整重建会员及上下级关系。');
 input.onchange=()=>{legacyPendingJob=null;confirmBtn.disabled=true;result.textContent='已选择：'+(input.files[0]?.name||'未选择')+'。点击「预览核对」。'};
 previewBtn.onclick=async()=>{legacyPendingJob=null;confirmBtn.disabled=true;const f=input.files[0];if(!f){showToast('请先选择旧版全员CSV或Excel');return}const fd=new FormData();fd.append('upload',f);result.textContent='正在解析账号、层级和资金…';try{const d=await api('/admin/legacy/preview','POST',fd);legacyPendingJob=d.job_id;confirmBtn.disabled=false;result.textContent=`可恢复会员：${d.members}人\n根节点：${d.roots}个\n当前正式系统会员：${d.existing_members}人（确认后会被替换）\n建仓合计：${d.amounts.stake}\n余额合计：${d.amounts.balance}\n总提现合计：${d.amounts.total}\n表内当日提现：${d.amounts.daily}\n前8个账号：${d.sample.map(x=>x.account).join('、')}\n\n⚠ ${d.notice}`;}catch(err){result.textContent='预览失败：'+err.message;showToast('未修改任何会员数据')}};
 confirmBtn.onclick=async()=>{if(!legacyPendingJob){showToast('请先上传并预览');return}if(!confirm('即将用导出文件完整替换正式会员资料，影响所有8名管理员。请确认你已保存目前的加密备份。'))return;
 const confirmText=prompt('最后确认：请输入「确认覆盖旧会员数据」');if(confirmText!=='确认覆盖旧会员数据'){showToast('未确认，数据保持不变');return}
 confirmBtn.disabled=true;try{const res=await api('/admin/legacy/'+encodeURIComponent(legacyPendingJob)+'/confirm','POST',{confirm:'确认覆盖旧会员数据'});legacyPendingJob=null;result.textContent='已成功从备份恢复 '+res.members+' 位会员及上下级关系。';view='tree';query='';el('search').value='';await refresh();await syncUndoStatus();showToast('成功恢复 '+res.members+' 位会员')}catch(err){result.textContent='恢复失败（未部分恢复）：'+err.message;confirmBtn.disabled=false}};
 buttons.append(input,previewBtn,confirmBtn);div.append(title,help,buttons,result);return div;
}

function importPanel(){const wrap=mk('div','import-panel');wrap.innerHTML=`<h3>上传会员余额 / 当日提现</h3><p>按会员账号匹配。三列模式允许某些行只有「账号＋余额」，这类行当日提现自动按0处理；未上传到的其他会员对应字段也设0。</p><div class="import-modes"><button class="mode" data-mode="balance">仅余额</button><button class="mode" data-mode="daily">仅当日提现</button><button class="mode" data-mode="both">余额 + 当日提现</button></div><textarea id="importText" placeholder="这里填写你自己新增的会员账号，以及余额、当日提现"></textarea><div class="import-controls"><input type="file" accept=".csv,.txt,.tsv,.xlsx,.xlsm" id="uploadFile"><button class="button" id="sample">填入示例</button><button class="button primary" id="previewButton">① 预览核对</button><button class="button primary" disabled id="confirmButton">② 确认批量更新</button></div><div class="preview" id="previewBox">尚未上传数据。</div><div class="alert">⚠ 余额和当日提现按所选字段全量覆盖，文件没有的账号设为0。上传“当日提现”将自动只覆盖当日提现快照；总提现在跨日结算时按最终数据计入。</div>`;
wrap.querySelectorAll('.mode').forEach(b=>{b.classList.toggle('selected',b.dataset.mode===importMode);b.onclick=()=>{importMode=b.dataset.mode;previewJob=null;render()}});
wrap.querySelector('#sample').textContent='填入当前账号模板';wrap.querySelector('#sample').onclick=()=>{wrap.querySelector('#importText').value=members.map(m=>m.account+' 0'+(importMode==='both'?' 0':'')).join('\n')};
wrap.querySelector('#previewButton').onclick=async()=>{const fd=new FormData();fd.append('mode',importMode);fd.append('content',wrap.querySelector('#importText').value);const file=wrap.querySelector('#uploadFile').files[0];if(file)fd.append('upload',file);try{const d=await api('/import/preview','POST',fd);previewJob=d.job_id;wrap.querySelector('#confirmButton').disabled=!d.valid;wrap.querySelector('#previewBox').textContent=`匹配成功：${d.matched} 位会员\n当日提现所属日期：${d.daily_date||'—'}\n本次当日提现快照修正差额（非立即计入累计提现）：${money(d.withdraw_delta_cents||0,true)}\n未出现在本次上传中（将置0）：${d.missing} 位\n不存在的会员账号：${d.unmatched_count} 个 ${d.unmatched.join('、')}\n重复账号：${d.duplicates.length} 个 ${d.duplicates.join('、')}\n格式错误：${d.errors.length} ${d.errors.join('；')}\n更新项目：${importMode==='balance'?'仅余额':importMode==='daily'?'仅当日提现':'余额和当日提现'}\n${d.summary}`;if(!d.valid)showToast('检查发现问题，本批次不可提交')}catch(e){wrap.querySelector('#previewBox').textContent='预览失败：'+e.message;wrap.querySelector('#confirmButton').disabled=true}};
wrap.querySelector('#confirmButton').onclick=async()=>{if(!previewJob)return;const agree=confirm('确认进行全量更新吗？本次未上传的会员，对应选定字段将被置0。');if(!agree)return;try{const res=await api('/import/'+previewJob+'/confirm','POST',{});previewJob=null;showToast(`成功更新 ${res.matched} 位会员；总提现调整 ${money(res.withdraw_delta_cents||0,true)}`);await refresh();render();await syncUndoStatus()}catch(e){showToast(e.message)}};
if(role==='admin')wrap.prepend(legacyRestorePanel());return wrap}
// V15 统计报表：与会员树共享服务器记录；不凭空补齐缺失的历史日期。
let reportMonth='',reportGroup='all',reportState=null,reportLoading=false,reportOrder='desc',reportSelectedDay='',reportLastLoad=0;
let overviewReportData=null,overviewLoadAt=0,overviewLoading=false;
const REPORT_TYPES=[
 ['new_count','今日裂变',false],['member_count','今日投注',false],['count_change','投注对比',false],
 ['new_stake_cents','今日充值',true],['withdraw_cents','今日提现',true],['fee_cents','手续费10%',true],
 ['profit_cents','团队输赢',true],['betting_cents','泡沫',true],['balance_cents','余额',true],
 ['avg_balance_cents','平均余额',true],['monthly_profit_cents','本月收益',true]
];
function reportVal(row,key,isMoney){if(!row||row[key]===null||row[key]===undefined)return '未记录';return isMoney?money(row[key],true):key==='business_day'?String(row[key]):Number(row[key]).toLocaleString('zh-CN')}
function reportTone(row,key){if(!row||row[key]===null||row[key]===undefined)return 'amount-black';const v=Number(row[key]);if(v===0)return 'amount-black';if(['withdraw_cents','fee_cents'].includes(key))return 'amount-red';if(['count_change','profit_cents','monthly_profit_cents','betting_cents','new_stake_cents'].includes(key))return v>0?'amount-green':'amount-red';return 'amount-black'}
function reportTable(rows,cols,empty='没有匹配记录',editable=false){
 const wrap=mk('div','report-table-wrap'),table=mk('table','report-table'),thead=mk('thead'),top=mk('tr');
 for(const [key,label] of cols)top.append(mk('th','',label));if(editable)top.append(mk('th','','报表修正'));thead.append(top);table.append(thead);
 const body=mk('tbody');for(const r of rows){const tr=mk('tr',(r.status==='未记录'?'report-missing':'')+(r.group_account==='__ALL__'?' report-total-row':''));
  for(const [key]of cols){const td=mk('td',REPORT_TYPES.some(x=>x[0]===key)?reportTone(r,key):'',
   key==='group_account'?(r[key]==='__ALL__'?'总计':r[key]):
   key==='status'?(r[key]||'未记录'):reportVal(r,key,REPORT_TYPES.some(x=>x[0]===key&&x[2])));
   if(r.status&&r.status!=='今日实时')td.title=`${r.status} · 最后采集 ${r.captured_at||'无'}`;
   tr.append(td)}
  if(editable){const tools=mk('td','report-edit-cell');if(['01','02','03','06','08'].includes(r.group_account)&&r.status!=='未记录'&&r.business_day&&r.business_day!==(businessDay||dateNow())){const btn=mk('button','button report-edit-button',r.is_manual?'✎ 已修正':'✎ 手动修改');btn.onclick=()=>openReportCorrection(r);tools.append(btn)}tr.append(tools)}body.append(tr)}
 if(!rows.length){const tr=mk('tr'),cell=mk('td','empty',empty);cell.colSpan=cols.length+(editable?1:0);tr.append(cell);body.append(tr)}
 table.append(body);wrap.append(table);return wrap;
}
// V16: manual corrections change the report presentation only, never member money.
function openReportCorrection(r){
 if(role!=='admin'||!r||r.group_account==='__ALL__'||r.status==='未记录')return;
 const dlg=document.createElement('dialog');dlg.className='report-edit-dialog';
 const form=mk('form','');form.onsubmit=e=>e.preventDefault();
 const header=mk('div','dialogHead');header.append(mk('h2','',`${r.group_account}组 · ${r.business_day} 报表修正`));
 const close=mk('button','tiny','✕');close.type='button';close.onclick=()=>dlg.close();header.append(close);form.append(header);
 const body=mk('div','dialogBody');body.append(mk('p','tip','修正只影响日报、月报和图表，不会改变会员本人的余额、建仓或提现。修改记录会保留管理员和时间。'));
 const fields=[['member_count','团队人数',false],['new_count','今日新增人数',false],['new_stake_cents','今日新增建仓',true],['withdraw_cents','今日提现',true],['balance_cents','团队总余额',true]];
 const inputs={};for(const [key,label,isMoney] of fields){const lbl=mk('label','',label),input=mk('input','');input.type='number';input.step=isMoney?'0.01':'1';input.min='0';input.required=true;input.value=String(isMoney?Number(r[key]||0)/100:Number(r[key]||0));lbl.append(input);body.append(lbl);inputs[key]=input}
 const err=mk('p','err'),buttons=mk('div','dialogActions');
 const cancel=mk('button','button','取消');cancel.type='button';cancel.onclick=()=>dlg.close();buttons.append(cancel);
 if(r.is_manual){const reset=mk('button','button','恢复自动统计');reset.type='button';reset.onclick=async()=>{if(!confirm(`恢复 ${r.business_day} ${r.group_account}组的原始快照？`))return;try{await api('/admin/reports/override','DELETE',{day:r.business_day,group:r.group_account,expected_updated_at:r.manual_updated_at||''});dlg.close();reportState=null;overviewReportData=null;overviewLoadAt=0;await requestReportData();showToast('已恢复原始报表，会员金额未改变')}catch(e){err.textContent=e.message}};buttons.append(reset)}
 const save=mk('button','button primary','保存报表修正');save.type='button';save.onclick=async()=>{try{
   const values={};for(const [key,,isMoney] of fields){const raw=inputs[key].value.trim();if(!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(raw)||(!isMoney&&!/^\d+$/.test(raw)))throw new Error('请输入有效的非负数，人数必须为整数，金额最多两位小数');values[key]=raw}
   if(Number(values.new_count)>Number(values.member_count))throw new Error('新增人数不能超过团队人数');
   await api('/admin/reports/override','PUT',{day:r.business_day,group:r.group_account,values,expected_updated_at:r.manual_updated_at||''});
   dlg.close();reportState=null;overviewReportData=null;overviewLoadAt=0;await requestReportData();showToast('报表修正已保存，原始会员数据未更改');
 }catch(e){err.textContent=e.message}};buttons.append(save);body.append(buttons,err);form.append(body);dlg.append(form);dlg.addEventListener('close',()=>dlg.remove());document.body.append(dlg);dlg.showModal();
}
function reportBarChart(rows){const data=rows.filter(x=>x.group_account!=='__ALL__'&&x.status),root=mk('div','report-chart-box');root.append(mk('h3','','今日充值与提现 · 分组对比'));
 if(!data.length){root.append(mk('p','muted','当前月份无今日数据'));return root}
 const svg=svgEl('svg',{viewBox:'0 0 900 260',role:'img','aria-label':'各组今日新增建仓与提现对比柱状图'}),mx=Math.max(1,...data.map(x=>Math.max(x.new_stake_cents,x.withdraw_cents)))/100;
 const chartX=85, chartW=740, y0=210, scale=150/mx;
 svg.append(svgEl('line',{x1:65,y1:y0,x2:865,y2:y0,stroke:'#9cb5b5','stroke-width':1.4}));
 data.forEach((d,i)=>{const center=chartX+(i+.5)*chartW/data.length,bw=Math.min(35,chartW/data.length*.20);
  for(const [key,color,k]of [['new_stake_cents','#16a36b',-1],['withdraw_cents','#df5969',1]]){
   const v=Math.max(0,Number(d[key])/100),h=v*scale;
   svg.append(svgEl('rect',{x:center+k*bw-2,y:y0-h,width:bw-3,height:Math.max(0,h),rx:5,fill:color}));
  }
  svg.append(svgEl('text',{x:center,y:232,'text-anchor':'middle','font-size':14,fill:'#324961'},d.group_account));
  svg.append(svgEl('text',{x:center,y:48,'text-anchor':'middle','font-size':11,fill:'#536b7c'},money(d.new_stake_cents,true)+' / '+money(d.withdraw_cents,true)));
 });root.append(svg);const leg=mk('p','report-chart-legend','● 绿色：今日新增建仓　 ● 红色：今日提现');root.append(leg);return root}
function reportLineChart(rows){const root=mk('div','report-chart-box');root.append(mk('h3','','本月团队输赢 · 逐日走势'));
 const pts=rows.map((x,i)=>({i,v:x.profit_cents===null||x.profit_cents===undefined?null:Number(x.profit_cents)/100,date:x.business_day}));
 const values=pts.filter(x=>x.v!==null);if(!values.length){root.append(mk('p','muted','本月尚无可用的每日快照。'));return root}
 const lo=Math.min(0,...values.map(x=>x.v)),hi=Math.max(0,...values.map(x=>x.v)),range=Math.max(1,hi-lo),svg=svgEl('svg',{viewBox:'0 0 900 260',role:'img','aria-label':'本月逐日团队输赢折线趋势图'});
 const px=i=>58+i*780/Math.max(1,rows.length-1),py=v=>212-(v-lo)/range*172;
 svg.append(svgEl('line',{x1:48,y1:py(0),x2:854,y2:py(0),stroke:'#a4b3bc','stroke-width':1,'stroke-dasharray':'4 5'}));
 let path='';let prev=null;
 pts.forEach(o=>{if(o.v===null){prev=null;return}const p={x:px(o.i),y:py(o.v)};path+=(prev?'L':'M')+p.x.toFixed(1)+' '+p.y.toFixed(1)+' ';prev=p});
 svg.append(svgEl('path',{d:path,stroke:'#12a16b','stroke-width':3,fill:'none','stroke-linejoin':'round'}));
 for(const p of pts.filter(x=>x.v!==null)){const dot=svgEl('circle',{cx:px(p.i),cy:py(p.v),r:4,fill:p.v<0?'#d84b5c':'#16a36b'});dot.append(svgEl('title',{},p.date+'：'+p.v.toLocaleString('zh-CN')));svg.append(dot)}
 pts.filter((x,i)=>i===0||i===pts.length-1||i%7===0).forEach(p=>svg.append(svgEl('text',{x:px(p.i),y:237,'text-anchor':'middle','font-size':13,fill:'#536879'},p.date.slice(-5))));
 root.append(svg);root.append(mk('p','report-chart-legend','断线表示该日期未记录，不能视为收益为0。'));return root}
function reportActiveDay(){
 const today=businessDay||dateNow();
 if(reportSelectedDay&&reportSelectedDay.slice(0,7)===reportMonth&&reportSelectedDay<=today)return reportSelectedDay;
 if(reportMonth===today.slice(0,7))return today;
 return reportMonth&&/^\d{4}-\d{2}$/.test(reportMonth)?new Date(Date.UTC(Number(reportMonth.slice(0,4)),Number(reportMonth.slice(5,7)),0)).toISOString().slice(0,10):today;
}
function changeReportDay(diff){
 const d=new Date(reportActiveDay()+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+diff);
 const next=d.toISOString().slice(0,10),today=businessDay||dateNow();
 if(next>today){showToast('不能查看未来日期');return}
 reportSelectedDay=next;reportMonth=next.slice(0,7);reportState=null;render();
}
async function requestReportData(){if(reportLoading)return;reportLoading=true;
 try{const m=reportMonth||(businessDay||dateNow()).slice(0,7),day=reportActiveDay(),res=await api(`/reports?month=${encodeURIComponent(m)}&group=${encodeURIComponent(reportGroup)}&day=${encodeURIComponent(day)}`);
  reportState=res;reportLastLoad=Date.now();if(day===(businessDay||dateNow()))overviewReportData=(res.overview&&res.overview.find(x=>x.group_account==='__ALL__'))||overviewReportData;
  if(view==='report')render();else updateOverviewReport();
 }catch(err){if(view==='report'){const c=el('content');c.replaceChildren(mk('p','alert','报表加载失败：'+err.message))}else showToast('报表摘要获取失败：'+err.message)}finally{reportLoading=false}}
async function loadOverviewReport(){if(overviewLoading||Date.now()-overviewLoadAt<60000)return;overviewLoading=true;overviewLoadAt=Date.now();
 try{const d=await api('/reports?month='+(businessDay||dateNow()).slice(0,7)+'&group=all');overviewReportData=(d.overview||[]).find(x=>x.group_account==='__ALL__');updateOverviewReport()}
 catch(e){console.warn('未能获取昨日快照',e.message)}finally{overviewLoading=false}}
function updateOverviewReport(){const r=overviewReportData;
 if(!r)return;
 for(const [id,v] of [['yesterdayMembers',r.count_change===null||r.count_change===undefined?'未记录':String(r.member_count-r.count_change)],
 ['todayMemberDiff',r.count_change===null||r.count_change===undefined?'未记录':(r.count_change>=0?'+':'')+r.count_change],
 ['yesterdayBalance',r.yesterday_balance_cents===null?'未记录':money(r.yesterday_balance_cents,true)],
 ['bubbleGrowth',r.bubble_change_cents===null?'未记录':(r.bubble_change_cents>0?'+':'')+money(r.bubble_change_cents,true)]]){const e=el(id);if(e)e.textContent=v}}
function renderReports(){const root=mk('div','report-page'),title=mk('div','report-title-row');title.append(mk('h2','',`万诚数据统计（${reportActiveDay()}）`));title.append(mk('span','report-chip','01 / 02 / 03 / 06 / 08 · 总计'));root.append(title);
 const hint=mk('p','report-hint','按北京时间统计。今日报表直接读取实时会员数据，与首页总计保持一致；约每10秒刷新。仅历史已结算日期可手动修正。跨日后保留当天最后采集值；免费服务休眠时无法保证精确午夜采样，缺失日期显示「未记录」。');root.append(hint);
 if(!reportMonth)reportMonth=(businessDay||dateNow()).slice(0,7);
 const filter=mk('div','report-controls');
 const mWrap=mk('label','','选择月份'),monthInput=mk('input','');monthInput.type='month';monthInput.value=reportMonth;monthInput.max=(businessDay||dateNow()).slice(0,7);monthInput.onchange=e=>{if(!e.target.value)return;reportMonth=e.target.value;reportSelectedDay='';reportState=null;render()};mWrap.append(monthInput);
 const gWrap=mk('label','','查看范围'),gs=mk('select','');for(const [v,l] of [['all','全盘：每日总计'],['01','01组：本月逐日'],['02','02组：本月逐日'],['03','03组：本月逐日'],['06','06组：本月逐日'],['08','08组：本月逐日']]){const opt=mk('option','',l);opt.value=v;gs.append(opt)}gs.value=reportGroup;gs.onchange=e=>{reportGroup=e.target.value;reportState=null;render()};gWrap.append(gs);
 const order=mk('button','button',reportOrder==='desc'?'日期：从近到远':'日期：从远到近');order.onclick=()=>{reportOrder=reportOrder==='desc'?'asc':'desc';render()};
 const prevDay=mk('button','button','❮ 前一天');prevDay.onclick=()=>changeReportDay(-1);
 const nextDay=mk('button','button','后一天 ❯');nextDay.onclick=()=>changeReportDay(1);
 const currentLabel=mk('span','report-chip',`当前查看：${reportActiveDay()}`);
 const excel=mk('button','button primary','⬇ 导出本月Excel');excel.onclick=()=>{const link=document.createElement('a');link.href=`/api/reports/export.xlsx?month=${encodeURIComponent(reportMonth)}&group=${encodeURIComponent(reportGroup)}`;document.body.append(link);link.click();link.remove()};
 const maxBtn=mk('button','button report-max-button',fullscreenActive()?'⛶ 退出全屏':'⛶ 报表最大化');maxBtn.id='reportFullscreenBtn';maxBtn.type='button';maxBtn.title='点击铺满屏幕，Alt+Enter 切换，Esc 退出';maxBtn.setAttribute('aria-pressed',String(fullscreenActive()));maxBtn.onclick=toggleTreeFullscreen;filter.append(mWrap,gWrap,order,prevDay,nextDay,currentLabel,excel,maxBtn);root.append(filter);
 if(!reportState||reportState.month!==reportMonth||reportState.group!==reportGroup||reportState.selected_day!==reportActiveDay()){root.append(mk('p','report-loading','正在获取每日快照…'));setTimeout(requestReportData,0);return root}
 const state=reportState,overview=state.overview||[];
 const block=mk('section','report-block');block.append(mk('h3','',`${reportActiveDay()} 各小组汇总（总计包含所有分组）`));
 if(!overview.length)block.append(mk('p','report-hint','该日期尚无采集记录；请使用「前一天/后一天」查询已记录日期。'));
 else block.append(reportTable(overview,[['group_account','组别'],...REPORT_TYPES],undefined,role==='admin'));root.append(block);
 if(overview.length){root.append(reportBarChart(overview));}
 const dailyBlock=mk('section','report-block');dailyBlock.append(mk('h3','',`${reportGroup==='all'?'全盘':reportGroup+'组'} · ${reportMonth} 每日数据对比`));
 const all=state.daily||[],sorted=reportOrder==='desc'?[...all].reverse():[...all];
 dailyBlock.append(mk('p','report-hint',`已记录 ${state.available_days}/${state.days} 天；灰色「未记录」不是0。月累计收益只在该月截至当日所有日期均有快照时显示完整数值。`));
 dailyBlock.append(reportTable(sorted,[['business_day','日期'],...REPORT_TYPES,['status','状态']],undefined,role==='admin'&&reportGroup!=='all'));root.append(dailyBlock);
 root.append(reportLineChart(all));const warning=mk('p','report-warning',state.warning||'历史数据只能按已采集的记录计算。');root.append(warning);
 const foot=mk('p','report-hint','提示：投注＝团队人数；泡沫＝今日团队余额－昨日最后有效余额。前一天/后一天可查询历史记录，免费服务休眠时历史采集可能不是精确24点。手续费＝当日提现×10%。');root.append(foot);
 return root}


// V34 流星AI学院 — knowledge base and optional grounded tutor.
// Course originals are preserved server-side; all imports require admin login.

// Session-scoped private dialogue; shared viewer credentials never share chat logs.
const ACADEMY_CHAT_STORAGE='academy-v35-chat-session';
function academyReadChat(){
 try{
  const saved=JSON.parse(sessionStorage.getItem(ACADEMY_CHAT_STORAGE)||'[]');
  if(!Array.isArray(saved))return [];
  return saved.filter(m=>m&&['user','assistant'].includes(m.role)&&
      typeof m.content==='string').slice(-36).map(m=>({
       role:m.role,content:m.content.slice(0,7000),mode:String(m.mode||''),
       sources:Array.isArray(m.sources)?m.sources.slice(0,6):[],
       diagnostic:m.diagnostic&&typeof m.diagnostic==='object'?m.diagnostic:null
      }));
 }catch(e){return []}
}
let academyChatMessages=academyReadChat(),academyChatPending=false,
    academyDiag=null,academyDiagBusy=false;
function academySaveChat(){
 try{sessionStorage.setItem(ACADEMY_CHAT_STORAGE,JSON.stringify(academyChatMessages.slice(-36)))}
 catch(e){/* Storage disabled; active dialogue still works */ }
}
function academyClearChat(){
 if(academyChatPending)return;
 academyChatMessages=[];academyQuestion='';academyDiag=null;
 try{sessionStorage.removeItem(ACADEMY_CHAT_STORAGE)}catch(e){}
 if(view==='academy')render();
}
async function academySendChat(){
 const question=String(academyQuestion||'').trim();
 if(!question||academyChatPending){if(!question)showToast('请先输入内容');return}
 const history=academyChatMessages.filter(m=>m.mode==='ai'||m.role==='user')
    .slice(-12).map(m=>({role:m.role,content:m.content.slice(0,1500)}));
 academyChatMessages.push({role:'user',content:question,mode:'user'});
 academyQuestion='';academyChatPending=true;academySaveChat();
 if(view==='academy')render();
 let answer;
 try{answer=await api('/academy/ask','POST',{question,tone:academyTone,history})}
 catch(e){answer={mode:'model_error',answer:'请求失败：'+e.message,sources:[]}}
 academyChatMessages.push({
  role:'assistant',content:String(answer.answer||'本次未获得回复').slice(0,7500),
  mode:answer.mode||'model_error',
  sources:Array.isArray(answer.sources)?answer.sources.slice(0,6):[],
  diagnostic:answer.diagnostic||null
 });
 academyChatPending=false;academySaveChat();
 if(view==='academy')render();
}
async function academyDiagnose(){
 if(role!=='admin'||academyDiagBusy)return;
 academyDiagBusy=true;academyDiag=null;if(view==='academy')render();
 try{academyDiag=await api('/academy/diagnose','POST',{})}
 catch(e){academyDiag={ok:false,diagnostic:{title:'连接检查失败：'+e.message}}}
 academyDiagBusy=false;if(view==='academy')render();
}

let academyLoaded=false,academyDocs=[],academyStats=null,academySearch='',
    academyScope='all',academyQuestion='',academyTone='亲切自然',
    academyAnswer=null,academySelected=null,academyBusy=false;
async function academyLoad(){
 try{
  const path='/academy/documents?q='+encodeURIComponent(academySearch)+'&scope='+encodeURIComponent(academyScope)+'&limit=80';
  const [stats,documents]=await Promise.all([api('/academy/stats'),api(path)]);
  academyStats=stats;academyDocs=documents.rows||[];
 }catch(e){academyStats={total:0,core:0,error:e.message};academyDocs=[]}
 academyLoaded=true;if(view==='academy')render();
}
function academyInput(label,tag,value){
 const outer=mk('label','academy-field');outer.append(mk('b','',label));
 const input=mk(tag,'academy-input');if(value!==undefined)input.value=value;
 outer.append(input);return [outer,input];
}
function renderAcademy(){
 const root=mk('div','academy-page');
 root.append(mk('h2','academy-heading','流星 AI 学院 · 企业知识库与话术导师'));
 root.append(mk('p','academy-muted','核心课程：群洗＋流星9—10；其余课程为辅助。原文保留，品牌统一稿作为单独的显示副本。'));
 if(!academyLoaded){
  root.append(mk('p','academy-muted','正在读取知识库…'));
  setTimeout(academyLoad,0);return root;
 }
 if(academyStats?.error)root.append(mk('p','err','知识库读取失败：'+academyStats.error));
 else{
  const summary=mk('div','academy-summary');
  summary.append(mk('span','','可检索课程 '+(academyStats?.total||0)+' 篇'));
  summary.append(mk('span','','核心 '+(academyStats?.core||0)+' 篇'));
  summary.append(mk('span','',academyStats?.connected?'AI 已配置':'AI 未连接 · 支持原文检索'));
  if(role==='admin')summary.append(mk('span','',String(academyStats?.drafts??0)+' 篇待审核'));
  root.append(summary);
 }

 const tutor=mk('section','academy-card academy-chat');
 const top=mk('div','academy-chat-heading');
 const heading=mk('div','');
 heading.append(mk('h3','','✦ AI话术导师 · 连续对话'));
 heading.append(mk('p','academy-muted','严格课程模式：先检索已审核核心课程，再按照课程思路回答；无课程依据时不借用外部观点。每次回答可展开查看来源。'));
 const actions=mk('div','academy-chat-actions');
 const clear=mk('button','button academy-chat-secondary','＋ 新对话');
 clear.type='button';clear.disabled=academyChatPending;clear.onclick=academyClearChat;
 actions.append(clear);
 if(role==='admin'){
  const diagnose=mk('button','button academy-chat-secondary',
      academyDiagBusy?'检测中…':'检测AI连接');
  diagnose.type='button';diagnose.disabled=academyDiagBusy;
  diagnose.onclick=academyDiagnose;actions.append(diagnose);
 }
 top.append(heading,actions);tutor.append(top);
 const status=mk('div','academy-chat-status');
 const keyMsg=academyStats?.connected?'● 模型密钥已配置 · 连接需实际检测':'○ 模型密钥未配置 · 可查知识库';
 status.append(mk('span',academyStats?.connected?'academy-status-configured':'academy-status-offline',keyMsg));
 status.append(mk('span','academy-muted','本次聊天仅保存在当前浏览器会话，退出后清除。'));
 tutor.append(status);
 if(academyDiag){
  const dx=academyDiag.diagnostic||{};
  const alert=mk('div',academyDiag.ok?'academy-diagnose-good':'academy-diagnose-bad');
  alert.append(mk('b','',dx.title||'连接状态未知'));
  if(dx.instruction)alert.append(mk('p','',dx.instruction));
  tutor.append(alert);
 }
 const log=mk('div','academy-chat-log');log.id='academyChatLog';
 log.setAttribute('role','log');log.setAttribute('aria-live','polite');
 if(!academyChatMessages.length){
  const welcome=mk('div','academy-chat-welcome');
  welcome.append(mk('div','academy-welcome-avatar','✦'));
  welcome.append(mk('h4','','你好，我是流星AI话术导师'));
  welcome.append(mk('p','','你可以直接聊天、问课程问题，或者让我按照核心讲课风格写新人培训、团队讲话和沟通话术。'));
  const suggestions=mk('div','academy-suggest');
  for(const t of ['在吗，老师？','帮我写一段新人学习动员讲话','如何向新人讲解团队合作？','帮我改一段客户沟通话术']){
   const chip=mk('button','academy-chip',t);
   chip.type='button';chip.onclick=()=>{academyQuestion=t;render();el('academyChatQuestion')?.focus()};
   suggestions.append(chip);
  }
  welcome.append(suggestions);log.append(welcome);
 }
 for(const [i,m] of academyChatMessages.entries()){
  const outer=mk('div','academy-message '+(m.role==='user'?'academy-message-user':'academy-message-assistant'));
  const avatar=mk('div','academy-message-avatar',m.role==='user'?'我':'AI');
  const body=mk('div','academy-message-body');
  const label=mk('small','academy-message-label',m.role==='user'?'我的提问':
    m.mode==='ai'?'AI话术导师':m.mode==='model_error'?'AI连接提示':'知识库课程检索');
  body.append(label);
  body.append(mk('div','academy-message-text',m.content));
  if(m.role==='assistant'){
    const utilities=mk('div','academy-message-utils');
    const copy=mk('button','academy-msg-copy','复制回答');
    copy.type='button';copy.onclick=async()=>{
      try{await navigator.clipboard.writeText(m.content);showToast('回答已复制')}
      catch(e){showToast('无法访问剪贴板，请手动选中文字复制')}
    };
    utilities.append(copy);
    if(m.mode==='model_error'&&m.diagnostic){
      const issue=mk('p','academy-ai-alert',m.diagnostic.title||'模型连接未成功');
      utilities.append(issue);
      if(m.diagnostic.instruction)utilities.append(mk('p','academy-muted',m.diagnostic.instruction));
    }
    if(m.mode!=='ai'&&m.mode!=='model_error')
      utilities.append(mk('span','academy-muted','当前非AI生成；仅供参考'));
    if(m.sources?.length){
      const refs=mk('details','academy-chat-references');
      refs.append(mk('summary','','查看课程依据（'+m.sources.length+'）'));
      for(const [idx,ref] of m.sources.entries()){
        const item=mk('div','academy-chat-ref');
        item.append(mk('b','',String(idx+1)+'. '+ref.title+(ref.priority>=100?' · 核心课程':'')));
        item.append(mk('small','academy-muted','来源：'+ref.source));
        item.append(mk('p','',ref.excerpt));
        refs.append(item);
      }
      utilities.append(refs);
    }
    body.append(utilities);
  }
  outer.append(avatar,body);log.append(outer);
 }
 if(academyChatPending){
  const pending=mk('div','academy-message academy-message-assistant');
  pending.append(mk('div','academy-message-avatar','AI'),mk('p','academy-chat-thinking','正在参考知识库，组织回复…'));
  log.append(pending);
 }
 tutor.append(log);
 const composer=mk('div','academy-chat-composer');
 const input=mk('textarea','academy-chat-textarea');
 input.id='academyChatQuestion';input.rows=3;
 input.value=academyQuestion;input.placeholder='给AI导师发消息…（Enter发送，Shift+Enter换行）';
 input.maxLength=1500;input.oninput=e=>{academyQuestion=e.target.value};
 input.onkeydown=e=>{
    if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){
      e.preventDefault();academySendChat();
    }
 };
 const composeTools=mk('div','academy-compose-tools');
 const style=mk('select','academy-input academy-chat-style');
 for(const value of ['亲切自然','领导讲话','课程讲解','简短有力','新人训练']){
  const opt=mk('option','',value);opt.value=value;style.append(opt);
 }
 style.value=academyTone;style.onchange=e=>academyTone=e.target.value;
 const send=mk('button','button primary academy-chat-send',academyChatPending?'发送中…':'发送 ↗');
 send.type='button';send.disabled=academyChatPending;
 send.onclick=academySendChat;
 composeTools.append(style,send);composer.append(input,composeTools);tutor.append(composer);
 root.append(tutor);
 requestAnimationFrame(()=>{const box=el('academyChatLog');if(box)box.scrollTop=box.scrollHeight});
 const docs=mk('section','academy-card');
 docs.append(mk('h3','','培训课程知识库'));
 const controls=mk('div','academy-toolbar');
 const search=mk('input','academy-input');search.placeholder='搜索课程标题或内容';
 search.value=academySearch;
 search.onkeydown=e=>{if(e.key==='Enter'){academySearch=search.value.trim();academyLoad()}};
 const group=mk('select','academy-input');
 for(const [key,label] of [['all','全部课程'],['core','核心课程'],['supplement','辅助课程']]){
   const opt=mk('option','',label);opt.value=key;group.append(opt);
 }
 group.value=academyScope;group.onchange=e=>{academyScope=e.target.value;academyLoad()};
 const button=mk('button','button','搜索');
 button.onclick=()=>{academySearch=search.value.trim();academyLoad()};
 controls.append(search,group,button);docs.append(controls);
 if(role==='admin'){
  const uploader=mk('div','academy-upload');
  uploader.append(mk('b','','管理员上传课程ZIP'));
  uploader.append(mk('p','academy-muted','原始内容原封不动保存。课程导入后先进入待审核，确认没有不适合向成员公开的隐私内容后再发布。'));
  const file=mk('input','academy-input');file.type='file';file.accept='.zip,application/zip';
  const publish=mk('button','button primary','导入到知识库');
  publish.onclick=async()=>{
   if(!file.files?.length){showToast('请选择课程ZIP文件');return}
   publish.disabled=true;publish.textContent='导入中…';
   const data=new FormData();data.append('file',file.files[0]);data.append('scope','auto');
   try{
     const res=await api('/academy/upload','POST',data);
     showToast('导入 '+res.created+' 篇；跳过重复 '+res.skipped+' 篇；请审核发布');
     file.value='';await academyLoad();
   }catch(e){showToast('导入失败：'+e.message)}
   finally{publish.disabled=false;publish.textContent='导入到知识库'}
  };
  uploader.append(file,publish);
  const bulk=mk('button','button','审核发布核心课程');
  bulk.type='button';
  bulk.onclick=async()=>{
    if(!confirm('确认已核对核心课程中的个人信息与原始表述，并发布所有待审核的核心课程给登录成员查看？'))return;
    try{
      const res=await api('/academy/approve-batch','POST',{scope:'core',acknowledge:true});
      showToast('核心课程已发布：'+res.approved+'篇');await academyLoad();
    }catch(e){showToast('批量审核失败：'+e.message)}
  };
  uploader.append(bulk);
  docs.append(uploader);
 }
 const list=mk('div','academy-doc-list');
 if(!academyDocs.length)list.append(mk('p','academy-muted','尚无已发布课程。管理员可导入课程ZIP并审核。'));
 for(const doc of academyDocs){
  const line=mk('div','academy-doc-row');
  const title=mk('button','academy-doc-title',doc.title);title.type='button';
  title.onclick=async()=>{
   try{academySelected=await api('/academy/documents/'+encodeURIComponent(doc.id));if(view==='academy')render()}
   catch(e){showToast('课程打开失败：'+e.message)}
  };
  line.append(title);
  line.append(mk('small','academy-muted',doc.source_path+' · '+(doc.priority>=100?'核心':'辅助')+' · '+(doc.status==='approved'?'已审核':'待审核')));
  if(role==='admin'&&doc.status!=='approved'){
   const approve=mk('button','tiny','审核发布');approve.type='button';
   approve.onclick=async()=>{
      try{await api('/academy/documents/'+encodeURIComponent(doc.id)+'/approve','POST',{});
          await academyLoad();showToast('课程已发布')}
      catch(e){showToast('审核失败：'+e.message)}
   };line.append(approve);
  }
  list.append(line);
 }
 docs.append(list);
 if(academySelected){
  const section=mk('div','academy-source-box');
  section.append(mk('h4','',academySelected.title+' · 全文'));
  section.append(mk('small','academy-muted','原始来源：'+academySelected.source_path));
  const modes=mk('select','academy-input');
  for(const [field,label] of [['original_text','原始全文（未修改）'],['display_text','品牌统一稿（仅显示副本）']]){
   const opt=mk('option','',label);opt.value=field;modes.append(opt);
  }
  const raw=mk('pre','academy-raw',academySelected.original_text);
  modes.onchange=()=>raw.textContent=academySelected[modes.value]||'';
  const close=mk('button','button','关闭');
  close.onclick=()=>{academySelected=null;render()};
  const download=mk('button','button','下载未修改的原始文件');
  download.onclick=()=>{window.location.href='/api/academy/documents/'+encodeURIComponent(academySelected.id)+'/download'};
  section.append(modes,raw,download,close);docs.append(section);
 }
 root.append(docs);return root;
}

function render(){if(!role)return;const c=el('content');el('totalMembers').textContent=members.length;
 const current=businessDay||dateNow(),todays=members.filter(r=>r.joined_on===current),sumNew=todays.reduce((s,r)=>s+Number(r.stake_cents||0),0);
 el('todayNewCount').textContent=todays.length;el('todayNewStake').textContent=money(sumNew,true);
 const fission=members.length?todays.length/members.length*100:0,fissionEl=el('todayFissionPct');fissionEl.textContent=fission.toFixed(1)+'%';fissionEl.className=fission===0?'amount-black':fission>=1.5?'amount-green':'amount-red';
 el('avgBalance').textContent=members.length?money(Number(total.balance_cents||0)/members.length):'0';
 el('totalBalance').textContent=money(total.balance_cents||0);
 const todayWithdraw=Number(total.daily_withdraw_cents||0),todayProfit=sumNew-todayWithdraw;
 setAmount('todayWithdrawTotal',todayWithdraw,true,'daily');
 setAmount('todayProfitTotal',todayProfit,true,'profit');
 setAmount('todayTeamBalance',Number(total.balance_cents||0),true);
 updateOverviewReport();
 el('updatedAt').textContent='最近更新：'+(window.lastRefresh||'—');const labels={tree:'会员树状图',list:'会员列表',table:'表格数据',ranking:'团队排行榜',report:'今日报表总览',branch:'分支分布图',detail:'会员详细概览',logs:'管理员操作日志',import:'批量上传',academy:'流星AI学院',help:'操作说明'};el('crumb').textContent=labels[view];el('sectionTitle').textContent=labels[view];document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===view));el('seedButton').classList.add('hidden');el('search').classList.toggle('hidden',!['tree','list','table','ranking','branch'].includes(view));el('branchSearchGo').classList.toggle('hidden',view!=='branch');el('search').placeholder=view==='branch'?'输入完整会员账号 · 回车精准定位':'🔎 搜索会员账号';el('treeGroupFilter').classList.toggle('hidden',!['tree','branch'].includes(view));
 el('treeGroupFilter').value=selectedTreeGroup;
 el('expandAll').classList.toggle('hidden',view!=='tree');el('collapseAll').classList.toggle('hidden',view!=='tree');el('treeFullscreenBtn').classList.toggle('hidden',!['tree','branch','report'].includes(view));
 for(const id of ['riskTreeBtn','withdrawTreeBtn'])el(id).classList.toggle('hidden',!['tree','branch'].includes(view));
 el('aiTreeBtn').classList.toggle('hidden',!['tree','branch'].includes(view));el('compactTreeBtn').classList.toggle('hidden',!['tree','branch'].includes(view));el('positionAlarmBtn').classList.toggle('hidden',!['tree','branch'].includes(view));el('positionAlarmBtn').textContent=positionAlarmOn?'关闭仓位告警':'◉ 仓位告警';el('positionAlarmBtn').setAttribute('aria-pressed',String(positionAlarmOn));el('compactTreeBtn').textContent=compactMode?'▣ 完整版':'▦ 简洁版';el('compactTreeBtn').setAttribute('aria-pressed',String(compactMode));
 for(const id of ['branchZoomOut','branchZoomIn','branchFit','branchExpand'])el(id).classList.toggle('hidden',view!=='branch');
 document.querySelector('.panel')?.classList.toggle('branch-compact',view==='branch');
 el('riskTreeBtn').textContent=riskMode?'关闭风险评估':'⚠ 风险评估';el('riskTreeBtn').setAttribute('aria-pressed',String(riskMode));
 el('withdrawTreeBtn').textContent=withdrawGlowOn?'关闭红色光圈':'🔴 显示当日提现';el('withdrawTreeBtn').setAttribute('aria-pressed',String(withdrawGlowOn));

 refreshFullscreenButton();if(view!=='branch')branchFullscreenReflow=null;
 hideCompactTooltip();const preserveScrollX=c.scrollLeft,preserveScrollY=c.scrollTop;
 c.replaceChildren(view==='academy'?renderAcademy():view==='help'?renderHelp():view==='import'?importPanel():view==='list'?renderList():view==='table'?renderDataTable():view==='ranking'?renderRanking():view==='report'?renderReports():view==='branch'?renderBranch():view==='detail'?renderMemberDetail():view==='logs'?renderAdminLogs():renderTree());
 if(['tree','branch'].includes(view)){c.scrollLeft=preserveScrollX;c.scrollTop=preserveScrollY;}
 lastDisplayDay=businessDay||dateNow();if(!members.length&&['tree','list'].includes(view))message(role==='admin'?'暂无会员。点击“新增会员”或者在操作说明中了解如何导入演示数据。':'暂无会员数据，请联系管理员添加。')}
async function refresh(silent=false){if(!role)return;try{const d=await api('/tree');const changed=JSON.stringify(d.members)!==JSON.stringify(members);const dateChanged=businessDay!==d.business_day;const previousDay=businessDay;
 const latestAlerts=new Map(Object.entries(d.position_alerts||{}));
 const alarmsChanged=JSON.stringify([...latestAlerts])!==JSON.stringify([...(positionAlarmById||new Map())]);
 positionAlarmById=latestAlerts;
 members=d.members;total=d.totals;businessDay=d.business_day||dateNow();if(dateChanged&&(!reportSelectedDay||reportSelectedDay===previousDay)){reportSelectedDay=businessDay;reportMonth=businessDay.slice(0,7)}if(changed||dateChanged){reportState=null;overviewReportData=null;}historyCoverage=d.history_coverage||{};window.lastRefresh=new Date().toLocaleString('zh-CN');if(changed||dateChanged||alarmsChanged||!silent||dateNow()!==lastDisplayDay)render();else el('updatedAt').textContent='最近同步：'+window.lastRefresh;if(view==='report'&&Date.now()-reportLastLoad>=5000)requestReportData();else if(view!=='report')loadOverviewReport()}catch(e){if(e.message.includes('登录')){setRole(null,null);return}if(!silent)message('加载失败：'+e.message)}}

/* V10：本地智能粘贴，仅提取并填写表单；不提交、不会修改原记录 */
function smartParseMemberText(value,nowOverride){
 const source=String(value||'').normalize('NFKC').replace(/[\u200b-\u200d\ufeff]/g,'').trim();
 const notes=[];let rest=source;
 const nowIso=nowOverride||(()=>{const bits=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const p=Object.fromEntries(bits.map(x=>[x.type,x.value]));return `${p.year}-${p.month}-${p.day}`})();
 const [thisYear,thisMonth,thisDay]=nowIso.split('-').map(Number);
 let joinedOn='', stake='';
 const dateReg=/(^|[^0-9A-Za-z])((?:20\d{2}|\d{2})[./\-年]\d{1,2}[./\-月]\d{1,2}日?|\d{1,2}[./\-]\d{1,2}|\d{1,2}月\d{1,2}日?)(?=$|[^0-9A-Za-z])/g;
 const dateMatches=[];for(const m of source.matchAll(dateReg)){
  const a=m[2], nums=(a.match(/\d+/g)||[]).map(Number);let year,month,day,implied=false;
  if(nums.length===3){year=nums[0]<100?2000+nums[0]:nums[0];month=nums[1];day=nums[2]}
  else if(nums.length===2){year=thisYear;month=nums[0];day=nums[1];implied=true;
   if(month>thisMonth||(month===thisMonth&&day>thisDay))year--;
  }else continue;
  const d=new Date(Date.UTC(year,month-1,day));
  if(year<2000||year>thisYear+1||d.getUTCFullYear()!==year||d.getUTCMonth()+1!==month||d.getUTCDate()!==day){notes.push(`日期「${a}」无效，请手动确认`);continue}
  const iso=[year,String(month).padStart(2,'0'),String(day).padStart(2,'0')].join('-');dateMatches.push({raw:a,iso,implied,start:m.index+m[1].length});
 }
 if(dateMatches.length){joinedOn=dateMatches[0].iso;for(const m of dateMatches)rest=rest.replace(m.raw,' ');
  if(dateMatches.length>1)notes.push('发现多个日期，仅采用第一个，请核对');
  if(dateMatches[0].implied&&Number(joinedOn.slice(0,4))!==thisYear)notes.push('日期未写年份且晚于今天，按上一年推算，请核对');
 }
 // 只在金额上下文、典型建仓数或带万/千单位时识别；避免把手机号误当金额。
 const moneyExp=/(?<![A-Za-z0-9])(?:[¥￥]\s*)?(\d{1,3}(?:,\d{3})+|\d{1,11})(?:\.(\d{1,2}))?\s*(w|万|k|千|元)?(?![A-Za-z0-9])/gi;
 const moneyCandidates=[];for(const m of rest.matchAll(moneyExp)){
   const base=Number(m[1].replace(/,/g,'')+(m[2]?'.'+m[2]:''));const unit=(m[3]||'').toLowerCase();
   const val=base*(unit==='w'||unit==='万'?10000:unit==='k'||unit==='千'?1000:1);
   const before=rest.slice(Math.max(0,m.index-12),m.index);
   const explicit=/建仓|充值|金额|仓位|投入|入金/.test(before);
   const plausible=unit==='w'||unit==='万'||unit==='k'||unit==='千'||explicit||[5000,10000,20000,30000,50000].includes(val);
   const bounded=Number.isFinite(val)&&val>0&&val<1e12&&!(m[1].replace(/,/g,'').length>=10&&!unit&&!explicit);
   if(!plausible||!bounded)continue;
   moneyCandidates.push({val,raw:m[0],at:m.index,priority:explicit?3:unit?2:1});
 }
 if(moneyCandidates.length){moneyCandidates.sort((a,b)=>b.priority-a.priority||a.at-b.at);const winner=moneyCandidates[0];stake=String(winner.val);rest=rest.slice(0,winner.at)+' '+rest.slice(winner.at+winner.raw.length);
  if(moneyCandidates.length>1)notes.push('发现多个疑似建仓金额，仅采用最可信的一项，请核对');
 }else notes.push('未识别到建仓金额，默认使用10000元，可手动修改');
 // 将账号标签去掉，防止被误当账号；按剩余账号的出现顺序选择第一个和最后一个。
 rest=rest.replace(/(?:本人|上级|直属上级|推荐人|邀请码|会员|账号|账户|入会|建仓|充值|余额|金额|时间|日期|备注|姓名|地址)\s*[:：=]?/g,' ');
 const acctExp=/(?<![A-Za-z0-9_])(?:[A-Za-z][A-Za-z0-9_]{3,63}|\d{5,20})(?![A-Za-z0-9_])/g;
 const matches=[...rest.matchAll(acctExp)];const accounts=matches.map(x=>x[0]);
 let own=accounts[0]||'',parent=accounts.length>1?accounts[accounts.length-1]:'';
 for(const m of matches)rest=rest.replace(m[0],' ');
 if(accounts.length<1)notes.push('未识别到本人账号，请手动填写');
 if(accounts.length===1)notes.push('未识别到上级账号，请手动选择；根节点可留空');
 if(accounts.length>2)notes.push('识别到多个疑似账号，已按首个为本人、末个为上级填写，请核对');
 if(own&&parent&&own.toLowerCase()===parent.toLowerCase())notes.push('本人账号与上级账号相同，必须手动修改');
 // 残余中文自动作为备注，单独的身份字段标签不放进去；保留中文附带的姓名尾号。
 const chunks=[...rest.matchAll(/[\u3400-\u9FFF]{1,}[0-9]?/g)].map(m=>m[0])
   .filter(x=>!['上','下','本人','会员','上级','推荐人','入会','建仓','仓位','金额','充值','日期','时间','账号','账户','备注','姓名','岁','元'].includes(x));
 let remark=chunks.join(' ').replace(/\s+/g,' ').trim();
 if(remark.length>20){remark=remark.slice(0,20);notes.push('中文备注超过20字，已截取前20字，可手动修改')}
 if(!joinedOn)notes.push('未识别到有效加入日期，请手动填写');
 return {account:own,parent_account:parent,joined_on:joinedOn,stake,remark,warnings:notes};
}
window.smartParseMemberText=smartParseMemberText;
function smartPasteReset(){el('smartPasteText').value='';const box=el('smartPasteResult');box.className='smart-paste-result';box.textContent='识别后会自动填写账号、上级、日期、建仓与中文备注。请核对后点击「保存会员」。'}
function smartPasteApply(){
 const value=el('smartPasteText').value.trim(),info=el('smartPasteResult');
 if(!value){info.className='smart-paste-result warn';info.textContent='请先粘贴一段会员信息。';return}
 const r=smartParseMemberText(value);const user=el('editAccount').value.trim();
 // 已识别金额优先；未识别金额时使用统一默认10000，管理员仍可手动修改。
 if(r.account)el('editAccount').value=r.account;
 if(r.parent_account)el('editParentAccount').value=r.parent_account;
 el('editDate').value=r.joined_on||'';
 if(r.stake)el('editStake').value=r.stake;else el('editStake').value='10000';
 if(r.remark)el('editRemark').value=r.remark;
 const warnings=[...r.warnings];if(r.account&&members.some(x=>x.account.toLowerCase()===r.account.toLowerCase()&&x.id!==editId))warnings.push('本人账号已存在，请核对，系统不会重复创建');
 if(r.parent_account&&!members.some(x=>x.account.toLowerCase()===r.parent_account.toLowerCase()))warnings.push('上级账号尚未建档，请先添加上级账号，或手动更改');
 const lines=[`本人账号：${r.account||'未识别'}`,`上级账号：${r.parent_account||'未识别'}`,`加入日期：${r.joined_on||'未识别'}`,`建仓资金：${r.stake?r.stake+' 元':'10000 元（默认，可修改）'}`,`备注：${r.remark||'未识别'}`];
 info.className='smart-paste-result '+(warnings.length?'warn':'good');info.textContent=lines.join('  ｜  ')+(warnings.length?'\n⚠ '+warnings.join('；'):'\n✅ 识别完成，请核对并点击「保存会员」');
 el('editError').textContent='';
}
async function smartPasteFromClipboard(){try{
  if(!navigator.clipboard?.readText)throw Error('浏览器未开放剪贴板权限');
  el('smartPasteText').value=await navigator.clipboard.readText();smartPasteApply();
 }catch(e){el('smartPasteResult').className='smart-paste-result warn';el('smartPasteResult').textContent='无法直接读取剪贴板，请按 Ctrl+V 粘贴到上方输入框，再点击「一键识别并填写」。'}}

function openEdit(m=null){if(role!=='admin')return;editId=m?.id||null;el('dialogTitle').textContent=m?'编辑会员':'新增会员';el('editId').value=editId||'';el('smartPastePanel').classList.toggle('hidden',!!m);smartPasteReset();el('editAccount').value=m?.account||'';el('editDate').value=m?.joined_on||dateNow();el('editWithdraw').value=m?(m.total_withdraw_cents/100).toFixed(2):'0';el('editStake').value=m?String(m.stake_cents/100):'10000';el('editRemark').value=m?.remark||'';el('editError').textContent='';const opts=el('parentAccounts');opts.replaceChildren();members.forEach(x=>{if(x.id!==editId)opts.append(new Option(x.account,x.account))});const byId=index();el('editParentAccount').value=m?.parent_id?(byId.get(m.parent_id)?.account||''):'';el('editDialog').showModal()}
async function saveEdit(e){e.preventDefault();const payload={account:el('editAccount').value.trim(),joined_on:el('editDate').value,parent_account:el('editParentAccount').value.trim()||null,stake:el('editStake').value,total_withdraw:el('editWithdraw').value.trim(),remark:el('editRemark').value.trim(),expected_revision:editId?(members.find(x=>x.id===editId)?.revision||null):null};try{await api(editId?'/members/'+editId:'/members',editId?'PUT':'POST',payload);el('editDialog').close();showToast(editId?'会员已更新':'会员添加成功');await refresh();await syncUndoStatus()}catch(e){el('editError').textContent=e.message}}
async function removeEdit(){if(!editId||!confirm('确定删除该会员？有下级的会员不可直接删除。'))return;try{await api('/members/'+editId+'?expected_revision='+encodeURIComponent(members.find(x=>x.id===editId)?.revision||0),'DELETE',{});el('editDialog').close();showToast('会员已删除');await refresh();await syncUndoStatus()}catch(e){el('editError').textContent=e.message}}
function testDownloadBlob(filename,content,mime){const blob=new Blob([content],{type:mime}),u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),500)}
function testToCsv(rows){return '\uFEFF'+rows.map(r=>r.map(x=>'"'+String(x??'').replace(/"/g,'""')+'"').join(',')).join('\r\n')}
function testDownloadMembers(rootAccount){let list=members.slice();if(rootAccount){const ids=tableNodeIds(rootAccount);list=list.filter(r=>ids?.has(r.id))}const lines=[['会员账号','加入日期','直属上级','层级','备注','建仓资金','余额','累计提现','当日提现','输赢']];for(const r of list)lines.push([r.account,r.joined_on,r.parent_account||'',r.level||1,r.remark||'',r.stake_cents/100,r.balance_cents/100,r.total_withdraw_cents/100,r.daily_withdraw_cents/100,r.profit_cents/100]);testDownloadBlob('V8测试会员明细'+(rootAccount?'-'+rootAccount:'')+'.csv',testToCsv(lines),'text/csv;charset=utf-8')}
function testDownloadLayers(account){const root=members.find(r=>r.account===account);if(!root){showToast('没有找到此会员');return}const lines=[['数据层级','人数','建仓资金','余额','累计提现','当日提现','输赢']],keys=['stake_cents','balance_cents','total_withdraw_cents','daily_withdraw_cents','profit_cents'];function add(label,rs){const sums=keys.map(k=>rs.reduce((a,r)=>a+(Number(r[k])||0),0)/100);lines.push([label,rs.length,...sums])}add(account+'本人',[root]);const by=new Map(members.map(r=>[r.id,r]));let level=[root],seen=new Set([root.id]),depth=0;while(true){const next=members.filter(r=>!seen.has(r.id)&&level.some(p=>p.id===r.parent_id));if(!next.length)break;next.forEach(r=>seen.add(r.id));add('第'+(++depth)+'层汇总',next);level=next;if(depth>500)break}testDownloadBlob('V8逐层汇总-'+account+'.csv',testToCsv(lines),'text/csv;charset=utf-8')}
const BACKUP_FORMAT='member-tree-v9-aes256-gcm',BACKUP_ITER=310000;
function bytesTo64(arr){let s='';for(const b of arr)s+=String.fromCharCode(b);return btoa(s)}
function from64(s){if(typeof s!=='string'||!s||s.length>30000000||!/^[A-Za-z0-9+/]*={0,2}$/.test(s))throw Error('加密备份文件内容格式不正确');return Uint8Array.from(atob(s),c=>c.charCodeAt(0))}
async function deriveBackupKey(password,salt){const base=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:BACKUP_ITER,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['encrypt','decrypt'])}
async function encryptedBackup(state,password){if(!crypto?.subtle||!crypto.getRandomValues)throw Error('浏览器当前环境不支持安全加密');const salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12));const key=await deriveBackupKey(password,salt);const body=new TextEncoder().encode(JSON.stringify({kind:'member-tree-v9-complete-state',version:1,saved_at:new Date().toISOString(),state}));const cipher=await crypto.subtle.encrypt({name:'AES-GCM',iv},key,body);return {format:BACKUP_FORMAT,version:1,created_at:new Date().toISOString(),kdf:'PBKDF2-SHA256',iterations:BACKUP_ITER,cipher:'AES-256-GCM',salt:bytesTo64(salt),iv:bytesTo64(iv),data:bytesTo64(new Uint8Array(cipher))}}
function validateRestoredState(s){if(!s||!Array.isArray(s.rows)||!Array.isArray(s.history)||!Array.isArray(s.logs))throw Error('备份结构不完整');if(s.rows.length>20000||s.history.length>500||s.logs.length>10000)throw Error('备份条目数量异常');const ids=new Set(),accounts=new Set();for(const r of s.rows){if(!r||typeof r.id!=='string'||!(/^[0-9a-fA-F-]{36}$/.test(r.id)||/^\d+$/.test(r.id)))throw Error('备份会员编号异常或重复');ids.add(r.id);if(typeof r.account!=='string'||!r.account||r.account.length>64)throw Error('备份会员账号无效');const lower=r.account.toLowerCase();accounts.add(lower);if(typeof r.joined_on!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(r.joined_on))throw Error('备份加入日期格式错误');if(typeof r.remark!=='string'||[...r.remark].length>20)throw Error('备份备注长度异常');if(!Number.isSafeInteger(Number(r.stake_cents))||Number(r.stake_cents)<0||Number(r.stake_cents)>=1e14)throw Error('备份建仓金额无效');for(const k of ['balance_cents','total_withdraw_cents','daily_withdraw_cents','revision']){if(!Number.isSafeInteger(Number(r[k])))throw Error('备份金额或版本号无效')}}const lookup=new Map(s.rows.map(x=>[x.id,x]));for(const r of s.rows){if(r.parent_id&&!lookup.has(r.parent_id))throw Error('备份会员存在缺失的上级关系');let x=r,visited=new Set();while(x){if(visited.has(x.id))throw Error('备份会员层级存在循环');visited.add(x.id);x=lookup.get(x.parent_id)}}if(!Number.isSafeInteger(Number(s.nextId))||Number(s.nextId)<1||!Number.isSafeInteger(Number(s.version)))throw Error('备份序号格式错误');return s}
async function decryptBackup(envelope,password){if(!envelope||envelope.format!==BACKUP_FORMAT||envelope.version!==1||envelope.cipher!=='AES-256-GCM'||envelope.kdf!=='PBKDF2-SHA256'||envelope.iterations!==BACKUP_ITER)throw Error('不是本测试版支持的加密备份文件');const salt=from64(envelope.salt),iv=from64(envelope.iv),data=from64(envelope.data);if(salt.length!==16||iv.length!==12||data.length<16)throw Error('加密文件已损坏');try{const key=await deriveBackupKey(password,salt),plain=await crypto.subtle.decrypt({name:'AES-GCM',iv},key,data),body=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(plain));if(body.kind!=='member-tree-v9-complete-state'||body.version!==1)throw Error('备份内容版本不支持');return validateRestoredState(body.state)}catch(e){if(e.name==='OperationError')throw Error('密码错误或备份文件已损坏');throw e}}
function testBackup(){if(role!=='admin'){showToast('仅管理员可以备份');return}el('backupPassword').value='';el('backupPasswordConfirm').value='';el('backupError').textContent='';el('backupDialog').showModal();el('backupPassword').focus()}
async function testBackupSubmit(e){e.preventDefault();const password=el('backupPassword').value,confirmPass=el('backupPasswordConfirm').value;if(password.length<8){el('backupError').textContent='密码至少8位';return}if(password!==confirmPass){el('backupError').textContent='两次输入的密码不一致';return}const btn=el('backupSubmit');btn.disabled=true;el('backupError').textContent='正在加密，请勿关闭页面…';try{const result=await api('/admin/backup');const payload=await encryptedBackup(result.state,password);const file='会员正式系统加密备份_'+dateNow()+'.mtbackup';testDownloadBlob(file,JSON.stringify(payload),'application/json;charset=utf-8');el('backupDialog').close();showToast('完整加密备份已下载，请安全保存密码与文件')}catch(err){el('backupError').textContent='备份失败：'+err.message}finally{btn.disabled=false;el('backupPassword').value='';el('backupPasswordConfirm').value=''}}
async function testRestore(ev){const f=ev.target.files?.[0];ev.target.value='';if(!f)return;if(f.size>15*1024*1024){showToast('备份文件大于15MB，拒绝加载');return}try{const x=JSON.parse(await f.text());if(x.format!==BACKUP_FORMAT)throw Error('请选择此版本生成的 .mtbackup 加密备份，旧版未加密JSON不适用');restoreChosenFile=x;el('restoreFilename').textContent=`文件：${f.name}（加密，需输入原密码）`;el('restorePassword').value='';el('restoreError').textContent='';el('restoreDialog').showModal();el('restorePassword').focus()}catch(err){showToast('文件读取失败：'+err.message)}}
async function testRestoreSubmit(e){e.preventDefault();const password=el('restorePassword').value;if(!restoreChosenFile){el('restoreError').textContent='请先选择备份文件';return}const btn=el('restoreSubmit');btn.disabled=true;el('restoreError').textContent='正在校验密码、数据和关系…';try{const data=await decryptBackup(restoreChosenFile,password);const active=data.rows.filter(x=>!x.deleted);if(!confirm(`解密成功：包含 ${active.length} 位会员，${data.logs.length} 条日志。确认要用此备份替换服务器上的全部会员数据吗？此操作影响所有8位管理员及全部成员，且无法直接撤销。`))return;if(prompt('这是正式数据库恢复。请输入「确认覆盖」继续：')!=='确认覆盖')return;const restoreResult=await api('/admin/restore','POST',{state:data,confirm:'RESTORE_WITH_BACKUP'});restoreChosenFile=null;el('restoreDialog').close();view='branch';detailId=null;query='';el('search').value='';await refresh();await syncUndoStatus();showToast(`成功恢复 ${restoreResult.members} 位会员；安全去重 ${restoreResult.duplicate_members_removed||0} 条`)}catch(err){el('restoreError').textContent='恢复失败：'+err.message}finally{btn.disabled=false;el('restorePassword').value=''}}
async function testClear(){showToast('正式系统禁止一键清空')}
function configure(){el('viewerTab').onclick=()=>selectedLogin('viewer');el('adminTab').onclick=()=>selectedLogin('admin');el('loginButton').onclick=login;el('loginPassword').addEventListener('keydown',e=>{if(e.key==='Enter')login()});el('logoutButton').onclick=logout;document.querySelectorAll('[data-view]').forEach(x=>x.onclick=()=>{if(['import','logs'].includes(x.dataset.view)&&role!=='admin')return;view=x.dataset.view;if(view==='academy'){academyLoaded=false;academySelected=null};render()});el('search').oninput=e=>{e.target.setCustomValidity('');if(view==='branch')return;query=e.target.value.trim();render()};el('search').onkeydown=e=>{if(view==='branch'&&e.key==='Enter'){e.preventDefault();locateBranchAccount()}};el('branchSearchGo').onclick=locateBranchAccount;el('treeGroupFilter').onchange=e=>selectTreeGroup(e.target.value);el('riskTreeBtn').onclick=toggleRiskTree;el('withdrawTreeBtn').onclick=toggleWithdrawalTree;el('compactTreeBtn').onclick=toggleCompactTree;el('positionAlarmBtn').onclick=togglePositionAlarm;el('aiTreeBtn').onclick=openAIEvaluation;
 for(const [id,action] of [['branchZoomOut','zoomOut'],['branchZoomIn','zoomIn'],['branchFit','fit'],['branchExpand','expand']])el(id).onclick=()=>branchViewportControls?.[action]?.();el('treeFullscreenBtn').onclick=toggleTreeFullscreen;el('expandAll').onclick=()=>{collapsed.clear();render()};el('collapseAll').onclick=()=>{collapsed=new Set(members.map(x=>x.id));render()};el('addButton').onclick=()=>openEdit();el('testBackupBtn').onclick=testBackup;el('backupForm').onsubmit=testBackupSubmit;el('backupClose').onclick=()=>el('backupDialog').close();el('backupCancel').onclick=()=>el('backupDialog').close();el('restoreForm').onsubmit=testRestoreSubmit;el('restoreClose').onclick=()=>el('restoreDialog').close();el('restoreCancel').onclick=()=>el('restoreDialog').close();el('remarkForm').onsubmit=saveQuickRemark;el('remarkClose').onclick=()=>el('remarkDialog').close();el('remarkCancel').onclick=()=>el('remarkDialog').close();el('testRestoreBtn').onclick=()=>el('testBackupInput').click();el('testBackupInput').onchange=testRestore;el('undoButton').onclick=undoPrevious;el('seedButton').onclick=()=>showToast('流星测试版不提供演示数据');el('closeEdit').onclick=()=>el('editDialog').close();el('cancelEdit').onclick=()=>el('editDialog').close();el('editForm').onsubmit=saveEdit;el('smartPasteApply').onclick=smartPasteApply;el('smartPasteClipboard').onclick=smartPasteFromClipboard;el('smartPasteClear').onclick=smartPasteReset;el('deleteEdit').onclick=removeEdit;el('exportBtn').onclick=()=>testDownloadMembers();selectedLogin('viewer')}
configure();api('/me').then(async d=>{if(d.role){setRole(d.role,d.csrf,d.username);await refresh();await syncUndoStatus()}}).catch(()=>{});setInterval(()=>{if(role&&view!=='import'&&!document.querySelector('dialog[open]'))refresh(true)},10000);
