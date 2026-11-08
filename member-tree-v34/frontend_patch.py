from pathlib import Path
root=Path('member-tree')
ap=root/'app.py'
h=root/'static/index.html'
j=root/'static/app.js'
cp=root/'static/style.css'
source=ap.read_text(encoding='utf-8')
html=h.read_text(encoding='utf-8')
js=j.read_text(encoding='utf-8')
css=cp.read_text(encoding='utf-8')
def rep(s,a,b,label):
    n=s.count(a)
    if n!=1:raise RuntimeError('V34 '+label+': wanted 1 anchor got '+str(n))
    return s.replace(a,b,1)

source += """

# V34 磐石AI学院: only creates independent academy tables and routes.
from academy import register_academy
register_academy(app,engine,require,utc_now)
"""
ap.write_text(source,encoding='utf-8')

html=rep(html,
    '<button class="nav" data-view="help">ⓘ　操作说明</button>',
    '<button class="nav" data-view="academy">♧　磐石AI学院</button><button class="nav" data-view="help">ⓘ　操作说明</button>',
    'navigation')
h.write_text(html,encoding='utf-8')

frontend="""
// V34 磐石AI学院 — knowledge base and optional grounded tutor.
// Course originals are preserved server-side; all imports require admin login.
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
 root.append(mk('h2','academy-heading','磐石 AI 学院 · 企业知识库与话术导师'));
 root.append(mk('p','academy-muted','核心课程：群洗＋磐石9—10；其余课程为辅助。原文保留，品牌统一稿作为单独的显示副本。'));
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
 const tutor=mk('section','academy-card');
 tutor.append(mk('h3','','AI 话术导师'));
 tutor.append(mk('p','academy-muted','优先按照已审核的核心课程指导表达，返回引用来源；课程原文的数字与资质说法不会擅自改写。'));
 const [wrap,q]=academyInput('需要培训或编排的问题','textarea',academyQuestion);
 q.rows=4;q.placeholder='例如：怎样为新成员介绍团队学习的重要性？';
 q.oninput=e=>academyQuestion=e.target.value;tutor.append(wrap);
 const [styleWrap,style]=academyInput('表达方式','select');
 for(const value of ['亲切自然','领导讲话','课程讲解','简短有力','新人训练']){
  const opt=mk('option','',value);opt.value=value;style.append(opt);
 }
 style.value=academyTone;style.onchange=e=>academyTone=e.target.value;
 tutor.append(styleWrap);
 const ask=mk('button','button primary',academyBusy?'查询中…':'知识库检索 / AI 指导');
 ask.disabled=academyBusy;ask.type='button';
 ask.onclick=async()=>{
   if(academyQuestion.trim().length<2){showToast('请先填写问题');return}
   academyBusy=true;ask.disabled=true;ask.textContent='正在查询课程…';
   try{academyAnswer=await api('/academy/ask','POST',{question:academyQuestion.trim(),tone:academyTone})}
   catch(e){academyAnswer={mode:'error',answer:'查询失败：'+e.message,sources:[]}}
   academyBusy=false;if(view==='academy')render();
 };
 tutor.append(ask);
 if(academyAnswer){
  const result=mk('div','academy-result');
  const heading=academyAnswer.mode==='ai'?'AI 话术建议':'已审核知识库检索';
  result.append(mk('b','',heading));
  result.append(mk('div','academy-output',academyAnswer.answer||''));
  for(const [i,source] of (academyAnswer.sources||[]).entries()){
   const cite=mk('details','academy-cite');
   cite.append(mk('summary','',String(i+1)+'. '+source.title+'｜'+source.source+(source.priority>=100?'【核心】':'【补充】')));
   cite.append(mk('p','',source.excerpt));
   result.append(cite);
  }
  tutor.append(result);
 }
 root.append(tutor);
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
"""
js=rep(js,'function render(){if(!role)return;',frontend+'\nfunction render(){if(!role)return;','academy render')
js=rep(js,"logs:'管理员操作日志',import:'批量上传',help:'操作说明'",
         "logs:'管理员操作日志',import:'批量上传',academy:'磐石AI学院',help:'操作说明'",
         'nav labels')
js=rep(js,"view==='help'?renderHelp():view==='import'?importPanel():",
         "view==='academy'?renderAcademy():view==='help'?renderHelp():view==='import'?importPanel():",
         'render route')
js=rep(js,"view=x.dataset.view;render()});",
         "view=x.dataset.view;if(view==='academy'){academyLoaded=false;academySelected=null};render()});",
         'academy nav')
j.write_text(js,encoding='utf-8')

css += """
/* V34 AI Academy: separate view; no changes to member tree layout. */
.academy-page{padding:18px;max-width:1200px;margin:auto;color:#24405c;display:grid;gap:15px}
.academy-heading{font-size:22px;margin:0;color:#154976}
.academy-muted{color:#617789;margin:0;line-height:1.65;font-size:12px;overflow-wrap:anywhere}
.academy-summary{display:flex;flex-wrap:wrap;gap:9px}
.academy-summary>span{padding:7px 11px;border-radius:7px;background:#e9f4ff;border:1px solid #bcdbfa;font-weight:800;font-size:12px;color:#245d8f}
.academy-card{display:grid;gap:12px;background:#fff;border:1px solid #d5e1ef;border-radius:12px;padding:18px;box-shadow:0 4px 18px #13456a15}
.academy-card h3{margin:0;font-size:17px;color:#24517e}
.academy-field{display:grid;gap:6px;font-size:12px}
.academy-input{width:100%;max-width:100%;box-sizing:border-box;font:inherit;padding:8px 10px;border:1px solid #a2b7cd;border-radius:6px;background:#fff;color:#214361}
.academy-field textarea{min-height:100px;resize:vertical}
.academy-result{padding:12px;background:#f3f8ff;border-left:4px solid #2673b9;display:grid;gap:9px}
.academy-output{white-space:pre-wrap;line-height:1.8;overflow-wrap:anywhere}
.academy-cite{padding:7px;background:#fff;border:1px solid #cdddf0;border-radius:7px;font-size:12px}
.academy-cite summary{cursor:pointer;font-weight:800}
.academy-cite p{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7}
.academy-toolbar{display:grid;grid-template-columns:minmax(150px,1fr) 160px auto;gap:8px}
.academy-upload{display:grid;gap:8px;padding:13px;border:1px solid #badcb9;background:#f1f9f0;border-radius:9px}
.academy-doc-list{display:grid;gap:6px;max-height:550px;overflow-y:auto}
.academy-doc-row{display:flex;flex-wrap:wrap;gap:7px;align-items:center;border:1px solid #e0eaf2;border-radius:7px;padding:7px 9px}
.academy-doc-title{font-weight:800;cursor:pointer;text-align:left;color:#11649d;border:0;background:none;font-size:13px}
.academy-doc-row .academy-muted{flex:1 1 220px}
.academy-source-box{display:grid;gap:8px;border:1px solid #abc8dc;border-radius:9px;padding:12px}
.academy-source-box h4{margin:0}
.academy-raw{max-height:540px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;font-size:12px;padding:10px;background:#f4f7f9}
@media(max-width:660px){.academy-page{padding:7px}.academy-card{padding:12px}.academy-toolbar{grid-template-columns:1fr}}
"""
cp.write_text(css,encoding='utf-8')

(root/'tests/test_v34_academy.cjs').write_text(r'''const assert=require('node:assert/strict'),fs=require('node:fs');
const js=fs.readFileSync('static/app.js','utf8');
const html=fs.readFileSync('static/index.html','utf8');
const app=fs.readFileSync('app.py','utf8');
const academy=fs.readFileSync('academy.py','utf8');
assert(js.includes('function renderAcademy(){'));
assert(js.includes("view==='academy'?renderAcademy()"));
assert(js.includes("api('/academy/ask','POST'"));
assert(js.includes("api('/academy/upload','POST',data)"));
assert(html.includes('data-view="academy"'));
assert(app.includes('register_academy(app,engine,require,utc_now)'));
assert(academy.includes("original_text TEXT NOT NULL"));
assert(academy.includes("source_priority"));
assert(academy.includes("status='approved'"));
console.log('V34 Academy UI and additive back-end contract passed');
''',encoding='utf-8')
print('V34 Academy integrated: additive route, separate navigation, and no member-table changes.')
