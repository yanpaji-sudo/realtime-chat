import test from 'node:test';
import assert from 'node:assert/strict';
import worker, {createPlan,gradePlan,TOTAL_PER_EXAM} from '../src/worker.js';
import {questions} from '../data/questions.js';

class MemoryD1 {
 constructor(){this.items=new Map();this.challenges=new Map();}
 prepare(sql) {
  const db=this;let bound=[];
  return {
   bind(...values){bound=values;return this;},
   async run(){
    if(sql.startsWith('INSERT INTO attempts')){
     const [id,token,nickname,started_at,question_plan,is_pk,challenge_target_id,challenge_target_nickname,challenge_target_score]=bound;
     db.items.set(id,{id,token,nickname,started_at,question_plan,finished_at:null,score:null,correct_count:null,elapsed_seconds:null,is_pk:is_pk||0,pk_success:0,defeated_at:null,challenge_target_id:challenge_target_id??null,challenge_target_nickname:challenge_target_nickname??null,challenge_target_score:challenge_target_score??null});
     return {meta:{changes:1}};
    }
    if(sql.startsWith('UPDATE attempts SET score=')){
     const [score,correct_count,elapsed_seconds,finished_at,id,token]=bound;
     const row=db.items.get(id);
     if(!row||row.token!==token||row.finished_at!==null)return {meta:{changes:0}};
     Object.assign(row,{score,correct_count,elapsed_seconds,finished_at});return {meta:{changes:1}};
    }
    if(sql.startsWith('UPDATE attempts SET defeated_at=')){
     const [now,nickname,exclude]=bound;let count=0;
     for(const r of db.items.values())if(r.nickname===nickname&&r.finished_at!==null&&r.defeated_at===null&&r.id!==exclude){r.defeated_at=now;count++;}
     return {meta:{changes:count}};
    }
    if(sql.startsWith('UPDATE attempts SET pk_success=')){
     const r=db.items.get(bound[0]);if(!r)return {meta:{changes:0}};r.pk_success=1;return {meta:{changes:1}};
    }
    if(sql.startsWith('INSERT INTO pk_challenges')){
     const [id,target_id,target_nickname,challenger_nickname,success,finished_at]=bound;
     db.challenges.set(id,{id,target_id,target_nickname,challenger_nickname,success,finished_at});return {meta:{changes:1}};
    }
    throw new Error('Unexpected run: '+sql);
   },
   async first(){
    if(sql.includes('WHERE id=? AND token=?')){
     const r=db.items.get(bound[0]);return r?.token===bound[1]?{...r}:null;
    }
    if(sql.includes('WHERE id=? AND finished_at IS NOT NULL AND defeated_at IS NULL')){
     const r=db.items.get(bound[0]);return r&&r.finished_at!==null&&r.defeated_at===null&&(!r.is_pk||r.pk_success)?{...r}:null;
    }
    if(sql.includes('WHERE id=? AND finished_at IS NOT NULL')){
     const r=db.items.get(bound[0]);return r&&r.finished_at!==null?{...r}:null;
    }
    if(sql.startsWith('SELECT COUNT(*)'))return {total:[...db.items.values()].filter(x=>x.finished_at!==null).length};
    throw new Error('Unexpected first: '+sql);
   },
   async all(){
    const rows=[...db.items.values()];
    if(sql.includes('ROW_NUMBER() OVER(PARTITION BY nickname')){
     const best=new Map();
     for(const r of rows.filter(x=>x.finished_at!==null&&x.defeated_at===null&&(!x.is_pk||x.pk_success))){
      const old=best.get(r.nickname);
      if(!old||r.score>old.score||(r.score===old.score&&r.elapsed_seconds<old.elapsed_seconds))best.set(r.nickname,r);
     }
     return {results:[...best.values()].sort((a,b)=>b.score-a.score||a.elapsed_seconds-b.elapsed_seconds).slice(0,50).map(r=>({...r,challenged_count:[...db.challenges.values()].filter(x=>x.target_nickname===r.nickname).length}))};
    }
    if(sql.includes('WHERE finished_at IS NULL'))return {results:rows.filter(r=>r.finished_at===null&&r.started_at>bound[0]).slice(-35).reverse().map(r=>({...r}))};
    throw new Error('Unexpected all: '+sql);
   }
  };
 }
}
async function endpoint(db,path,method='GET',body){
 const req=new Request('https://test.workers.dev'+path,{method,headers:method==='GET'?undefined:{'content-type':'application/json'},body:method==='GET'?undefined:JSON.stringify(body)});
 const response=await worker.fetch(req,{DB:db});return {status:response.status,body:await response.json()};
}
const choicesFor=(row,correctCount=100)=>{
 const plan=JSON.parse(row.question_plan);
 return plan.map((p,i)=>{const q=questions.find(x=>x.id===p.id);const a=p.order.indexOf(q.answer);return i<correctCount?a:(a+1)%4;});
};
async function finish(db,start,correctCount=100){
 return endpoint(db,'/api/submit','POST',{id:start.id,token:start.token,answers:choicesFor(db.items.get(start.id),correctCount)});
}
test('108 candidate questions after removal, all five user-specified rules remain',()=>{
 assert.equal(questions.length,108);
 assert.equal(new Set(questions.map(q=>q.id)).size,108);
 for(const term of ['合作共赢','48小时','7天','多开账号','家庭成员'])assert(questions.some(q=>q.question.includes(term)));
 for(const id of ['q031','q032','q075','q076','q077','q116','q117','q119','q120'])assert(!questions.some(q=>q.id===id));
});
test('100 random unique questions with balanced A-D answer positions',()=>{
 const variants=new Set();
 for(let i=0;i<30;i++){
  const plan=createPlan();assert.equal(plan.length,TOTAL_PER_EXAM);assert.equal(new Set(plan.map(q=>q.id)).size,100);
  const answers=plan.map(p=>p.order.indexOf(questions.find(q=>q.id===p.id).answer));
  assert.equal(gradePlan(plan,answers).score,100);
  assert.deepEqual([0,1,2,3].map(k=>answers.filter(x=>x===k).length),[25,25,25,25]);
  variants.add(plan.map(x=>x.id).join(','));
 }
 assert(variants.size>1);
});
test('normal quiz, cloud leaderboard, certificate, double-submit prevention',async()=>{
 const db=new MemoryD1();const health=await endpoint(db,'/api/health');assert.equal(health.body.questionPool,108);
 const start=(await endpoint(db,'/api/start','POST',{nickname:'测试学员'})).body;
 assert.equal(start.questions.length,100);assert.equal(start.isPk,false);
 const done=await finish(db,start,100);assert.equal(done.status,200);assert.equal(done.body.certificate.score,100);
 assert.equal(done.body.certificate.pkSuccess,false);
 const board=await endpoint(db,'/api/leaderboard');assert.equal(board.body.leaderboard[0].score,100);
 const cert=await endpoint(db,'/api/certificate/'+start.id);assert.equal(cert.body.certificate.nickname,'测试学员');
 assert.equal((await finish(db,start)).status,409);
});
test('PK uses exact same paper, counts completed challenges, only strict high score displaces name',async()=>{
 const db=new MemoryD1();
 const original=(await endpoint(db,'/api/start','POST',{nickname:'榜上高手'})).body;
 assert.equal((await finish(db,original,80)).body.certificate.score,80);
 let board=(await endpoint(db,'/api/leaderboard')).body;
 assert.equal(board.leaderboard[0].challenged_count,0);
 const first=(await endpoint(db,'/api/start','POST',{nickname:'挑战失败者',targetId:original.id})).body;
 assert.equal(first.isPk,true);
 assert.equal(first.targetNickname,'榜上高手');
 assert.deepEqual(first.questions.map(q=>[q.id,...q.options]),original.questions.map(q=>[q.id,...q.options]));
 const fail=await finish(db,first,80);assert.equal(fail.body.pkSuccess,false);assert.equal(fail.body.certificate.pkSuccess,false);
 board=(await endpoint(db,'/api/leaderboard')).body;assert.equal(board.leaderboard[0].nickname,'榜上高手');
 assert.equal(board.leaderboard[0].challenged_count,1);
 assert(!board.leaderboard.some(r=>r.nickname==='挑战失败者'));
 const second=(await endpoint(db,'/api/start','POST',{nickname:'成功挑战者',targetId:original.id})).body;
 assert.deepEqual(second.questions.map(q=>q.options),original.questions.map(q=>q.options));
 const won=await finish(db,second,81);assert.equal(won.status,200);assert.equal(won.body.pkSuccess,true);
 assert.equal(won.body.certificate.pkSuccess,true);assert.equal(won.body.certificate.targetNickname,'榜上高手');
 assert.equal(won.body.certificate.nickname,'成功挑战者');
 assert.equal(won.body.certificate.targetScore,80);
 board=(await endpoint(db,'/api/leaderboard')).body;
 assert(board.leaderboard.some(r=>r.nickname==='成功挑战者'));
 assert(!board.leaderboard.some(r=>r.nickname==='榜上高手'));
 assert.equal((await endpoint(db,'/api/start','POST',{nickname:'第三人',targetId:original.id})).status,409);
 const certificate=(await endpoint(db,'/api/certificate/'+second.id)).body.certificate;
 assert.equal(certificate.targetNickname,'榜上高手');
});
test('input validation and incomplete exam rejection',async()=>{
 const db=new MemoryD1();assert.equal((await endpoint(db,'/api/start','POST',{nickname:'a'})).status,400);
 const s=(await endpoint(db,'/api/start','POST',{nickname:'学员08'})).body;
 assert.equal((await endpoint(db,'/api/submit','POST',{id:s.id,token:s.token,answers:[0,1,2]})).status,400);
});
