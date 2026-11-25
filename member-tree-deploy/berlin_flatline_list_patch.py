"""Berlin test-only read-only three-month flatline roster.
Consumes the already loaded member tree; no member, ledger or DB mutations.
"""
from pathlib import Path
script = r"""
// Berlin 躺平名单：以当前树结构判断最近三个自然月内是否有新下级。
let berlinFlatlineUI=null;
function berlinFlatlineMonthsAgo(day,months){
 const p=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(day||''));
 if(!p)return '';
 const dt=new Date(Date.UTC(+p[1],+p[2]-1,1));
 dt.setUTCMonth(dt.getUTCMonth()-months);
 const end=new Date(Date.UTC(dt.getUTCFullYear(),dt.getUTCMonth()+1,0)).getUTCDate();
 dt.setUTCDate(Math.min(+p[3],end));
 return dt.toISOString().slice(0,10);
}
function berlinFlatlineLetter(n){
 let out='';for(;n>0;n=Math.floor((n-1)/26))out=String.fromCharCode(65+(n-1)%26)+out;
 return out||'—';
}
function berlinFlatlineRows(){
 const all=Array.isArray(members)?members:[];
 const index=new Map(all.map(m=>[String(m.id),m]));
 const today=dateNow(),cutoff=berlinFlatlineMonthsAgo(today,3);
 const recentCount=new Map();
 // A newly added member counts towards EVERY upstream team's growth;
 // the member's own join does not count as an addition under itself.
 for(const child of all){
  const joined=String(child.joined_on||'').slice(0,10);
  if(!/^\d{4}-\d{2}-\d{2}$/.test(joined)||joined<cutoff||joined>today)continue;
  let current=child,visited=new Set([String(child.id)]);
  for(let depth=0;depth<all.length&&current?.parent_id!=null;depth++){
   const id=String(current.parent_id),parent=index.get(id);
   if(!parent||visited.has(id))break;
   visited.add(id);
   recentCount.set(id,(recentCount.get(id)||0)+1);
   current=parent;
  }
 }
 const dayMs=Date.parse(today+'T00:00:00Z');
 return all.filter(m=>String(m.remark||'')!=='上级占位（待补资料）')
   .filter(m=>(recentCount.get(String(m.id))||0)===0)
   .map(m=>{
     let parent=m,level=1,seen=new Set([String(m.id)]);
     for(let i=0;i<all.length&&parent?.parent_id!=null;i++){
       const p=index.get(String(parent.parent_id));
       if(!p||seen.has(String(p.id)))break;
       seen.add(String(p.id));parent=p;level++;
     }
     const directGroup=String(m.group_name||m.group_label||m.group||m.team_group||'').trim();
     const parentName=String(parent.remark||'').trim();
     let group=directGroup||(parentName&&parentName!=='上级占位（待补资料）'?parentName:String(parent.account||'未分组'));
     if(/^\d{1,2}$/.test(group))group=group.padStart(2,'0')+'组';
     const day=String(m.joined_on||'').slice(0,10);
     const t=Date.parse(day+'T00:00:00Z');
     const days=Number.isFinite(t)?Math.max(0,Math.floor((dayMs-t)/86400000)):null;
     return {m,group,level,label:level>=2?berlinFlatlineLetter(level-1):'—',day,days,
       cents:Number(m.balance_cents)||0};
   }).sort((a,b)=>(b.days??-1)-(a.days??-1)||String(a.m.account).localeCompare(String(b.m.account)));
}
function berlinFlatlineEnsure(){
 const toolbar=berlinHistoryToolbar?.bar;
 if(!toolbar)return;
 let open=document.getElementById('berlinFlatlineOpen');
 if(!open){
  open=document.createElement('button');open.type='button';open.id='berlinFlatlineOpen';
  open.className='berlin-history-nav berlin-flatline-open';
  open.textContent='📋 躺平名单';
  open.onclick=berlinFlatlineOpen;
 }
 if(open.parentElement!==toolbar)toolbar.append(open);
}
function berlinFlatlineOpen(){
 let ui=berlinFlatlineUI;
 if(!ui){
   const overlay=document.createElement('div');overlay.className='berlin-flatline-overlay';
   overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');
   overlay.setAttribute('aria-label','躺平名单');
   const panel=document.createElement('section');panel.className='berlin-flatline-panel';
   const header=document.createElement('div');header.className='berlin-flatline-header';
   const title=document.createElement('strong');title.textContent='📋 躺平名单 · 近三个月无新增下级';
   const close=document.createElement('button');close.type='button';close.textContent='关闭 ×';
   close.className='berlin-flatline-close';close.onclick=()=>{overlay.hidden=true};
   header.append(title,close);
   const notice=document.createElement('p');notice.className='berlin-flatline-note';
   notice.textContent='统计范围：当前全部会员树；以会员注册/加入日期判断最近三个月的团队下级新增（包括间接下级）。躺平天数=加入日至今天。';
   const filters=document.createElement('div');filters.className='berlin-flatline-filters';
   const label=document.createElement('label');label.textContent='选择小组：';
   const select=document.createElement('select');select.setAttribute('aria-label','选择小组');
   label.append(select);
   const count=document.createElement('span');count.className='berlin-flatline-count';
   filters.append(label,count);
   const aggregates=document.createElement('div');aggregates.className='berlin-flatline-aggregates';
   const wrap=document.createElement('div');wrap.className='berlin-flatline-scroll';
   const table=document.createElement('table');table.className='berlin-flatline-table';
   const head=document.createElement('thead');const tr=document.createElement('tr');
   for(const s of ['会员账号','备注信息','小组','层级','加入日期','躺平天数','当前余额','定位']){
     const th=document.createElement('th');th.textContent=s;tr.append(th);
   }
   head.append(tr);const body=document.createElement('tbody');
   table.append(head,body);wrap.append(table);
   const footer=document.createElement('div');footer.className='berlin-flatline-footer';
   panel.append(header,notice,filters,aggregates,wrap,footer);
   overlay.append(panel);document.body.append(overlay);
   overlay.onclick=e=>{if(e.target===overlay)overlay.hidden=true};
   select.onchange=()=>berlinFlatlineDraw();
   ui=berlinFlatlineUI={overlay,select,count,aggregates,body,footer};
 }
 ui.overlay.hidden=false;
 berlinFlatlineDraw();
}
function berlinFlatlineDraw(){
 const ui=berlinFlatlineUI;if(!ui)return;
 const all=berlinFlatlineRows(),oldValue=ui.select.value;
 const groups=[...new Set(all.map(x=>x.group))].sort((a,b)=>a.localeCompare(b,'zh-CN',{numeric:true}));
 ui.select.replaceChildren();
 for(const [value,label] of [['','全部小组'],...groups.map(g=>[g,g])]){
  const opt=document.createElement('option');opt.value=value;opt.textContent=label;ui.select.append(opt);
 }
 ui.select.value=groups.includes(oldValue)?oldValue:'';
 const rows=all.filter(x=>!ui.select.value||x.group===ui.select.value);
 const amount=rows.reduce((v,x)=>v+x.cents,0),money=v=>
   new Intl.NumberFormat('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2}).format(v/100);
 ui.count.textContent='符合条件 '+rows.length+' 人';
 ui.aggregates.replaceChildren();
 for(const [label,value] of [['总人数',rows.length+' 人'],['当前余额合计',money(amount)],
   ['涉及小组',new Set(rows.map(x=>x.group)).size+' 组'],['统计截止',dateNow()]]){
   const card=document.createElement('div');card.className='berlin-flatline-stat';
   const small=document.createElement('span');small.textContent=label;
   const strong=document.createElement('strong');strong.textContent=value;
   card.append(small,strong);ui.aggregates.append(card);
 }
 const fragment=document.createDocumentFragment();
 for(const x of rows){
  const tr=document.createElement('tr');
  const columns=[x.m.account||'',x.m.remark||'—',x.group,x.label,x.day||'—',
    x.days==null?'—':x.days+' 天',money(x.cents)];
  columns.forEach((v,i)=>{const td=document.createElement('td');td.textContent=String(v);
     if(i===6)td.className='berlin-flatline-balance';tr.append(td)});
  const td=document.createElement('td');const b=document.createElement('button');
  b.type='button';b.textContent='查看';b.className='berlin-flatline-focus';
  b.onclick=()=>{ui.overlay.hidden=true;berlinHistoryFocusMember(x.m)};
  td.append(b);tr.append(td);fragment.append(tr);
 }
 if(!rows.length){const tr=document.createElement('tr'),td=document.createElement('td');
  td.colSpan=8;td.textContent='当前筛选范围没有符合条件的账号';tr.append(td);fragment.append(tr);}
 ui.body.replaceChildren(fragment);
 const byLevel=new Map(),byGroup=new Map();
 for(const x of rows){
  const lv=x.label==='—'?'第一级':x.label+'层';
  const a=byLevel.get(lv)||{n:0,c:0};a.n++;a.c+=x.cents;byLevel.set(lv,a);
  const g=byGroup.get(x.group)||{n:0,c:0};g.n++;g.c+=x.cents;byGroup.set(x.group,g);
 }
 ui.footer.replaceChildren();
 const section=(name,map)=>{
  const d=document.createElement('div');const h=document.createElement('strong');h.textContent=name;d.append(h);
  const p=document.createElement('p');
  p.textContent=[...map].map(([k,v])=>k+'：'+v.n+'人 / 余额 '+money(v.c)).join('　｜　')||'无';
  d.append(p);ui.footer.append(d);
 };
 section('层级汇总',byLevel);section('小组汇总',byGroup);
}
"""
anchor="function berlinHistoryDateShift(value,days){"
assert j.count(anchor)==1,'history toolbar not available'
j=j.replace(anchor,script+'\n'+anchor,1)
anchor=" berlinHistoryEnsureControls();\n lastDisplayDay=businessDay||dateNow();"
assert j.count(anchor)==1,'cannot find history toolbar render hook'
j=j.replace(anchor," berlinHistoryEnsureControls();\n berlinFlatlineEnsure();\n lastDisplayDay=businessDay||dateNow();",1)
css=r"""
<style id="berlin-flatline-css">
.berlin-flatline-open{font-weight:800!important;background:#fff4dc!important;color:#85520b!important;border-color:#efcb77!important}
.berlin-flatline-overlay[hidden]{display:none!important}
.berlin-flatline-overlay{position:fixed;z-index:99999;inset:0;background:#071c29c4;display:flex;align-items:center;justify-content:center;padding:14px}
.berlin-flatline-panel{box-sizing:border-box;background:#fff;color:#162d39;width:min(1120px,98vw);max-height:92vh;border-radius:14px;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 15px 55px #0006}
.berlin-flatline-header{display:flex;justify-content:space-between;align-items:center;padding:15px 18px;border-bottom:1px solid #d7e4e7;gap:10px;font-size:17px}
.berlin-flatline-close,.berlin-flatline-focus{border:1px solid #c8dade;background:#fff;border-radius:7px;padding:6px 10px;cursor:pointer;color:#234b61}
.berlin-flatline-note{margin:10px 18px 4px!important;font-size:12px;color:#55747f}
.berlin-flatline-filters{padding:10px 18px;display:flex;align-items:center;flex-wrap:wrap;gap:14px}
.berlin-flatline-filters label{font-size:13px;font-weight:700}
.berlin-flatline-filters select{padding:6px;border:1px solid #acc2ca;border-radius:7px;background:white;color:#1c3c49;min-width:155px}
.berlin-flatline-count{font-size:13px;color:#84500b;font-weight:700}
.berlin-flatline-aggregates{padding:0 18px 10px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}
.berlin-flatline-stat{border:1px solid #e0e8ec;border-radius:9px;background:#f6fafb;padding:9px 12px;display:flex;flex-direction:column;gap:5px}
.berlin-flatline-stat span{font-size:11px;color:#5d7984}
.berlin-flatline-stat strong{font-size:18px;color:#16495d;font-variant-numeric:tabular-nums}
.berlin-flatline-scroll{overflow:auto;min-height:100px;flex:1;margin:0 18px}
.berlin-flatline-table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}
.berlin-flatline-table th{position:sticky;top:0;background:#e8f2f4;color:#244e5b;font-weight:800}
.berlin-flatline-table th,.berlin-flatline-table td{padding:9px 10px;text-align:center;border-bottom:1px solid #ebeff0}
.berlin-flatline-table tbody tr:nth-child(even){background:#f9fbfc}
.berlin-flatline-table .berlin-flatline-balance{color:#18734f;font-weight:700;font-variant-numeric:tabular-nums}
.berlin-flatline-footer{padding:11px 18px 15px;background:#f7fafb;border-top:1px solid #dae4e7;max-height:155px;overflow:auto;font-size:12px}
.berlin-flatline-footer div{margin:4px 0}.berlin-flatline-footer p{line-height:1.7;margin:3px 0 9px;color:#415a65;overflow-wrap:anywhere}
@media(max-width:750px){.berlin-flatline-panel{max-height:95vh}
 .berlin-flatline-aggregates{grid-template-columns:repeat(2,minmax(0,1fr))}
 .berlin-flatline-stat strong{font-size:15px}
 .berlin-flatline-header{font-size:14px}}
</style>
"""
assert h.count('</body>')==1
h=h.replace('</body>',css+'</body>',1)
assert j.count('function berlinFlatlineRows(){')==1
jp.write_text(j,encoding='utf-8');hp.write_text(h,encoding='utf-8')
print('PASS: Berlin read-only flatline list, group filtering, 3-month descendants, layer and balance totals')
