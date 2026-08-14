# AI 청중 반응 파이프라인 11단계 Unity/API 통합 결과

> 선행 단계: `reaction-rule_stage10_selection.md` 완료  
> 단계 상태: 완료

## 구현 결과

- `command_builder.py`가 Core/Action을 Face, Body, GazeHead의 `UnityCommand`로 분해한다.
- 발화 위치별 start offset, 행동별 sync group, Core priority 50, Action priority 100, mapping blend mode와 agent expressivity intensity를 적용한다.
- 같은 layer의 Core/Action은 두 명령과 priority를 함께 보내 Unity가 Action override 후 Core로 복귀할 수 있게 한다.
- `pipeline.update_pipeline()`이 token, idempotency, expected step, client time을 확인한 뒤 STT→평가→delta→6명 상태→후보→선택→명령을 조립한다.
- agent/RNG 복제본에서 전체 응답 검증을 끝낸 뒤 상태·RNG·step·이력·cooldown을 한 번에 commit한다.
- 외부 실패는 commit하지 않으며 같은 request ID는 캐시 응답을 반환한다.
- 빈 transcript는 step/state를 유지하고 명시적 no-op 응답을 캐시한다.
- `router.py`를 v2 smart-start/read/update 계약으로 전환하고 session token과 구조화 오류 mapping을 적용했다.
- 기존 `initial_evc_state`, `evc_state`, `behavior` 호환 필드를 유지한다.

## 검증 결과

```text
$env:PYTHONPATH='sushi-fast'
.\.venv\Scripts\python.exe -m pytest sushi-fast/odi/EVC/tests -q

............................................... [100%]
47 passed, 1 dependency deprecation warning
```

추가 검증 항목:

- layer 분해, start time, Core/Action priority, sync group, intensity
- update의 6명 상태와 명령 생성
- idempotent 재요청이 step을 중복 증가시키지 않음
- expected step과 client time 역행 거부
- 평가 provider 실패 시 상태/RNG/step 미변경
- FastAPI smart-start→token read→update 실제 multipart 계약
- token 누락 401

경고는 설치된 FastAPI/Starlette TestClient가 현재 httpx 사용 방식에 대해 내는 향후 호환성 알림이며 테스트 결과나 API 동작 실패는 아니다.

## 완료 판정

한 update가 6명 각각의 상태, Core/Action 선택과 실행 가능한 layer 명령 또는 no-op을 반환한다. Unity는 서버 내부 상태/선택 규칙을 재구현할 필요가 없다. 원자성과 API v2 계약도 통합 테스트로 검증했다. 따라서 11단계 완료 기준을 충족한다. 다음 실제 작업은 12단계인 세션 안정성, 오류 처리, 보안 및 관측성 보강이다.
