import os,tempfile,io,zipfile,json
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH',str(Path(tempfile.mkdtemp())/'grading.sqlite'))
os.environ['DISABLE_KAKAO_BRIDGE']='1';os.environ['DISABLE_TREND_REFRESH']='1'
import fitz,pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import workspace_router as w,grading as g
app=FastAPI();app.include_router(w.router);app.dependency_overrides[w.current_user_id]=lambda:98761
client=TestClient(app);BASE='/api/personal/aura/grading'
def pdf():
 d=fitz.open();p=d.new_page(width=300,height=300);p.insert_text((10,280),'original vector text');return d.tobytes()
def setup():
 rid=client.post(BASE,json={'name':'Exam'}).json()['id']
 assert client.post(BASE+f'/rounds/{rid}/files',files={'file':('answer.pdf',pdf(),'application/pdf')}).status_code==200
 a=client.get(BASE+f'/rounds/{rid}').json()['files'][0]['id']
 assert client.post(BASE+f'/rounds/{rid}/files',files={'file':('student.pdf',pdf(),'application/pdf')}).status_code==200
 b=next(f['id'] for f in client.get(BASE+f'/rounds/{rid}').json()['files'] if f['id']!=a)
 config={'answer':a,'first':1,'last':1,'boxes':[{'page':0,'x':10,'y':10,'w':200,'h':200,'number':'1-1','points':5}]}
 r=client.put(BASE+f'/rounds/{rid}',json={'data':config,'revision':0});assert r.status_code==200,r.text
 return rid,a,b,config

def test_owner_revision_and_vector_export():
 rid,a,b,config=setup()
 def stroke(y):return {'width':2,'color':'#ff0000','kind':'pen','points':[{'x':20,'y':y},{'x':35,'y':y+5}]}
 data={'ink':{'0':[stroke(20),stroke(100)]}}
 assert client.put(BASE+f'/files/{b}',json={'data':data,'revision':0}).status_code==200
 assert client.put(BASE+f'/files/{b}',json={'data':data,'revision':0}).status_code==409
 result=client.get(BASE+f'/files/{b}/pdf');assert result.status_code==200
 doc=fitz.open(stream=result.content,filetype='pdf');assert 'original vector text' in doc[0].get_text()
 assert len(doc[0].get_drawings())==1 # comment ink kept; score-box ink excluded
 app.dependency_overrides[w.current_user_id]=lambda:98762
 try:assert client.get(BASE+f'/files/{b}/pdf').status_code==404
 finally:app.dependency_overrides[w.current_user_id]=lambda:98761

def test_rubric_not_client_points_controls_total():
 rid,a,b,config=setup();qs=[{'number':'1-1','points':500,'deduction':0,'comment':'test','reviewed':True}]
 client.put(BASE+f'/files/{b}',json={'data':{'questions':qs},'revision':0})
 assert client.get(BASE+f'/rounds/{rid}/results').json()[0]['total'] is None
 assert client.get(BASE+f'/rounds/{rid}/xlsx').status_code==409
 qs[0]['points']=5;qs[0]['deduction']=1
 assert client.put(BASE+f'/files/{b}',json={'data':{'questions':qs},'revision':1}).status_code==200
 assert client.get(BASE+f'/rounds/{rid}/results').json()[0]['total']==4
 assert zipfile.is_zipfile(io.BytesIO(client.get(BASE+f'/rounds/{rid}/xlsx').content))

def test_bad_boxes_and_unknown_ocr(monkeypatch):
 rid,a,b,config=setup();config['boxes'][0]['w']=-1
 assert client.put(BASE+f'/rounds/{rid}',json={'data':config,'revision':1}).status_code==400
 monkeypatch.setattr(g,'recognize',lambda *a:'unreadable')
 result=g.recognize_file(b,98761);assert result['questions'][0]['deduction'] is None and result['requiresReview']

def test_zip_names_cannot_escape_storage(tmp_path,monkeypatch):
 monkeypatch.setattr(g,'ROOT',tmp_path/'files');rid=client.post(BASE,json={'name':'ZIP'}).json()['id']
 archive=io.BytesIO()
 with zipfile.ZipFile(archive,'w') as z:z.writestr('../../escaped.pdf',pdf())
 result=client.post(BASE+f'/rounds/{rid}/files',files={'file':('batch.zip',archive.getvalue(),'application/zip')})
 assert result.status_code==200 and not (tmp_path/'escaped.pdf').exists()
 assert client.get(BASE+f'/rounds/{rid}').json()['files'][0]['name']=='escaped.pdf'
