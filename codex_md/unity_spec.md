# Unity용 AI 청중 반응 파이프라인 연동 명세

> API 계약 버전: `2.0`  
> 서버 기준 구현: `sushi-fast/odi/EVC/`  
> action mapping 원본: `sushi-fast/odi/EVC/clip_pool.json`

## 1. 연동 흐름

Unity는 한 발표를 하나의 EVC 세션으로 관리한다.

1. 발표 시작 전에 `smart-start`를 한 번 호출한다.
2. 응답의 `session_id`, `session_token`, `seed`, `step=0`, 6명 profile을 발표 종료까지 보관한다.
3. 발화 chunk가 준비될 때마다 현재 `step`을 `expected_step`으로 넣어 `update`를 한 번씩 순차 호출한다.
4. 성공 응답의 `step`, 상태와 명령을 반영한다. 다음 요청은 새 step과 새 `request_id`를 사용한다.
5. 네트워크 응답을 받지 못한 요청은 같은 `request_id`와 같은 payload로 재전송한다.
6. 재연결 시 필요하면 `GET session`으로 현재 step을 복구한다.
7. 발표 종료 시 `DELETE session`을 호출한다.

동일 세션의 update를 병렬 전송하지 않는다. 서버는 세션별로 직렬 처리하며 잘못된 step은 409로 거부한다.

## 2. 공통 규칙

- 전체 경로 prefix: `/odi/xreal_rehear/evc`
- 요청/응답: UTF-8
- 시간 단위: 초(float)
- `client_time_s`: Unity 발표 세션 시작 이후의 monotonic time
- 보호 endpoint header: `X-EVC-Session-Token: <smart-start token>`
- `session_token`은 secret으로 취급하고 로그, PlayerPrefs, 분석 이벤트에 기록하지 않는다.
- Unity는 응답의 `api_version` major가 `2`인지 확인한다. 다른 major면 명령 실행을 중단하고 호환 오류를 표시한다.

## 3. Smart Start

`POST /odi/xreal_rehear/evc/smart-start`  
Content-Type: `multipart/form-data`

| form 필드 | 필수 | 형식/규칙 |
| --- | --- | --- |
| `presentation_title` | 예 | trim 후 1~200자 |
| `topic_interest` | 아니오 | `low/middle/high`, `낮음/중간/높음` 또는 `0.25/0.50/0.75`; 기본 `middle` |
| `prior_knowledge` | 아니오 | 위와 동일; 기본 `middle` |
| `slide_file` | 아니오 | PDF/PPT/PPTX, 최대 25 MiB |
| `seed` | 아니오 | 정수 `0~2147483647`; 생략 시 서버 생성 |

예:

```bash
curl -X POST "${BASE_URL}/odi/xreal_rehear/evc/smart-start" \
  -F "presentation_title=AI 발표" \
  -F "topic_interest=middle" \
  -F "prior_knowledge=high" \
  -F "seed=2026"
```

응답 구조:

```json
{
  "api_version": "2.0",
  "session_id": "9b00d714-1cdc-4f80-a0a9-43603cd649f3",
  "session_token": "opaque-secret-returned-once",
  "seed": 2026,
  "presentation_title": "AI 발표",
  "initial_evc_state": {"E": 0.01, "V": 0.0, "C": 0.49},
  "topic_interest": 0.5,
  "prior_knowledge": 0.75,
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
      "state": {"E": 0.01, "V": 0.0, "C": 0.47}
    }
  ],
  "step": 0,
  "expires_in_s": 7200,
  "slide_count": 0,
  "slides": []
}
```

실제 `audiences` 배열은 항상 6개다.

## 4. 6명 agent와 profile

| agent_id | row | seat | 장면 규칙 |
| --- | --- | --- | --- |
| `audience_01` | front | left | 일반 |
| `audience_02` | front | right | 일반 |
| `audience_03` | middle | left | 일반 |
| `audience_04` | middle | right | 일반 |
| `audience_05` | rear | left | Side Conversation 허용 |
| `audience_06` | rear | right | Side Conversation 허용 |

세션마다 `audience_01~04` 중 1명과 `audience_05~06` 중 1명, 정확히 2명이 `has_laptop=true`다. `responsiveness`, `expressivity`, `critical_bias`, 채널 선호도는 seed로 고정된다. Unity는 smart-start 응답의 profile을 진실의 원천으로 사용하며 자체 재생성하지 않는다.

상태 의미:

- `E`: Engagement
- `V`: Evaluative Valence
- `C`: Cognitive Clarity
- 모든 상태 범위는 `[-1.0, 1.0]`
- `evc_state`는 6명 상태의 평균이고 실제 캐릭터 구동에는 각 audience의 `state`와 결정/명령을 사용한다.

## 5. Update 요청

`POST /odi/xreal_rehear/evc/update`  
Content-Type: `multipart/form-data`  
Header: `X-EVC-Session-Token` 필수

| form 필드 | 필수 | 형식/규칙 |
| --- | --- | --- |
| `session_id` | 예 | smart-start의 UUID |
| `request_id` | 예 | 요청마다 새 UUID; retry 시 동일 UUID |
| `expected_step` | 예 | Unity가 마지막으로 확정한 현재 step, `>=0` |
| `client_time_s` | 예 | 발표 시작 기준 monotonic seconds, `>=0` |
| `audio` | 예 | WAV/MP3/M4A/OGG/WebM, 최대 15 MiB, 빈 파일 금지 |
| `current_slide_index` | 아니오 | 기본 0; slide가 있으면 유효 index |
| `utterance_position` | 아니오 | 아래 enum, 기본 `during_speech` |
| `language` | 아니오 | BCP-47 형식, 기본 `ko-KR` |
| `gaze_delivery_score` | 아니오 | `[-1,1]`; 미제공 시 0과 warning/missing input |
| `slide_reference` | 아니오 | boolean, 기본 false |
| `event_signals` | 아니오 | JSON object를 form string으로 전달 |

`utterance_position` enum:

- `during_speech`
- `utterance_boundary`
- `silence_or_pause`
- `slide_transition`

`event_signals`가 허용하는 key와 값은 다음과 같다. 모든 strength는 `[0,1]`이다.

```json
{
  "information_dense": 0.8,
  "slide_reference": 1.0,
  "repeated_disengagement": 0.0,
  "low_arousal": 0.0,
  "long_static_posture": 0.0,
  "tension": 0.2,
  "nearby_interaction": 0.0
}
```

예:

```bash
curl -X POST "${BASE_URL}/odi/xreal_rehear/evc/update" \
  -H "X-EVC-Session-Token: ${SESSION_TOKEN}" \
  -F "session_id=${SESSION_ID}" \
  -F "request_id=40af1bf8-574b-42c5-a710-b3dd4de883b7" \
  -F "expected_step=0" \
  -F "client_time_s=12.5" \
  -F "utterance_position=utterance_boundary" \
  -F "current_slide_index=0" \
  -F "gaze_delivery_score=0.4" \
  -F 'event_signals={"slide_reference":1.0}' \
  -F "audio=@segment.wav;type=audio/wav"
```

## 6. Update 응답

```json
{
  "api_version": "2.0",
  "request_id": "40af1bf8-574b-42c5-a710-b3dd4de883b7",
  "session_id": "9b00d714-1cdc-4f80-a0a9-43603cd649f3",
  "step": 1,
  "accepted_client_time_s": 12.5,
  "latest_speech": "발표 구간 전사문",
  "current_slide_index": 0,
  "speech_metrics": {
    "duration_s": 3.2,
    "word_count": 12,
    "speech_rate_wps": 3.75,
    "pause_count": 1,
    "pause_total_s": 0.4,
    "filler_count": 0,
    "repeated_word_count": 0,
    "avg_confidence": 0.91,
    "vocal_delivery_score": 0.3
  },
  "evaluation": {
    "move": "Purpose",
    "content": {
      "organization": 0.4,
      "supporting_material": 0.2,
      "central_message": 0.5,
      "cer_validity": 0.1
    },
    "delivery": {
      "language_clarity": 0.5,
      "vocal_delivery": 0.3,
      "gaze_delivery": 0.4,
      "slide_speech_alignment": 0.2
    },
    "segment_note": "요점을 소개함",
    "short_reason": "구성과 전달이 비교적 명확함",
    "missing_inputs": [],
    "confidence": 0.8
  },
  "delta": {
    "content": {"E": 0.45, "V": 0.3, "C": 1.0},
    "delivery": {"E": 0.95, "V": 0.45, "C": 0.7},
    "common": {"E": 0.725, "V": 0.3675, "C": 0.85}
  },
  "evc_state": {"E": 0.73, "V": 0.37, "C": 1.0},
  "behavior": null,
  "audiences": [
    {
      "agent_id": "audience_01",
      "previous_state": {"E": 0.01, "V": 0.0, "C": 0.47},
      "sensitivity": {"E": 1.0, "V": 1.0, "C": 1.0},
      "state": {"E": 0.735, "V": 0.3675, "C": 1.0},
      "dominant_axis": "C",
      "direction": "positive",
      "core_behavior": {
        "behavior_id": "CT_01",
        "variation_id": "CT_01.comprehension_nod",
        "probability": 0.42
      },
      "action_overlay": null,
      "no_op_reason": null
    }
  ],
  "commands": [
    {
      "agent_id": "audience_01",
      "start_time": 12.55,
      "layer": "Body",
      "action_id": "body.comprehension_nod",
      "duration": 1.2,
      "sync_group": "8115e684-20eb-4d38-aef1-eeef5c2481e5",
      "selected_behavior_id": "CT_01",
      "selected_variation_id": "CT_01.comprehension_nod",
      "priority": 50,
      "blend_mode": "override",
      "intensity": 0.48
    }
  ],
  "warnings": [],
  "no_op_reason": null,
  "diagnostics": null
}
```

예시는 구조 설명용이며 점수와 선택 결과는 실제 입력 및 seed에 따라 달라진다. `audiences`는 항상 6개지만 `commands`는 유효한 no-op에서 비어 있을 수 있다. `behavior`는 `audience_01`용 레거시 축약 필드이므로 신규 Unity 구현은 `audiences`와 `commands`를 사용한다.

빈 STT transcript는 상태와 step을 갱신하지 않고 `no_op_reason="empty_transcript"`를 반환한다. 같은 `request_id`로 다시 요청하면 캐시된 동일 응답이 반환된다.

## 7. Unity 명령 실행 계약

각 `UnityCommand`를 다음 순서로 처리한다.

1. `agent_id`로 대상 캐릭터를 찾는다.
2. `start_time`을 Unity 발표 clock과 비교해 예약한다. 이미 지났다면 즉시 실행하되 순서는 보존한다.
3. 같은 `sync_group`의 명령은 동일 프레임에 시작한다.
4. `layer`에 따라 Face/Body/GazeHead 컨트롤러로 전달한다.
5. 동일 agent/layer/start time 충돌은 높은 `priority`를 실행한다.
6. `duration` 이후 Action override를 끝내고 현재 Core stable 상태로 0.20초 cross-fade한다.

필드 규칙:

| 필드 | Unity 처리 |
| --- | --- |
| `agent_id` | `audience_01~06` GameObject lookup key |
| `start_time` | 세션 기준 절대 초; wall clock이나 Unix time이 아님 |
| `layer` | `Face`, `Body`, `GazeHead` 중 하나 |
| `action_id` | 아래 표의 논리 ID; Unity asset/state에 매핑 |
| `duration` | 권장 재생/유지 시간(초) |
| `sync_group` | 한 variation의 다중 layer 동시 시작 그룹 |
| `selected_behavior_id` | 상위 행동군 ID |
| `selected_variation_id` | 실제 변형 및 cooldown 추적 ID |
| `priority` | Core `50`, Action `100` |
| `blend_mode` | `override` 또는 `additive` |
| `intensity` | 해당 agent expressivity, `[0,1]`; animation/BlendShape 배율 |

start offset:

| utterance position | `client_time_s` 대비 offset |
| --- | --- |
| `during_speech` | `+0.10s` |
| `utterance_boundary` | `+0.05s` |
| `silence_or_pause` | `+0.10s` |
| `slide_transition` | `+0.05s` |

서버가 variation cooldown과 반복 억제를 관리하므로 Unity가 별도 후보를 재선택하면 안 된다. 단, 네트워크 중복 명령 방지를 위해 Unity는 최근 처리한 `(request_id, sync_group, agent_id, action_id)`를 세션 동안 기억하는 것이 좋다.

### Layer 중재

- Core: priority 50
- Action: priority 100
- 같은 layer에서 Action `override`가 Core를 대체한다.
- 충돌하지 않는 Core layer는 계속 재생한다.
- `additive`는 표에 표시된 Face micro-expression에만 허용한다.
- GazeHead 충돌은 Action target 우선이다.
- Body/GazeHead의 실제 AvatarMask와 Face additive weight는 Unity 측에서 구성한다.

## 8. action ID 매핑표

표의 `O`는 `override`, `A`는 `additive`다. 이 ID는 서버-Unity 계약 ID이며 오른쪽 실제 Animator state, BlendShape clip, IK preset 이름은 Unity 팀이 등록한다. 여러 layer가 한 variation에 있으면 같은 `sync_group`으로 동시에 실행한다.

| variation_id | Unity mapping (`layer:action_id / duration / mode`) |
| --- | --- |
| `BL_01.neutral_listening` | Body:`body.neutral_listening` / 2.0 / O; GazeHead:`gaze_head.neutral_listening` / 2.0 / O |
| `BL_02.neutral_gaze_shift` | GazeHead:`gaze_head.neutral_gaze_shift` / 1.8 / O |
| `BL_03.quiet_stable_posture` | Body:`body.quiet_stable_posture` / 3.0 / O |
| `AL_01.stable_attention` | Body:`body.stable_attention` / 2.0 / O; GazeHead:`gaze_head.stable_attention` / 2.0 / O |
| `AL_01.active_following` | Body:`body.active_following` / 1.4 / O; GazeHead:`gaze_head.active_following` / 1.4 / O |
| `AL_01.agreement_nod` | Body:`body.agreement_nod` / 1.2 / O |
| `AL_02.attentive_slide_check` | GazeHead:`gaze_head.attentive_slide_check` / 1.6 / O |
| `AL_02.slight_head_tilt_check` | Body:`body.slight_head_tilt_check` / 1.4 / O; Face:`face.slight_head_tilt_check` / 1.4 / A |
| `AL_03.low_engagement_positive` | Body:`body.low_engagement_positive` / 2.5 / O; GazeHead:`gaze_head.low_engagement_positive` / 2.5 / O |
| `AL_03.passive_acceptance` | Body:`body.passive_acceptance` / 3.0 / O; Face:`face.passive_acceptance` / 3.0 / O |
| `EM_01.positive_monitoring` | Face:`face.positive_monitoring` / 2.2 / O; GazeHead:`gaze_head.positive_monitoring` / 2.2 / O; Body:`body.positive_monitoring` / 2.2 / O |
| `EM_01.approving_smile` | Face:`face.approving_smile` / 1.5 / A; GazeHead:`gaze_head.approving_smile` / 1.5 / O |
| `EM_01.soft_approval_nod` | Body:`body.soft_approval_nod` / 1.3 / O; Face:`face.soft_approval_nod` / 1.3 / A |
| `EM_02.positive_but_uncertain` | Face:`face.positive_but_uncertain` / 2.0 / O; GazeHead:`gaze_head.positive_but_uncertain` / 2.0 / O |
| `EM_02.smile_with_slide_check` | Face:`face.smile_with_slide_check` / 1.8 / A; GazeHead:`gaze_head.smile_with_slide_check` / 1.8 / O |
| `EM_02.curious_head_tilt` | Body:`body.curious_head_tilt` / 1.5 / O; Face:`face.curious_head_tilt` / 1.5 / A |
| `EM_04.weak_positive_low_clarity` | Face:`face.weak_positive_low_clarity` / 2.5 / O; Body:`body.weak_positive_low_clarity` / 2.5 / O; GazeHead:`gaze_head.weak_positive_low_clarity` / 2.5 / O |
| `EM_04.fading_approval` | Face:`face.fading_approval` / 3.0 / O; Body:`body.fading_approval` / 3.0 / O |
| `EM_05.cold_monitoring` | Face:`face.cold_monitoring` / 2.2 / O; GazeHead:`gaze_head.cold_monitoring` / 2.2 / O; Body:`body.cold_monitoring` / 2.2 / O |
| `EM_05.skeptical_monitoring` | Face:`face.skeptical_monitoring` / 2.0 / O; Body:`body.skeptical_monitoring` / 2.0 / O |
| `EM_05.restrained_disagreement` | Body:`body.restrained_disagreement` / 1.5 / O; Face:`face.restrained_disagreement` / 1.5 / O |
| `EM_07.disengaged_negative` | Face:`face.disengaged_negative` / 2.8 / O; GazeHead:`gaze_head.disengaged_negative` / 2.8 / O; Body:`body.disengaged_negative` / 2.8 / O |
| `EM_07.gaze_withdrawal_negative` | GazeHead:`gaze_head.gaze_withdrawal_negative` / 2.2 / O; Body:`body.gaze_withdrawal_negative` / 2.2 / O |
| `EM_07.closed_posture_negative` | Face:`face.closed_posture_negative` / 3.5 / O; Body:`body.closed_posture_negative` / 3.5 / O |
| `CT_01.stable_comprehension` | GazeHead:`gaze_head.stable_comprehension` / 2.2 / O; Body:`body.stable_comprehension` / 2.2 / O |
| `CT_01.comprehension_nod` | Body:`body.comprehension_nod` / 1.2 / O |
| `CT_01.slide_speaker_tracking` | GazeHead:`gaze_head.slide_speaker_tracking` / 1.8 / O |
| `CT_02.understood_but_reserved` | Face:`face.understood_but_reserved` / 2.3 / O; GazeHead:`gaze_head.understood_but_reserved` / 2.3 / O; Body:`body.understood_but_reserved` / 2.3 / O |
| `CT_02.closed_comprehension` | Face:`face.closed_comprehension` / 2.5 / O; Body:`body.closed_comprehension` / 2.5 / O |
| `CT_02.limited_nod_reserved` | Face:`face.limited_nod_reserved` / 1.4 / O; Body:`body.limited_nod_reserved` / 1.4 / O |
| `CT_03.understood_low_engagement` | GazeHead:`gaze_head.understood_low_engagement` / 2.5 / O; Body:`body.understood_low_engagement` / 2.5 / O |
| `CT_03.delayed_gaze_return` | GazeHead:`gaze_head.delayed_gaze_return` / 1.8 / O |
| `CT_05.trying_to_understand` | Face:`face.trying_to_understand` / 2.2 / O; GazeHead:`gaze_head.trying_to_understand` / 2.2 / O |
| `CT_05.confused_glance` | GazeHead:`gaze_head.confused_glance` / 1.7 / O; Face:`face.confused_glance` / 1.7 / A |
| `CT_05.head_tilt_recheck` | Body:`body.head_tilt_recheck` / 1.5 / O; Face:`face.head_tilt_recheck` / 1.5 / A |
| `CT_06.confused_skeptical` | Face:`face.confused_skeptical` / 2.4 / O; Body:`body.confused_skeptical` / 2.4 / O |
| `CT_06.skeptical_slide_check` | Face:`face.skeptical_slide_check` / 1.8 / A; GazeHead:`gaze_head.skeptical_slide_check` / 1.8 / O |
| `CT_06.furrowed_head_tilt` | Face:`face.furrowed_head_tilt` / 1.6 / O; Body:`body.furrowed_head_tilt` / 1.6 / O |
| `CT_07.lost_understanding` | GazeHead:`gaze_head.lost_understanding` / 2.6 / O; Body:`body.lost_understanding` / 2.6 / O |
| `CT_07.off_target_gaze` | GazeHead:`gaze_head.off_target_gaze` / 2.0 / O |
| `CT_07.low_response_flat` | Face:`face.low_response_flat` / 3.0 / O; Body:`body.low_response_flat` / 3.0 / O |
| `CT_08.strong_confusion_disengagement` | Face:`face.strong_confusion_disengagement` / 2.8 / O; GazeHead:`gaze_head.strong_confusion_disengagement` / 2.8 / O; Body:`body.strong_confusion_disengagement` / 2.8 / O |
| `CT_08.gaze_withdrawal_confusion` | GazeHead:`gaze_head.gaze_withdrawal_confusion` / 2.3 / O; Body:`body.gaze_withdrawal_confusion` / 2.3 / O |
| `CT_08.collapsed_posture_confusion` | Face:`face.collapsed_posture_confusion` / 3.5 / O; Body:`body.collapsed_posture_confusion` / 3.5 / O |
| `ACT_01.laptop_typing` | Body:`body.laptop_typing` / 4.0 / O; GazeHead:`gaze_head.laptop_typing` / 4.0 / O |
| `ACT_02.photo_slide` | Body:`body.photo_slide` / 3.0 / O; GazeHead:`gaze_head.photo_slide` / 3.0 / O |
| `ACT_03.device_checking` | Body:`body.device_checking` / 4.0 / O; GazeHead:`gaze_head.device_checking` / 4.0 / O |
| `ACT_04.drowsy_nod` | Face:`face.drowsy_nod` / 3.0 / O; Body:`body.drowsy_nod` / 3.0 / O |
| `ACT_05.seat_adjust` | Body:`body.seat_adjust` / 2.0 / O |
| `ACT_06.small_stretch` | Body:`body.small_stretch` / 3.0 / O |
| `ACT_07.self_contact` | Face:`face.self_contact` / 3.0 / O; Body:`body.self_contact` / 3.0 / O |
| `ACT_08.side_conversation` | Face:`face.side_conversation` / 4.0 / O; Body:`body.side_conversation` / 4.0 / O; GazeHead:`gaze_head.side_conversation` / 4.0 / O |

`clip_pool.json` 변경 시 Unity mapping table도 함께 갱신하고, CI에서 모든 `variation_id`, `layer`, `action_id`의 완전성을 비교해야 한다.

## 9. Session 조회와 종료

조회:

```http
GET /odi/xreal_rehear/evc/sessions/{session_id}
X-EVC-Session-Token: <token>
```

현재 `step`, 6명 상태, 세션 시간, slide와 warning을 반환한다. token, RNG 상태, 전체 행동 이력, 서버 파일 경로는 반환하지 않는다.

종료:

```http
DELETE /odi/xreal_rehear/evc/sessions/{session_id}
X-EVC-Session-Token: <token>
```

성공은 `204 No Content`다. Unity는 로컬 token과 세션 캐시를 즉시 폐기한다.

## 10. 재시도, 재연결과 시간 복구

- update 전 UUID `request_id`를 만들고 응답이 확정될 때까지 보관한다.
- timeout/연결 단절은 같은 request ID, expected step, audio와 context로 재전송한다.
- 동일 request ID는 서버가 최근 32개 범위에서 원래 응답을 반환하며 step을 중복 증가시키지 않는다.
- 409 `step_conflict` 시 자동으로 새 update를 만들지 말고 GET session으로 서버 step을 읽어 로컬 queue와 조정한다.
- `client_time_s`가 직전 accepted time보다 최대 0.25초 작으면 서버가 직전 시간으로 보정한다. 0.25초보다 크게 역행하면 409다.
- 프로세스 재시작 시 메모리 세션은 사라진다. 404가 반환되면 기존 세션을 복원할 수 없으므로 새 smart-start 후 청중 장면을 초기화한다.
- 세션 TTL 기본값은 마지막 정상 접근 후 7200초다.

## 11. 오류 처리

오류 body의 핵심은 일반적으로 `detail.code`와 `detail.message`다. FastAPI 자체 form/schema 검증 오류는 표준 422 배열 형태일 수 있다.

| HTTP | code | Unity 동작 |
| --- | --- | --- |
| 401 | `invalid_session_token` | 세션 사용 중단; token 재확인 또는 새 세션 |
| 404 | `session_not_found` | 만료/재시작으로 간주하고 새 smart-start |
| 409 | `step_conflict` | GET session으로 step 재동기화 |
| 409 | `client_time_regression` | Unity session clock 점검; 현재 시간으로 새 요청 |
| 413 | `payload_too_large` | chunk 크기를 줄여 새 request ID로 요청 |
| 415 | `unsupported_media_type` | 지원 audio/slide 형식으로 변환 |
| 422 | `validation_error` 또는 FastAPI validation | enum/range/form 수정; 동일 잘못된 요청 반복 금지 |
| 429 | `session_capacity_exceeded` | backoff 후 재시도 또는 불필요 세션 종료 |
| 502 | `stt_provider_error`, `evaluation_provider_error` | 상태는 미변경; 동일 request ID로 제한적 retry |
| 500 | `internal_pipeline_error` | 상태 미확정으로 취급; 로깅 후 제한적 retry |

외부 provider 실패와 내부 처리 실패는 성공 commit 전에 중단되므로 서버 상태·이력·step을 갱신하지 않는다.

## 12. 운영 설정과 제약

서버 설치 및 실행 예:

```powershell
python -m pip install -r sushi-fast/requirements-evc.txt
Set-Location sushi-fast
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

필수 환경 변수:

- `OPENAI_API_KEY`
- `DEEPGRAM_API_KEY`

주요 선택 변수와 기본값:

| 환경 변수 | 기본값 |
| --- | --- |
| `OPENAI_EVC_MODEL` | `gpt-4.1-nano` |
| `DEEPGRAM_PRIMARY_MODEL` | `nova-3` |
| `EVC_SESSION_TTL_S` | `7200` |
| `EVC_MAX_SESSIONS` | `100` |
| `EVC_MAX_AUDIO_BYTES` | `15728640` |
| `EVC_MAX_SLIDE_BYTES` | `26214400` |
| `EVC_STT_TIMEOUT_S` | `30` |
| `EVC_LLM_TIMEOUT_S` | `20` |
| `EVC_PROVIDER_RETRIES` | `1` |
| `EVC_INCLUDE_DIAGNOSTICS` | `false` |
| `EVC_DEBUG_LOG` | `false` |

현재 저장소는 프로토타입 메모리 store다. 반드시 단일 worker로 실행해야 하며 프로세스 재시작, 다중 worker, 수평 확장 사이에 세션이 공유되지 않는다. 운영 확장 시 동일한 token/lock/step/idempotency 원자성을 보장하는 공유 저장소가 필요하다.

## 13. Unity 통합 승인 체크리스트

- [ ] `audience_01~06`이 장면 GameObject에 유일하게 매핑된다.
- [ ] smart-start의 row/seat/profile/state를 6명 모두 적용한다.
- [ ] token을 메모리에서만 보호하고 로그/분석/PlayerPrefs에 남기지 않는다.
- [ ] 하나의 세션에서 update를 순차 전송하고 step을 성공 응답 후에만 증가시킨다.
- [ ] request ID 기반 retry와 GET 기반 reconnect를 구현한다.
- [ ] Unity session monotonic clock과 `start_time`의 기준이 일치한다.
- [ ] 표의 모든 action ID가 Animator/BlendShape/GazeHead asset 또는 preset에 매핑된다.
- [ ] 같은 sync group의 layer가 동일 프레임에 시작한다.
- [ ] Core 50/Action 100 충돌과 Face additive 규칙을 구현한다.
- [ ] Action 종료 후 현재 Core stable 상태로 0.20초 cross-fade한다.
- [ ] 빈 `commands`와 audience별 `no_op_reason`을 정상 상태로 처리한다.
- [ ] 401/404/409/413/415/422/429/502/500 UX와 retry 한도를 구현한다.
- [ ] 4개 발화 위치를 실제 장면에서 재생하고 6명 다양성을 확인한다.
- [ ] 8개 Action을 각 scene gate와 함께 실제 asset으로 검증한다.
- [ ] 실제 OpenAI/Deepgram을 포함한 목표 환경에서 p50/p95 지연, timeout 및 audio chunk 크기를 측정한다.
- [ ] 서버 `clip_pool.json`과 Unity mapping manifest의 ID 차이를 빌드 전에 자동 검사한다.

서버 측 headless 계약 리허설과 66개 자동 테스트는 통과했다. 실제 Animator, BlendShape, Gaze/Head IK 에셋 재생과 시각적 승인 항목은 Unity 프로젝트에서 완료해야 한다.
