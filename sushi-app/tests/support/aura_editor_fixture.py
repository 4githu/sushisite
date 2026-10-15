"""Synthetic Aura records for manual browser QA; never mounted by production."""
from fastapi import APIRouter
router=APIRouter(prefix='/api/personal/aura')
reports={i:{'id':i,'targetId':i,'studentName':'학생가' if i==1 else '학생나','schoolId':1,'schoolName':'검증고','progressStage':'accepted','roundNumber':1,'roundNumbers':[1],'roundLabel':'1회차','templateVersion':1,'status':'draft','sourceNotes':'','questionChecks':{},'lectureProgress':5,'lectureComprehension':5,'memoryBefore':4,'memoryAfter':5,'assessmentJson':None,'generatedReportJson':None,'aiModel':None,'clinicTargets':[{'id':1,'studentName':'학생가','status':'draft'},{'id':2,'studentName':'학생나','status':'draft'}],'contentJson':{'version':1,'documentId':'same-template','createdAt':'2026-09-25T00:00:00Z','updatedAt':'2026-09-25T00:00:00Z','blocks':[{'id':'shared-question','type':'paragraph','children':[{'type':'text','text':'공통 질문'}]}]}} for i in (1,2)}
@router.get('/targets/{i}/report')
def get(i:int):return reports[i]
@router.patch('/target-reports/{i}')
def save(i:int,body:dict):
    reports[i].update(contentJson=body['content_json'],questionChecks=body.get('question_checks',{}));return reports[i]
@router.get('/targets/{i}/attachments')
def attachments(i:int):return []
@router.get('/targets/{i}/ai-reports')
def ai(i:int):return {'results':[]}
@router.get('/ai/models')
def models():return {'models':[],'defaultModel':''}
