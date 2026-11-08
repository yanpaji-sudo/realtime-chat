import io,json,os
from urllib import error as http_error
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import academy
from academy import register_academy

def make_app():
    engine=create_engine('sqlite://',poolclass=StaticPool,
                         connect_args={'check_same_thread':False})
    app=FastAPI()
    def require(req,role='viewer',mutation=False):
        user=req.headers.get('x-test-role','viewer')
        if role=='admin' and user!='admin':raise HTTPException(403)
        return {'role':user,'username':'test'}
    register_academy(app,engine,require,lambda:'2026-11-08T12:00:00Z')
    return TestClient(app)

class FakeResp:
    def __init__(self,answer):self.content=json.dumps({'choices':[{'message':{'content':answer}}]}).encode('utf8')
    def __enter__(self):return self
    def __exit__(self,*a):return None
    def read(self,n):return self.content

def test_greetings_are_real_ai_conversation_without_sources(monkeypatch):
    calls=[]
    def respond(request,timeout):
        data=json.loads(request.data)
        calls.append(data)
        assert request.headers.get('Authorization','').startswith('Bearer ')
        assert timeout<=24
        return FakeResp('在的！你想学习哪方面的知识？')
    monkeypatch.setenv('OPENAI_API_KEY','not-a-real-secret')
    monkeypatch.setattr(academy.http_request,'urlopen',respond)
    with make_app() as client:
        response=client.post('/api/academy/ask',json={'question':'在吗'})
        assert response.status_code==200,response.text
        assert response.json()['mode']=='ai'
        assert '在的' in response.json()['answer']
        assert not response.json()['sources']
        chat=client.post('/api/academy/ask',json={
            'question':'那怎么继续？',
            'history':[{'role':'user','content':'我想了解团队学习'},
                       {'role':'assistant','content':'从团队学习习惯入手'}]})
        assert chat.json()['mode']=='ai'
        assert calls[-1]['messages'][-3]['content']=='我想了解团队学习'
        assert calls[-1]['messages'][-2]['content']=='从团队学习习惯入手'
        assert '那怎么继续' in calls[-1]['messages'][-1]['content']

def test_safe_diagnostics_quota_and_authentication(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','dummy-test-secret-must-not-leak')
    def fake_error(request,timeout):
        raise http_error.HTTPError(request.full_url,429,'Too Many Requests',
             {},io.BytesIO(b'{"error":{"code":"insufficient_quota","message":"dummy-test-secret-must-not-leak"}}'))
    monkeypatch.setattr(academy.http_request,'urlopen',fake_error)
    with make_app() as client:
        result=client.post('/api/academy/ask',json={'question':'请帮我介绍团队培训'}).json()
        assert result['mode']=='model_error'
        assert result['diagnostic']['kind']=='quota'
        assert 'dummy-test-secret' not in str(result)
        assert client.post('/api/academy/diagnose').status_code==403
        diagnosed=client.post('/api/academy/diagnose',headers={'x-test-role':'admin'}).json()
        assert diagnosed['ok'] is False and diagnosed['diagnostic']['kind']=='quota'
        assert 'dummy-test-secret' not in str(diagnosed)

def test_missing_key_greeting_and_history_limits(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with make_app() as client:
        res=client.post('/api/academy/ask',json={'question':'在吗'}).json()
        assert res['mode']=='offline'
        assert res['diagnostic']['kind']=='no_key'
        res=client.post('/api/academy/ask',json={'question':'如何学习团队管理'}).json()
        assert res['mode']=='no_sources'

def test_model_401_and_404_do_not_leak_response(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','dummy')
    for status,kind in [(401,'invalid_key'),(404,'model')]:
        def fake(request,timeout):
            raise http_error.HTTPError(request.full_url,status,'Error',{},io.BytesIO(b'sensitive-provider-body'))
        monkeypatch.setattr(academy.http_request,'urlopen',fake)
        with make_app() as client:
            res=client.post('/api/academy/ask',json={'question':'在吗'}).json()
            assert res['diagnostic']['kind']==kind
            assert 'sensitive-provider-body' not in str(res)
