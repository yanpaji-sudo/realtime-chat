import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { createPlan, gradePlan, TOTAL_PER_EXAM } from '../src/worker.js';
import { questions } from '../data/questions.js';

class MemoryD1{
 constructor(){this.items=new Map();}
 prepare(sql){
  const db=this;let bound=[];
  return {
   bind(...values){bound=values;return this;},
   async run(){
    if(sql.startsWith('INSERT INTO attempts')){
      const [id,token,nickname,started_at,question_plan]=bound;
      db.items.set(id,{id,token,nickname,started_at,question_plan,finished_at:null,score:null,correct_count:null,elapsed_seconds:null});
      return {meta:{changes:1}};
    }
    if(sql.startsWith('UPDATE attempts')){
      const [score,correct_count,elapsed_seconds,finished_at,id,token]=bound;
      const row=db.items.get(id);
      if(!row||row.token!==token||row.finished_at!==null)return {meta:{changes:0}};
      Object.assign(row,{score,correct_count,elapsed_seconds,finished_at});
      return {meta:{changes:1}};
    }
    throw new Error('Unmocked run '+sql);
   },
   async first(){
    if(sql.includes('WHERE id=? AND token=?')){
      const r=db.items.get(bound[0]);return r?.token===bound[1]?{...r}:null;
    }
    if(sql.includes('WHERE id=? AND finished_at IS NOT NULL')){
      const r=db.items.get(bound[0]);return r&&r.finished_at!==null?{...r}:null;
    }
    if(sql.startsWith('SELECT COUNT(*)'))return {total:[...db.items.values()].filter(r=>r.finished_at!==null).length};
    throw new Error('Unmocked first '+sql);
   },
   async all(){
    const rows=[...db.items.values()];
    if(sql.includes('ROW_NUMBER() OVER(PARTITION BY nickname')){
      const best=new Map();
      for(const r of rows.filter(x=>x.finished_at!==null)){
        const old=best.get(r.nickname);
        if(!old||r.score>old.score||(r.score===old.score&&r.elapsed_seconds<old.elapsed_seconds))best.set(r.nickname,r);
      }
      return {results:[...best.values()].sort((a,b)=>b.score-a.score||a.elapsed_seconds-b.elapsed_seconds).map(r=>({...r})).slice(0,50)};
    }
    if(sql.includes('WHERE finished_at IS NULL'))return {results:rows.filter(r=>r.finished_at===null&&r.started_at>bound[0]).map(r=>({...r})).slice(-35).reverse()};
    throw new Error('Unmocked all '+sql);
   }
  };
 }
}
const endpoint=async (db,path,method='GET',body)=>{
 const req=new Request('https://test.workers.dev'+path,{method,headers:method==='GET'?undefined:{'content-type':'application/json'},body:method==='GET'?undefined:JSON.stringify(body)});
 const resp=await worker.fetch(req,{DB:db});return {status:resp.status,body:await resp.json()};
};

test('题库包含120道不重复题和新增5条制度',()=>{
 assert.equal(questions.length,120);
 assert.equal(new Set(questions.map(x=>x.id)).size,120);
 for(const term of ['合作共赢','48小时','7天','多开账号','家庭成员'])assert(questions.some(x=>x.question.includes(term)));
});
test('抽题100道无重复、每张试卷正确选项A-D各25个',()=>{
 const found=new Set();
 for(let j=0;j<80;j++){
  const plan=createPlan();assert.equal(plan.length,TOTAL_PER_EXAM);
  assert.equal(new Set(plan.map(x=>x.id)).size,100);
  const results=gradePlan(plan,plan.map(p=>p.order.indexOf(questions.find(q=>q.id===p.id).answer)));
  assert.equal(results.score,100);assert.equal(results.count,100);
  const counts=[0,0,0,0];for(const r of results.detail)counts[r.correct]++;
  assert.deepEqual(counts,[25,25,25,25]);
  found.add(plan.map(x=>x.id).join(','));
 }
 assert(found.size>1,'不同场次应有不同选题');
});
test('云端注册、排名、交卷、证书、重复提交、错误成绩拦截',async()=>{
 const db=new MemoryD1();
 const health=await endpoint(db,'/api/health');assert.equal(health.body.questionPool,120);
 const st=await endpoint(db,'/api/start','POST',{nickname:'测试学员'});
 assert.equal(st.status,201);assert.equal(st.body.questions.length,100);
 assert(!JSON.stringify(st.body.questions).includes('"answer"'));
 assert(st.body.questions.every(q=>q.options.length===4));
 let rank=await endpoint(db,'/api/leaderboard');
 assert(rank.body.active.some(x=>x.nickname==='测试学员'));
 const dbPlan=JSON.parse(db.items.get(st.body.id).question_plan);
 const ans=dbPlan.map(p=>p.order.indexOf(questions.find(q=>q.id===p.id).answer));
 const done=await endpoint(db,'/api/submit','POST',{id:st.body.id,token:st.body.token,answers:ans});
 assert.equal(done.status,200);assert.equal(done.body.certificate.score,100);
 assert.equal(done.body.review.length,100);
 assert.equal(done.body.certificate.id,st.body.id);
 const cert=await endpoint(db,`/api/certificate/${st.body.id}`);assert.equal(cert.body.certificate.score,100);
 rank=await endpoint(db,'/api/leaderboard');assert.equal(rank.body.leaderboard[0].score,100);assert.equal(rank.body.completed,1);
 const duplicate=await endpoint(db,'/api/submit','POST',{id:st.body.id,token:st.body.token,answers:ans});assert.equal(duplicate.status,409);
 const forged=await endpoint(db,'/api/submit','POST',{id:st.body.id,token:'bad-token',answers:ans});assert.equal(forged.status,403);
});
test('昵称校验和未答完拒绝提交',async()=>{
 const db=new MemoryD1();
 const err=await endpoint(db,'/api/start','POST',{nickname:'a'});assert.equal(err.status,400);
 const st=await endpoint(db,'/api/start','POST',{nickname:'清风08'});assert.equal(st.status,201);
 const bad=await endpoint(db,'/api/submit','POST',{id:st.body.id,token:st.body.token,answers:[0,1,2]});assert.equal(bad.status,400);
});