"""V34 additive internal Academy: immutable lesson records, verified provenance and optional AI tutor.

No access to member money, member tables or user credentials.  Existing session
middleware enforces viewer/admin permissions.  Original lesson text is never
silently rewritten and uploaded archives are not automatically published.
"""
import hashlib
import base64
import io
import json
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib import request as http_request, error as http_error
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text

MAX_ARCHIVE=12*1024*1024
MAX_UNPACKED=30*1024*1024
MAX_FILE=450000
MAX_FILES=2500
ALLOWED={'.txt','.md','.text'}
BRAND_MAP=[
    ('流星鸿轩','君主娱乐场'),('鸿轩','君主娱乐场'),
    ('百乐宫','君主娱乐场'),('顺达','磐石'),
]
def brand_display(original):
    """Creates a derived reading copy; does not modify original source text."""
    for a,b in BRAND_MAP: original=original.replace(a,b)
    return original

def source_priority(source):
    p=str(source).replace('\\','/')
    return 100 if p.startswith(('01_核心_群洗/','02_核心_磐石9-10/')) else 20

def _decode(data):
    for enc in ('utf-8-sig','gb18030','utf-16'):
        try:
            out=data.decode(enc)
            if len(out.strip())>0:return out
        except (UnicodeError,LookupError):pass
    raise ValueError('文本编码无法解析，请转换为UTF-8再上传')

def _excerpt(text0,query,limit=520):
    text0=str(text0)
    terms=re.findall(r'[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{3,}',query)[:6]
    where=0
    for term in terms:
        pos=text0.casefold().find(term.casefold())
        if pos>=0:
            where=max(0,pos-70);break
    return ('…' if where else '')+text0[where:where+limit]+('…' if len(text0)>where+limit else '')

class AskIn(BaseModel):
    question: str = Field(min_length=2,max_length=1500)
    tone: str = Field(default='亲切自然',max_length=40)

def register_academy(app,engine,require,utc_now):
    router=APIRouter(prefix='/api/academy')
    def create_tables():
        with engine.begin() as db:
            db.execute(text("""CREATE TABLE IF NOT EXISTS academy_documents(
                id TEXT PRIMARY KEY, title TEXT NOT NULL,source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 20,
                status TEXT NOT NULL DEFAULT 'draft', original_text TEXT NOT NULL,
                display_text TEXT NOT NULL,raw_bytes_b64 TEXT NOT NULL,created_at TEXT NOT NULL,
                reviewed_at TEXT,reviewer TEXT,
                UNIQUE(source_path,source_sha256))"""))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_academy_docs_status ON academy_documents(status,priority)"))
            db.execute(text("""CREATE TABLE IF NOT EXISTS academy_skill_drafts(
                id TEXT PRIMARY KEY,title TEXT NOT NULL,content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',created_at TEXT NOT NULL,
                approved_at TEXT,operator TEXT)"""))
    app.on_event('startup')(create_tables)

    @router.get('/stats')
    def stats(req:Request):
        user=require(req)
        with engine.connect() as db:
            where='' if user['role']=='admin' else " WHERE status='approved'"
            row=db.execute(text("SELECT count(*) AS total,COALESCE(SUM(CASE WHEN priority>=100 THEN 1 ELSE 0 END),0) AS core FROM academy_documents"+where)).mappings().first()
            drafts=int(db.execute(text("SELECT count(*) FROM academy_documents WHERE status='draft'")).scalar() or 0) if user['role']=='admin' else None
        return {'total':int(row['total']), 'core':int(row['core']), 'drafts':drafts,
                'connected':bool(os.environ.get('OPENAI_API_KEY')),'core_rule':'群洗＋磐石9—10优先，其他为辅助；原文不修改'}

    @router.get('/documents')
    def list_docs(req:Request,q:str='',limit:int=50,scope:str='all'):
        user=require(req)
        q=q.strip()[:120];limit=min(100,max(1,limit))
        filters=[]
        params={'limit':limit}
        if user['role']!='admin':filters.append("status='approved'")
        if scope=='core':filters.append("priority>=100")
        elif scope=='supplement':filters.append("priority<100")
        if q:
            filters.append("(LOWER(title) LIKE :q OR LOWER(display_text) LIKE :q OR LOWER(source_path) LIKE :q)")
            params['q']='%'+q.casefold()+'%'
        where=' WHERE '+' AND '.join(filters) if filters else ''
        sql="""SELECT id,title,source_path,source_sha256,priority,status,
                       length(original_text) AS chars,created_at,reviewed_at
                 FROM academy_documents"""+where+" ORDER BY priority DESC,created_at DESC LIMIT :limit"
        with engine.connect() as db:
            rows=[dict(x) for x in db.execute(text(sql),params).mappings()]
        return {'rows':rows}

    @router.get('/documents/{doc_id}')
    def get_doc(doc_id:str,req:Request):
        user=require(req)
        with engine.connect() as db:
            row=db.execute(text("""SELECT id,title,source_path,source_sha256,priority,
                         status,original_text,display_text,created_at
                         FROM academy_documents WHERE id=:id"""),{'id':doc_id}).mappings().first()
        if not row or (user['role']!='admin' and row['status']!='approved'):
            raise HTTPException(404,'课程不存在或未发布')
        return dict(row)

    @router.get('/documents/{doc_id}/download')
    def download_original(doc_id:str,req:Request):
        user=require(req)
        with engine.connect() as db:
            row=db.execute(text("SELECT status,raw_bytes_b64 FROM academy_documents WHERE id=:id"),
                           {'id':doc_id}).mappings().first()
        if not row or (user['role']!='admin' and row['status']!='approved'):
            raise HTTPException(404,'课程不存在或未发布')
        # Original bytes, including unusual source encoding and embedded NULs,
        # remain exactly the same as in the user-supplied ZIP.
        data=base64.b64decode(row['raw_bytes_b64'],validate=True)
        return Response(content=data,media_type='application/octet-stream',
                        headers={'Content-Disposition':'attachment; filename="course-original.txt"'})

    @router.post('/documents/{doc_id}/approve')
    def approve(doc_id:str,req:Request):
        user=require(req,'admin',True)
        with engine.begin() as db:
            r=db.execute(text("""UPDATE academy_documents SET status='approved',
                  reviewed_at=:at,reviewer=:by WHERE id=:id"""),
                  {'at':utc_now(),'by':user.get('username',''),'id':doc_id})
            if r.rowcount==0:raise HTTPException(404,'课程不存在')
        return {'ok':True}

    class ReviewBatchIn(BaseModel):
        scope: str = Field(default='core',max_length=20)
        acknowledge: bool = False

    @router.post('/approve-batch')
    def approve_batch(req:Request,body:ReviewBatchIn):
        user=require(req,'admin',True)
        if not body.acknowledge:
            raise HTTPException(400,'请先确认课程内容和个人信息已经人工审核')
        if body.scope not in ('core','supplement','all'):
            raise HTTPException(400,'审核范围不正确')
        where={'core':" AND priority>=100",
               'supplement':" AND priority<100",'all':''}[body.scope]
        with engine.begin() as db:
            result=db.execute(text("""UPDATE academy_documents
                SET status='approved',reviewed_at=:at,reviewer=:by
                WHERE status='draft'"""+where),
                {'at':utc_now(),'by':user.get('username','')})
        return {'approved':max(0,result.rowcount),'scope':body.scope}

    @router.post('/upload')
    async def upload(req:Request,file:UploadFile=File(...),scope:str=Form('auto')):
        user=require(req,'admin',True)
        data=await file.read(MAX_ARCHIVE+1)
        if len(data)>MAX_ARCHIVE:raise HTTPException(413,'课程ZIP超过12MB，请分包上传')
        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise HTTPException(400,'请上传ZIP课程包；RAR可先转换为ZIP')
        entries=[];total=0
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos=z.infolist()
                if len(infos)>MAX_FILES:raise HTTPException(400,'单包最多2500个条目')
                for f in infos:
                    if f.is_dir():continue
                    name=f.filename.replace('\\','/')
                    if f.flag_bits&0x1:raise HTTPException(400,'不支持带密码的ZIP')
                    if PurePosixPath(name).suffix.lower() not in ALLOWED:continue
                    if f.file_size>MAX_FILE:raise HTTPException(400,'单篇课程超过450KB：'+name[:100])
                    total+=f.file_size
                    if total>MAX_UNPACKED:raise HTTPException(400,'解压总量超出30MB')
                    raw=z.read(f)
                    if not raw.strip():continue
                    original=_decode(raw)
                    priority=(100 if scope=='core' else 20) if scope in ('core','supplement') else source_priority(name)
                    entries.append({
                       'id':hashlib.sha256((name+'\0'+hashlib.sha256(raw).hexdigest()).encode()).hexdigest()[:40],
                       'title':PurePosixPath(name).stem[:220],
                       'source':name[:800],
                       'sha':hashlib.sha256(raw).hexdigest(),
                       'priority':priority,'original':original.replace('\x00','␀'),'display':brand_display(original.replace('\x00','␀')),'raw_b64':base64.b64encode(raw).decode('ascii')
                    })
        except zipfile.BadZipFile as exc:
            raise HTTPException(400,'课程ZIP损坏') from exc
        if not entries:raise HTTPException(400,'ZIP内没有可识别的TXT或MD课程')
        with engine.begin() as db:
            before=int(db.execute(text('SELECT count(*) FROM academy_documents')).scalar() or 0)
            statement=text("""INSERT INTO academy_documents
                  (id,title,source_path,source_sha256,priority,status,
                   original_text,display_text,raw_bytes_b64,created_at)
                  VALUES (:id,:title,:source,:sha,:priority,'draft',
                          :original,:display,:raw_b64,:now)
                  ON CONFLICT(source_path,source_sha256) DO NOTHING""")
            # Bulk executemany avoids 1171 database round-trips on the free server.
            db.execute(statement,[{**e,'now':utc_now()} for e in entries])
            after=int(db.execute(text('SELECT count(*) FROM academy_documents')).scalar() or 0)
        created=max(0,after-before)
        return {'ok':True,'created':created,'skipped':len(entries)-created,
                'total_files':len(entries),'review_required':True,
                'message':'原文未改动；默认待审核，管理员可逐篇批准发布'}

    def retrieve(question,limit=7):
        # Natural Chinese questions require short overlapping search terms.
        raw_terms=re.findall(r'[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{3,}',question)[:18]
        tokens=set()
        for raw in raw_terms:
            if len(raw)<=7:tokens.add(raw)
            if re.search(r'[\u4e00-\u9fff]',raw):
                for n in (2,3):
                    for i in range(min(60,max(0,len(raw)-n+1))):
                        tokens.add(raw[i:i+n])
            else:tokens.add(raw)
        terms=[t for t in sorted(tokens,key=lambda x:(-len(x),x)) if t not in
            {'如何','怎么','什么','请问','可以','帮我','一下','大家','我们','你们'}][:90]
        with engine.connect() as db:
            rows=[dict(x) for x in db.execute(text("""
                SELECT id,title,source_path,priority,display_text,
                       original_text FROM academy_documents
                WHERE status='approved' ORDER BY priority DESC,id LIMIT 2200""")).mappings()]
        ranked=[]
        for r in rows:
            content=r['display_text']
            score=sum((3 if t.casefold() in r['title'].casefold() else 0)+
                      min(9,content.casefold().count(t.casefold())) for t in terms)
            if score>0:ranked.append((score,r))
        ranked.sort(key=lambda sr:(-sr[1]['priority'],-sr[0],sr[1]['title']))
        result=[]
        for _,r in ranked[:limit]:
            result.append({'id':r['id'],'title':r['title'],'source':r['source_path'],
                           'priority':r['priority'],'excerpt':_excerpt(r['display_text'],question,780)})
        return result

    @router.post('/ask')
    def ask(req:Request,payload:AskIn):
        require(req)
        sources=retrieve(payload.question)
        if not sources:
            return {'mode':'no_sources','answer':'知识库中暂未检索到已审核的相关课程。请管理员导入并批准对应资料。','sources':[]}
        key=os.environ.get('OPENAI_API_KEY','').strip()
        if not key:
            return {'mode':'retrieval_only','answer':'目前未连接AI模型，以下为知识库原文的可检索节选。可点开课程查看完整原文；这不是AI自动生成的话术。','sources':sources}
        evidence='\n\n'.join('['+str(i+1)+'] '+s['title']+'｜来源 '+s['source']+'\n'+s['excerpt'] for i,s in enumerate(sources))
        prompt=("你是企业内部课程检索与写作助手。严格参照提供的课程原文和表达风格。"
           "不得修改引文中的任何收益数值、资质描述或原始事实；不编造材料没有的内容。"
           "允许改编表达结构但所有事实要归属来源。未经独立验证的收益、资质与平台合法性必须用"
           "「课程原文称」或「根据内部资料」形式归属，不能当作已核实结论或向客户作收益保证。"
           "遇到具体金钱投资、博彩操作、反诈规避等要求，不生成误导或保证回报的招募宣传。"
           "请先简洁解释，再给与用户语气匹配的示例话术，最后列使用的课程编号。")
        body={'model':os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),
            'messages':[{'role':'system','content':prompt},
                        {'role':'user','content':'风格：'+payload.tone+'\n问题：'+payload.question+'\n\n课程参考：\n'+evidence}],
            'temperature':0.4,'max_tokens':900}
        endpoint=os.environ.get('OPENAI_CHAT_URL','https://api.openai.com/v1/chat/completions')
        if not endpoint.startswith('https://'):raise HTTPException(503,'AI地址配置无效')
        r=http_request.Request(endpoint,data=json.dumps(body,ensure_ascii=False).encode('utf-8'),
          headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},
          method='POST')
        try:
            with http_request.urlopen(r,timeout=24) as result:
                response=json.loads(result.read(250000).decode('utf-8'))
            answer=response['choices'][0]['message']['content']
            if not isinstance(answer,str) or not answer.strip():raise ValueError('empty AI response')
            return {'mode':'ai','answer':answer,'sources':sources}
        except (http_error.HTTPError,http_error.URLError,ValueError,KeyError,TimeoutError) as exc:
            return {'mode':'retrieval_only','answer':'模型服务暂不可用，已返回已审核课程节选。','sources':sources}

    app.include_router(router)
