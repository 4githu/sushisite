#!/usr/bin/env python3
"""Live product fallback check: synthetic report, own room only, isolated DB."""
import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
proof=ROOT/'sushi-fast/.runtime/kakao-live-checks/fallback-20261111-01.json'
proof.parent.mkdir(parents=True,exist_ok=True)
if proof.exists():
    print(proof.read_text());raise SystemExit(0)
with proof.open('x') as f:json.dump({'state':'started'},f)
sys.path.insert(0,str(ROOT/'sushi-fast'))
with tempfile.TemporaryDirectory(prefix='kakao-fallback-check-') as tmp:
    os.environ['PERSONAL_PROJECT_DB_PATH']=str(Path(tmp)/'test.sqlite')
    os.environ['PERSONAL_RESOURCE_ROOT']=str(Path(tmp)/'resources')
    os.environ['DISABLE_KAKAO_BRIDGE']='1'
    os.environ['DISABLE_TREND_REFRESH']='1'
    from personal_project import native_kakao, kakao_bridge
    real=kakao_bridge.invoke;calls=[]
    def invoke(command,**args):
        if command=='send' and (args.get('room')!='본계정' or args.get('files')):
            raise RuntimeError('This live fixture permits text to own room only')
        result=real(command,**args)
        calls.append({'command':command,'own_room':args.get('room')=='본계정','searchEvidence':result.get('searchEvidence'),'sent':result.get('sent'),'verifiedBy':result.get('verifiedBy'),'cleanup':result.get('cleanup')})
        return result
    kakao_bridge.invoke=invoke
    report={'schoolName':'가상학교_점검20261111','studentName':'가상학생','roundLabel':'실제 학생과 무관한 전송 점검',
            'generatedReportJson':{'learningContent':{'paragraphs':['합성 리포트 본계정 텍스트 대체 전달 검증입니다. 답장은 필요 없습니다.']}}}
    try:
        job=native_kakao.create_clinic_job(999999,0,report)
        result=native_kakao.send_clinic_job(job['jobId'],999999,0)
        record={'state':'succeeded' if result.get('sent') else 'failed','result':result,'calls':calls}
    except Exception as error:
        record={'state':'failed','error_type':type(error).__name__,'calls':calls}
    proof.write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print(json.dumps(record,ensure_ascii=False))
    raise SystemExit(0 if record['state']=='succeeded' else 2)
