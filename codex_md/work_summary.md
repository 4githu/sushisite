# AI 청중 반응 파이프라인 개발 작업 요약

## 결과

`PROJECT_ONBOARDING.md`와 `reaction-rule.md`를 기준으로 15단계 계획을 수립하고, `sushi-fast/odi/EVC/`에 AI 청중 반응 파이프라인 v2를 구현했다. 파이프라인은 발표 음성·슬라이드·시선·사건 신호를 평가하여 6명 청중의 E/V/C 상태를 갱신하고, Core 행동과 선택적 Action overlay를 Unity layer 명령으로 반환한다.

## 단계별 작업

1. 기존 EVC 코드, 상위 FastAPI 조립, 인증 구조와 실행 제약을 조사했다.
2. 상태 경계, 우세축, 수식, 랜덤성, 선택 확률, 시간, 오류 및 API v2 계약을 고정했다.
3. strict Pydantic v2 도메인 스키마와 모듈 경계를 정비했다.
4. Core 44개와 Action 8개, 총 52개 variation 및 모든 Unity mapping을 `clip_pool.json`으로 구축했다.
5. seed 기반 6명 profile, 에이전트별 RNG, 정확히 2명의 laptop 조건과 메모리 세션을 구현했다.
6. audio/slide 크기·형식 검증, 임시 파일 정리, PDF 추출, Deepgram STT 정규화와 음성 지표를 구현했다.
7. OpenAI structured output 기반 M/D 평가, 누락 입력, timeout/retry 및 실패 정책을 구현했다.
8. 명세의 가중치 수식, 음수 민감도와 `[-1,1]` clamp를 그대로 구현했다.
9. 상태·발화 위치·scene/event·cooldown 후보 필터와 우세축 동률 규칙을 구현했다.
10. 점수, 안정적 Softmax, categorical sampling, transient gate, Baseline/no-op 및 Action overlay를 구현했다.
11. Unity layer 명령 생성과 FastAPI smart-start/read/delete/update API를 연결했다.
12. token digest, constant-time 비교, TTL, capacity, session lock, step/idempotency, 원자 commit, 비식별 로그를 보강했다.
13. 단위·통합·시나리오·OpenAPI 테스트와 전용 의존성 검증을 수행했다.
14. headless Unity 소비자로 연속 발화 위치, timing, sync, layer 중재 및 재연결을 리허설했다. 이 과정에서 Baseline 폴백 점수의 빈 집합 결함을 발견해 수정했다.
15. 본 요약과 Unity 인계 명세를 생성했다.

각 단계의 상세 근거는 루트의 `reaction-rule_stage1_baseline.md`부터 `reaction-rule_stage14_unity_rehearsal.md`까지 기록돼 있다.

## 핵심 구현 규칙

- 상태: Engagement(E), Evaluative Valence(V), Cognitive Clarity(C), 각 `[-1,1]`
- 청중: `audience_01`~`audience_06`, front/middle/rear의 좌·우 고정 배치
- 초기 상태: topic interest가 E, prior knowledge가 C에 반영되고 seed 기반 개인 오프셋을 적용
- 갱신: content와 delivery 점수를 명세 가중치로 합성한 뒤 에이전트별 음수 민감도와 clamp 적용
- 선택: 이산 상태 후보 필터 → 점수화 → 안정적 Softmax → 에이전트별 RNG 표본 추출
- 출력: agent당 Core 최대 1개와 Action 최대 1개; Core priority 50, Action priority 100
- 시간: Unity 세션 시작 기준 초, 발화 위치에 따라 `+0.05` 또는 `+0.10`초 offset
- 복구: 동일 `request_id`는 동일 응답, 잘못된 `expected_step`은 409, 실패 요청은 상태를 변경하지 않음
- 보안: 원문 session token은 반환 시에만 노출하고 서버에는 SHA-256 digest로 저장; transcript/token/업로드 경로는 로그에서 제외

## API 변경

- `POST /odi/xreal_rehear/evc/smart-start`
- `GET /odi/xreal_rehear/evc/sessions/{session_id}`
- `DELETE /odi/xreal_rehear/evc/sessions/{session_id}`
- `POST /odi/xreal_rehear/evc/update`

응답 계약은 `api_version: "2.0"`이며, Unity 호출부는 smart-start에서 받은 `session_id`, `session_token`, 현재 `step`을 보관해야 한다. 전체 연동 요구사항은 `unity_spec.md`를 따른다.

## 주요 파일

- 계약/스키마: `sushi-fast/odi/EVC/schema.py`
- API: `sushi-fast/odi/EVC/router.py`
- 오케스트레이션: `sushi-fast/odi/EVC/pipeline.py`
- 세션: `sushi-fast/odi/EVC/session_store.py`
- 입력/STT/평가: `inputs.py`, `speech2text.py`, `evaluation.py`
- 상태/후보/선택: `state_engine.py`, `behavior_engine.py`
- Unity 명령: `command_builder.py`
- Clip Pool: `clip_pool.json`, `clip_pool.py`, `CLIP_POOL.md`
- 관측성/설정: `observability.py`, `config.py`
- 테스트: `sushi-fast/odi/EVC/tests/`
- 운영/개발 의존성: `sushi-fast/requirements-evc.txt`, `sushi-fast/requirements-evc-dev.txt`

## 검증 결과

최종 실행 결과:

```text
66 passed in 2.05s
compileall: OK
pip check: No broken requirements found.
git diff --check: 오류 없음 (Windows CRLF 안내만 존재)
```

검증 범위에는 수식, 경계와 clamp, seed 재현성, 52개 Clip 데이터, 8개 Action 사건, cooldown, Softmax, 6명 결정, Unity timing/sync/priority, API 수명주기, 오류 원자성, idempotency, 보안 로그 및 headless Unity 리허설이 포함된다. 상위 `odi.router`의 OpenAPI에 네 endpoint가 등록되는 것도 확인했다.

## 외부 서비스 및 설정

운영 의존성은 고정 파일에서 설치한다.

```powershell
python -m pip install -r sushi-fast/requirements-evc.txt
```

필수 provider secret은 `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`다. 주요 선택 설정은 `OPENAI_EVC_MODEL`, `DEEPGRAM_PRIMARY_MODEL`, `EVC_SESSION_TTL_S`, `EVC_MAX_SESSIONS`, `EVC_STT_TIMEOUT_S`, `EVC_LLM_TIMEOUT_S`, `EVC_PROVIDER_RETRIES`, `EVC_INCLUDE_DIAGNOSTICS`, `EVC_DEBUG_LOG`다. 기본값과 전체 목록은 `sushi-fast/odi/EVC/config.py`가 기준이다.

## 알려진 제한과 후속 과제

- 현재 세션은 프로세스 메모리에만 존재한다. 단일 Uvicorn worker만 지원하며 재시작 시 세션이 사라진다. 운영 확장 전 Redis 또는 DB 기반 원자 저장소로 교체해야 한다.
- 현재 환경에는 provider API key가 없어 실제 OpenAI/Deepgram 종단 smoke test와 p50/p95 지연 측정을 수행하지 않았다. fake provider로 retry/timeout/rollback 경계를 검증했다.
- 작업공간에 Unity 프로젝트와 실제 animation/BlendShape/IK 에셋이 없어 시각적 재생과 asset mapping은 Unity 팀 인수 테스트가 필요하다.
- PPT/PPTX는 업로드 가능하지만 이 프로토타입에서는 본문 추출이 활성화되지 않아 빈 slide text와 안내 summary를 사용한다. PDF 본문 추출은 지원한다.
- 전체 `sushi-fast/main.py`는 EVC 외 Bommal 모듈의 추가 의존성이 현 전용 가상환경에 없어 기동하지 못했다. EVC가 포함된 `odi.router` import와 OpenAPI 조립은 검증했다.
- 프로덕션 적용 전 실제 Unity 장면에서 action ID 매핑, 0.20초 cross-fade, layer 충돌, 프레임 안정성과 실제 provider 지연을 승인해야 한다.

이 문서에는 API key, session token, 발표 원문, 음성 원본 또는 개인정보를 포함하지 않는다.
