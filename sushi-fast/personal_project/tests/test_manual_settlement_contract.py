"""Latest user decision: no calculation except explicit monthly generation."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import db,repository as repo
from personal_project.router import router,current_user_id
USER=84023
@pytest.fixture
def client(tmp_path,monkeypatch):
 monkeypatch.setattr(db,'DB_PATH',tmp_path/'manual.sqlite');db.init_db()
 app=FastAPI();app.include_router(router);app.dependency_overrides[current_user_id]=lambda:USER
 return TestClient(app)

def create(client):
 sid=client.post('/api/personal/aura/schools',json={'admission_year':2026,'school_name':'합성'}).json()['id']
 r=client.post('/api/personal/aura/rounds',json={'school_id':sid,'progress_stage':'grade1_semester1_midterm','round_number':1,'student_names':['가'],'start_time':'2026-11-22T10:30:00+09:00','end_time':'2026-11-22T11:30:00+09:00'})
 assert r.status_code==201,r.text
 return r.json()

def test_create_edit_read_and_student_changes_never_calculate(client,monkeypatch):
 def forbidden(*a,**k):raise AssertionError('Only explicit calculate can call pricing')
 with monkeypatch.context() as m:
  m.setattr(repo,'clinic_settlement_amount',forbidden);m.setattr(repo,'clinic_hourly_cost',forbidden)
  r=create(client);assert r['amount']==0
  url=f"/api/personal/aura/rounds/{r['id']}"
  assert client.patch(url,json={'end_time':'2026-11-22T12:30:00+09:00'}).status_code==200
  added=client.post(url+'/targets',json={'student_name':'나'});assert added.status_code==201,added.text
  assert client.delete(f"/api/personal/aura/targets/{added.json()['id']}?confirm=true").status_code==204
  assert client.get(url).json()['amount']==0
  assert client.get('/api/personal/aura/settlements?year=2026&month=11').json()['generatedAt'] is None
 # Explicit calculation is a single request and can be repeated without a 409.
 path='/api/personal/aura/settlements/generate?year=2026&month=11'
 for _ in range(2):
  calculated=client.post(path);assert calculated.status_code==200,calculated.text
  assert calculated.json()['totalAmount']==60000
 assert client.get(url).json()['amount']==60000
 assert client.patch(url,json={'end_time':'2026-11-22T13:30:00+09:00'}).status_code==200
 assert client.get(url).json()['amount']==60000
 assert client.get('/api/personal/aura/settlements?year=2026&month=11').json()['totalAmount']==60000
 assert client.post(path).json()['totalAmount']==90000


def test_thirteen_hour_input_reports_actual_am_pm_and_does_not_save(client):
 r=create(client);url=f"/api/personal/aura/rounds/{r['id']}"
 response=client.patch(url,json={'end_time':'2026-11-22T23:30:00+09:00'})
 assert response.status_code==400,response.text
 detail=response.json()['detail'];assert detail['code']=='clinic_duration_exceeded'
 assert '13시간' in detail['message'] and '오전 10:30' in detail['message'] and '오후 11:30' in detail['message']
 assert client.get(url).json()['endTime']==r['endTime']
 assert client.patch(url,json={'end_time':'2026-11-22T22:30:00+09:00'}).status_code==200


def test_manual_calculation_uses_current_composition_and_preserves_paid_acknowledgement(client):
 r=create(client);url=f"/api/personal/aura/rounds/{r['id']}";path='/api/personal/aura/settlements/generate?year=2026&month=11'
 assert client.post(path).json()['totalAmount']==30000
 with db.connection() as c:c.execute("UPDATE aura_clinic_rounds SET payment_status='paid' WHERE id=?",(r['id'],));c.commit()
 added=client.post(url+'/targets',json={'student_name':'나'});assert added.status_code==201
 assert client.patch(url,json={'end_time':'2026-11-22T12:30:00+09:00'}).status_code==200
 assert client.get(url).json()['amount']==30000
 calculated=client.post(path);assert calculated.status_code==200 and calculated.json()['totalAmount']==60000
 saved=client.get(url).json();assert saved['amount']==60000 and saved['paymentStatus']=='paid'
