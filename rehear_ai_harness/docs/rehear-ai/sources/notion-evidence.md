# Notion 원본 스냅샷

출처: https://app.notion.com/p/3fadfd91e6c681c4a681f8833b1b31a4?pvs=204

마지막 편집: 2026-10-15T03:19:32.556Z

수집일: 2026-10-15. 아래는 Notion enhanced Markdown이며 원본 table/mention 표기를 보존했다.

**자료:** sushisite(2).zip · SHA-256 935579bc0fc63c061b05b4a3adaff30d42d1f4181062aacff6f8d868c6549f49. 아래 경로는 ZIP의 sushisite/를 기준으로 한다. 행 번호는 첨부 코드 기준이며 원문 위치를 찾기 위한 것이다.
## A. 코드 근거 색인
<table fit-page-width="true" header-row="true">
<tr>
<td>근거</td>
<td>파일·함수·행</td>
<td>확인한 사실</td>
</tr>
<tr>
<td>B1 · 활성 mount</td>
<td>`sushi-fast/main.py:27–32` · `odi/router.py:3–17` · `odi/EVC/router.py:77–80`</td>
<td>현재 API prefix는 /odi/xreal_rehear/evc. EVCv1은 활성 include_router가 아니며 `service.py`의 옛 상태 갱신과 구분한다.</td>
</tr>
<tr>
<td>B2 · 구간 평가</td>
<td>`sushi-fast/odi/EVC/evaluation.py:23–84,174–263` · `schema.py:77–138`</td>
<td>모델이 내용 4·전달 2 점수를 -1..1로 반환. 서버가 음성·시선 점수를 조립한다. 누락 시 실시간 중립값+missing_inputs를 사용한다.</td>
</tr>
<tr>
<td>B3 · 청중 규칙</td>
<td>`state_engine.py:19–122,137–202` · `behavior_engine.py:50–260,429–650` · `clip_pool.py:10–45`</td>
<td>6명 초기화·seed·개별 특성·가산 상태 변화·clamp·행동 gate. catalog의 44 core variation·8 action과 의미를 보존한다. 파일은 odi/EVC 아래.</td>
</tr>
<tr>
<td>B4 · 명령·반응</td>
<td>`odi/EVC/command_builder.py:15–85` · `schema.py:530–558` · `reaction_scheduler.py:1–5,67–219`</td>
<td>재생 layer·시간 offset·우선순위·공유 sync UUID·intensity=1.0. 독립 반응은 STT/LLM 없이 실행.</td>
</tr>
<tr>
<td>B5 · update 기록</td>
<td>`odi/EVC/pipeline.py:147–208,305–379`</td>
<td>step/time/request cache 검사, STT·provider 주입, 응답 구성, 메모리 변경·DB 저장·보고서 기록 순서.</td>
</tr>
<tr>
<td>B6 · 초기/적응 질문</td>
<td>`odi/EVC/question_service.py:28–96` · `question_generation.py:16–161` · `answer_service.py:21–108`</td>
<td>질문 생성 seam·중복/개수·source_steps 보정. 답변 후 다음 질문을 교체하며 초기 생성과 적응형 payload는 다르다.</td>
</tr>
<tr>
<td>B7 · 활성 보고서</td>
<td>`sushi-fast/odi/EVC/report_service.py:1–7` · `report_v2/report_generation.py:41–84,91–217`</td>
<td>상위 import는 report_v2 호환 alias. 현재 OpenAI는 점수 없는 10개 ReportNarrativeOutput을 반환하고 Protocol은 기존 AIInsight도 허용. 선택/축약 입력·cache·retry wrapper가 존재한다.</td>
</tr>
<tr>
<td>B8 · 보고서 조립·복구</td>
<td>`odi/EVC/report_v2/report_service.py:50–97,113–211,293–366`</td>
<td>정상 finish QA 포함, score 대신 reason/coaching 적용. 키 조건·generator 고정. recovery는 구간/반응에서 복원하지만 QA 복원은 없음.</td>
</tr>
<tr>
<td>B9 · 점수·10개 지표</td>
<td>`odi/EVC/report_v2/report_aggregation.py:35–46,77–127,273–297` · `report_metric_catalog.py:59–146`</td>
<td>구간 점수의 confidence·word_count 가중 평균을 0–100으로 변환. filler/time은 계산 지표, pronunciation은 null.</td>
</tr>
<tr>
<td>B10 · 외부 보고서 schema</td>
<td>`odi/EVC/report_v2/report_schema.py:121–152,204–219,267–308`</td>
<td>내용5+전달5의 정확한 ID·순서, 0–100/null, 10개 narrative, finish/status와 비교 정보 제외 위치.</td>
</tr>
<tr>
<td>B11 · 웹 소비 규칙</td>
<td>`sushi-app/src/lib/odi/components/report/DetailAnalysisCard.svelte:43–89,116–119` · `reportUtils.ts` · `domain/sessionSummary.ts:65–98`</td>
<td>기존 ID·라벨·null 미측정·배지·추천 규칙. 웹 소스는 읽기만 했으며 수정하지 않는다.</td>
</tr>
<tr>
<td>B12 · Firebase·조회</td>
<td>`sushi-app/src/lib/odi/firebase/session-materials.ts:104–150` · `stores/session.ts:149–192,235–327,394–419`</td>
<td>PIN별 RTDB 게시 구조, 1.5초 pre-session polling, report retry, 영구 세션과 comparison 조회.</td>
</tr>
<tr>
<td>B13 · 관측</td>
<td>`sushi-fast/odi/EVC/observability.py:16–115`</td>
<td>운영 이벤트는 transcript/prompt 없이 metadata 기록. 이를 없애지 않고 실험 trace를 분리·확장한다.</td>
</tr>
</table>
## B. 현재 외부 API 계약 요약
**아래 6명은 수정 전 코드의 사실이다.** 요청된 수정 목표는 기존 count 설정에 따른 a명이며, 필드/명령 의미를 유지하면서 목록 길이·ID 검증을 일반화한다. G절 참조.
모든 EVC 세션 호출은 기존 X-EVC-Session-Token을 사용한다. 아래 표는 핵심 필드이며 전체 필수/선택·검증은 위 schema와 router가 기준이다. 기존 route별 오류 응답의 형태도 유지한다.
<table fit-page-width="true" header-row="true">
<tr>
<td>현재 경로</td>
<td>입력</td>
<td>출력·행동</td>
</tr>
<tr>
<td>POST /smart-start</td>
<td>presentation_title, 관심/지식, slide_file?, seed?, pre_session_pin?, independent_reactions=false</td>
<td>session UUID/token, api_version=2.0, 6개 audiences, step=0, slides·STT provider</td>
</tr>
<tr>
<td>POST /update</td>
<td>session_id/request_id/expected_step/client_time_s/audio + slide index/발화 위치/언어/gaze?/event_signals?</td>
<td>evaluation·speech_metrics·delta·evc_state·6명·commands·warnings·legacy behavior</td>
</tr>
<tr>
<td>POST /sessions/\{id\}/reactions</td>
<td>request_id/client_time_s</td>
<td>sequence·audiences·commands·source_steps. opt-in 모드만 사용</td>
</tr>
<tr>
<td>POST /sessions/\{id\}/questions/generate</td>
<td>request_id, question_count=3(1–5)</td>
<td>status=ready, generated_at, questions\[id,order,question,intent,source_steps\]</td>
</tr>
<tr>
<td>GET /sessions/\{id\}/questions</td>
<td>token</td>
<td>ready·total·questions</td>
</tr>
<tr>
<td>POST /sessions/\{id\}/questions/\{index\}/speech</td>
<td>token, X-Speech-Voice, X-Audience-Id</td>
<td>현재 질문의 audio/wav, Cache-Control:no-store</td>
</tr>
<tr>
<td>POST /sessions/\{id\}/questions/\{index\}/answer</td>
<td>raw WAV, token, X-Request-Id, X-Next-Audience-Id</td>
<td>saved·transcript·total·next_question. 무음은 saved=false이며 total이 없는 현재 응답도 보존</td>
</tr>
<tr>
<td>POST /sessions/\{id\}/finish</td>
<td>request_id, planned_seconds=0, qa_seconds=0</td>
<td>ready·generated_at·persistent_session_id·report</td>
</tr>
<tr>
<td>GET /sessions/\{id\}/report</td>
<td>token</td>
<td>not_started/generating/ready/failed, persistent_session_id, error, report</td>
</tr>
<tr>
<td>웹 GET /odi/db/sessions/\{persistent id\}</td>
<td>기존 cookie 인증</td>
<td>session과 comparison. EVC UUID와 영구 세션 ID를 혼동하지 않음</td>
</tr>
</table>
UnityCommand 필드는 agent_id/start_time/layer/action_id/duration/sync_group/selected_behavior_id/selected_variation_id/priority/blend_mode/intensity다. core 우선순위 50, action 100, start offset은 발화/휴지 .10초·문장 경계/슬라이드 전환 .05초다. 이는 모델 출력이 아니라 서버가 만든다.
질문 STT·TTS와 보고서 error 처리의 모든 상세를 하나의 일반 provider 오류로 합치지 않는다. 대표적으로 401 token, 404 세션/질문 없음, 409 step/time/진행 상태, 422 자료·입력, 502 모델/STT 오류, 503 STT 구성 오류를 구분한다. speech/answer에는 별도 plain-string detail도 있다.
## C. 현재 웹의 10개 지표
<table fit-page-width="true" header-row="true">
<tr>
<td>구분</td>
<td>고정 ID 순서</td>
</tr>
<tr>
<td>content_metrics</td>
<td>message_clarity → structure_flow → evidence_use → claim_evidence_link → vocabulary_expression</td>
</tr>
<tr>
<td>delivery_metrics</td>
<td>gaze → speech_rate → pronunciation → filler_words → time_management</td>
</tr>
</table>
각 저장 지표는 id·score·reason·coaching·evidence_ids를 유지한다. label/rank_label/status는 새 저장값으로 추가하지 않는다. percentile은 참조 집단 없이 생성하지 않는다. comparison은 report feedback 안이 아니라 세션 조회 응답 옆에 있다. Q&A 원문은 qa_feedback.questions에 저장하고 읽기 호환 qa_history를 새 출력에 중복하지 않는다.
**미측정 보완 설계:** 전 구간 gaze가 누락되면 보고서 gaze.score=null과 미측정 사유를 반환한다. 일부 구간만 있으면 유효 구간만으로 집계할지/coverage 기준으로 보류할지 먼저 결정하고 검증한다. 실시간 MtDtEvaluation의 gaze 중립값·E/V/C 규칙을 바꾸지 않는다. pronunciation.score는 기존처럼 null이고 이유·코칭도 측정된 것처럼 생성하지 않는다.
## D. 연구 입력의 현재 확보 범위
<table fit-page-width="true" header-row="true">
<tr>
<td>연구 입력</td>
<td>현재 상태</td>
<td>외부 계약을 바꾸지 않는 대응</td>
</tr>
<tr>
<td>전사·단어 시점</td>
<td>STT 결과에 words·start/end가 있으나 ReportSegmentRecord에는 구간 전사·집계 특징만 보존</td>
<td>backend에서 word timestamp를 내부 EvidencePack/실험 자료로 보존. 구간 client_time_s와 상대 STT 시간의 offset을 명시</td>
</tr>
<tr>
<td>속도·휴지·필러</td>
<td>compute_speech_metrics에 존재</td>
<td>운영 계산을 유지하고 연구 측정 정의·STT 보존 특성은 별도로 검증</td>
</tr>
<tr>
<td>음량·F0</td>
<td>현재 SpeechMetrics에 없음</td>
<td>기존 음성 업로드 내부에서 추가 계산하거나 D3 평가 불가. 프론트 새 필수 입력 금지</td>
</tr>
<tr>
<td>머리 방향 시계열</td>
<td>현재 외부 입력은 gaze_delivery_score scalar</td>
<td>정확한 구역·시간 분포로 복원할 수 없음. D4 제한/평가 불가를 기록하고 Unity 수정 요구 금지</td>
</tr>
<tr>
<td>슬라이드·표시 구간</td>
<td>PDF text/summary·구간별 slide index/client time. 정확한 전환 이력과 동일하지 않음</td>
<td>backend에서 관측한 전환만 기록하고 S4 근거의 정밀도 명시. PPTX text 추출은 현재 prototype 미지원</td>
</tr>
<tr>
<td>청중 프로필·참고자료</td>
<td>관심/지식과 내부 청중 profile은 있으나 활성 평가 payload에 외부 논문 본문·출처는 안 들어감</td>
<td>기존 template snapshot에 있는 자료 참조를 내부에서 연결할 수 있는지 확인. 제공 자료 밖 사실 확인 금지</td>
</tr>
<tr>
<td>AI 반응·Q&A</td>
<td>report_reactions·reaction_trace 및 메모리 qa_answers. recovery에서 QA 재구성 안 함</td>
<td>실제 event 기록과 이후 발화를 연결하고 질문/답변을 내부 지속 저장. AI 반응 자체를 독립 정답으로 쓰지 않음</td>
</tr>
</table>
기존 report 설명 payload의 segment_note/short_reason/confidence/metric_impacts에는 **기존 구간 평가 모델의 판단**이 들어 있다. 연구용 OpenAI/Qwen 채점 비교에서는 원전사·측정 특징과 이 선행 모델 판단을 구분하고, 사용 범위·고정 여부를 기록한다. 기존 모델의 점수를 정답처럼 입력해 개선을 주장하지 않는다.
## E. 두 가지 오프라인 재현
### 1. provider 캐시 격리
ReportInsightProvider 모양의 가짜 provider A/B에 같은 model 식별자·payload를 주고 순서대로 실행했다. 외부 네트워크는 사용하지 않았다.
```json
{"first_title":"provider-A","second_title":"provider-A","first_calls":1,"second_calls":0,"provider_isolation":false}
```
원인 위치: `report_v2/report_generation.py:35–38,196–201`. provider 종류·adapter·prompt/추론 설정이 다른데 model 문자열을 재사용하면 잘못된 캐시를 공유할 수 있다. 같은 provider 반복 실험도 현재 cache hit를 실제 재추론으로 오해하지 않게 해야 한다.
### 2. 시선 누락의 보고서 변환
assemble_mt_dt → aggregate_report를 최소 구간 fixture로 실행했다.
```json
{"gaze_missing":true,"live_neutral_gaze":0.0,"report_gaze_score":50,"pronunciation_score":null}
```
원인 위치: `evaluation.py:237–240`와 `report_aggregation.py:35–36,290–292,103`. 실시간 중립값의 의미와 보고서의 미측정 의미를 구분해야 한다.
**검증 한계:** 32개 EVC Python 파일을 AST 파싱했고 두 최소 재현을 수행했다. 전체 pytest/FastAPI 앱·실모델·Unity 재생·웹 빌드는 실행하지 않았다. 환경에 pytest/FastAPI/httpx가 없으며, 실제 Qwen adapter도 아직 구현되지 않았다. 이 문서를 ‘전체 테스트 통과’로 해석하지 않는다.
## F. 기존 검사를 재사용할 위치
- `test_schema.py`, `test_command_pipeline_api.py`, `test_unity_rehearsal.py`: schema·step/time·동일 요청·headless Unity 명령.
- `test_state_engine.py`, `test_behavior_candidates.py`, `test_behavior_selection.py`, `test_diversity_acceptance.py`, `test_reaction_scheduler.py`: 기존 청중·시계·행동 규칙.
- `test_question_generation.py`, `test_answer_service.py`: 질문 개수·순서·중복·답변 재시도·다음 질문.
- `test_report_generation.py`, `test_report_followup.py`: 10개 지표·저장·회복·인용·cache.
- `test_security_observability.py`, `test_inputs_stt.py`: 입력·정보 노출·운영 관측·STT.
기존 검사는 유지하고 provider 격리·adapter/cache version·미측정 코칭·DB 실패·QA recovery·도구 삭제 후 import 검사를 추가한다. 원본 ZIP에 `clip_pool.json`과 benchmark JSON data/results가 존재함을 확인했다. 이 자료를 없다고 가정하지 않는다.
## G. 청중 수 전달 경로·하드코딩
<table fit-page-width="true" header-row="true">
<tr>
<td>단계</td>
<td>근거</td>
<td>확인 결과</td>
</tr>
<tr>
<td>웹 입력</td>
<td>`sushi-app/src/lib/odi/components/session/PresentationAISettingCard.svelte:56–63,116–125` · `AIsetup/+page.svelte:83–98`</td>
<td>정수 slider min=1, max=50, step=1. draft.audience.audience_count를 읽고 저장한다. ‘50+’ 표시는 실제 50 값이다.</td>
</tr>
<tr>
<td>서버 저장</td>
<td>`sushi-fast/odi/db/schema.py:49–54` · `router.py:358–374` · `template_service.py:89–169`</td>
<td>템플릿 JSON을 받아 pre_sessions.template_snapshot에 저장·응답한다. 현재 count 자체의 정수/범위 검증은 없다.</td>
</tr>
<tr>
<td>Firebase 게시</td>
<td>`sushi-app/src/lib/odi/firebase/session-materials.ts:104–141`</td>
<td>page_3.audience_scale에 template.audience.audience_count를 넣는다.</td>
</tr>
<tr>
<td>EVC 누락</td>
<td>`sushi-fast/odi/EVC/router.py:83–128` · `schema.py:567–572` · `session_store.py:142–144`</td>
<td>snapshot에서 관심/전문성만 읽고 count를 무시한다. SmartStartOptions에도 count가 없다. 새 외부 필수 form보다 기존 snapshot→내부 옵션 연결이 적절하다.</td>
</tr>
<tr>
<td>초기화 고정</td>
<td>`state_engine.py:19–122`</td>
<td>6개 좌석·RNG·특성 배열·노트북 대상·대칭쌍 분배가 결합되어 있다. 초기 목록 길이만 바꾸면 불충분하다.</td>
</tr>
<tr>
<td>ID·길이 고정</td>
<td>`schema.py:322,339,531,550,600,621,656`</td>
<td>ID 정규식은 audience_01–06, 응답 검증은 정확히 6명. 목표는 1–50 범위와 세션별 정확한 a명 registry 검사다.</td>
</tr>
<tr>
<td>질문·집계</td>
<td>`state_engine.py:126–134` · `router.py:440` · `answer_service.py:46–48`</td>
<td>집계는 실제 목록 길이, 질문 음성·답변은 실제 청중 membership을 사용한다. TTS 음성 8개가 청중 수 상한이라는 근거는 없다.</td>
</tr>
<tr>
<td>짝 반응</td>
<td>`reaction_scheduler.py:181–183`</td>
<td>ACT08 rear 짝은 다른 rear가 정확히 한 명일 때만 선택한다. rear가 늘면 기존 의미를 보존하는 배치별 pairing이 필요하다.</td>
</tr>
</table>
**순수 모델 재현 · 외부 호출 없음:** 현 상태에서 초기 청중은 6명이며 `SmartStartOptions(audience_count=12)`는 extra_forbidden, `audience_07`은 string_pattern_mismatch로 거부된다. 새 a명 구현이 통과했다는 결과가 아니다.
**구현 시 검사:** a=1/6/12/50, count 누락(default6), bool·소수·문자열 오류·0/음수/51, 고유 ID/세션 membership·평균 보존·seed 결정성·a=6 기존 결과·질문 연결. Unity actor 수/ID 매핑은 C# 미제공으로 확인하지 못했다.
## H. 30초 수집·명령 시각 조사
<table fit-page-width="true" header-row="true">
<tr>
<td>위치</td>
<td>코드로 확인한 위험</td>
</tr>
<tr>
<td>`odi/EVC/pipeline.py:159–188,274–319` · `command_builder.py:15–32`</td>
<td>요청에서 수락한 client_time_s를 STT/평가 후에도 그대로 명령 생성에 사용한다. 발화/휴지는 +.10초, 경계/전환은 +.05초다.</td>
</tr>
<tr>
<td>`live_latency_benchmark/live_rehear_benchmark.py:45,321–338,374–394`</td>
<td>기본 30초 WAV를 다 수집해 queue에 넣고 nominal client_end_s=30/60/90…를 넘긴다. 응답 시각으로 갱신하지 않는다. 실제 Unity의 수집 주기라는 증거는 아니다.</td>
</tr>
<tr>
<td>`reaction_scheduler.py:99–110,142–161`</td>
<td>독립 반응은 최신 poll 시간으로 명령을 만들지만 마지막 과거 Evidence의 slide/event/utterance 문맥을 재사용하며 freshness gate가 없다. pending delta를 한 번 적용하고 시각만 바꾼다.</td>
</tr>
<tr>
<td>`reaction_scheduler.py:101–132`</td>
<td>시간을 max(last,request)로 clamp한다. 큰 미래 시각 뒤 clock reset이 오면 진행이 막힐 수 있다. 전역 .35초 간격과 tick당 1명 선택은 인원 증가 시 대기 원인이 된다.</td>
</tr>
<tr>
<td>`schema.py:567–568` · `router.py:91,186–202` · `pipeline.py:90–92,367–369`</td>
<td>독립 모드는 opt-in false. true이면 update.commands는 비고 별도 reactions polling이 필요하다. 기존 소비자 확인 없이 켜면 호환이 깨질 수 있다.</td>
</tr>
<tr>
<td>`AUDIENCE_REACTIONS.md:14–28,44–46`</td>
<td>250ms polling·발표 시계 pause 규칙과 8초 업로드 예시가 있다. 문서의 /sessions/\{id\}/update 표기와 달리 실제 route는 /update다. benchmark는 30초로 설정되어 있다.</td>
</tr>
<tr>
<td>benchmark producer/consumer · session lock</td>
<td>단일 소비자·대기열과 STT/평가를 포함한 세션 lock은 처리시간이 입력 주기보다 길면 backlog를 만들 수 있다. 아래 완료 결과는 최대 queue wait가 0.551–1.201ms이므로 당시 backlog가 관찰됐다고 단정하지 않는다.</td>
</tr>
<tr>
<td>기존 command 검사</td>
<td>`test_unity_rehearsal.py:84–105` · `test_command_pipeline_api.py:68–105`는 즉시 fake provider와 요청 시각 기준을 검사한다. 응답 도착 시점 freshness 검증을 대신하지 못한다.</td>
</tr>
</table>
### 실제 command builder의 시간 계산 재현
실제 catalog·state 초기화·command builder를 외부 호출 없이 사용했다. 결과 start_time=30.1초, duration=2.0초였다. 응답 시계 35초는 지연 상황을 설명하기 위한 가정이다.
```json
{"submitted_clock":30.0,"hypothetical_response_clock":35.0,"command_start":30.1,"duration":2.0,"late_seconds":4.9}
```
### ZIP에 포함된 과거 완료 결과
아래는 새로 API를 호출한 측정이 아니라 `sushi-fast/live_latency_benchmark/results/`의 JSON을 다시 읽은 값이다. 모두 segment_seconds=30, duration_seconds=180이다.
<table fit-page-width="true" header-row="true">
<tr>
<td>파일</td>
<td>구간 처리 median / max</td>
<td>최대 queue wait</td>
<td>capture wall</td>
</tr>
<tr>
<td>`live_latency_20261001_205503.json`</td>
<td>3.488 / 5.527초</td>
<td>1.201ms</td>
<td>181.307초</td>
</tr>
<tr>
<td>`live_latency_20261001_210236.json`</td>
<td>3.478 / 4.659초</td>
<td>0.707ms</td>
<td>181.314초</td>
</tr>
<tr>
<td>`live_latency_20261001_211253.json`</td>
<td>4.028 / 5.094초</td>
<td>0.551ms</td>
<td>181.282초</td>
</tr>
</table>
capture 시작 monotonic을 발표 0으로 보고 응답 종료 시각에서 nominal segment end와 .05/.10초를 뺀 **조건부 추정**은 각각 약 3.764–5.666초, 3.382–5.729초, 4.304–6.139초다. 이는 direct CLI 경로의 계산이며 Unity·Firebase·실제 네트워크·클라이언트 pause와 렌더링 지연을 측정하지 않았다. nominal180초와 capture wall 약181.3초 차이도 시간 정렬 시 기록해야 한다.
### 수정·검증 방향
- 근거의 capture/segment time은 보존하고, 서버 monotonic 처리시간과 재생 시계를 별도로 기록한다. session 생성 시각을 발표 0초라고 가정하지 않는다.
- 최신 시계가 있는 기존 reactions 소비자를 확인한 경우에만 독립 모드 활용. 이벤트별 freshness·만료 처리와 늦은 명령 drop 사유를 두되 분석용 Evidence를 버리지 않는다.
- 처리시간 보정만으로 업로드 지연·pause·응답 이후 네트워크를 정확히 보정할 수 없다. 30초 수집 자체의 지연은 백엔드가 수신 후 WAV를 잘게 나눠도 사라지지 않는다.
- a명에 맞는 청중별 deadline/공정성·제한 batch·provider 동시성·queue age를 검증한다. timeout으로 to_thread 작업이 실제 중단됐다고 가정하지 않는다.
- 지연 fake provider + fake clock, stale pause/slide 이벤트, pause/resume·큰 clock jump, duplicate request_id, a명 부하 검사를 추가한다. 재시도 캐시 결과는 시각을 다시 써서 새 명령처럼 만들지 않는다.
**분석·설계 본문:** <mention-page url="https://app.notion.com/p/3fadfd91e6c681a2a8d4c1fe9da8b3c9">백엔드 AI 파이프라인 분석·모듈 교체 설계</mention-page>

