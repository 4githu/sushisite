# Reaction Rule 14단계 완료 기록 — Unity 연동 리허설

## 검증 방식

현재 작업공간에는 Unity 프로젝트와 실제 Animator/BlendShape/GazeHead 에셋이 없으므로, 계획에서 허용한 합의된 요청 샘플 방식의 headless Unity 소비자 테스트를 구현했다. 테스트는 실제 파이프라인 함수를 호출하고 Unity가 수신한 명령을 분해·그룹화·중재하는 계약을 재현한다.

테스트 파일: `sushi-fast/odi/EVC/tests/test_unity_rehearsal.py`

## 시나리오 결과

하나의 세션에서 아래 순서로 연속 update를 실행했다.

1. 발화 중(`during_speech`, 1.0초, 긍정 평가)
2. 발화 경계(`utterance_boundary`, 3.0초, 긍정 평가)
3. 침묵/일시 정지(`silence_or_pause`, 5.0초, 부정 평가)
4. 슬라이드 전환(`slide_transition`, 7.0초, 부정 평가)

검증 결과:

- 매 update가 정확히 6명의 audience 상태와 결정을 반환했다.
- 모든 `action_id`가 서버 Clip Pool에 등록된 ID였다.
- 모든 명령의 `start_time`이 요청 `client_time_s`보다 이르지 않았다.
- 모든 명령 layer가 `Face`, `Body`, `GazeHead` 중 하나였다.
- 같은 선택에서 분해된 layer 명령은 동일한 `sync_group`을 사용했다.
- 같은 agent/layer/time 충돌은 priority가 높은 Action(100)이 Core(50)를 덮도록 소비자 중재를 검증했다.
- 마지막 요청을 동일한 `request_id`와 `expected_step`으로 재전송했을 때 캐시된 동일 응답을 반환했고 세션 step은 중복 증가하지 않았다.
- 고정 seed에서도 연속 시나리오 전체가 한 종류에 고정되지 않고 둘 이상의 Core variation을 선택했다.
- mock provider 조건의 각 update 처리 시간은 1초 미만이었다.

## 리허설에서 발견하고 수정한 결함

명시적 Baseline 폴백 후보가 현재 비중립 상태의 trigger와 일치하지 않을 때 빈 점수 집합에 `max()`를 적용하던 결함을 발견했다. 폴백 후보의 상태 적합도를 중립값 `0.50`으로 계산하도록 수정하고 전용 회귀 테스트를 추가했다.

## 최종 자동 검증

- EVC 전체 테스트: `66 passed in 2.05s`
- Python bytecode 컴파일: 통과
- `git diff --check`: 오류 없음(CRLF 변환 안내만 존재)

## 프로덕션 승인 체크리스트

- [x] 6명 agent 응답 및 등록된 action ID 계약
- [x] 세션 기준 초 단위 start time과 sync group 계약
- [x] Core/Action layer 충돌 우선순위 계약
- [x] 연속 step, 재연결 및 중복 요청 계약
- [x] mock 기반 기능 지연 기준
- [ ] 실제 Unity Animator Controller의 state/action ID 매핑
- [ ] 실제 BlendShape 이름과 Face action ID 매핑
- [ ] 실제 Gaze/Head IK target과 GazeHead action ID 매핑
- [ ] 실기기 프레임에서 cross-fade, 동시 layer 재생 및 시각적 품질
- [ ] 실제 OpenAI/Deepgram 호출을 포함한 p50/p95 종단 지연과 timeout 기준

미완료 항목은 Unity 프로젝트/에셋과 외부 provider 자격 증명이 필요한 외부 인수 검증이다. 서버 계약과 재현 가능한 headless 연동 리허설 범위에서는 14단계를 완료했다.
