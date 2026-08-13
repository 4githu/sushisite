# AI 청중 반응 파이프라인 2단계 정책 및 데이터 계약

> 선행 단계: `reaction-rule_stage1_baseline.md` 완료  
> 적용 대상: `sushi-fast/odi/EVC/` 신규 구현  
> 계약 버전: `2.0`  
> 단계 상태: 완료

## 1. 목적

이 문서는 `reaction-rule.md`에서 수치나 처리 방식이 확정되지 않은 부분을 프로토타입 구현값으로 고정한다. 이후 단계는 이 문서의 상수, 식별자, fallback 및 API 계약을 사용하며 별도 근거 없이 다른 값을 추가하지 않는다.

## 2. 상태와 우세축 정책

### 2.1 상태 범위와 수준

- 모든 E/V/C 값과 갱신 입력은 유한한 float이어야 한다.
- 상태와 delta는 계산 단계에 명시된 시점마다 `[-1.0, 1.0]`으로 clamp한다.
- 문서에 표기된 두 자리 경계를 연속 실수에 적용하기 위해 다음처럼 해석한다.

```text
low:  -1.00 <= x <= -0.34
mid:  -0.34 <  x <   0.34
high:  0.34 <= x <=  1.00
```

따라서 `-0.34`는 low, `+0.34`는 high이며 `-0.339`와 `+0.339`는 mid이다. NaN과 infinity는 422 오류로 거부한다.

### 2.2 우세축과 근사 동률

1. E/V/C가 모두 mid이면 우세축 없이 `Baseline Listening`을 선택한다.
2. 그 외에는 축별 절대값을 구하고 가장 큰 값 `m1`과 두 번째 값 `m2`를 구한다.
3. `m1 - m2 > 0.10`이면 절대값이 가장 큰 단일 축이 우세축이다.
4. `m1 - m2 <= 0.10`이면 `max_abs - abs(axis) <= 0.10`인 모든 축을 tie 후보로 포함한다.
5. 후보 중 아래 첫 조건을 만족하는 축을 선택한다.

```text
1. 값이 low인 C
2. 값이 low인 V
3. 값이 low인 E
4. 직전 우세축과 같은 축
5. E
6. C
7. V
```

- 직전 우세축은 에이전트별로 저장한다.
- 방향은 선택된 축 값이 0보다 크면 `positive`, 작으면 `negative`이다. 모두 mid인 baseline 외에는 0인 축이 우세축이 될 수 없다.

## 3. 식별자 정책

명세 표의 중복 `clip_id`를 보존하면서 실행 변형을 고유하게 식별하기 위해 두 ID를 사용한다.

- `behavior_id`: 명세의 원래 ID. 예: `AL_01`, `EM_05`, `ACT_03`
- `variation_id`: 시스템 전체에서 고유한 `<behavior_id>.<snake_case_name>` 형식. 예: `AL_01.active_following`, `EM_05.skeptical_monitoring`, `ACT_03.device_checking`
- `selected_behavior_id`: Unity 명령에서 원래 행동군 추적을 위해 `behavior_id`를 전달한다.
- `selected_variation_id`: 실제 선택·쿨다운·이력·Unity mapping의 기준으로 `variation_id`를 전달한다.
- 내부 no-op ID는 `NOOP_CORE.no_op`이며 Clip Pool에는 포함하지 않는다. no-op은 명령 배열을 만들지 않는다.
- ID는 대소문자를 구분하며 배포 후 의미를 바꾸지 않는다. 이름 변경은 API 계약 버전 변경으로 처리한다.

Unity 하위 action ID는 다음 namespace를 사용한다.

```text
face.<variation_name>
body.<variation_name>
gaze_head.<variation_name>
```

4단계에서 각 variation에 실제 action ID와 duration을 전부 지정한다. Unity 자산명이 확정되지 않은 동안에도 위 ID를 계약 ID로 사용하고 Unity에서 자산 이름으로 매핑한다.

## 4. 청중 구성과 랜덤성

### 4.1 고정 장면 구성

| agent_id | row | seat | 특수 조건 |
| --- | --- | --- | --- |
| `audience_01` | front | left | - |
| `audience_02` | front | right | - |
| `audience_03` | middle | left | - |
| `audience_04` | middle | right | - |
| `audience_05` | rear | left | Side Conversation 허용 |
| `audience_06` | rear | right | Side Conversation 허용 |

- 세션마다 seed로 `audience_01~04` 중 한 명과 `audience_05~06` 중 한 명을 뽑아 정확히 2명에게 `has_laptop=true`를 부여한다.
- 나머지 개인 기기 보유 여부는 상태로 관리하지 않는다. `ACT_03 Device Checking`은 노트북 조건 없이 허용한다.

### 4.2 seed와 개인차

- `smart-start`가 optional `seed`를 받는다. 범위는 `0~2,147,483,647`이다.
- seed가 없으면 서버가 `secrets.randbits(31)`로 생성하며 응답에 반환한다.
- 에이전트별 RNG seed는 `SHA-256("{session_seed}:{agent_id}")`의 앞 8바이트 정수로 파생한다. Python의 비고정 `hash()`는 사용하지 않는다.
- 각 에이전트의 `delta_E`, `delta_C`는 독립 균등분포 `U(-0.05, +0.05)`에서 한 번 생성한다. V 초기 오프셋은 없다.
- `responsiveness`: `U(0.40, 0.75)`
- `expressivity`: `U(0.30, 0.70)`
- `critical_bias`: `U(0.25, 0.75)`
- Face/Body/GazeHead channel preference는 각 원시값을 `U(0.20, 1.00)`에서 생성한 뒤 합이 1.0이 되도록 정규화한다.
- RNG 상태는 에이전트별로 세션에 보관한다. 동일 seed와 동일 요청 순서는 동일 결과를 만든다.

## 5. 상태 갱신 계약

명세 수식을 그대로 사용하며 기존 `move_toward` 보간은 사용하지 않는다.

```text
delta_E_M = clamp(0.50*Org + 0.50*Msg)
delta_V_M = clamp(1.00*Sup + 1.00*CER)
delta_C_M = clamp(1.00*Org + 0.50*Sup + 1.00*Msg + 0.50*CER)

delta_E_D = clamp(0.50*Lang + 1.00*Voc + 1.00*Gaze)
delta_V_D = clamp(0.50*Voc + 0.50*Gaze + 0.50*Align)
delta_C_D = clamp(1.00*Lang + 1.00*Align)

delta_E = 0.45*delta_E_M + 0.55*delta_E_D
delta_V = 0.55*delta_V_M + 0.45*delta_V_D
delta_C = 0.50*delta_C_M + 0.50*delta_C_D
```

- 공통 delta에는 추가 학습률이나 confidence 배율을 적용하지 않는다.
- E delta가 음수일 때만 Topic Interest에 따라 `1.20/1.00/0.80`을 곱한다.
- C delta가 음수일 때만 Prior Knowledge에 따라 `1.20/1.00/0.80`을 곱한다.
- V와 양수 E/C delta의 민감도는 항상 `1.00`이다.
- 각 에이전트의 다음 상태는 `clamp(previous + sensitivity * delta)`이다.
- 응답에는 공통 delta, 적용 민감도, 에이전트별 previous/next state를 포함해 계산을 추적할 수 있게 한다.

## 6. Clip 조건과 적합도

### 6.1 메타데이터 필드

각 Core variation은 다음 값을 가진다.

```text
behavior_id, variation_id, parent_group, trigger_condition,
utterance_positions, requires_slide_reference, channels,
cooldown_s, expressivity_target, motion_class, unity_actions
```

각 Action variation은 다음 값을 가진다.

```text
behavior_id, variation_id, event_triggers, state_gate,
utterance_positions, requires_slide_reference, scene_gate,
channels, cooldown_s, expressivity_target, unity_actions
```

- `motion_class`는 `stable` 또는 `transient`이다.
- 표의 `Slide reference`는 발화 위치가 아니라 `requires_slide_reference=true`인 별도 context 조건으로 정규화한다.
- `Slide transition`만 `utterance_position=slide_transition`이다.

### 6.2 수준 affinity와 StateFit

후보 필터는 low/mid/high를 이산 조건으로 먼저 검사한다. 통과한 후보의 연속 적합도는 다음 membership을 사용한다.

```text
low_affinity(x)  = clamp((-x - 0.33) / 0.67, 0, 1)
mid_affinity(x)  = 1 - clamp((abs(x) - 0.33) / 0.67, 0, 1)
high_affinity(x) = clamp(( x - 0.33) / 0.67, 0, 1)
```

- 한 축이 여러 수준을 허용하면 허용 수준 affinity 중 최댓값을 사용한다.
- `StateFit`은 trigger/state gate에 명시된 축 affinity의 산술평균이다.
- 조건이 `state 제한 없음`이면 `StateFit=0.5`이다.

## 7. Core 선택 점수와 확률

### 7.1 고정 계수

```text
lambda_state       = 2.00
lambda_preference  = 1.00
lambda_channel     = 0.75
lambda_history     = 0.50
lambda_repetition  = 1.25
softmax_temperature = 1.00
```

### 7.2 점수 구성요소

모든 구성요소는 `[0,1]`로 제한한다.

```text
expressivity_fit = 1 - abs(agent.expressivity - clip.expressivity_target)
base_preference = 0.50*agent.responsiveness + 0.50*expressivity_fit
```

- 후보가 `critical=true`이고 현재 V가 mid 이하이며 행동 방향이 negative일 때만 다음을 적용한다.

```text
critical_adjustment = 0.25 * (2*critical_bias - 1)
Preference = clamp(base_preference + critical_adjustment, 0, 1)
```

- 그 외에는 `Preference=base_preference`이다. Positive V 행동에 CriticalBias를 적용하지 않는다.
- `ChannelPreference`는 clip이 사용하는 채널의 agent channel weight 산술평균이다.
- `History`는 최근 Core가 없으면 `0.50`, 같은 group의 다른 variation이면 `0.75`, 다른 group이면 `0.50`, 바로 직전과 같은 variation이면 `0.00`이다.
- `Repetition`은 최근 Core 5개 중 같은 variation 횟수를 `min(count/3, 1)`로 계산한다.

```text
z_core =
  2.00*StateFit
+ 1.00*Preference
+ 0.75*ChannelPreference
+ 0.50*History
- 1.25*Repetition
```

Softmax는 overflow를 막기 위해 다음처럼 계산한다.

```text
scaled_z = (z - max_z) / 1.00
probability = exp(scaled_z) / sum(exp(all_scaled_z))
```

Categorical sampling은 에이전트별 RNG를 사용한다.

### 7.3 Responsiveness와 no-op

- `stable` Core는 선택되면 항상 출력한다.
- `transient` Core는 선택 후 `p_emit = 0.35 + 0.65*responsiveness` 확률 gate를 통과해야 출력한다.
- gate 실패 시 같은 후보 집합의 최고 확률 `stable` variation으로 대체한다.
- stable 후보가 없으면 `NOOP_CORE.no_op`을 반환하고 명령은 생성하지 않는다.
- 후보 집합 자체가 비면 현재 발화 위치와 맞는 Baseline stable variation을 찾고, 그것도 없으면 no-op을 반환한다.

## 8. Action 선택과 삽입

### 8.1 사건 enum과 판정

클라이언트는 아래 key와 `[0,1]` strength를 optional `event_signals` JSON object로 보낼 수 있다.

```text
information_dense
slide_reference
repeated_disengagement
low_arousal
long_static_posture
tension
nearby_interaction
```

서버 파생 조건은 다음과 같다. 같은 key가 양쪽에 있으면 `max(client_strength, derived_strength)`를 사용한다.

| 사건 | 서버 파생 조건 | derived strength |
| --- | --- | --- |
| `information_dense` | 구간 word count `>=45` 또는 현재 슬라이드 정규화 텍스트 `>=700자` | `1.0` |
| `slide_reference` | explicit `slide_reference=true` 또는 발화 위치가 slide transition | `1.0` |
| `repeated_disengagement` | 해당 agent의 E가 low인 완료 update가 2회 연속 | `1.0` |
| `low_arousal` | 해당 agent의 E가 `<=-0.60`인 완료 update가 3회 연속 | `1.0` |
| `long_static_posture` | 해당 agent의 마지막 Body 명령 이후 `>=12.0초` | `1.0` |
| `tension` | 해당 agent의 V가 low이고 이번 `delta_V<=-0.15` | `1.0` |
| `nearby_interaction` | 서버에서 파생하지 않음 | - |

`nearby_interaction`은 명시 입력이 있어도 rear의 `audience_05`, `audience_06`만 후보가 된다. `ACT_01`은 `has_laptop=true`인 agent만 후보가 된다.

### 8.2 Action 점수와 gate

```text
z_action =
  2.00*StateFit
+ 1.50*event_strength
+ 0.75*ChannelPreference
+ 0.50*responsiveness
- 1.00*Repetition
```

- Action의 `Repetition`은 최근 Action 5개 중 같은 variation 횟수를 `min(count/3,1)`로 계산한다.
- 후보 간에는 temperature 1.0의 안정적 Softmax/Categorical sampling을 사용한다.
- 선택 후보의 삽입 확률은 다음과 같다.

```text
p_insert = clamp(0.15 + 0.55*responsiveness + 0.20*event_strength, 0, 0.85)
```

- 삽입 gate가 실패하거나 후보가 없으면 Action은 `null`이다.
- 한 agent/update에 Action은 최대 하나다.

### 8.3 레이어 충돌

- Core priority는 `50`, Action priority는 `100`이다.
- 같은 레이어 충돌 시 Action의 기본 blend mode는 `override`이며 Action duration 동안 Core의 해당 레이어 명령을 대체한다.
- 충돌하지 않는 Core 레이어는 계속 실행한다.
- Action 종료 후 Unity는 현재 Core의 stable 상태로 `0.20초` cross-fade한다.
- 명시적으로 `additive`로 매핑된 Face micro-expression만 Core Face 위에 합성할 수 있다.
- GazeHead 충돌 시 Action target이 우선한다.

## 9. 발화 위치, 시간과 cooldown

허용 위치는 `during_speech`, `utterance_boundary`, `silence_or_pause`, `slide_transition` 네 값만 사용한다.

명령 start offset:

| 위치 | offset |
| --- | --- |
| during speech | `+0.10초` |
| utterance boundary | `+0.05초` |
| silence or pause | `+0.10초` |
| slide transition | `+0.05초` |

- update 입력의 `client_time_s`는 Unity 세션 시작 기준 monotonic seconds이다.
- `start_time = accepted_client_time_s + offset`이며 단위는 초다.
- 이전 accepted time보다 최대 `0.25초` 작은 값은 이전 time으로 clamp한다. 그보다 크게 역행하면 409를 반환한다.
- cooldown은 `variation_id`별 마지막 실제 출력 start time과 현재 accepted time의 차이로 검사한다.
- no-op과 gate에서 탈락한 variation은 이력/cooldown을 갱신하지 않는다.
- Core/Action 이력은 각각 최근 8개를 유지하며 반복 점수는 최근 5개만 사용한다.

## 10. 외부 평가 입력과 fallback

- Gaze Delivery 미제공: `0.0`을 사용하고 `missing_inputs`에 `gaze_delivery_score` 추가
- 슬라이드 없음: Slide-Speech Alignment `0.0`을 사용하고 `missing_inputs`에 `slide_context` 추가
- explicit event 없음: 해당 client strength `0.0`; 서버 파생만 적용
- 빈 STT transcript: 상태와 step을 갱신하지 않고 `no_op_reason=empty_transcript`; 같은 request ID 응답을 캐시
- STT 신뢰도 평균 `<0.50`: LLM 평가는 수행할 수 있으나 `missing_inputs`에 `low_stt_confidence`를 추가하고 응답에 warning 제공
- STT timeout: 30초, retry 1회
- LLM timeout: 20초, retry 1회
- 외부 호출 실패 시 상태·이력·step을 변경하지 않고 502를 반환한다.
- LLM이 스키마를 위반하면 한 번 재요청한 뒤 실패 처리한다.
- 입력을 임의 평가값으로 대체해 상태를 갱신하는 fallback은 사용하지 않는다.

## 11. API v2 계약

기존 endpoint 경로는 유지하고 `api_version="2.0"`을 응답에 추가한다. 기존 필드명도 가능한 한 유지하지만, 세션 보호와 동시성 때문에 Unity 호출부는 v2 필드를 사용해야 한다.

### 11.1 Smart Start

`POST /odi/xreal_rehear/evc/smart-start`, multipart/form-data

| 필드 | 형식 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `presentation_title` | string | 예 | trim 후 1~200자 |
| `topic_interest` | string/number | 아니오 | low/middle/high, 낮음/중간/높음 또는 정확히 0.25/0.50/0.75; 기본 middle |
| `prior_knowledge` | string/number | 아니오 | 위와 동일; 기본 middle |
| `slide_file` | file | 아니오 | PDF/PPT/PPTX, 최대 25 MiB |
| `seed` | integer | 아니오 | 0~2,147,483,647 |

응답 핵심:

```json
{
  "api_version": "2.0",
  "session_id": "uuid",
  "session_token": "opaque-secret",
  "seed": 1234,
  "initial_evc_state": {"E": 0.0, "V": 0.0, "C": 0.0},
  "audiences": [
    {
      "agent_id": "audience_01",
      "profile": {
        "row": "front",
        "seat": "left",
        "has_laptop": false,
        "responsiveness": 0.52,
        "expressivity": 0.48,
        "critical_bias": 0.41,
        "channel_preference": {"Face": 0.3, "Body": 0.3, "GazeHead": 0.4}
      },
      "state": {"E": 0.01, "V": 0.0, "C": -0.02}
    }
  ],
  "step": 0,
  "expires_in_s": 7200,
  "slides": []
}
```

`initial_evc_state`는 6명 state의 축별 산술평균인 호환 필드다.

### 11.2 Session Read

`GET /odi/xreal_rehear/evc/sessions/{session_id}`

- Header `X-EVC-Session-Token` 필수
- 응답은 smart-start의 공개 세션 정보와 현재 6명 상태, step, 최근 warning을 반환한다.
- token 원문, RNG 내부 상태, 전체 행동 이력, 업로드 실제 경로는 반환하지 않는다.

### 11.3 Update

`POST /odi/xreal_rehear/evc/update`, multipart/form-data

Header:

| 이름 | 필수 | 설명 |
| --- | --- | --- |
| `X-EVC-Session-Token` | 예 | smart-start에서 받은 opaque token |

Form:

| 필드 | 형식 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `session_id` | UUID string | 예 | 대상 세션 |
| `request_id` | UUID string | 예 | idempotency key |
| `expected_step` | integer | 예 | 현재 session step과 일치해야 함 |
| `client_time_s` | float | 예 | Unity 세션 시작 기준 monotonic seconds, `>=0` |
| `audio` | file | 예 | WAV/MP3/M4A/OGG/WebM, 최대 15 MiB |
| `current_slide_index` | integer | 아니오 | 기본 0; 슬라이드가 있으면 범위 검증 |
| `utterance_position` | enum | 아니오 | 기본 during_speech |
| `language` | string | 아니오 | BCP-47, 기본 ko-KR |
| `gaze_delivery_score` | float | 아니오 | `[-1,1]` |
| `slide_reference` | boolean | 아니오 | 기본 false |
| `event_signals` | JSON object string | 아니오 | 허용 사건 key→`[0,1]` strength |

응답 핵심:

```json
{
  "api_version": "2.0",
  "request_id": "uuid",
  "session_id": "uuid",
  "step": 1,
  "accepted_client_time_s": 12.5,
  "latest_speech": "...",
  "speech_metrics": {},
  "evaluation": {},
  "common_delta": {"E": 0.1, "V": 0.0, "C": 0.2},
  "evc_state": {"E": 0.1, "V": 0.0, "C": 0.2},
  "behavior": {},
  "audiences": [
    {
      "agent_id": "audience_01",
      "previous_state": {},
      "sensitivity": {"E": 1.0, "V": 1.0, "C": 1.0},
      "state": {},
      "dominant_axis": "C",
      "direction": "positive",
      "core_behavior": {
        "behavior_id": "CT_01",
        "variation_id": "CT_01.comprehension_nod",
        "probability": 0.42
      },
      "action_overlay": null
    }
  ],
  "commands": [
    {
      "agent_id": "audience_01",
      "start_time": 12.55,
      "layer": "Body",
      "action_id": "body.comprehension_nod",
      "duration": 1.2,
      "sync_group": "uuid",
      "selected_behavior_id": "CT_01",
      "selected_variation_id": "CT_01.comprehension_nod",
      "priority": 50,
      "blend_mode": "override",
      "intensity": 0.5
    }
  ],
  "warnings": []
}
```

- `evc_state`는 6명 현재 state의 축별 산술평균이다.
- `behavior`는 레거시 호환을 위한 `audience_01`의 축약 선택 결과다.
- 내부 점수 전체는 기본 응답에 넣지 않고 `EVC_INCLUDE_DIAGNOSTICS=true`일 때 `diagnostics`로 제공한다.

## 12. 오류와 원자성 계약

| HTTP | error code | 의미 |
| --- | --- | --- |
| 400 | `invalid_input` | 파싱할 수 없는 form/JSON |
| 401 | `invalid_session_token` | token 누락/불일치 |
| 404 | `session_not_found` | 없거나 만료된 세션 |
| 409 | `step_conflict` | expected step 불일치 |
| 409 | `client_time_regression` | 허용치보다 큰 시간 역행 |
| 413 | `payload_too_large` | 파일 제한 초과 |
| 415 | `unsupported_media_type` | 허용되지 않은 파일 형식 |
| 422 | `validation_error` | enum/range/ID 검증 실패 |
| 429 | `session_capacity_exceeded` | 최대 active session 초과 |
| 502 | `stt_provider_error` / `evaluation_provider_error` | 외부 공급자 실패 |
| 500 | `internal_pipeline_error` | 예상하지 못한 내부 오류 |

- update는 session lock 안에서 `expected_step`과 idempotency를 확인한다.
- 같은 `request_id` 재요청은 원래 응답을 반환하며 다시 평가/갱신하지 않는다.
- 상태, 이력, cooldown, step, idempotency cache는 응답 생성이 모두 성공한 뒤 한 번에 commit한다.
- 실패한 요청은 세션 상태를 변경하지 않는다.
- 세션별 최근 request/response 32개를 캐시한다.

## 13. 세션 저장 및 보안 정책

프로토타입 1차 구현은 메모리 저장을 유지한다.

- 단일 Uvicorn worker만 지원한다. 다중 worker/수평 확장은 명시적으로 지원하지 않는다.
- 세션 TTL은 마지막 정상 접근 후 7,200초다.
- active session 최대 수는 100개다. 만료 세션을 먼저 정리한 후에도 100개면 429를 반환한다.
- 만료/삭제 시 저장한 슬라이드 파일과 메모리 상태를 제거한다.
- session token은 `secrets.token_urlsafe(32)`로 생성하고 메모리에는 SHA-256 digest만 저장한다.
- token 비교는 constant-time 비교를 사용한다.
- smart-start를 제외한 read/update는 session token을 요구한다.
- 디버그 로그 기본값은 false다. 활성화해도 transcript, 원본 평가 근거, token, 업로드 경로는 기록하지 않는다.
- 프로세스 재시작 시 세션이 소실된다는 제한을 API 문서와 최종 Unity 명세에 표기한다.

## 14. 설정 상수

다음 환경 변수를 지원하고 괄호 값을 기본값으로 사용한다.

```text
OPENAI_EVC_MODEL (gpt-4.1-nano)
EVC_DEBUG_LOG (false)
EVC_INCLUDE_DIAGNOSTICS (false)
EVC_SESSION_TTL_S (7200)
EVC_MAX_SESSIONS (100)
EVC_MAX_AUDIO_BYTES (15728640)
EVC_MAX_SLIDE_BYTES (26214400)
EVC_STT_TIMEOUT_S (30)
EVC_LLM_TIMEOUT_S (20)
EVC_PROVIDER_RETRIES (1)
EVC_RANDOM_SEED (unset; 테스트에서만 사용)
```

기존 `DEBUG_EVC_LOG`도 한 릴리스 동안 deprecated alias로 읽되 `EVC_DEBUG_LOG`가 우선한다.

## 15. 2단계 완료 판정

- 상태 경계, tie, ID, 랜덤성, 점수 계수, Softmax, no-op을 확정했다.
- Action 사건, 파생 임계값, 선택 확률과 레이어 충돌 규칙을 확정했다.
- 발화 위치, 시간 기준, cooldown과 이력 규칙을 확정했다.
- 누락 입력과 외부 서비스 실패 정책을 확정했다.
- 기존 경로/호환 필드를 포함한 v2 요청·응답 및 오류 계약을 확정했다.
- 메모리 세션의 TTL, 용량, token, 단일 worker 제한을 확정했다.

따라서 이후 단계에서 임의의 정책값을 추가하지 않고 도메인 스키마와 구현을 진행할 수 있다. 다음 실제 작업은 3단계인 모듈 구조와 도메인 스키마 정비이다.
