import io
import zipfile
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text
from sqlalchemy.pool import StaticPool
from academy import register_academy,source_priority,brand_display,_decode

def make_zip(records):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in records.items():
            if isinstance(content,str):content=content.encode('utf-8')
            z.writestr(name,content)
    return out.getvalue()

def make_app():
    engine=create_engine('sqlite://',poolclass=StaticPool,
                         connect_args={'check_same_thread':False})
    app=FastAPI()
    def require(req,role='viewer',mutation=False):
        current=req.headers.get('x-test-role','viewer')
        if role=='admin' and current!='admin':raise HTTPException(403)
        return {'role':current,'username':'test-admin'}
    register_academy(app,engine,require,lambda:'2026-11-08T10:00:00Z')
    with TestClient(app) as client:
        yield client,engine

def test_original_preservation_scoped_priorities_and_no_auto_approval():
    for c,engine in make_app():
        orig='顺达原文：鸿轩历史收益 15%，香港资质XYZ；金额12345。'
        data=make_zip({
            '01_核心_群洗/讲稿.txt':orig,
            '02_核心_磐石9-10/9月课程.txt':'团队沟通与客户信任。',
            '10_辅助课程/6月课程.txt':'团队沟通的其他参考。',
        })
        resp=c.post('/api/academy/upload',files={'file':('courses.zip',data,'application/zip')},
                    data={'scope':'auto'},headers={'x-test-role':'admin'})
        assert resp.status_code==200,resp.text
        assert resp.json()['created']==3
        assert c.get('/api/academy/documents').json()['rows']==[]
        docs=c.get('/api/academy/documents',headers={'x-test-role':'admin'}).json()['rows']
        assert len(docs)==3
        orig_doc=next(x for x in docs if x['title']=='讲稿')
        assert orig_doc['priority']==100 and orig_doc['status']=='draft'
        detailed=c.get('/api/academy/documents/'+orig_doc['id'],headers={'x-test-role':'admin'}).json()
        assert detailed['original_text']==orig
        assert '磐石' in detailed['display_text']
        assert '君主娱乐场' in detailed['display_text']
        assert '15%' in detailed['display_text']
        assert 'XYZ' in detailed['display_text']
        assert '12345' in detailed['display_text']
        assert c.post('/api/academy/documents/'+orig_doc['id']+'/approve').status_code==403
        assert c.post('/api/academy/documents/'+orig_doc['id']+'/approve',
            headers={'x-test-role':'admin'}).status_code==200
        assert len(c.get('/api/academy/documents').json()['rows'])==1
        assert c.get('/api/academy/documents/'+orig_doc['id']).json()['original_text']==orig
        result=c.post('/api/academy/ask',json={'question':'历史收益','tone':'领导讲话'})
        assert result.status_code==200,result.text
        assert result.json()['mode']=='retrieval_only'
        assert result.json()['sources'][0]['source'].startswith('01_核心_群洗')
        again=c.post('/api/academy/upload',
            files={'file':('courses.zip',data,'application/zip')},
            data={'scope':'auto'},headers={'x-test-role':'admin'})
        assert again.json()['created']==0
        assert again.json()['skipped']==3

def test_core_ranks_ahead_of_supplement_on_matching_search():
    for c,engine in make_app():
        payload=make_zip({'01_核心_群洗/核心.txt':'沟通真实需求和成员成长。',
                          '10_辅助课程/参考.txt':'沟通沟通沟通沟通沟通沟通。'})
        assert c.post('/api/academy/upload',
              files={'file':('test.zip',payload,'application/zip')},
              headers={'x-test-role':'admin'}).status_code==200
        docs=c.get('/api/academy/documents',headers={'x-test-role':'admin'}).json()['rows']
        for d in docs:
            c.post('/api/academy/documents/'+d['id']+'/approve',headers={'x-test-role':'admin'})
        res=c.post('/api/academy/ask',json={'question':'沟通'})
        assert res.json()['sources'][0]['source'].startswith('01_核心_群洗')

def test_unknown_files_and_rar_archive_rejected():
    for c,_ in make_app():
        bad=c.post('/api/academy/upload',
             files={'file':('wrong.rar',b'not zip','application/octet-stream')},
             headers={'x-test-role':'admin'})
        assert bad.status_code==400
        assert c.post('/api/academy/upload',
              files={'file':('test.zip',make_zip({'doc.jpg':b'x'}),'application/zip')},
              headers={'x-test-role':'admin'}).status_code==400

def test_preservation_utilities():
    assert source_priority('01_核心_群洗/a.txt')==100
    assert source_priority('02_核心_磐石9-10/b.txt')==100
    assert source_priority('10_辅助课程/a.txt')==20
    s='顺达有鸿轩，一颗流星划过，资质号码999和收益1.5%。'
    t=brand_display(s)
    assert '磐石' in t and '君主娱乐场' in t
    assert '流星划过' in t
    assert '999' in t and '1.5%' in t
    assert _decode('中文'.encode('gbk'))=='中文'


def test_exact_source_bytes_with_nul_and_batch_approval():
    raw=b'\xe4\xbd\xa0\xe5\xa5\xbd\x00\x00\x00 15% XYZ \x00'
    for c,_ in make_app():
        archive=make_zip({'01_核心_群洗/raw.txt':raw})
        response=c.post('/api/academy/upload',
             files={'file':('raw.zip',archive,'application/zip')},
             headers={'x-test-role':'admin'})
        assert response.status_code==200,response.text
        docs=c.get('/api/academy/documents',
              headers={'x-test-role':'admin'}).json()['rows']
        docid=docs[0]['id']
        assert c.get('/api/academy/documents/'+docid+'/download',
              headers={'x-test-role':'admin'}).content==raw
        assert c.get('/api/academy/documents/'+docid+'/download').status_code==404
        assert c.post('/api/academy/approve-batch',
              json={'scope':'core','acknowledge':True}).status_code==403
        assert c.post('/api/academy/approve-batch',
              json={'scope':'core','acknowledge':False},
              headers={'x-test-role':'admin'}).status_code==400
        approved=c.post('/api/academy/approve-batch',
              json={'scope':'core','acknowledge':True},
              headers={'x-test-role':'admin'})
        assert approved.status_code==200,approved.text
        assert approved.json()['approved']==1
        assert c.get('/api/academy/documents/'+docid+'/download').content==raw
