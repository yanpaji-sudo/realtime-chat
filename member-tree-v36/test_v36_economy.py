import json
import academy
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

class FakeResp:
    def __init__(self, body):
        self.body=body
    def __enter__(self):return self
    def __exit__(self,*args):return None
    def read(self,n):return self.body

def test_gpt6_luna_uses_compatible_low_cost_api_params(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','fake-only-for-mocked-tests')
    monkeypatch.setenv('OPENAI_MODEL','gpt-6-luna')
    calls=[]
    def fake(req,timeout):
        body=json.loads(req.data)
        calls.append(body)
        return FakeResp(json.dumps({'choices':[{'message':{'content':'你好，可以帮助你编排新人课程。'}}]}).encode())
    monkeypatch.setattr(academy.http_request,'urlopen',fake)
    engine=create_engine('sqlite://',poolclass=StaticPool,
                         connect_args={'check_same_thread':False})
    app=FastAPI()
    def require(req,role='viewer',mutation=False):
        if role=='admin':raise HTTPException(403)
        return {'role':'viewer','username':'tester'}
    academy.register_academy(app,engine,require,lambda:'2026-11-08T00:00:00Z')
    with TestClient(app) as c:
        r=c.post('/api/academy/ask',json={'question':'在吗'})
        assert r.status_code==200,r.text
        assert r.json()['mode']=='ai'
        assert calls[0]['model']=='gpt-6-luna'
        assert calls[0]['reasoning_effort']=='none'
        assert calls[0]['max_completion_tokens']==900
        assert 'temperature' not in calls[0]
        assert 'max_tokens' not in calls[0]
        assert 'messages' in calls[0]
    assert len(calls)==1

def test_legacy_model_is_still_compatible(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','fake')
    monkeypatch.setenv('OPENAI_MODEL','gpt-4.1-mini')
    requested=[]
    def fake(req,timeout):
        requested.append(json.loads(req.data))
        return FakeResp(b'{"choices":[{"message":{"content":"OK"}}]}')
    monkeypatch.setattr(academy.http_request,'urlopen',fake)
    engine=create_engine('sqlite://',poolclass=StaticPool,
                         connect_args={'check_same_thread':False})
    app=FastAPI()
    academy.register_academy(app,engine,lambda req,role='viewer',mutation=False:{'role':'viewer','username':'tester'},lambda:'2026-11-08T00:00:00Z')
    with TestClient(app) as c:
        assert c.post('/api/academy/ask',json={'question':'在吗'}).json()['mode']=='ai'
    assert requested[0]['model']=='gpt-4.1-mini'
    assert requested[0]['temperature']==0.4
    assert requested[0]['max_tokens']==900
    assert 'reasoning_effort' not in requested[0]
