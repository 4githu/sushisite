# Codex 작업 규칙

## 증거와 변경 범위

- 기준 문서: `sources/notion-ai-design.md`, `sources/notion-evidence.md`. 이 스냅샷은 2026-10-15 기준이며 현재 코드가 다르면 실제 함수/호출 경로를 먼저 확인하고 차이를 기록한다.
- 파일 탐색은 `rg`/`rg --files` 우선. 비밀키·실사용자 음성·전사·토큰을 출력/새 fixture로 복사하지 않는다. 합성 fixture를 사용한다.
- 기존 변경을 reset/clean/덮어쓰기하지 않는다. unrelated 리팩토링·프론트·Unity·clip catalog 변경은 하지 않는다.
- 기존 테스트를 삭제하거나 assertion을 느슨하게 해 통과시키지 않는다. ‘정확히 6명’ assertion 중 요구사항과 충돌하는 것만 a명 계약으로 바꾸고 a=6 회귀는 남긴다.
- 깨진 보호 검사를 baseline 재생성이나 guard 코드 완화로 숨기지 않는다. 의도적 backend 동작 변화는 단계 문서에 설명하고 제품 테스트로 증명한다.

## 구현 경계

- `sushi-fast/odi/EVC`가 활성 대상이다. 오래된 EVCv1/service/legacy report를 현재 구현으로 오인하지 않는다.
- 기존 segment/question/report provider는 보존한다. 연구용 `rehear_ai`가 FastAPI·DB·Unity·웹·tools를 import하지 않게 한다.
- 모듈별 파일은 작게 유지하고 공통 전처리·Evidence·검증·API transport는 실제 재사용할 수 있을 때만 추출한다. 새 framework/agent orchestration 제품은 필요하지 않다.
- Qwen local은 모델/tokenizer/LoRA·추론 부분만 분기한다. ‘OpenAI 호환 endpoint’와 ‘기존 10개 feature 동일 Task’는 서로 다른 문제다.
- provider·모델 revision·adapter·prompt/Rubric/Policy·추론 설정의 버전을 명시한다. 실제 연구 반복은 추론 캐시를 끄고 호출 수를 검증한다.
- GPU 다운로드나 실모델 실행 없이 adapter 연결 여부를 fake로 확인할 수 있다. 결과는 연결 검사로만 보고한다. 공식 Rubric/가중치가 없으면 만들었다고 주장하지 않는다.

## 검증과 진행

- 오프라인 테스트는 실제 STT/TTS/API를 호출하지 않는다. 새 기능은 fake provider/clock/임시 저장소를 주입해 테스트한다.
- 신규 단계 테스트 파일은 해당 단계 계획의 이름으로 만든다. 하네스 `test --suite …`가 그 파일을 요구한다.
- backend 앱 전체를 실행해야 증명되는 것은 순수 함수 검사만으로 완료 처리하지 않는다. Unity 실행이 없으면 headless 검사라고 명시한다.
- 실행 실패·skip·환경 미설치를 구분한다. 하네스의 doctor/guard 성공과 제품 테스트 성공을 구분한다.
- 각 단계에서 `PROGRESS.md`에 변경 파일·실행 명령·exit code·테스트 개수·잔여 제한을 남긴다. 독립 검토가 없으면 자체 검토라고 적는다.
- 대화가 길어져 재개할 때는 PROGRESS의 마지막 검증 상태와 실제 diff부터 읽는다. 완료된 일을 처음부터 반복하지 않는다.

## 테스트 선택

| 단계 | 새 파일 | 함께 볼 기존 검사 |
|---|---|---|
| 01 | `odi/EVC/tests/test_audience_count_contract.py` | schema/session_initialization/state_engine/reaction_scheduler/question_generation/answer_service |
| 02 | `odi/EVC/tests/test_playback_freshness.py` | command_pipeline_api/unity_rehearsal/reaction_scheduler/e2e_scenarios |
| 03 | `odi/EVC/tests/test_rehear_assessment_boundary.py` | inputs_stt/evaluation/report_generation |
| 04 | `odi/EVC/tests/test_report_integrity.py` | report_generation/report_followup/security_observability/answer_service |

기존 suite는 `python3 tools/rehear_harness.py test --suite original`, 최종은 `--suite all`로 실행한다. 불필요한 실제 API 호출을 추가하지 않는다.
