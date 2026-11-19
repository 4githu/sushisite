# Aura 합성 리포트 예약·발송 회귀 (2026-11-13)

## 실행
`sushi-fast` 디렉터리에서:

```sh
./.venv/bin/python -m pytest -q personal_project/tests/test_scheduled_synthetic_regression.py personal_project/tests/test_clinic_scheduled_delivery.py personal_project/tests/test_scheduled_delivery_acceptance_extra.py personal_project/tests/test_kakao_process_lock_acceptance.py personal_project/tests/test_kakao_preflight_serialization.py personal_project/tests/test_classroom_delivery.py personal_project/tests/test_settlement_delivery.py personal_project/tests/test_real_report_pdf_path_acceptance.py personal_project/tests/test_report_delivery_completion.py --disable-warnings --tb=short
```

실행 결과: 61 passed, 8 warnings. 실제 HTTP 라우터, 임시 SQLite, 실제 PDF 렌더러를 사용하고 AI 및 카카오 브리지는 합성 대역이다. 외부 메시지는 발송하지 않았다.

신규 회귀 파일 `tests/test_scheduled_synthetic_regression.py`는 AI 미생성 시 생성, 버튼 요청 시각 +90분, 실제 PDF의 한글·내부 키, 동일 대상 동시 예약, 조회·취소, 전송 중 미제출, 확정 결과에서만 제출, 불확실·실패 자동 재시도 금지와 생성/전송 중 재시작 복구를 검증한다. 나머지 파일은 여러 진입점의 잠금 사용, 프로세스 간 flock, PDF 및 제출 경계를 보완한다.

## 한계
프로세스 간 잠금 기본 동작과 일부 교실·정산·사전 점검 경로를 테스트했으나 모든 외부 도구·카카오 진입점이 같은 잠금을 사용하는지는 이 통과 결과만으로 증명되지 않는다. 재시작은 격리 DB의 중간 상태를 설정하고 recover를 호출한 테스트이며 OS 프로세스 강제 종료 실험이 아니다. AI 공급자 및 실제 카카오 앱/브리지, 운영 배포는 검증하지 않았다. 기존 발송 여부가 불확실한 건을 재발송하지 않았다.
