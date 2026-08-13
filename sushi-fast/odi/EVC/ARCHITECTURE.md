# EVC v2 모듈 구조

이 문서는 `reaction-rule_stage2_contract.md`를 구현하기 위한 내부 책임과 의존 방향을 고정한다. `EVC/EVCv1`은 이 구조에 포함하지 않는다.

## 의존 방향

```text
router.py
  -> pipeline.py
      -> evaluation.py -> speech2text.py
      -> state_engine.py
      -> behavior_engine.py -> clip_pool.py -> clip_pool.json
      -> command_builder.py
      -> session_store.py

schema.py <- 모든 모듈이 공유하는 유일한 도메인/API 모델 계층
config.py <- 환경 설정과 고정 계산 상수
```

하위 모듈은 `router.py`나 `pipeline.py`를 import하지 않는다. `state_engine.py`, `behavior_engine.py`, `command_builder.py`는 FastAPI, UploadFile, 외부 AI SDK를 import하지 않는 순수 계산 계층으로 유지한다.

## 모듈별 책임

| 모듈 | 책임 | 금지 사항 |
| --- | --- | --- |
| `schema.py` | Pydantic 도메인/API/Clip/Unity 모델과 enum | 세션 저장, 외부 호출, 랜덤 선택 |
| `config.py` | 계약 상수, 환경 변수 파싱/범위 검증 | 요청별 상태 보관 |
| `speech2text.py` | STT provider 호출과 표준 `SpeechTextResult` 변환 | E/V/C 및 행동 계산 |
| `evaluation.py` | 구간 context, 음성 지표, LLM M/D 평가 조립 | 상태 갱신과 행동 ID 생성 |
| `state_engine.py` | 초기 상태, M/D delta, 민감도, 6명 상태 갱신 | 외부 API 호출, 세션 commit |
| `clip_pool.py` | JSON 로딩, 시작 시 검증, immutable 조회 | 확률 sampling과 이력 변경 |
| `behavior_engine.py` | 수준/우세축/tie, 후보 필터, 점수, 확률, Core/Action 선택 | Unity action 실행 세부사항 |
| `command_builder.py` | 선택 결과를 레이어별 `UnityCommand`로 분해, 충돌 해결 | 상태/확률 재계산 |
| `session_store.py` | token, TTL, 용량, lock, idempotency, 원자 commit | STT/LLM 호출과 행동 계산 |
| `pipeline.py` | update 단계 순서와 실패 시 rollback 조정 | 개별 계산 공식의 중복 구현 |
| `router.py` | multipart/header 파싱, 인증, HTTP 오류 mapping | 비즈니스 수식과 직접 상태 변경 |

## 공개 인터페이스

이름과 반환 타입은 구현 단계에서 유지한다.

```python
# state_engine.py
create_agent_rngs(seed: int) -> dict[str, random.Random]
initialize_audiences(options: SmartStartOptions, seed: int, rngs: dict[str, random.Random] | None = None) -> list[AudienceRuntimeState]
compute_state_delta(evaluation: MtDtEvaluation) -> StateDeltaBreakdown
update_audience_state(agent: AudienceRuntimeState, delta: AudienceState, topic_interest: float, prior_knowledge: float) -> tuple[AudienceState, StateSensitivity]
aggregate_state(audiences: list[AudienceRuntimeState]) -> AudienceState

# clip_pool.py
load_clip_pool(path: Path | None = None) -> ClipPoolCatalog

# behavior_engine.py
classify_level(value: float) -> StateLevel
choose_dominant_axis(state: AudienceState, previous: DominantAxis | None) -> tuple[DominantAxis | None, Direction | None]
select_behaviors(agent: AudienceRuntimeState, context: SegmentContext, catalog: ClipPoolCatalog, now_s: float, delta: AudienceState) -> SelectionResult

# command_builder.py
build_unity_commands(agent_id: str, core: BehaviorChoice | None, action: BehaviorChoice | None, catalog: ClipPoolCatalog, context: SegmentContext, accepted_time_s: float) -> list[UnityCommand]

# session_store.py
create_session(...) -> SessionRecord
get_authorized_session(session_id: UUID, token: str) -> SessionRecord
locked_update(session_id: UUID, token: str, request_id: UUID, expected_step: int) -> AsyncContextManager[SessionTransaction]

# pipeline.py
create_pipeline_session(...) -> SmartStartResponseV2
read_pipeline_session(...) -> SessionResponseV2
update_pipeline(...) -> EVCUpdateResponseV2
```

`SelectionResult`, `SessionRecord`, `SessionTransaction`은 해당 내부 모듈의 dataclass로 두며 API 직렬화 모델과 분리한다.

## 호환성 원칙

- 기존 `AudienceState`, `BehaviorCommand`, `EVCUpdateResponse`는 v2 전환 중 기존 서비스가 import 가능하도록 유지한다.
- 신규 코드의 외부 응답은 `SmartStartResponseV2`, `SessionResponseV2`, `EVCUpdateResponseV2`만 사용한다.
- 기존 `initial_evc_state`, `evc_state`, `behavior`는 v2 응답에서 집계/축약 호환 필드로 유지한다.
- v2 내부에서 단일 공통 E/V/C를 개별 상태 대신 저장하지 않는다.

## 검증 경계

- HTTP/form 문자열 파싱은 router에서 수행한 뒤 `SmartStartOptions`, `UpdateRequestMetadata`, `SegmentContext`로 검증한다.
- Clip 데이터는 애플리케이션 시작 시 `ClipPoolCatalog`로 한 번 검증한다. 한 variation의 대체 상태 조건은 `trigger_conditions`/`state_gates` 목록으로 표현한다.
- 상태 계산 함수는 유효한 schema 인스턴스만 받고 새 인스턴스를 반환한다.
- 세션 commit 전에 `EVCUpdateResponseV2` 전체를 생성·검증한다.
- Unity에는 `UnityCommand`로 검증된 명령만 반환한다.
