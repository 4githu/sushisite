# Re:hear AI 수정 작업 진입점

이 파일을 읽는 작업자는 sushisite의 **기존 백엔드**를 수정한다. 본 묶음 자체는 패치가 아니며, 사용자가 지정한 단계만 구현한다. 진행 기록에 계획을 완료로 소급하지 않는다.

1. 상위/루트/수정 경로의 기존 `AGENTS.md`, `docs/rehear-ai/AGENT_RULES.md`를 읽는다.
2. `SPEC.md`, `CONTRACTS.md`, `PROGRESS.md`와 이번 단계 계획을 읽는다.
3. `git status --short`, `git rev-parse HEAD`를 확인하고 사용자 변경을 보존한다. Git이 없는 ZIP이라면 그 사실을 기록하고 해시 baseline을 사용한다.
4. `python3 tools/rehear_harness.py doctor`로 환경을 확인한다. 부족한 개발 의존성만 기존 프로젝트의 설치 방식으로 해결하며, dependency 설치 실패를 테스트 성공으로 바꾸지 않는다.
5. 제품 수정 전에 `capture`한다. baseline이 이미 있으면 다시 만들지 않고 `guard`로 비교한다.
6. 실패 재현 → 최소 구현 → 새 테스트 → 기존 회귀 → guard → 진행 기록 순서로 수행한다. API/GPU/마이크 없이 가능한 검증부터 한다.

| 단계 | 계획 | 결과 |
|---|---|---|
| 01 | `docs/rehear-ai/plans/01-audience-count.md` | 기존 count 입력이 a명 세션으로 연결 |
| 02 | `docs/rehear-ai/plans/02-playback-clock.md` | 시간 근거/재생 분리·오래된 이벤트/시계 검증 |
| 03 | `docs/rehear-ai/plans/03-research-assessment.md` | 16개 연구 평가용 독립 Qwen 모듈·터미널 실행 |
| 04 | `docs/rehear-ai/plans/04-integrity-cleanup.md` | 기존 보고서 보완·복구·명령 도구·임시 폴더 정리 |

## 이번 작업에서 특히 틀리면 안 되는 것

- 청중 수는 이미 웹 `audience.audience_count`와 PIN의 `template_snapshot`에 있다. Firebase `page_3.audience_scale`도 기존 게시 값이다. 새 프론트 요청을 만들지 않는다.
- Qwen은 **16개 연구 Rubric**용이다. 기존 OpenAI **10개 보고서 설명**을 Qwen의 필수 출력으로 만들지 않는다.
- Unity·웹 코드는 수정하지 않는다. 명령 필드·layer/action·시간 단위·재시도 의미를 유지한다. 청중 수/유효 ID는 a명으로 확장하는 명시적 예외다.
- 30초 수집+분석 지연을 백엔드만으로 없앴다고 주장하지 않는다. clock 관측이 없으면 관측 불가로 기록한다.
- 기존 3개 provider seam과 서비스의 기본 OpenAI를 유지한다. 연구 모듈 추가로 `/update`나 `/finish`의 기본 모델을 바꾸지 않는다.
- 같은 request_id 재응답의 명령 시각을 다시 계산하지 않는다. 분석 근거 시각을 애니메이션 보정 때문에 덮어쓰지 않는다.
- `clip_pool.json`, 운영 반응 시계·STT timestamp·관측·테스트는 삭제 대상이 아니다.
- 전체 04 완료 전, 또는 case/과거 결과/측정 정의 이전 검증 전에는 benchmark 폴더를 삭제하지 않는다.

## 끝날 때 보고할 내용

무엇을 바꿨는지 → 실제 실행한 명령과 성공/실패/skip → 보호 검사 → 미검증/외부 자료 필요 → 다음 단계. `ACCEPTANCE.md`와 `PROGRESS.md`를 사실에 맞게 갱신한다. Git 커밋/PR/배포는 현재 사용자 지시와 환경의 정책을 따른다. 하네스 문서만 작성했거나 fake provider만 통과한 것을 제품/실모델 완료라고 말하지 않는다.
