# Research Assessment Module Implementation Plan

> **For agentic workers:** 구현 시 superpowers:executing-plans를 사용할 수 있으면 task 단위로 수행한다.

**Goal:** 기존 전처리를 재사용하는 독립 16개 Rubric 채점 모듈과 CLI를 만든다.
**Architecture:** backend adapter → EvidencePack/RubricBundle → AssessmentEngine(fake/Qwen/선택적 OpenAI) → AssessmentResult. 기존 OpenAI10 report와 다른 경로.
**Tech Stack:** 기존 Python/Pydantic; 로컬 runner는 프로젝트 환경·모델에 맞춰 최소 하나 선택. 모델 라이브러리/버전은 실제 환경에서 확인·고정한다.
**Spec:** `../SPEC.md`, `../CONTRACTS.md`.

## Global Constraints

Qwen은16개 연구 Task; OpenAI10 설명 구현 불필요; 서비스 기본 provider 유지; core는 odi/FastAPI/DB/web/tools import 금지; 실제 Rubric/Policy 임의 생성 금지; 단독 실행에 OpenAI 키 불필요.

## Review Focus

실제 Rubric 미제공·16개 ID 중복/누락·Evidence 허위 인용·optional 모델 의존성 미설치·동일 캐시 반복을 추론으로 오해 — Task 1/2/3에서 검사한다.

### Task 1: 실제 연구 계약과 독립 core

**Files:** Create `sushi-fast/rehear_ai/{__init__,contracts,evidence,validation}.py`; Create `sushi-fast/odi/EVC/assessment_adapter.py`; Test `sushi-fast/odi/EVC/tests/test_rehear_assessment_boundary.py`.
**Interfaces:** SPEC의 EvidencePack/RubricBundle/CriterionAssessment/AssessmentResult. `build_evidence_pack(records, *, source_version: str) -> EvidencePack`. records 형태는 기존 DTO를 adapter에서 변환하고 core로 import하지 않음.

- [ ] 현재 팀의 Qwen v2 원본 Rubric/Anchor/Policy를 찾고 출처·버전을 고정한다. 현재 노션 분석 페이지에는 전체 16개 기준 정의가 없다. 없다면 이 데이터만 blocked로 기록하고 계약/fake 구현은 계속한다.
- [ ] `test_rubric_ids_exactly_match_result` 작성: production bundle16개 고유 ID; result는 같은 집합/개수. 누락/중복/임의 ID를 거부. 합성 16개 toy fixture는 TEST_ONLY로 표시하고 실제 Rubric으로 저장하지 않음.
- [ ] `test_abstention_and_reference_validation`: score1–5 strict int/null, bool·0·6 거부; abstained↔null+사유 일관; 미존재 Evidence 참조 거부. 의미적 지지는 별도 검토 과제로 기록.
- [ ] `test_evidence_preserves_offsets_and_missing_inputs`: STT 상대 시점과 segment offset/슬라이드 관측 정밀도/축약/QA 누락을 보존. 없는 F0/시선 시계열을 생성하지 않음.
- [ ] 실패 확인 후 계약·검증·backend adapter 구현. 기존 보고서 점수를 연구 정답/입력으로 몰래 사용하지 않음.

### Task 2: engine 경계·로컬 수명·선택적 API

**Files:** Create `sushi-fast/rehear_ai/engines/{__init__,base,fake,qwen_local,openai_api}.py`와 작은 config/factory. OpenAI engine은 비교를 실제 사용할 때만 구현해도 됨.
**Interfaces:** `AssessmentEngine.assess(evidence, rubric) -> AssessmentResult`; factory `create_engine(config) -> AssessmentEngine`; model load/runtime 의존성은 qwen_local 안에서 lazy하게 로드.

- [ ] `test_fake_and_core_work_without_gpu_or_openai_key`: 최소 환경 import와 fake 실행이 torch/transformers/OpenAI 설치를 요구하지 않음.
- [ ] `test_local_runtime_is_loaded_once`: fake loader로 연속2회 assess 시 load1회/추론2회 확인. adapter/tokenizer·base revision identity 기록.
- [ ] `test_engine_selection_preserves_research_schema`: Qwen/OpenAI fake transport가 같은16개 계약을 쓰며 service10 report가 호출되지 않음.
- [ ] `test_cache_bypass_causes_real_engine_calls`: 동일 입력2회 cache off이면2회 호출. identity 차이(provider/model/adapter/prompt/Rubric/Policy/추론 설정)는 cache 공유 금지.
- [ ] 실패 확인 후 로컬 추론 경계 구현. 실제 모델 family/chat template/structured output 지원은 설치된 runner로 확인한다. 무조건 OpenAI .parse 지원 가정 금지. 실제 GPU/가중치가 없으면 그 검증만 미완료로 남긴다.

### Task 3: CLI·내부 보관·기존 서비스 무변경

**Files:** Create `sushi-fast/tools/rehear_cli/{__init__,__main__}.py`, `sushi-fast/Makefile.ai`; 필요한 backend 내부 저장 adapter; 같은 테스트.
**Interfaces:** `python -m tools.rehear_cli eval --input CASE --rubric BUNDLE --engine fake|qwen_local --output RESULT`. 명령은 이 단계에서 새로 구현한다.

- [ ] `test_cli_subprocess_and_json_output`: 임시 synthetic 입력+rubric으로 fake engine 실행(exit0), schema/version/16개/coverage/call count 출력; 잘못된 입력은 nonzero+실행 실패 설명.
- [ ] `test_service_contract_does_not_require_research_result`: 기존 finish/read-report/질문/청중 경로의 필수 필드나 기본 provider가 바뀌지 않음. 연구 내부 저장의 연결은 opt-in/internal이며 공개 projection 미구현을 숨기지 않음.
- [ ] `test_tool_removal_leaves_runtime_importable`: 임시 복사본에서 CLI tools 없이 core와 backend adapter import. 운영 의존성 설치된 테스트 환경에서 수행.
- [ ] 구현 후 `test --suite assessment`, 기존 관련 검사, `guard`. 원자료→Evidence→fake의 연결과 실제 Qwen 채점 품질 검증은 별개로 기록한다.
