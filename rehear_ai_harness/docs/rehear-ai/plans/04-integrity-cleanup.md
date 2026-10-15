# Report Integrity and Tooling Implementation Plan

> **For agentic workers:** 구현 시 superpowers:executing-plans를 사용할 수 있으면 task 단위로 수행한다.

**Goal:** 기존 서비스 누락/복구·캐시 문제를 보완하고 측정 도구를 삭제 가능한 CLI로 이전한다.
**Architecture:** 서비스 내부 validation/persistence 보완. reusable case/result와 제품 코드를 분리하고 CLI만 실험 orchestration 담당.
**Tech Stack:** 현재 Python/FastAPI/Pydantic·기존 DB 트랜잭션 패턴·pytest.
**Spec:** `../SPEC.md`, `../CONTRACTS.md`.

## Global Constraints

웹10 계약 유지; 연구16 점수의 임의 공개 변환 금지; 제품 core/catalog/observability/test 삭제 금지; 시간 측정 폴더는 이전 검증 후 삭제; 서비스→tools import 금지.

## Review Focus

모든 gaze 누락·부분 coverage·null 발음에 허위 코칭·DB 저장 실패 후 재시도·recovery QA 순서 누락 — Task 1/2에 검사. benchmark history 유실은 Task 3.

### Task 1: 보고서 의미와 캐시

**Files:** Modify 활성 `sushi-fast/odi/EVC/report_v2/{report_aggregation,report_generation,report_service}.py`; Test `sushi-fast/odi/EVC/tests/test_report_integrity.py`.
**Interfaces:** 기존 public report schema 유지. cache identity에 provider/model/adapter/prompt/Rubric/Policy/추론 설정과 payload fingerprint. 연구 engine cache와 서비스 ready cache를 분리.

- [ ] `test_all_missing_gaze_is_null_not_fifty`: 실시간 중립0.0+missing_inputs는 그대로, report gaze.score=null·미측정 사유.
- [ ] `test_partial_gaze_coverage_is_explicit`: 일부만 유효하면 유효 구간 집계/보류 정책을 하나로 정하고 coverage와 이유를 내부 기록. 누락을50으로 채우지 않음.
- [ ] `test_unmeasured_pronunciation_reason_not_overwritten`: null 발음에 측정한 듯한 coaching 거부; 기존 미측정 사유 유지.
- [ ] `test_report_cache_isolated_between_providers`: 같은 model/payload의 fake A/B에서 B도 실제1회 호출하고 B결과 반환. 기존 ready/request 재시도는 그대로.
- [ ] `test_invalid_reference_rejected_and_failure_visible`: 존재하지 않는 ID 거부·정해진 fallback/오류만 사용. 코드 인용 유효성 검사가 의미적 사실 검증을 대체한다고 하지 않음.
- [ ] 실패 확인 후 최소 보완, 기존 report_generation/report_followup 검사 실행.

### Task 2: QA 지속 저장과 commit 실패

**Files:** Modify `pipeline.py`, `answer_service.py`, report recovery와 관련 `odi/db` 저장 경계/필요한 migration; 같은 새 테스트.
**Interfaces:** 기존 external IDs/token/state/error 의미 유지. QA 질문/답변/source steps/audience 연결을 backend에서 지속 저장·복원. DB schema 변경이 필요하면 기존 migration 방식에 맞춘다.

- [ ] `test_recovery_restores_qa_and_order`: 저장 후 메모리 세션 없이 복구해 동일 QA순서/질문ID/답변/청중 연결 확인. 자료 없으면 I4 평가 불가.
- [ ] `test_qa_retry_is_idempotent`: 같은 답변 요청으로 저장·적응 질문 생성이 중복되지 않음. 다른 세션 자료 접근 거부.
- [ ] `test_db_failure_does_not_advance_step_without_committed_response`: 구간 저장 실패를 주입하고 메모리 step/state/cache가 불일치하지 않음; 같은 request_id 재시도로 중복 반영 없음.
- [ ] 실패 확인 후 현재 repository/transaction 패턴에 맞춰 구현. 메모리 rollback뿐 아니라 지속 저장과 cache의 일관성을 검사한다.
- [ ] 기존 Q&A/security/report 검사와 stage integrity 검사 실행.

### Task 3: CLI/Makefile·측정 이전·삭제

**Files:** Extend `sushi-fast/tools/rehear_cli/`, `Makefile.ai`; 새 synthetic fixtures `sushi-fast/odi/EVC/tests/fixtures/`; 과거 case/result는 사용자 데이터 포함 여부 점검 후 내부 archive 위치로 이전. 두 임시 benchmark 폴더 삭제는 마지막.
**Interfaces:** `make -f Makefile.ai ai-doctor|ai-contracts|ai-eval|ai-compare|ai-repeat|ai-replay|ai-bench`. fake 기본값, 실모델/API/마이크는 명시 선택. 기존 Makefile 있으면 덮어쓰지 않음.

- [ ] doctor/contract/replay는 offline. compare는 같은 연구16 Task, repeat는 cache off 실제 호출 횟수 기록. bench는 cold load/warm inference/총 처리시간 구분.
- [ ] 공통 결과에 run_id/input hash/task/engine/model/adapter/Rubric/Policy/prompt/실제 호출·retry·cache hit/실패/elapsed 포함. 음성/전사 원문을 일반 로그에 넣지 않음.
- [ ] `test_migrated_case_and_measurement_inventory`: 기존 두 폴더 case·유용 결과·측정 정의의 inventory/hash와 새 위치를 비교. 개인 음성/비밀키가 있으면 public fixture로 복사하지 않음.
- [ ] `test_cli_delete_does_not_break_product`: CLI 없이 core/backend import 및 기존 제품 테스트 통과. 제품 코드가 옛 benchmark 폴더나 새 tools를 import하지 않음.
- [ ] 이전 CLI 검증 뒤에만 두 폴더 삭제. `rg`로 잔여 참조 검사. import 검사만으로 파일/README 경로 참조까지 없다고 하지 않음.
- [ ] `python3 tools/rehear_harness.py test --suite all`과 `guard`, 실제 가능 환경의 웹/XR 회귀 상태를 기록. 미보유 GPU·Unity·전문가 참조는 미검증으로 남긴다.
