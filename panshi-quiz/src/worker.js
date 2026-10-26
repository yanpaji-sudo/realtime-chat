import { questions, chapterNames } from '../data/questions.js';

export const TOTAL_PER_EXAM=100;
const BASE_CHAPTERS=['仓位篇','收益篇','流量篇','保障篇','动态篇','市场方法篇','市场问题篇','磐石甄选篇','福利制度篇'];
const HEADERS={'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'};
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:HEADERS});
const fail=(message,status=400)=>json({error:message},status);
const index=new Map(questions.map(q=>[q.id,q]));
function shuffle(arr){
  for(let i=arr.length-1;i>0;i--){
    const random=new Uint32Array(1);
    crypto.getRandomValues(random);
    const j=random[0]%(i+1);
    [arr[i],arr[j]]=[arr[j],arr[i]];
  }
  return arr;
}
export function createPlan(pool=questions,amount=TOTAL_PER_EXAM){
  if(pool.length<amount || amount%4!==0) throw new Error('题库数量不足或试卷分配错误');
  const picks=shuffle([...pool]).slice(0,amount);
  const targets=shuffle(Array.from({length:amount},(_,i)=>i%4));
  return picks.map((q,i)=>{
    const order=shuffle([0,1,2,3]);
    const correctPosition=order.indexOf(q.answer);
    [order[correctPosition],order[targets[i]]]=[order[targets[i]],order[correctPosition]];
    return {id:q.id,order};
  });
}
function cleanName(s){
  if(typeof s!=='string')return '';
  const value=s.normalize('NFKC').replace(/[\u0000-\u001f\u007f\u202a-\u202e\u2066-\u2069]/g,'').trim();
  return [...value].length>=2&&[...value].length<=16&&/^[\p{L}\p{N}_\- ]+$/u.test(value)?value:'';
}
async function payload(req){
  if(Number(req.headers.get('content-length')||0)>16000)throw new Error('内容超过限制');
  const raw=await req.text();
  if(raw.length>16000)throw new Error('内容超过限制');
  return JSON.parse(raw);
}
function presentPlan(plan){return plan.map(item=>{const q=index.get(item.id);return {id:q.id,chapter:q.chapter,question:q.question,options:item.order.map(j=>q.options[j])};});}
export function gradePlan(plan,answers){
  if(!Array.isArray(answers)||answers.length!==plan.length||answers.some(a=>!Number.isInteger(a)||a<0||a>3))throw new Error('答案数量或格式错误');
  const detail=plan.map((item,i)=>{
    const q=index.get(item.id);
    if(!q||!Array.isArray(item.order)||item.order.length!==4)throw new Error('题目不存在');
    const correct=item.order.indexOf(q.answer);
    return {id:q.id,selected:answers[i],correct,ok:correct===answers[i],explanation:q.explanation,question:q.question,options:item.order.map(j=>q.options[j])};
  });
  const count=detail.filter(v=>v.ok).length;
  return {detail,count,score:Math.round(count*100/plan.length)};
}
const makeCertificate=row=>({id:row.id,nickname:row.nickname,score:row.score,correctCount:row.correct_count,total:TOTAL_PER_EXAM,finishedAt:row.finished_at,grade:row.score>=95?'知识王者':row.score>=85?'闯关达人':row.score>=80?'合格学员':'学习参与证书'});
export default {
 async fetch(request,env){
  const url=new URL(request.url),path=url.pathname;
  if(!path.startsWith('/api/')){
    return env.ASSETS ? env.ASSETS.fetch(request):new Response('Not found',{status:404});
  }
  if(request.method==='GET'&&path==='/api/health')return json({ok:!!env.DB,questionPool:questions.length,examQuestions:TOTAL_PER_EXAM,mainChapters:BASE_CHAPTERS.length,storage:env.DB?'D1':'unconfigured'},env.DB?200:503);
  if(!env.DB)return fail('云数据库尚未初始化，排行榜暂不可用',503);
  try{
   if(request.method==='GET'&&path==='/api/leaderboard'){
    const now=Date.now();
    const [leaders,active,stats]=await Promise.all([
     env.DB.prepare(`WITH r AS(SELECT nickname,score,elapsed_seconds,finished_at,ROW_NUMBER() OVER(PARTITION BY nickname ORDER BY score DESC,elapsed_seconds ASC,finished_at ASC) rn FROM attempts WHERE finished_at IS NOT NULL) SELECT nickname,score,elapsed_seconds,finished_at FROM r WHERE rn=1 ORDER BY score DESC,elapsed_seconds ASC,finished_at ASC LIMIT 50`).all(),
     env.DB.prepare('SELECT nickname,started_at FROM attempts WHERE finished_at IS NULL AND started_at>? ORDER BY started_at DESC LIMIT 35').bind(now-60*60*1000).all(),
     env.DB.prepare('SELECT COUNT(*) AS total FROM attempts WHERE finished_at IS NOT NULL').first()
    ]);
    const uniqueActive=[...new Map((active.results||[]).map(x=>[x.nickname,x])).values()];
    return json({leaderboard:leaders.results||[],active:uniqueActive,completed:Number(stats?.total||0),asOf:now});
   }
   if(request.method==='POST'&&path==='/api/start'){
    const data=await payload(request),nickname=cleanName(data?.nickname);
    if(!nickname)return fail('昵称需为2到16字符，仅支持中文、英文、数字、空格、下划线、短横线');
    const plan=createPlan(),id=crypto.randomUUID(),token=crypto.randomUUID()+'-'+crypto.randomUUID(),now=Date.now();
    await env.DB.prepare('INSERT INTO attempts (id,token,nickname,started_at,question_plan) VALUES (?,?,?,?,?)').bind(id,token,nickname,now,JSON.stringify(plan)).run();
    return json({id,token,nickname,startedAt:now,questions:presentPlan(plan),poolCount:questions.length},201);
   }
   if(request.method==='POST'&&path==='/api/submit'){
    const data=await payload(request);
    if(typeof data?.id!=='string'||typeof data?.token!=='string'||!Array.isArray(data?.answers))return fail('交卷信息不完整');
    const row=await env.DB.prepare('SELECT * FROM attempts WHERE id=? AND token=?').bind(data.id,data.token).first();
    if(!row)return fail('会话不存在或无权限',403);
    if(row.finished_at!==null)return fail('该考试已经完成评分，无法重复交卷',409);
    const plan=JSON.parse(row.question_plan),out=gradePlan(plan,data.answers);
    const now=Date.now(),elapsed=Math.max(1,Math.round((now-row.started_at)/1000));
    const dbResult=await env.DB.prepare('UPDATE attempts SET score=?,correct_count=?,elapsed_seconds=?,finished_at=? WHERE id=? AND token=? AND finished_at IS NULL').bind(out.score,out.count,elapsed,now,data.id,data.token).run();
    if(dbResult.meta?.changes!==1)return fail('本次交卷已经处理',409);
    return json({certificate:makeCertificate({...row,score:out.score,correct_count:out.count,finished_at:now}),review:out.detail,elapsedSeconds:elapsed});
   }
   if(request.method==='GET'&&path.startsWith('/api/certificate/')){
    const id=path.slice('/api/certificate/'.length);
    if(!/^[0-9a-f-]{36}$/i.test(id))return fail('证书编号无效');
    const row=await env.DB.prepare('SELECT id,nickname,score,correct_count,finished_at FROM attempts WHERE id=? AND finished_at IS NOT NULL').bind(id).first();
    if(!row)return fail('未找到证书',404);
    return json({certificate:makeCertificate(row)});
   }
   return fail('接口不存在',404);
  }catch(e){
   if(e instanceof SyntaxError)return fail('JSON格式有误');
   if(e instanceof Error&&/答案数量|内容超过|题目不存在/.test(e.message))return fail(e.message);
   return fail('服务处理失败，请检查数据库初始化和运行日志',500);
  }
 }
};