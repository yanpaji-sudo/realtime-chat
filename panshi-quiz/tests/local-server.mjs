import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import worker from '../src/worker.js';
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

const dir=path.resolve('public');
const db=new MemoryD1();
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'};
const assets={async fetch(req){const url=new URL(req.url);const file=path.resolve(dir,url.pathname==='/'?'index.html':url.pathname.replace(/^\//,''));if(!file.startsWith(dir))return new Response('Forbidden',{status:403});try{return new Response(await fs.readFile(file),{headers:{'content-type':mime[path.extname(file)]||'application/octet-stream'}});}catch{return new Response('Not found',{status:404});}}};
const port=Number(process.env.PORT||8765);
http.createServer(async(req,res)=>{try{const chunks=[];for await(const b of req)chunks.push(b);const request=new Request(`http://localhost:${port}${req.url}`,{method:req.method,headers:req.headers,body:['GET','HEAD'].includes(req.method)?undefined:Buffer.concat(chunks)});const response=await worker.fetch(request,{DB:db,ASSETS:assets});res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));}catch(e){console.error(e);res.writeHead(500);res.end('error');}}).listen(port,'127.0.0.1',()=>console.log('http://127.0.0.1:'+port));