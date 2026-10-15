# 04 측정 정의와 과거 자료 이전

기존 두 폴더의 원본은 `artifacts/rehear-private/legacy-benchmarks/`에 byte 단위로 이전했다. 이 경로는 Git 제외이며 음성·전사·모델 출력·오류 원문을 공개 fixture로 만들지 않는다. 공개 `legacy-benchmark-inventory.json`은 127개 파일의 내용 SHA-256, 크기, 분류, 원래 상대 경로의 hash와 새 경로를 기록한다. 실제 원래 경로 대응은 private `source-index.json`에만 있다. archive와 index를 함께 백업해야 원래 이름으로 복원할 수 있다. 공개 checkout만으로 개인 archive를 복원할 수는 없다.

원본 녹음 75개는 내용을 청취하거나 익명화했다고 주장하지 않는다. 모든 legacy 파일을 사용자 자료가 있을 수 있는 private 자료로 취급했다. 아래 정의는 원본 구현을 확인해 옮겼으며, 과거 수치를 새 실행 결과로 승격하지 않는다.

## 기존 post-presentation 측정

`benchmark_post_presentation.py`의 `perf_counter()` 차이에 1000을 곱한 ms이다. provider wrapper는 `finally`에서 시도별 시간을 합산한다. 성공한 추론만의 시간이나 장치 시간으로 해석하면 안 된다.

| 필드 | 원래 정의 |
|---|---|
| question_service_total_ms | 질문 서비스 호출 시작→종료 |
| question_generate_questions_total_ms | generate_questions wrapper 전체 |
| question_openai_provider_ms | 질문 provider 각 호출의 경과 시간 합 |
| question_service_outer_overhead_ms | max(0, service total − generate total) |
| question_generation_non_provider_ms | max(0, generate total − provider total) |
| qa_injection_ms | case의 답변 텍스트를 memory에 주입하는 시간; 실제 STT 아님 |
| report_service_total_ms | finish 서비스 호출 전체 |
| report_payload_build_ms / report_aggregate_ms / report_apply_narratives_ms / report_build_qa_feedback_ms | 각각의 wrapper 누적 시간 |
| report_insight_non_provider_ms | max(0, generate insight total − report provider total) |
| report_other_overhead_ms | max(0, report service total − 위 payload/insight/aggregate/apply/QA wrapper 합) |
| post_presentation_machine_total_ms | question service total + QA injection + report service total |
| qa_complete_to_report_ready_ms | report service total |

질문/보고서 payload 크기와 provider 호출 수, fallback/error/generator도 원본 결과에 남아 있다. 당시 report cache를 비웠다는 코드가 현재 모델 품질이나 모든 과거 실행의 무캐시 증거는 아니다.

## 기존 live 측정

`timing.py`/`instrumentation.py`/`retry_logger.py`의 wall time은 `perf_counter()` 차이(ms)이고 UTC 시작/끝 문자열은 별도 메타데이터다. `AttemptTimer`의 오류 원문과 EventLog의 metadata는 private 원본에만 남긴다.

| 필드 | 원래 정의 |
|---|---|
| segment_queue_wait | segment 처리 시작 − captured_at |
| backend_drain_wait | max(0, analysis drained − recording ended) |
| post_presentation_to_q1_ready_ms | Q1 TTS ready − 발표 recording ended; backend drain 포함 |
| qN_answer_end_to_qN+1_ready_ms | 다음 질문 TTS ready − 답변 recording ended |
| q3_answer_end_to_report_ready_ms | report ready − Q3 recording ended |
| total_non_human_wait_ms | 위 4개 wait의 합; 원본 summary는 누락/None을 0으로 취급 |
| segment_update_median/max_ms | success인 segment_update_total만 집계 |
| segment_queue_wait_max_ms | status와 무관하게 segment_queue_wait 최대; 없으면 0 |
| provider_retry_attempt_count | attempt≥2인 event 개수; 논리 요청 수와 다를 수 있음 |
| late_provider_completion_count | late_success_after_timeout_window status 개수 |

Q1/Q2/Q3 ready는 backend 파일 준비 시각이며 Unity 수신/렌더/실제 들린 시각이 아니다. 녹음 시간·TTS playback human time은 별도였다. old wait의 None→0 합계는 미관측을 0초 지연으로 증명하지 않으므로 새 결과와 직접 평균 비교하지 않는다.

## 새 Research16 CLI 측정

제품의 질문/보고서 10개 설명 benchmark와 **다른 task**다. `compare`의 두 engine은 같은 EvidencePack/RubricBundle/Policy를 받는다. fake는 모두 기권하며 fake 호출 수를 모델 추론 수로 해석하지 않는다. 비교는 criterion별 두 점수/null을 보여 주며 전문가 정확도를 계산하지 않는다.

- 공통 `research-run.v1`: run_id, canonical input hash, task, engine/model/base/tokenizer/adapter revision, Rubric/Policy digest·version, prompt, settings, call_count, retry_count, cache_hits, failed_attempts, failures, elapsed_s. `failures`는 최종 run 실패 수(0/1), `failed_attempts`는 결과를 만들지 못한 provider 시도 수다. load 실패는 call_count=0일 수 있다.
- `eval`은 기존 AssessmentResult 파일을 유지하고 `OUTPUT.run.json`에 원문 없는 run metadata를 쓴다. 다른 명령은 결과와 metadata를 명시 출력 파일에 쓴다. stdout/stderr에는 음성·전사·모델 reason·오류 원문을 쓰지 않는다.
- `repeat`/`compare`/`bench`와 eval repeat>1은 cache off를 강제한다. call_count는 engine의 실제 `_infer` 진입 수이며 내부 retry를 포함한다. cache hit는 infer 호출이 아니다.
- `bench`: cold_load_s는 새 engine의 준비/모델 load wall time. first_generation_s는 load 후 첫 assess wall time. warm_generation_s는 이후 assess wall time 목록이다. 각각 검증/retry를 포함하며 device kernel만의 시간이 아니다. elapsed_s는 engine 생성부터 load와 모든 assess/결과 변환까지이고 JSON 입력 읽기/출력 쓰기는 제외한다. fake의 load_kind는 no_model_fake다.
- doctor/contracts/replay는 모델을 로드하지 않는다. replay는 Evidence/Rubric, 선택한 기존 AssessmentResult의 출처·참조 존재를 재검증한다. semantic support는 검증하지 않는다.
- `--input-format legacy-post`는 보존된 세 text case의 명시된 text/client_time_s/slide 연결만 import한다. offset·단어 시간·음성 지표·시선·정확한 slide history를 추측하지 않는다. standalone qa_answers는 질문이 없어 pairing하지 않는다. live case/config는 대본/슬라이드 설정이며 관측 전사로 변환하지 않는다. 이전 live 마이크/STT/TTS orchestration을 새 Research16 실행으로 대체했다고 주장하지 않는다.

`SPEC.md`, `sources/*`, 단계 계획/과거 PROGRESS와 원본 하네스 묶음의 옛 경로는 역사/이전 대상 참조다. 실행 지침은 `sushi-fast/tools/rehear_cli/README.md`를 따른다. 운영 코드가 옛 폴더를 import하지 않는지는 guard와 별도 참조 검색으로 확인한다.
