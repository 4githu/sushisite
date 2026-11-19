# Aura modality following 저장 경합 계약

합성 SQLite API 검증용. 운영 데이터, 발송, 스케줄 활성화와 무관합니다.

1. `GET /api/personal/aura/rounds/{id}/modality-preview?scope=following`의 `rounds`를 사용자에게 보여주고, 같은 응답의 `roundState` 문자열을 보존합니다. 각 회차의 `id`, `modality`, `startTime`, `endTime`, `schoolId`, `targets` 등을 명시적으로 확인합니다. `roundState`는 프리뷰 당시 회차 내용의 불투명한 SHA-256 비교값이지 인증/권한 토큰이나 시간 기반 잠금이 아닙니다. 대상 리포트 편집 내용은 비교에서 제외됩니다.
2. 확인 뒤 `PATCH /api/personal/aura/rounds/{id}`에 `{ "scope": "following", "modality": "in_person", "expected_round_ids": [/* 프리뷰 rounds 순서의 id */], "expected_round_state": "/* 프리뷰 roundState */" }`를 보냅니다. 모드 값은 `in_person`, `remote`, `unverified` 중 하나입니다.
3. ID 또는 내용이 달라지거나 기대값이 빠지면 **409**, `detail.message`와 현재 `affectedRoundIds`를 돌려주며 쓰지 않습니다. 반드시 프리뷰를 새로 받아 재확인해야 합니다. 기존 기대값으로 무조건 재시도하지 않습니다. 성공 시 `affectedRoundIds` 확인 후 GET 재조회합니다.

내용 비교는 회차 번호/학교/모드/시각/메모/상태/정산 입력값과 대상 ID·이름·순서를 포함합니다. 저장은 `BEGIN IMMEDIATE`의 같은 쓰기 트랜잭션에서 비교한 뒤 수행하므로 프리뷰→PATCH 사이의 동일 ID 편집도 차단됩니다. `scope=this`의 modality PATCH는 기존처럼 기대값 없이 동작하고, modality 없는 일반 PATCH와 시리즈 생성/일반 scope 경로는 새 검사 대상이 아닙니다. 단일 회차 안의 혼합 방식 학생 정책은 별도 결정 전 자동 발송에 사용하지 않습니다.
