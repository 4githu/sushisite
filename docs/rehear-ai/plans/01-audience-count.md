# Dynamic Audience Count Implementation Plan

> **For agentic workers:** 구현 시 사용할 수 있다면 superpowers:executing-plans를 사용해 task 단위로 진행한다. 문서 작성만 요청된 세션에서 제품 구현을 시작하지 않는다.

**Goal:** 기존 PIN snapshot의 count를 실제 a명 세션으로 연결한다.
**Architecture:** snapshot → strict count resolver → options/registry → 초기화/검증. count=6의 기존 RNG 결과를 보존한다.
**Tech Stack:** 현재 Python/FastAPI/Pydantic/pytest. 신규 framework 없음.
**Spec:** `../SPEC.md`, `../CONTRACTS.md`.

## Global Constraints

Unity·sushi-app 무변경; count 누락=6; 값 존재 시 strict int 1–50; 세션 membership 필수; 질문 수 1–5와 별개; catalog/EVC 식 보존.

## Review Focus

1. bool/소수/문자열이 int로 통과하지 않음 — Task 1.
2. PIN 준비 후 템플릿 편집이 세션 count를 바꾸지 않음 — Task 1.
3. 홀수/1명과 평균·없는 짝 — Task 2.
4. 허용 정규식 ID라도 다른 세션의 ID는 거부 — Task 3.
5. a=6의 seed/trait/행동이 바뀌지 않음 — Task 2/3.

### Task 1: 기존 입력을 options까지 연결

**Files:** Create `sushi-fast/odi/EVC/audience_config.py`; Modify `router.py`, `schema.py`, `session_store.py`; Test `sushi-fast/odi/EVC/tests/test_audience_count_contract.py`.
**Interfaces:** `resolve_audience_count(snapshot: dict | None) -> int`; `SmartStartOptions.audience_count: int = 6`. 외부 smart-start의 새 필수 인자는 없다.

- [ ] `test_count_resolution_strict_and_missing` 작성: None/빈 snapshot/count 누락→6; 1/6/12/50→동일; True/False/3.5/6.0/"12"/None(명시값)/0/-1/51→ValueError. audience 객체가 있는데 구조가 잘못됐으면 오류.
- [ ] `test_pin_uses_bound_snapshot` 작성: prepare 때 count12, 나중 최신 template50이어도 start는12. 기존 pinless는6. invalid count는 기존422 입력 오류로 매핑.
- [ ] 위 node를 pytest로 실행해 기존 누락 경로로 실패하는지 확인한다. import/setup 오류만 있으면 준비를 먼저 해결한다.
- [ ] resolver를 구현하고 router의 snapshot 관심/전문성 처리 옆에서 options로 전달한다. 내부 생성 호출과 session registry를 함께 연결한다.
- [ ] 새 테스트와 기존 `test_session_initialization.py`, `test_schema.py` 실행. 동작 변경·명령·결과를 PROGRESS에 기록한다.

### Task 2: 초기화/RNG/프로필 일반화

**Files:** Modify `state_engine.py`, `session_store.py`; 필요 시 layout helper는 `audience_config.py`; 같은 새 테스트 파일.
**Interfaces:** `build_audience_layout(count: int) -> tuple[tuple[str,str,str], ...]`; 기존 `create_agent_rngs`와 `distribute_population_trait`에 optional count를 추가하되 기본6·기존 호출 호환 유지.

- [ ] 수정 전 seeds=0,1,2026의 6명 초기 profile/state/RNG 소비 결과를 합성 golden으로 확보한다. UUID 등 비결정 필드는 비교에서 제외한 이유를 기록한다.
- [ ] `test_population_counts_and_traits` 작성: a=1/3/6/12/50에서 len==a, ID 정확·유일, row/seat 기존 enum, 특성 범위[0,1], 평균 설정과 오차1e-12 이내, seed 반복 동일. mean=0/0.5/1 검사.
- [ ] `test_six_audience_golden_unchanged`, `test_single_actor_has_no_phantom_partner_or_laptop`를 실패 상태로 확인한다.
- [ ] count=6 기존 코드 경로/RNG 순서를 보존하고 나머지 count의 layout·대칭 특성·노트북/짝 정책을 일반화한다. seed에 count를 임의 혼합해 기존6 결과를 바꾸지 않는다.
- [ ] 새 테스트 및 기존 state/behavior/initialization 검사를 실행한다.

### Task 3: 응답·명령·질문의 세션 membership

**Files:** Modify `schema.py`, `reaction_scheduler.py`, 필요한 `router.py`/`answer_service.py` 경계; 동일 신규 테스트.
**Interfaces:** element ID 허용 범위01–50 + 세션 registry 기준 확인. 응답 목록은 그 세션의 a명과 일치.

- [ ] `test_start_read_update_return_exact_registry`: a=1/6/12/50의 start/read/update 목록과 command agent_id가 동일 registry에 속함.
- [ ] `test_questions_reject_out_of_session_id`: a=1일 때 유효 형식 audience_02도 speech/answer에서 거부. a=12의 audience_12는 허용. 질문 총수는 기존 설정 유지.
- [ ] `test_rear_pairing_uses_valid_deterministic_partner`: 홀수·짝 없음·rear 다수에서 없는 ID/자기 자신을 짝으로 만들지 않음; a=6 기존 pairing 유지.
- [ ] 실패 확인 후 정확히6 검사/정규식과 pairing을 변경한다. 대량 반응 throughput은 02에서 검증한다.
- [ ] `python3 tools/rehear_harness.py test --suite audience`, `--suite original`, `guard` 실행. 실패/skip 원인은 기록하고 성공으로 표시하지 않는다.
- [ ] 변경 diff 자체 검토 후 사용자 지시가 허용한 방식으로 단계 결과를 저장한다. Unity actor 실제 매핑은 미검증으로 남긴다.
