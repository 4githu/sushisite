# sushisite AI 백엔드 수정 기준

**목표:** 현재 서비스 계약을 유지하며 설정한 a명 청중을 만들고, 시간 불일치 위험을 보완하고, 연구용 16개 채점 Qwen을 탈부착 가능한 모듈로 만든다.

이번 산출물은 하네스다. 아래 제품 코드는 앞으로 구현한다. 현재 source의 기능과 구현 목표를 혼동하지 않는다.

## 결정된 제약

1. Unity·sushi-app 파일/규칙 무변경. 필수 외부 필드 추가 금지.
2. 기존 OpenAI 서비스의 10개 보고서 지표/설명 유지. Qwen의 출력/학습/벤치마크 목표는 연구용 16개 Rubric.
3. 청중 수는 PIN-bound template_snapshot의 `audience.audience_count`를 권위 입력으로 사용. count 누락 또는 PIN 없는 기존 호출은 6. 값이 있으면 **strict int 1–50**, bool·float·string은 거부한다. 웹이 실제 number를 전송하므로 새 문자열 관용 규칙이 필요하지 않다.
4. ID는 `audience_01`…`audience_50` 중 세션에 등록된 01…a만 허용. 기존 목록 길이/ID 범위 고정은 이 요청에 한해 변경한다. 질문 수 기본 3·범위 1–5는 청중 수와 별개다.
5. a=6의 기존 layout·seed/RNG·특성·행동 결과를 보존한다. 계산 E/V/C 식·clip catalog·command 해석은 유지한다.
6. 원본 분석 근거 시각과 재생 시계를 분리. 기존 독립 반응 opt-in=false·재시도 계약 유지. 관측되지 않는 Unity 시계/actor 구조는 추측하지 않는다.
7. 제품 코드 → tools import 금지. 연구 core → odi/FastAPI/DB/Unity/web import 금지. CLI 삭제와 운영/연구 core 동작을 분리한다.

## 모듈과 경계

| 경계 | 처리 |
|---|---|
| 웹/PIN → 세션 | 기존 snapshot count → SmartStartOptions → 세션 registry |
| 세션 → 청중 | 실제 a명에 맞는 layout/RNG/특성·ID 검증 |
| update → Evidence | capture/client time·STT/특징·슬라이드/누락 보존 |
| Evidence → 반응 | 이벤트 freshness·관측 가능한 최신 시계·명령 admission |
| Evidence → 연구 Task | 독립 EvidencePack·RubricBundle·AssessmentResult |
| 연구 Task → engine | `fake` / `qwen_local` / 선택적 `openai` |
| 기존 report | 기존 집계+OpenAI 10개 설명. 연구 16개 결과는 내부 저장 |
| 개발 도구 | CLI/Makefile과 이 하네스. 운영에서 역방향 import 금지 |

## 새 내부 인터페이스 · 권장 이름

다른 이름을 택해야 하면 코드 패턴에 맞춰 일관되게 바꾸고 PROGRESS에 이유를 남긴다. 이 하네스의 guard는 아래 제안 이름을 구현됐다고 가정하지 않는다.

- `resolve_audience_count(snapshot: dict | None) -> int`: 누락만 6, 잘못된 값은 ValueError → router에서 기존 입력 오류(422)로 변환.
- `build_audience_layout(count: int) -> tuple[tuple[str, str, str], ...]`: count=6 기존 layout 그대로. row/seat의 기존 enum 의미 유지. Unity world 좌표/새 필수 필드 생성 금지.
- `EvidencePack`: source ID·시간 기준·측정 특징·원전사·누락·coverage·축약 여부. 기존 모델의 평가 문장은 별도 provenance.
- `RubricBundle`: version·정확한 16개 criteria·1–5 Anchor·Policy. 실제 연구자료에서 가져오며 임의 항목 생성 금지.
- `AssessmentEngine.assess(evidence: EvidencePack, rubric: RubricBundle) -> AssessmentResult`: 같은 연구 Task 안에서 엔진 교체. 로컬 가중치 로딩은 수명 동안 재사용.
- `CriterionAssessment`: criterion_id·score(int 1–5/null)·reason·evidence_ids·abstained·abstain_reason. 평가 불가이면 score=null과 사유, 점수를 주면 abstained=false. 참조는 존재하는 Evidence ID여야 한다.
- `AssessmentResult`: schema/rubric/policy/model/prompt/adapter 버전·16개 중복 없는 기준 ID·coverage·추론 metadata. 실제 criterion ID는 RubricBundle의 목록을 따른다.

## 청중 수 세부 규칙

배치 일반화는 backend의 logical row/seat 분류이며 Unity의 새 좌표 규칙이 아니다. a=6은 기존 순서를 보존하고, 기타 수는 순서·row/seat 배정·노트북 대상 비율/수·ACT08 짝 정책을 순수 함수로 문서화한다. 실제 client actor 매핑이 없으면 시각적 좌석 일치까지 완료라고 하지 않는다.

특성 평균은 입력 설정을 보존한다. 홀수는 대칭쌍+중앙값 방식이 가능하다. 인원이 많을 때 모든 특성이 서로 달라야 한다는 조건은 두지 않는다. a=1에서 없는 짝/노트북/청중 ID가 생성되면 안 된다.

## 시간 보완의 한계와 목표

현재 명령은 수락된 client time +.05/.10초여서 STT/평가 후 과거 명령이 될 수 있다. 실제 Unity 수신 시계가 없으면 backend만으로 완전 보정할 수 없다. 서버 monotonic elapsed는 처리시간이며 발표 시계의 정확한 현재값이 아니다. pause 상태를 무시해 더하지 않는다.

따라서 02의 완료는 관측·stale event 검사·clock 정책·재시도·모드 호환·headless 재현에 한정한다. 실제 렌더링 동기화는 별도 관측 대기다. 고정된 30초 수집의 초기 발화 지연을 서버 후처리로 제거했다고 주장하지 않는다.

## 연구 입력 부족

F0/음량(D3), 시간별 머리 방향(D4), 정확한 슬라이드 표시 이력(S4), 외부 사실 자료, recovery의 QA 이력 등이 부족할 수 있다. 기존 음성에서 계산 가능한 특징만 backend에서 추가한다. scalar 시선에서 시계열을 복원하지 않는다. 확보되지 않은 항목은 평가 불가이며 fake 입력으로 실제 품질을 주장하지 않는다.

## 대상 파일

기존: `sushi-fast/odi/EVC/{router,schema,session_store,state_engine,pipeline,reaction_scheduler,command_builder,observability}.py`, 활성 `report_v2/`, 필요한 `odi/db/` 내부 저장 경계.

신규 제안: `sushi-fast/odi/EVC/audience_config.py`, `playback_policy.py`, `assessment_adapter.py`, `sushi-fast/rehear_ai/`와 `sushi-fast/tools/rehear_cli/`, 보조 `sushi-fast/Makefile.ai`.

시간 측정 폴더 `sushi-fast/latency_benchmark_with_outputs/`, `sushi-fast/live_latency_benchmark/`는 case·과거 결과·측정 정의 이전 후 삭제. catalog/운영 관측/제품 반응 시계/제품 테스트는 유지한다.
