"""V38: strictly source-grounded Panshi Academy tutor.

Only modifies member-tree/academy.py and adds a truthful UI status strip.
Read-only toward all existing lessons, member hierarchy, finance and backups.
"""
from pathlib import Path
p=Path("member-tree/academy.py")
s=p.read_text(encoding="utf-8")

a=s.index("    def retrieve(question,limit=7):")
b=s.index("    def model_diagnostic(",a)
strict_retrieval=r'''    # V38: course-first relevance retrieval. Never make broad, unrelated
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
                    '磐石','林总','时候','自己','这些','那些','什么','怎么',
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
        ranked.sort(key=lambda x:(-x[0],-x[1],-x[2],x[3]['title']))
        selected=ranked[:limit]
        # Guarantee the leading cited sources are relevant core lessons when
        # they exist; the input corpus is otherwise never promoted blindly.
        result=[]
        for _,score,priority,r in selected:
            result.append({'id':r['id'],'title':r['title'],'source':r['source_path'],
                           'priority':priority,'excerpt':_course_excerpt(r['display_text'],terms),
                           'match_strength':round(score,2)})
        return result

'''
s=s[:a]+strict_retrieval+s[b:]
old="""        sources=retrieve(search_text)
        key=os.environ.get('OPENAI_API_KEY','').strip()
        is_greeting="""
new="""        sources=retrieve(search_text)
        key=os.environ.get('OPENAI_API_KEY','').strip()
        is_greeting="""
assert s.count(old)==1,'ask core anchor missing'
# Ensure greeting is evaluated before withholding unsourced model answers.
greet_end="""                                       payload.question.strip()))
        if not key:"""
if s.count(greet_end)!=1:raise RuntimeError('greeting end anchor missing')
s=s.replace(greet_end,"""                                       payload.question.strip()))
        # Source-lock: do not call a generative model for substantive topics
        # when there is no matching approved course to ground it.
        if not sources and not is_greeting:
            return {'mode':'no_sources',
                    'answer':'你问的主题暂时没有检索到匹配的已审核课程。为严格按照你提供的培训资料，我不会自行引入别的平台观点或编造话术。请换一个课程中的具体主题，或请管理员补充并审核相关课程。',
                    'sources':[],'grounding':'strict'}
        if not key:""",1)
# Replace system instruction with tightly scoped source-derived writing.
a=s.index('        prompt=("你是磐石AI学院的对话式话术导师。')
b=s.index('        messages=[{',a)
new_prompt=r'''        prompt=("你是【磐石AI学院·课程专属话术导师】，当前启用【严格课程模式】。"
                "【唯一知识来源】是本轮消息末尾附带的“已审核课程原文节选”，"
                "核心优先级为《群洗》和《磐石9—10》；其他课只能补充，"
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
'''
s=s[:a]+new_prompt+s[b:]
# V36 kept only four x450 characters, losing the key structure. Use up to
# five full 700-char source excerpts to improve fidelity; still bounded cost.
old_e="""        # 4 matching references x ~450 characters rather than 7 x ~780.
        # The full referenced lessons remain available unchanged in the UI.
        evidence='\\n\\n'.join('['+str(i+1)+'] '+x['title']+'｜来源 '+x['source']+'\\n'+x['excerpt'][:450]
                             for i,x in enumerate(sources[:4]))"""
new_e="""        # Real teaching content needs more context than the first 450 chars.
        # Use up to 5 focused verbatim windows (700 chars each), not summaries.
        evidence='\\n\\n'.join('['+str(i+1)+'] '+x['title']+'｜来源 '+x['source']+
                             '｜属性 '+('核心' if x['priority']>=100 else '辅助')+
                             '\\n'+x['excerpt'][:700] for i,x in enumerate(sources[:5]))"""
assert s.count(old_e)==1,'V36 evidence anchor missing'
s=s.replace(old_e,new_e,1)
p.write_text(s,encoding='utf-8')

# Add visible strict-mode indicator without changing any other navigation.
js=Path("member-tree/static/app.js")
front=js.read_text(encoding='utf-8')
marker="tutor.append(mk('p','academy-muted','优先按照已审核的核心课程指导表达，返回引用来源；课程原文的数字与资质说法不会擅自改写。'));"
# V35 has custom chat heading; target the live V35 banner rather than old V34.
marker="heading.append(mk('p','academy-muted','优先参考已审核的《群洗》和磐石9—10课程。每次回答可展开查看来源。'));"
replacement="heading.append(mk('p','academy-muted','严格课程模式：先检索已审核核心课程，再按照课程思路回答；无课程依据时不借用外部观点。每次回答可展开查看来源。'));"
assert front.count(marker)==1,'V35 banner anchor missing'
front=front.replace(marker,replacement,1)
js.write_text(front,encoding='utf-8')
print('V38: improved subject relevance, strict source-lock, on-topic speechstyle and visible AI course mode')
