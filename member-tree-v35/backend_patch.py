"""V35: additive conversational AI tutor and safe provider diagnostics.

This patch is applied to the unpacked V34 payload in isolated CI; it does not
create/change any member tables and does not contact production data.
"""
from pathlib import Path
p=Path('member-tree/academy.py')
s=p.read_text(encoding='utf-8')
def unique(old,new,label):
    global s
    if s.count(old)!=1:raise RuntimeError(label+': expected one anchor got '+str(s.count(old)))
    s=s.replace(old,new,1)

unique("""class AskIn(BaseModel):
    question: str = Field(min_length=2,max_length=1500)
    tone: str = Field(default='亲切自然',max_length=40)
""","""class AskIn(BaseModel):
    question: str = Field(min_length=1,max_length=1500)
    tone: str = Field(default='亲切自然',max_length=40)
    # Browser-local dialogue only; no member database storage or shared viewer history.
    history: list = Field(default_factory=list)
""",'chat model')

a=s.index("    @router.post('/ask')\n")
b=s.index("    app.include_router(router)",a)
patch=r'''    def model_diagnostic(http_status=None, code='', network=False):
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
        body={'model':os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),
              'messages':messages,'temperature':0.4,'max_tokens':max_tokens}
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
                cleaned.append({'role':m['role'],'content':content[:1500]})
        # Follow-up questions may be short; recover the last user topic for search.
        search_text=payload.question
        if len(payload.question.strip())<18:
            prior=next((x['content'] for x in reversed(cleaned) if x['role']=='user'), '')
            if prior:search_text+=' '+prior[:160]
        sources=retrieve(search_text)
        key=os.environ.get('OPENAI_API_KEY','').strip()
        is_greeting=bool(re.fullmatch(r'(在吗|你好|您好|嗨|哈喽|早上好|下午好|晚上好|老师好|谢谢|感谢|你好呀|在不在)[！？!?。 ]*',
                                       payload.question.strip()))
        if not key:
            if is_greeting:
                return {'mode':'offline','answer':'在的！你可以直接告诉我想学习的课程或需要编排的话术。当前AI模型尚未连接，课程检索仍可使用。',
                        'sources':sources,'diagnostic':{'kind':'no_key','title':'AI 密钥尚未配置'}}
            if sources:
                return {'mode':'retrieval_only','answer':'AI 模型尚未连接；已找到相关课程，请查看下方原文节选。',
                        'sources':sources,'diagnostic':{'kind':'no_key','title':'AI 密钥尚未配置'}}
            return {'mode':'no_sources','answer':'目前没有检索到匹配的已审核课程，且 AI 尚未连接。你可以让管理员补充课程。',
                    'sources':[],'diagnostic':{'kind':'no_key','title':'AI 密钥尚未配置'}}
        evidence='\n\n'.join('['+str(i+1)+'] '+x['title']+'｜来源 '+x['source']+'\n'+x['excerpt']
                             for i,x in enumerate(sources))
        prompt=("你是磐石AI学院的对话式话术导师。以《群洗》和磐石9—10月已审核核心课程的"
                "教育理念、讲课节奏、领导讲话、团队关怀、实事求是和沟通风格为第一优先级，"
                "辅助课程为其次。自然地连续聊天；短问短答，遇到新人困惑时耐心地给出"
                "方法和可实践的例句。不要每次都重新自我介绍。"
                "课程中的原始数字、日期、资质描述不应擅自改动；"
                "未独立核实的收益、资质、商业结果必须明确归属于“内部课程原文称”，"
                "不能假装已核实或保证未来收益；不得编造政府背书或资质。"
                "涉及招募、博彩投资、金钱收益时不得提供误导性承诺，尊重对方自主判断。"
                "引用知识库时请用提供的课程编号标明来源。"
                "如果未检索到课程，明确说明这是通用指导，不能冒称引自知识库。"
                "当用户只是打招呼，直接友好回应并询问需要学习什么。")
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
'''
s=s[:a]+patch+s[b:]
p.write_text(s,encoding='utf-8')
print('V35: Academy conversation model, last-12-turn context and safe diagnostic endpoint ready')
