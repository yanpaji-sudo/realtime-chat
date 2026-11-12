"""V38 mandatory-course-grounding acceptance tests."""
import io,zipfile,json
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import academy

def make_app():
    engine=create_engine('sqlite://',poolclass=StaticPool,
          connect_args={'check_same_thread':False})
    app=FastAPI()
    def require(req,role='viewer',mutation=False):
        is_admin=req.headers.get('x-test-role')=='admin'
        if role=='admin' and not is_admin:raise HTTPException(403)
        return {'role':'admin' if is_admin else 'viewer','username':'test'}
    academy.register_academy(app,engine,require,lambda:'2026-11-08T00:00:00Z')
    return TestClient(app)

def upload(c,lessons):
    memory=io.BytesIO()
    with zipfile.ZipFile(memory,'w') as z:
        for name,body in lessons.items():z.writestr(name,body)
    res=c.post('/api/academy/upload',files={'file':('lessons.zip',memory.getvalue(),'application/zip')},
         headers={'x-test-role':'admin'})
    assert res.status_code==200,res.text
    approved=c.post('/api/academy/approve-batch',
        json={'scope':'all','acknowledge':True},headers={'x-test-role':'admin'})
    assert approved.status_code==200,approved.text

def test_only_material_from_approved_course_used(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','mock-do-not-send')
    seen=[]
    class R:
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def read(self,n):
            return '{"choices":[{"message":{"content":"团队领导要多教新人，互相帮助。[1]"}}]}'.encode('utf-8')
    def fake(request,timeout):
        seen.append(json.loads(request.data))
        return R()
    monkeypatch.setattr(academy.http_request,'urlopen',fake)
    with make_app() as c:
        upload(c,{
            '01_核心_群洗/带领新成员.txt':
              '团队学习要有耐心，帮助新成员认识团队。新人不懂多教一句，伙伴有问题多讲一遍，互帮互助，增强团队凝聚力。',
            '02_核心_流星9-10/9月团队精气神.txt':
              '团队领导要带着伙伴学习和成长，主动沟通和及时帮助。',
            '10_辅助课程/无关选品.txt':
              '洗衣凝珠如何洗衣，产品质量，物流速度，价格。',
        })
        resp=c.post('/api/academy/ask',json={'question':'请讲讲团队领导如何培养新成员、增强团队凝聚力？'})
        assert resp.status_code==200,resp.text
        data=resp.json()
        assert data['mode']=='ai'
        assert data['sources']
        assert data['sources'][0]['priority']==100
        assert '团队' in data['sources'][0]['excerpt'] or '新成员' in data['sources'][0]['excerpt']
        system=seen[-1]['messages'][0]['content']
        assert '严格课程模式' in system
        assert '不得将话题自行转向别的平台' in system
        assert '内部课程原文' not in repr(resp.headers)
        evidence=seen[-1]['messages'][-1]['content']
        assert '团队' in evidence
        assert '来源 ' in evidence or '来源' in evidence

def test_no_course_means_no_general_ai_on_unrelated_subject(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','mock')
    triggered=[]
    def fake(request,timeout):
        triggered.append(True)
        raise AssertionError('Do not generate unsourced answers!')
    monkeypatch.setattr(academy.http_request,'urlopen',fake)
    with make_app() as c:
        upload(c,{'01_核心_群洗/团队管理.txt':'关于团队关怀、培养新成员与学习。'})
        ret=c.post('/api/academy/ask',json={'question':'请讲解航天卫星的钛合金涡轮叶片结构'})
        assert ret.status_code==200,ret.text
        obj=ret.json()
        assert obj['mode']=='no_sources'
        assert '不会自行引入别的平台观点' in obj['answer']
        assert obj['sources']==[]
        assert not triggered
        # A greeting can be answered without making up course facts only when
        # the model key is absent.
        monkeypatch.delenv('OPENAI_API_KEY',raising=False)
        resp=c.post('/api/academy/ask',json={'question':'在吗'})
        assert resp.json()['mode']=='offline'
        assert not triggered

def test_course_text_never_rewritten(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    text='原文称：2026年进行讲解，团队是靠诚信建立，项目收益不能假装保证。'
    with make_app() as c:
        upload(c,{'02_核心_流星9-10/诚信.txt':text})
        docs=c.get('/api/academy/documents').json()['rows']
        assert len(docs)==1
        doc=c.get('/api/academy/documents/'+docs[0]['id']).json()
        assert doc['original_text']==text
        assert doc['priority']==100
