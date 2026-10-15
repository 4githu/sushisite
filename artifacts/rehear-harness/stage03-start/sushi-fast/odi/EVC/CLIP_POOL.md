# EVC Clip Pool 및 Unity 매핑

`clip_pool.json`은 `reaction-rule.md` 9장의 기계 판독 가능한 원본이다.

- Core Behavior variation: 44개
- Action Clip variation: 8개 (`ACT_01`~`ACT_08`)
- 전체 고유 `variation_id`: 52개
- 명세의 중복 `clip_id`는 `behavior_id`로 보존하고 `<behavior_id>.<variation_name>`을 고유 `variation_id`로 사용한다.
- 표의 `Head` 동작은 Body animation으로, `Gaze·Head`는 GazeHead script/IK layer로 정규화했다.
- Face/Body/GazeHead 각 layer는 `<namespace>.<variation_name>` Unity 계약 action ID를 가진다.
- 표의 `Slide reference`는 `requires_slide_reference` context gate로 분리했다.
- 복합 `또는` 상태는 `trigger_conditions` 또는 `state_gates` 배열의 대안 조건으로 표현한다.
- duration과 `expressivity_target`은 `reaction-rule_stage2_contract.md`의 프로토타입 정책에 따라 고정했다.

## 데이터 필드

Core:

```text
behavior_id, variation_id, parent_group, trigger_conditions,
utterance_positions, requires_slide_reference, channels, cooldown_s,
expressivity_target, motion_class, critical, unity_actions
```

Action:

```text
behavior_id, variation_id, event_triggers, state_gates,
utterance_positions, requires_slide_reference, scene_gate, channels,
cooldown_s, expressivity_target, unity_actions
```

## Unity mapping 사용법

각 variation의 `unity_actions`가 권위 있는 mapping table이다. 항목마다 다음 값이 있다.

```json
{
  "layer": "Body",
  "action_id": "body.comprehension_nod",
  "duration": 1.2,
  "blend_mode": "override"
}
```

`blend_mode`가 생략되면 `override`다. Face micro-expression 중 일부만 `additive`로 명시된다. Unity 실제 Animator/BlendShape 자산은 계약 `action_id`에 매핑하며 서버 JSON의 ID를 자산명에 맞춰 변경하지 않는다.

## 로딩과 실패 처리

`clip_pool.load_clip_pool()`은 JSON을 Pydantic `ClipPoolCatalog`로 검증하고 다음 조건을 강제한다.

- Core 44개와 Action 8개
- variation ID 전역 유일성
- `ACT_01`~`ACT_08` 정확한 포함
- behavior/variation namespace 일치
- 허용 enum/range
- 선언 channel과 Unity action layer의 정확한 일치
- Unity action namespace와 layer 일치

애플리케이션 시작 시 `validate_default_clip_pool()`을 호출하여 잘못된 배포 데이터를 요청 처리 전에 탐지한다.
