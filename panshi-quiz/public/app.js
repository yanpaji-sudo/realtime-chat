const $=id=>document.getElementById(id);
const sessionKey='panshi-quiz-session-v4';
const state={nickname:'',id:'',token:'',questions:[],answers:[],current:0,review:[],certificate:null,submitted:false};
const chapterOrder=['仓位篇','收益篇','流量篇','保障篇','动态篇','市场方法篇','市场问题篇','磐石甄选篇','福利制度篇'];
const chapterNames=['仓位入门','收益计算','流量价值','资金保障','团队建设','市场方法','疑问解答','磐石甄选','福利制度'];
const chapterSymbols=['01','02','03','04','05','06','07','08','09'];
let leaderboardMode='leaders',refreshTimer=null;
const escapeHtml=value=>String(value).replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const setVisible=(id,visible)=>$(id).classList.toggle('hidden',!visible);
function notify(message){const box=$('notice');box.textContent=message;setVisible('notice',true);box.scrollIntoView({behavior:'smooth',block:'nearest'});}
function dismissNotice(){setVisible('notice',false);}
async function api(path,method='GET',data){
 const opts={method,headers:{'accept':'application/json'}};
 if(data!==undefined){opts.headers['content-type']='application/json';opts.body=JSON.stringify(data);}
 let response;
 try{response=await fetch(path,opts);}catch(err){throw new Error('网络未连接，无法访问云端评分和排行榜。请确认已完成服务器部署。');}
 let body={};try{body=await response.json();}catch{throw new Error('服务器返回内容异常，请检查部署。');}
 if(!response.ok)throw new Error(body.error||`请求失败（${response.status}）`);
 return body;
}
function buildMap(){
 $('chapterMap').innerHTML=chapterOrder.map((name,i)=>`<div class="map-card"><div class="stage">第${chapterSymbols[i]}关</div><h3>${chapterNames[i]}</h3><p>${name}</p><div class="counter">随机题库</div></div>`).join('');
}
async function loadBoard(){
 try{
 const data=await api('/api/leaderboard');
 const leaders=data.leaderboard||[],active=data.active||[];
 $('leaderList').innerHTML=leaders.length?leaders.slice(0,30).map((r,i)=>`<div class="leader-row"><span class="rank-index ${i<3?'top':''}">${i+1}</span><span class="leader-name">${escapeHtml(r.nickname)}</span><span class="leader-score">${r.score}分</span></div>`).join(''):'<p class="empty">暂无交卷成绩，成为第一位上榜学员！</p>';
 $('activeList').innerHTML=active.length?active.map((r,i)=>`<div class="leader-row"><span class="active-dot"></span><span class="leader-name">${escapeHtml(r.nickname)}</span><small>答题中</small></div>`).join(''):'<p class="empty">当前暂时没有活跃学员</p>';
 $('countCompleted').textContent=String(data.completed||0);
 $('countActive').textContent=String(active.length);
 dismissNotice();
 }catch(e){
 $('leaderList').innerHTML=`<p class="empty">排行榜暂时无法连接云端：${escapeHtml(e.message)}</p>`;
 $('activeList').innerHTML='<p class="empty">参赛名单暂不可用</p>';
 }
}
function showTab(which){leaderboardMode=which;$('leaderTab').classList.toggle('active',which==='leaders');$('activeTab').classList.toggle('active',which==='active');setVisible('leaderList',which==='leaders');setVisible('activeList',which==='active');}
function persist(){if(!state.submitted){sessionStorage.setItem(sessionKey,JSON.stringify({id:state.id,token:state.token,nickname:state.nickname,questions:state.questions,answers:state.answers,current:state.current}));}}
function restore(){try{
 const raw=JSON.parse(sessionStorage.getItem(sessionKey)||'null');
 if(!raw||!Array.isArray(raw.questions)||raw.questions.length!==100||!Array.isArray(raw.answers)||raw.answers.length!==100)return;
 Object.assign(state,raw,{submitted:false,review:[],certificate:null});
 setVisible('mapPanel',false);setVisible('quizPanel',true);setVisible('resultPanel',false);
 $('nickname').value=state.nickname;
 drawQuestion();
 }catch{sessionStorage.removeItem(sessionKey);}}
async function start(e){
 e.preventDefault();dismissNotice();
 const nick=$('nickname').value.trim();if(!nick){notify('请先输入匿名昵称');return;}
 const button=$('startForm').querySelector('button');button.disabled=true;button.textContent='正在生成随机试卷…';
 try{
  const result=await api('/api/start','POST',{nickname:nick});
  if(!Array.isArray(result.questions)||result.questions.length!==100)throw new Error('题库返回异常');
  Object.assign(state,{nickname:result.nickname,id:result.id,token:result.token,questions:result.questions,answers:Array(100).fill(null),current:0,review:[],certificate:null,submitted:false});
  persist();setVisible('mapPanel',false);setVisible('quizPanel',true);setVisible('resultPanel',false);
  drawQuestion();$('quizPanel').scrollIntoView({behavior:'smooth',block:'start'});loadBoard();
 }catch(err){notify(err.message);}finally{button.disabled=false;button.innerHTML='开始闯关 <span aria-hidden="true">→</span>';}
}
function drawQuestion(){
 const q=state.questions[state.current],selected=state.answers[state.current],answered=state.answers.filter(n=>Number.isInteger(n)).length;
 $('chapterTag').textContent=q.chapter;
 $('questionNum').textContent=`第 ${state.current+1} / ${state.questions.length} 题`;
 $('quizAlias').textContent=state.nickname;
 $('answeredNum').textContent=`已选 ${answered} / 100`;
 $('progressFill').style.width=`${answered}%`;
 $('questionText').textContent=q.question;
 $('choices').innerHTML=q.options.map((v,i)=>`<button type="button" class="choice ${selected===i?'selected':''}" data-choice="${i}"><span class="choice-letter">${'ABCD'[i]}</span><span>${escapeHtml(v)}</span></button>`).join('');
 $('choices').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
 state.answers[state.current]=Number(b.dataset.choice);persist();drawQuestion();
 }));
 $('prevBtn').disabled=state.current===0;
 setVisible('finishBtn',state.current===99);
 setVisible('nextBtn',state.current!==99);
 const missing=100-answered;
 $('pageHint').textContent=missing?`还剩 ${missing} 题未选`:'已全部选择，可以交卷';
}
function next(delta){state.current=Math.max(0,Math.min(99,state.current+delta));persist();drawQuestion();}
async function submit(){
 const missing=state.answers.findIndex(x=>!Number.isInteger(x));
 if(missing>=0){state.current=missing;persist();drawQuestion();notify(`还有题目未选，已跳转到第${missing+1}题。`);return;}
 if(!window.confirm('确认提交100道答案？提交后不能修改，系统将自动评分并颁发证书。'))return;
 $('finishBtn').disabled=true;$('finishBtn').textContent='云端评分中…';
 try{
 const res=await api('/api/submit','POST',{id:state.id,token:state.token,answers:state.answers});
 state.submitted=true;state.certificate=res.certificate;state.review=res.review;
 sessionStorage.removeItem(sessionKey);setVisible('quizPanel',false);setVisible('resultPanel',true);
 drawResult();loadBoard();$('resultPanel').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(e){notify(e.message);}finally{$('finishBtn').disabled=false;$('finishBtn').textContent='交卷 · 自动评分';}
}
function stamp(ts){return new Date(ts).toLocaleDateString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit'});}
function drawResult(){
 const cert=state.certificate;
 $('scoreValue').textContent=cert.score;$('correctValue').textContent=`${cert.correctCount} / ${cert.total}`;$('gradeValue').textContent=cert.grade;
 $('certName').textContent=cert.nickname;$('certScore').textContent=cert.score;$('certGrade').textContent=`学习称号：${cert.grade}`;$('certDate').textContent=`颁发日期：${stamp(cert.finishedAt)}`;$('certId').textContent=`证书编号：${cert.id}`;
 setVisible('review',false);
}
function makeCertificateCanvas(){
 const c=document.createElement('canvas');c.width=1240;c.height=1754;
 const x=c.getContext('2d');
 const bg=x.createLinearGradient(0,0,1240,1754);bg.addColorStop(0,'#fff9ee');bg.addColorStop(1,'#f5edda');x.fillStyle=bg;x.fillRect(0,0,1240,1754);
 x.lineWidth=8;x.strokeStyle='#be9a58';x.strokeRect(60,60,1120,1634);x.lineWidth=3;x.strokeRect(85,85,1070,1584);
 x.textAlign='center';x.textBaseline='middle';
 const font=(size,weight='700')=>`${weight} ${size}px 'Microsoft YaHei','PingFang SC',sans-serif`;
 x.fillStyle='#b7934e';x.font=font(92);x.fillText('✦',620,280);
 x.font=font(32,'400');x.fillText('CERTIFICATE OF COMPLETION',620,384);
 x.fillStyle='#263551';x.font=font(78);x.fillText('知识学习结业证书',620,500);
 x.font=font(37,'400');x.fillText('磐石学习学院 · 九大知识闯关赛',620,606);
 x.fillStyle='#79829b';x.font=font(32,'400');x.fillText('兹证明',620,744);
 x.fillStyle='#1d3155';x.font=font(84);x.fillText(state.certificate.nickname,620,860);
 x.font=font(30,'400');x.fillText('已完成九大知识模块100道题的知识学习测评',620,982);
 x.fillStyle='#ac8640';x.font=font(120);x.fillText(String(state.certificate.score),620,1150);
 x.font=font(30);x.fillText('分 / 满分100分',620,1225);
 x.fillStyle='#263551';x.font=font(35);x.fillText(`学习称号：${state.certificate.grade}`,620,1340);
 x.font=font(29,'400');x.fillText(`颁发日期：${stamp(state.certificate.finishedAt)}`,620,1470);
 x.font=font(25,'400');x.fillText(`证书编号：${state.certificate.id}`,620,1530);
 x.fillStyle='#777';x.font=font(20,'400');x.fillText('本证书仅证明完成知识答题，不代表投资资格、收益承诺或合规认证',620,1610);
 return c;
}
function downloadCertificate(){
 if(!state.certificate)return;
 const link=document.createElement('a');link.href=makeCertificateCanvas().toDataURL('image/png');
 link.download=`磐石学习证书-${state.certificate.nickname}-${state.certificate.score}分.png`;
 document.body.appendChild(link);link.click();link.remove();
}
function review(){
 const root=$('review');if(!root.classList.contains('hidden')){setVisible('review',false);return;}
 const wrong=state.review.filter(q=>!q.ok);
 root.innerHTML='<h3>错题复盘</h3>'+(wrong.length?wrong.map((q,i)=>`<article class="review-item"><strong>${i+1}. ${escapeHtml(q.question)}</strong><p>你的选择：${'ABCD'[q.selected]} · 正确答案：${'ABCD'[q.correct]}（${escapeHtml(q.options[q.correct])}）</p><small>${escapeHtml(q.explanation)}</small></article>`).join(''):'<p>全部答对，恭喜！</p>');
 setVisible('review',true);root.scrollIntoView({behavior:'smooth',block:'start'});
}
function reset(){
 Object.assign(state,{nickname:'',id:'',token:'',questions:[],answers:[],current:0,review:[],certificate:null,submitted:false});
 sessionStorage.removeItem(sessionKey);setVisible('resultPanel',false);setVisible('quizPanel',false);setVisible('mapPanel',true);window.scrollTo({top:0,behavior:'smooth'});
}
$('startForm').addEventListener('submit',start);
$('prevBtn').addEventListener('click',()=>next(-1));$('nextBtn').addEventListener('click',()=>next(1));$('finishBtn').addEventListener('click',submit);
$('leaderTab').addEventListener('click',()=>showTab('leaders'));$('activeTab').addEventListener('click',()=>showTab('active'));
$('pngBtn').addEventListener('click',downloadCertificate);$('printBtn').addEventListener('click',()=>window.print());
$('reviewBtn').addEventListener('click',review);$('restartBtn').addEventListener('click',reset);
buildMap();restore();loadBoard();refreshTimer=setInterval(loadBoard,20000);