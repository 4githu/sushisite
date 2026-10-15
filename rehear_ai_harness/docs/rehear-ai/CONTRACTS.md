# 유지할 계약과 명시적 변경

## 외부 계약

| 항목 | 유지 | 이번 변경 |
|---|---|---|
| API | `/odi/xreal_rehear/evc` prefix·기존 route·multipart/JSON 필드·token·오류 의미 | 새 필수 필드 없음 |
| 요청 순서 | request_id·expected_step·step/time·권한·idempotency | 동일 ID 재시도 결과의 명령을 retime하지 않음 |
| 청중 | E/V/C 값 범위·프로필/상태 필드·seed 결정성 | snapshot count a명, 유효 ID 01…a |
| 명령 | agent_id/start_time/layer/action_id/duration/sync_group/selected_behavior_id/selected_variation_id/priority/blend_mode/intensity | clock provenance·freshness는 내부 처리 |
| clip | catalog 44 core variation·8 action, ACT_01…ACT_08와 기존 mapping | catalog 자체 변경 없음 |
| 질문 | 총수 기본3(1–5)·순서/id/order/source_steps·답변/다음 질문·TTS | 선택 청중 ID는 세션 registry 검사 |
| 보고서 | presentation-report-v2·content5+delivery5·0–100/null·기존 화면 해석 | 미측정/근거/QA 복구의 backend 의미 보완 |
| Firebase | PIN/page_1/page_2/page_3/status·기존 슬라이드/완료 조회 | audience_scale은 기존 값 |
| 모드 | independent_reactions=false 기본값 | 실제 소비자 확인 없이 true 전환 금지 |

**고정 6명은 유지 대상이 아니다.** ID 정규식/응답 cardinality는 count 요구에 맞게 변경한다. element schema만 50명까지 열고 세션 membership 검사를 생략하면 안 된다.

## 공개 보고서의 정확한 ID 순서

- content: message_clarity, structure_flow, evidence_use, claim_evidence_link, vocabulary_expression
- delivery: gaze, speech_rate, pronunciation, filler_words, time_management

연구 Qwen은 이 10개를 생성할 의무가 없다. 연구 점수 1–5를 0–100으로 기계 변환하거나 16개를 10개로 임의 평균하지 않는다. comparison 위치와 label/rank_label/status의 기존 frontend 규칙도 바꾸지 않는다.

## source에서 확인된 결함과 별도 보완

- 캐시가 model 문자열+payload를 사용해 다른 provider 결과를 공유할 수 있다. provider/model/adapter/prompt/Rubric/Policy/추론 설정 identity를 반영한다.
- 시선 누락의 실시간 중립 0.0을 보고서에서 50점으로 해석한다. 실시간 식은 유지하고 보고서 null/coverage 정책을 검증한다.
- score=null인 pronunciation에 측정된 것처럼 설명을 덮어쓰지 않는다. 존재하는 evidence ID와 실제 지지를 구분해 검증한다.
- recovery에서 QA가 복원되지 않는다. 내부 지속 저장/순서/권한/idempotency가 필요하다.
- 메모리 step 전진 후 DB 실패 시 상태 불일치 위험이 있다. 저장/commit/cache 순서의 실패 주입 검사가 필요하다.

보고서의 OpenAI key gate/generator 고정은 기존 서비스 결합이다. 연구 Qwen에 10개 설명 provider를 구현하게 만드는 이유로 쓰지 않는다.

## guard가 실제 확인하는 범위

프론트/Unity 파일·catalog hash, E/V/C 핵심 5개 함수의 AST, 기존 route 집합, protected 파일의 추가/삭제, 운영→tools 및 연구 core→서비스 import의 정적 의존을 검사한다. 계산식의 다른 helper 변경·동적 import·route 세부 권한·응답의 모든 의미까지 증명하지 못한다. 제품 테스트와 diff 검토가 필수다.
