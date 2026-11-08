"""V39 course speech uses secure TTS endpoint without saving audio to members."""
import base64,json,os
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import academy
from urllib import error as http_error
import io

class FakeResponse:
    def __init__(self, data=b'ID3\x04\x00\x00FakeMP3Frames'):
        self.data=data
    def __enter__(self):return self
    def __exit__(self,*x):return False
    def read(self,maxlen):return self.data

def app_context():
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    app=FastAPI()
    def require(req,role='viewer',mutation=False):
        if not req.headers.get('x-auth'):
            raise HTTPException(401,'login required')
        if mutation and not req.headers.get('x-test-csrf'):
            raise HTTPException(403,'csrf required')
        return {'role':'viewer','username':'member'}
    academy.register_academy(app,engine,require,lambda:'2026-11-08T00:00:00Z')
    return TestClient(app)

def test_voice_generation_requires_login_csrf_and_uses_fixed_style(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','fake-secret-never-expose')
    monkeypatch.setenv('OPENAI_SPEECH_MODEL','gpt-4o-mini-tts')
    calls=[]
    def urlopen(req,timeout):
        calls.append({'url':req.full_url,'json':json.loads(req.data.decode('utf8')),
                      'headers':dict(req.header_items()),'timeout':timeout})
        return FakeResponse()
    monkeypatch.setattr(academy.http_request,'urlopen',urlopen)
    payload={'script':'大家好，今天来和大家讲解团队学习、沟通与信任的重要性。',
             'voice':'cedar','style':'lecturer','speed':1.0}
    with app_context() as c:
        assert c.post('/api/academy/speech',json=payload).status_code==401
        assert c.post('/api/academy/speech',json=payload,headers={'x-auth':'ok'}).status_code==403
        good=c.post('/api/academy/speech',json=payload,
                    headers={'x-auth':'ok','x-test-csrf':'valid'})
        assert good.status_code==200,good.text
        response=good.json()
        assert response['ok'] and response['format']=='mp3'
        assert base64.b64decode(response['audio_b64']).startswith(b'ID3')
        assert calls[0]['url']=='https://api.openai.com/v1/audio/speech'
        assert calls[0]['json']['voice']=='cedar'
        assert '标准的中文普通话' in calls[0]['json']['instructions']
        assert calls[0]['json']['response_format']=='mp3'
        assert calls[0]['json']['model']=='gpt-4o-mini-tts'
        assert calls[0]['json']['input']==payload['script']
        assert 'fake-secret' not in good.text
        assert c.post('/api/academy/speech',json={**payload,'voice':'malicious'},
                headers={'x-auth':'ok','x-test-csrf':'valid'}).status_code==400

def test_voice_rate_limit_prevents_uncontrolled_cost(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','fake')
    monkeypatch.setattr(academy.http_request,'urlopen',lambda *a,**k:FakeResponse())
    payload={'script':'今天我们共同学习培训课程中的真诚沟通和团队合作。'}
    with app_context() as c:
        for n in range(3):
            r=c.post('/api/academy/speech',json=payload,
              headers={'x-auth':'ok','x-test-csrf':'valid'})
            assert r.status_code==200,(n,r.text)
        denied=c.post('/api/academy/speech',json=payload,
           headers={'x-auth':'ok','x-test-csrf':'valid'})
        assert denied.status_code==429,denied.text

def test_missing_key_and_reject_oversize(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with app_context() as c:
        base={'script':'今天一起学习团队沟通和成长的主要内容。'}
        headers={'x-auth':'ok','x-test-csrf':'valid'}
        assert c.post('/api/academy/speech',json=base,headers=headers).status_code==503
        oversize='知识库课程' * 410
        assert len(oversize)>1600
        assert c.post('/api/academy/speech',json={'script':oversize},headers=headers).status_code==422

def test_provider_error_is_safely_reported_without_secret(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','fake-nonpublic-secret')
    def issue(request,timeout):
        raise http_error.HTTPError(request.full_url,401,'Auth denied',{},
             io.BytesIO(b'{"error":{"code":"invalid_api_key","message":"fake-nonpublic-secret"}}'))
    monkeypatch.setattr(academy.http_request,'urlopen',issue)
    with app_context() as c:
        r=c.post('/api/academy/speech',json={'script':'今天我们学习新人沟通与团队凝聚力。'},
           headers={'x-auth':'ok','x-test-csrf':'valid'})
        assert r.status_code==503
        assert '密钥' in r.text
        assert 'fake-nonpublic-secret' not in r.text
