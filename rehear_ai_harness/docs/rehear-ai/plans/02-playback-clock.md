# Playback Freshness Implementation Plan

> **For agentic workers:** 구현 시 superpowers:executing-plans를 사용할 수 있으면 task 단위로 수행한다.

**Goal:** 근거 시간과 재생 clock을 분리하고 늦은 이벤트·시계·인원별 대기를 검증한다.
**Architecture:** 주입 가능한 monotonic observer + 내부 playback policy. 기존 소비자 계약이 허용하는 범위만 적용한다.
**Tech Stack:** 기존 Python/pytest·fake clock/provider.
**Spec:** `../SPEC.md`, `../CONTRACTS.md`.

## Global Constraints

Unity·웹 변경 금지; 독립 모드 기본 false; 분석 근거 시간 불변; duplicate request_id 응답 불변; start_time/duration 의미 불변. 네트워크/클라이언트 시계를 모르면 전체 동기화 완료를 주장하지 않는다.

## Review Focus

지연 응답·stale slide/pause·pause/reset/큰 미래 점프·같은 요청 재시도·50명 한꺼번에 due — 각각 Task 1/2/3에서 검사한다.

### Task 1: 시간 provenance와 실패 재현

**Files:** Modify `pipeline.py`, `observability.py`; Create `playback_policy.py`; Test `odi/EVC/tests/test_playback_freshness.py` (경로는 모두 `sushi-fast/` 기준).
**Interfaces:** 내부 `TimingTrace`에 수신/lock 대기/STT/평가/commit·response monotonic, evidence client time, evidence age의 관측 가능 여부를 담는다. 제품 응답 필수 필드 추가 없음.

- [ ] `test_delayed_provider_keeps_evidence_clock`: request30.0, fake processing5.0에서 원본 근거 시간30.0 유지·processing5.0 기록. session 생성 시각을 발표0으로 쓰지 않음.
- [ ] `test_no_authoritative_playback_clock_is_reported_unknown`: 최신 소비자 시계가 없는 legacy 경로에서 ‘정확한 현재 Unity 시계’를 만들어내지 않음. existing client time과 서버 elapsed를 서로 구분.
- [ ] 요청30.0→명령30.1이 응답 시계35.0 가정 시 늦는 현상을 먼저 재현한다. 시각 변경을 fake로 숨기지 않는다.
- [ ] 주입 clock/observer를 구현하고 측정값·unknown 상태를 내부 trace에 기록한다. timeout된 thread가 계속 돌 수 있어 동시성/입장 예산을 별도 둔다.
- [ ] 테스트와 기존 command/rehearsal 검사를 실행한다. 최신 시계가 없으면 legacy 경로의 지연 보정 한계와 남은 작업을 PROGRESS에 분명히 남긴다.

### Task 2: 독립 모드 freshness·clock·재시도

**Files:** Modify `reaction_scheduler.py`, `pipeline.py`, 내부 policy/session 필드; 동일 새 테스트.
**Interfaces:** 과거 Evidence 문맥과 최신 poll time 분리; freshness 판정 결과에 source_step/event age/drop reason. TTL은 event별 설정으로 주입하고 제품 기본값은 과거 측정과 이벤트 의미를 바탕으로 문서화한다.

- [ ] `test_stale_momentary_event_not_replayed`: 테스트 설정 TTL2초, 이벤트30초, poll35초이면 slide/pause의 순간 action 미발행. Evidence 저장·delta 적용은 정확히1회. TTL2는 테스트 입력이지 무조건 제품 기본값이 아니다.
- [ ] `test_duplicate_poll_keeps_identical_commands`: 같은 request_id는 명령 UUID/시각/sequence까지 동일. 새 시각에 다시 발행하지 않음.
- [ ] `test_clock_pause_reset_and_forward_jump`: pause 중 같은 시각에 due 폭주 없음; regression/큰 jump는 명시 정책(기존 오류 의미 또는 안전 보류)으로 처리하고 조용한 max clamp로 무기한 고착시키지 않음.
- [ ] `test_independent_mode_remains_opt_in`: false의 update 소비 경로 유지, true는 기존 reactions 소비 경로. 자료 없는 소비자를 이미 polling한다고 가정하지 않음.
- [ ] 실패 확인 후 정책 구현·측정 근거/시간 도메인 문서화. 이미 알려진 시계 없이는 새 epoch를 임의 시작하지 않는다.

### Task 3: a명 부하·대기·명령 예산

**Files:** Modify `reaction_scheduler.py`·관측/설정; 동일 새 테스트.
**Interfaces:** 세션 registry 기반 fair scheduling·bounded command budget·관측 가능한 queue/evidence age. 캐시와 state 순서 보존.

- [ ] `test_many_due_actors_are_fair_and_bounded`: fake poll250ms, a=1/6/12/50에서 모두 due인 합성 case의 첫/마지막 dispatch·actor별 wait를 기록. 굶는 actor/존재하지 않는 ID/무제한 동시 burst 없음.
- [ ] 현재 전역 .35초 규칙의 병목을 수치로 먼저 남긴다. 제품 batch/rate 설정의 실제값과 6명 회귀 허용 범위를 결정·문서화한다. 무조건50명 일괄 명령은 금지.
- [ ] `test_overload_preserves_analysis_order_and_drops_only_stale_playback`: bounded provider/queue에서 분석 기록 유실·중복 delta 없이 오래된 재생 후보만 구분. 처리 순서를 무조건 병렬화하지 않음.
- [ ] 구현 후 `test --suite timing`, `--suite original`, `guard`를 실행한다.
- [ ] 결과를 backend/headless 확인으로 기록한다. 실제 Unity 수신 시계·actor mapping 없는 전체 동기화 검증은 후속으로 남긴다.
