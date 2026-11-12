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
    ('百乐宫','君主娱乐场'),('顺达','流星'),
]
def brand_display(original):
    """Creates a derived reading copy; does not modify original source text."""
    for a,b in BRAND_MAP: original=original.replace(a,b)
    return original

def source_priority(source):
    p=str(source).replace('\\','/')
    return 100 if p.startswith(('01_核心_群洗/','02_核心_流星9-10/')) else 20

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
    question: str = Field(min_length=1,max_length=1500)
    tone: str = Field(default='亲切自然',max_length=40)
    # Browser-local dialogue only; no member database storage or shared viewer history.
    history: list = Field(default_factory=list)

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
                'connected':bool(os.environ.get('OPENAI_API_KEY')),'core_rule':'群洗＋流星9—10优先，其他为辅助；原文不修改'}

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

    # V38: course-first relevance retrieval. Never make broad, unrelated
    # corpus matches based on filler such as "帮我" "大家" or "如何".
    _filler_words=('请帮我','按照','根据','结合','请你','麻烦','告诉我',
                   '我应该','我想','一下','一段','一篇','写一份','帮我','生成',
                   '老师','你好','如何','怎样','什么','为什么','今天',
                   '这是','他们','我们','你们','让我','相关','内容',
                   '进行','一个','这种','可以','这个','要求','必须',
                   '多少字','几百字','字左右','不少于')
    _format_words={'话术','文案','讲稿','讲话','演讲','开头','结尾','口播',
                   '文章','一段','课件','帮我','学习内容','写作','写篇',
                   '帮忙','精华','资料','知识库'}
    _generic_terms={'在吗','你好','您好','是不是','我觉得','别人','有人','公司',
                    '流星','林总','时候','自己','这些','那些','什么','怎么',
                    '怎么做','介绍','知识','学习','事情','工作','大家','我们',
                    '个人','方式','方法','成为','今天','课程','内容','老师',
                    '给我','想要','觉得','现在','希望','需要','我在','什么是'}
    _focus_map={
        '新人':['新成员','新人','新伙伴','新人培训','培养新人','带新人'],
        '团队':['团队','战队','团长','上下级','团队建设','凝聚力','团建'],
        '沟通':['沟通','聊天','交流','客户','介绍','分享','讲解','话术'],
        '质疑':['质疑','不信任','顾虑','担心','怀疑','顾客疑虑'],
        '学习':['学习','培训','课堂','课程','教育','培养','成长'],
        '信任':['信任','诚信','口碑','认可','信心','责任'],
        '执行':['行动力','执行力','落实','做事','勤奋','积极'],
        '产品':['产品','商品','甄选','质量','品质','选品','供应链'],
        '售后':['退款','售后','退货','退单','购物','消费'],
        '公益':['公益','慈善','老人','责任','志愿','爱心'],
        '流量':['流量','引流','流量转化','私域','变现'],
        '分润':['分润','抽点','提现','收入','现金流'],
        '成团':['成团','一带五','师傅','徒弟','直推','团队奖励'],
        '仓位':['仓位','建仓','仓','余额','风控'],
        '博弈':['博弈','共赢','零和','负和','正和'],
    }
    def _course_terms(question):
        # Preserve actual subject words rather than searching all of a short
        # sentence; ordinary Chinese questions don't have spaces between words.
        value=re.sub(r'\d{1,5}\s*字|[0-9A-Za-z]*\d+[A-Za-z]*',' ',question or '')
        for word in sorted(_filler_words,key=len,reverse=True):
            value=value.replace(word,' ')
        words=[]
        for fragment in re.findall(r'[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}',value):
            if fragment in _format_words or fragment in _generic_terms:continue
            if 2<=len(fragment)<=8:words.append((fragment,4.0 if len(fragment)>=4 else 2.0))
            if len(fragment)>2:
                for n in (4,3,2):
                    for i in range(len(fragment)-n+1):
                        token=fragment[i:i+n]
                        if token not in _generic_terms and token not in _format_words:
                            words.append((token,{4:2.3,3:1.3,2:0.38}[n]))
        for base,synonyms in _focus_map.items():
            if any(word in question for word in synonyms):
                words.append((base,6.0))
                # Light synonym expansion to bridge training-vs-user wording.
                # Do not use all synonyms as independent exact evidence.
                for word in synonyms[:6]:
                    words.append((word,1.7))
        # Exact repeated concepts retain only max weight; avoid large stopword
        # combinations that previously caused arbitrary core course matches.
        unique={}
        for term,w in words:
            if term and term not in _generic_terms:
                unique[term]=max(unique.get(term,0),w)
        return list(sorted(unique.items(),key=lambda tw:(-tw[1],-len(tw[0]),tw[0])))[:70]

    def _course_excerpt(content,terms,max_chars=800):
        # Find the most relevant training paragraph rather than always the
        # first paragraph, which can be an unrelated date/announcement.
        content=str(content or '')
        if len(content)<=max_chars:return content
        text_low=content.casefold()
        best_pos=0
        best_score=0.
        # A scoring window yields on-topic material when long lessons contain
        # many separate subjects; it is not an AI-generated paraphrase.
        for pos in range(0,len(content),max(140,max_chars//3)):
            start=max(0,pos-50); window=text_low[start:start+max_chars]
            score=sum(min(4,window.count(t.casefold()))*w for t,w in terms)
            if score>best_score:best_score=score;best_pos=start
        excerpt=content[best_pos:best_pos+max_chars]
        return ('…' if best_pos else '')+excerpt+('…' if best_pos+max_chars<len(content) else '')

    def retrieve(question,limit=6):
        terms=_course_terms(str(question)[:500])
        if not terms:return []
        with engine.connect() as db:
            rows=[dict(x) for x in db.execute(text("""
                SELECT id,title,source_path,priority,display_text
                FROM academy_documents
                WHERE status='approved' ORDER BY priority DESC,id LIMIT 2200
            """)).mappings()]
        ranked=[]
        for r in rows:
            content=r['display_text'] or ''
            title=(r['title'] or '').casefold()
            text_l=content.casefold()
            # Relevance is the main factor; core has a strong but bounded
            # preference so it cannot crowd out an obviously topical lesson.
            score=0.
            matches=0
            for token,weight in terms:
                if token.casefold() in text_l or token.casefold() in title:
                    matches+=1
                    count=min(4,text_l.count(token.casefold()))
                    score+=weight*(0.6+min(3,count)*0.5)
                    if token.casefold() in title:score+=2.5*weight
            if matches<1 or score<2.2:continue
            priority=int(r['priority'] or 0)
            # Relevant core courses are preferred, but 3x topical relevance
            # can still beat a weakly matching core lesson.
            blended=score*(1.30 if priority>=100 else 1.0)
            ranked.append((blended,score,priority,r))
        # First eliminate documents with far weaker topical relevance.
        # Within that relevant set always prefer the author's core courses,
        # even when a supporting document repeats the same word more often.
        best=max((x[1] for x in ranked),default=0)
        cutoff=max(2.2,best*0.33)
        ranked=[x for x in ranked if x[1]>=cutoff]
        ranked.sort(key=lambda x:(-x[2],-x[1],x[3]['title']))
        selected=ranked[:limit]
        # Guarantee the leading cited sources are relevant core lessons when
        # they exist; the input corpus is otherwise never promoted blindly.
        result=[]
        for _,score,priority,r in selected:
            result.append({'id':r['id'],'title':r['title'],'source':r['source_path'],
                           'priority':priority,'excerpt':_course_excerpt(r['display_text'],terms),
                           'match_strength':round(score,2)})
        return result

    def model_diagnostic(http_status=None, code='', network=False):
        """Fixed safe messages: no secrets, provider response body or credentials."""
        code=str(code or '').lower()
        if network:
            return {'kind':'network','title':'AI 服务网络连接失败或请求超时','instruction':'稍后重试；若持续出现，检查 Render 出站网络与模型接口地址。'}
        if http_status==401:
            return {'kind':'invalid_key','title':'API 密钥未通过认证','instruction':'在 Render Environment 检查 OPENAI_API_KEY；更新后重新部署。'}
        if http_status==403:
            return {'kind':'permission','title':'AI 模型访问权限不足','instruction':'检查 API 项目权限以及模型可用性。'}
        if http_status==404 or code=='model_not_found':
            return {'kind':'model','title':'模型名称不存在或当前项目不可使用','instruction':'检查 OPENAI_MODEL 配置和项目可用模型。'}
        if http_status==429:
            if code in ('insufficient_quota','billing_hard_limit_reached','quota_exceeded'):
                return {'kind':'quota','title':'API 账户额度不足或未开通计费','instruction':'查看 OpenAI API 项目余额和 Billing 设置；ChatGPT 会员与 API 独立计费。'}
            return {'kind':'rate_limit','title':'API 请求频率达到限制','instruction':'减少连续请求，稍后再试；如持续出现，检查 API 项目额度限制。'}
        if http_status==400:
            return {'kind':'request','title':'AI 服务不接受当前模型请求参数','instruction':'检查模型名称和接口参数配置。'}
        return {'kind':'provider','title':'模型服务暂时不可用','instruction':'可使用下方课程节选；管理员可点击「检测AI连接」查看具体状态。'}

    def call_model(messages,max_tokens=900,timeout=24):
        key=os.environ.get('OPENAI_API_KEY','').strip()
        if not key:
            return None,{'kind':'no_key','title':'尚未配置模型 API 密钥',
                         'instruction':'管理员需在 Render Environment 设置 OPENAI_API_KEY。'}
        endpoint=os.environ.get('OPENAI_CHAT_URL','https://api.openai.com/v1/chat/completions')
        if not endpoint.startswith('https://'):
            return None,{'kind':'endpoint','title':'AI 接口地址不合法',
                         'instruction':'OPENAI_CHAT_URL 必须为 HTTPS 地址。'}
        model=os.environ.get('OPENAI_MODEL','gpt-6-luna').strip() or 'gpt-6-luna'
        body={'model':model,'messages':messages}
        if model.startswith(('gpt-6-', 'gpt-6.')):
            # GPT-6 Luna supports 'none'; prevents paid internal reasoning
            # tokens for routine knowledge-based conversational training.
            # GPT-6 Chat Completions prefers max_completion_tokens.
            body['reasoning_effort']='none'
            body['max_completion_tokens']=min(1200,max(32,int(max_tokens)))
        elif model.startswith(('gpt-5-', 'gpt-5.')):
            body['reasoning_effort']='minimal'
            body['max_completion_tokens']=min(1200,max(32,int(max_tokens)))
        else:
            # Preserve compatibility with existing GPT-4.1 mini installation.
            body['temperature']=0.4
            body['max_tokens']=min(1200,max(32,int(max_tokens)))
        req=http_request.Request(endpoint,data=json.dumps(body,ensure_ascii=False).encode('utf-8'),
                 headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        try:
            with http_request.urlopen(req,timeout=timeout) as result:
                data=json.loads(result.read(250000).decode('utf-8'))
            answer=data['choices'][0]['message']['content']
            if not isinstance(answer,str) or not answer.strip():
                return None,model_diagnostic()
            return answer.strip(),None
        except http_error.HTTPError as exc:
            # Only look at a machine-readable error code; never echo raw provider
            # error bodies into the browser or logs.
            error_code=''
            try:
                obj=json.loads(exc.read(3000).decode('utf-8','replace'))
                error_code=obj.get('error',{}).get('code','') if isinstance(obj,dict) else ''
            except (ValueError,TypeError,AttributeError):pass
            return None,model_diagnostic(exc.code,error_code)
        except (http_error.URLError,TimeoutError,ValueError,KeyError,TypeError):
            return None,model_diagnostic(network=True)

    @router.post('/diagnose')
    def diagnose(req:Request):
        # Restricted to an authenticated administrator and its CSRF token.
        require(req,'admin',True)
        out,issue=call_model([{'role':'user','content':'仅回复四个字：连接正常'}],
                            max_tokens=20,timeout=16)
        if issue:return {'ok':False,'diagnostic':issue}
        return {'ok':True,'diagnostic':{'kind':'connected','title':'AI 模型连接成功',
                                      'instruction':'现在可以连续聊天，按课程生成话术。'}}

    @router.post('/ask')
    def ask(req:Request,payload:AskIn):
        require(req)
        # Preserve only bounded, explicitly typed dialogue messages.
        cleaned=[]
        for m in payload.history[-16:]:
            if not isinstance(m,dict):continue
            if m.get('role') not in ('user','assistant'):continue
            content=m.get('content')
            if isinstance(content,str) and content.strip():
                cleaned.append({'role':m['role'],'content':content[:600]})
        # Follow-up questions may be short; recover the last user topic for search.
        search_text=payload.question
        if len(payload.question.strip())<18:
            prior=next((x['content'] for x in reversed(cleaned) if x['role']=='user'), '')
            if prior:search_text+=' '+prior[:160]
        sources=retrieve(search_text)
        key=os.environ.get('OPENAI_API_KEY','').strip()
        is_greeting=bool(re.fullmatch(r'(在吗|你好|您好|嗨|哈喽|早上好|下午好|晚上好|老师好|谢谢|感谢|你好呀|在不在)[！？!?。 ]*',
                                       payload.question.strip()))
        # Source-lock: do not call a generative model for substantive topics
        # when there is no matching approved course to ground it.
        if not sources and not is_greeting:
            return {'mode':'no_sources',
                    'answer':'你问的主题暂时没有检索到匹配的已审核课程。为严格按照你提供的培训资料，我不会自行引入别的平台观点或编造话术。请换一个课程中的具体主题，或请管理员补充并审核相关课程。',
                    'sources':[],'grounding':'strict'}
        if not key:
            if is_greeting:
                return {'mode':'offline','answer':'在的！你可以直接告诉我想学习的课程或需要编排的话术。当前AI模型尚未连接，课程检索仍可使用。',
                        'sources':sources,'diagnostic':{'kind':'no_key','title':'AI 密钥尚未配置'}}
            if sources:
                return {'mode':'retrieval_only','answer':'AI 模型尚未连接；已找到相关课程，请查看下方原文节选。',
                        'sources':sources,'diagnostic':{'kind':'no_key','title':'AI 密钥尚未配置'}}
            return {'mode':'no_sources','answer':'目前没有检索到匹配的已审核课程，且 AI 尚未连接。你可以让管理员补充课程。',
                    'sources':[],'diagnostic':{'kind':'no_key','title':'AI 密钥尚未配置'}}
        # Real teaching content needs more context than the first 450 chars.
        # Use up to 5 focused verbatim windows (700 chars each), not summaries.
        evidence='\n\n'.join('['+str(i+1)+'] '+x['title']+'｜来源 '+x['source']+
                             '｜属性 '+('核心' if x['priority']>=100 else '辅助')+
                             '\n'+x['excerpt'][:700] for i,x in enumerate(sources[:5]))
        prompt=("你是【流星AI学院·课程专属话术导师】，当前启用【严格课程模式】。"
                "【唯一知识来源】是本轮消息末尾附带的“已审核课程原文节选”，"
                "核心优先级为《群洗》和《流星9—10》；其他课只能补充，"
                "不能代替核心课程的思想、结构和表达。"
                "【绝对优先级】先回答用户本轮问的具体问题，只围绕该主题；"
                "不得将话题自行转向别的平台、其他行业、泛泛的励志建议、"
                "政策分析或无关的经营方向。"
                "【内容约束】必须从提供的节选概括要点；写讲稿时模仿课程"
                "原文中通俗、举例、提问、鼓励和总结的结构；"
                "保留课程原有术语、人物、数字和案例，不编造文中没有的数据、"
                "事实、政府认可、资质或承诺。"
                "涉及原课程中未经外部核验的企业资质、收益、保证时，"
                "只能使用“课程原文称”归属，不能改写成保证回报或客观认证。"
                "【表达约束】用户要求话术，直接给可用的话术；用户问概念，"
                "直接解释概念；用户问怎么做，按来源给操作步骤。"
                "尽量沿用课程措辞和讲课逻辑，不增设旁支话题，"
                "不要出现与用户问题无关的免责声明或泛泛延伸。"
                "【引用】只引用本轮给出的 [1][2]... 编号，"
                "不得杜撰引用课程，结尾标明主要参考课程编号与标题。"
                "【缺口】如果原文不足以支持某个细节，简短说“课程未提及”，"
                "不要用模型背景知识自行补齐。"
                "【连续对话】最近消息仅用于理解代词和用户偏好的风格，"
                "不将旧问题强行带入新话题；短问短答。"
                "如果只是问好，简单回应并询问要学习什么。")
        messages=[{'role':'system','content':prompt}]
        messages+=cleaned[-12:]
        messages.append({'role':'user','content':'表达方式：'+payload.tone+'\n问题：'+payload.question+
                         ('\n\n本轮核实的课程节选（编号仅对应本轮检索）：\n'+evidence
                          if evidence else '\n\n本轮没有匹配的已审核课程。')})
        answer,issue=call_model(messages)
        if issue:
            fallback=('模型暂时没有生成回答。'+issue['title']+'。'
                      +('下面保留了已审核课程节选供你查看。' if sources else '你仍可浏览知识库。'))
            return {'mode':'model_error','answer':fallback,'sources':sources,'diagnostic':issue}
        return {'mode':'ai','answer':answer,'sources':sources,'history_used':len(cleaned)}
    app.include_router(router)
