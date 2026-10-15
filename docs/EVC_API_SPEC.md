# Unity용 EVC API 명세

기준: `feature/ai-pipeline` **bdd871e**, 비교: 로컬 `main` **42d4240** (2026-09-09).
FastAPI router/schema 및 호출 서비스 기준. 범위는 Unity용 EVC API이며 웹 로그인·PIN 발급 API는 제외한다.

## 1. 전체 API 목록

아래 Endpoint 앞에 `/odi/xreal_rehear/evc`를 붙인다. 구분은 endpoint 신설뿐 아니라 반환 데이터·처리 동작 변경도 포함한다.

| 기능 | Method | Endpoint | 역할 | 구분 |
| -- | -- | -- | -- | -- |
| 세션 시작 | POST | `/smart-start` | PIN 연결, UUID/token, 청중 6명 초기화 | 이번 브랜치에서 변경 |
| 세션 조회 | GET | `/sessions/{session_id}` | 현재 step·상태·개별 청중 profile 조회 | 이번 브랜치에서 변경 |
| 세션 삭제 | DELETE | `/sessions/{session_id}` | 메모리 세션 종료·삭제 | 기존 |
| 발표 분석 | POST | `/update` | 발표 STT·평가·EVC·Unity command 반환 | 이번 브랜치에서 변경 |
| 최초 질문 생성 | POST | `/sessions/{session_id}/questions/generate` | 최초 N개 질문 생성; 기존 provider를 adaptive 생성에도 재사용 | 이번 브랜치에서 변경 |
| 질문 목록 | GET | `/sessions/{session_id}/questions` | 답변으로 교체된 질문을 포함한 현재 목록 | 이번 브랜치에서 변경 |
| 질문 TTS | POST | `/sessions/{session_id}/questions/{index}/speech` | 현재 질문의 Azure WAV 반환 | 이번 브랜치에서 추가 |
| 답변 업로드·STT·다음 질문 | POST | `/sessions/{session_id}/questions/{index}/answer` | Azure 인식 후 다음 질문 한 칸 교체 | 이번 브랜치에서 추가 |
| 최종 report 생성 | POST | `/sessions/{session_id}/finish` | 발표 리포트 생성·Q&A 이력 포함·PIN 연결 시 저장 | 이번 브랜치에서 변경 |
| report·Q&A 이력 조회 | GET | `/sessions/{session_id}/report` | 상태 및 생성된 report 조회 | 이번 브랜치에서 변경 |

**신규 endpoint는 `/speech`, `/answer` 두 개다.** 질문 생성·최종 report endpoint는 main에도 있었다. 별도 답변 STT, 다음 질문 생성, Q&A history endpoint는 없다. 최초 질문 생성 요청/응답 필드 자체는 기존과 같다.

## 2. 각 API 명세

### 공통 계약

- Unity 설정: 서버 origin을 `Base URL`로 보관하고 아래 전체 경로를 붙인다. 예시 origin은 `https://<server-host>`이며 실제 배포 주소는 별도 확인한다. `/odi/xreal_rehear/evc`를 중복해서 붙이지 않는다.
- `smart-start` 외에는 `X-EVC-Session-Token`이 필요하다. EVC 호출은 웹 로그인 쿠키나 Azure key를 요구하지 않는다.
- 모든 `{session_id}`는 시작 응답의 UUID이다. PIN 및 report의 `persistent_session_id`와 구분한다. Query parameter는 모든 EVC API에서 없다.
- UUID는 하이픈 포함 표준 문자열로 전송하고 UUID 값으로 비교한다. 아래 UUID·날짜는 설명용이며 token은 placeholder다.
- JSON 성공 응답 예시는 **주요 필드 발췌**다. 누락된 필드가 실제 응답에 없다는 뜻이 아니다. 성공은 기본 200, 삭제만 204다.
- 공통 오류: **401** token 누락/불일치, **404** 세션 없음/만료, **422** UUID·필수 필드·schema 검증 실패, **500** 처리되지 않은 내부 오류. `smart-start`에는 token 인증 오류가 없다.
- 오류 body는 `{"detail":{"code":"...","message":"..."}}`, `{"detail":"..."}`, FastAPI 검증 오류 배열 형태가 모두 가능하다.

### 2.1 세션 시작

**Method / Endpoint**
```text
POST /odi/xreal_rehear/evc/smart-start
```
**역할**: 발표·청중 세션을 만든다. 웹 리포트 영구 저장을 연결하려면 웹에서 발급한 `pre_session_pin`을 보낸다.

**Headers**
```text
Content-Type: multipart/form-data; boundary=<Unity가 생성>
```
**Path / Query Parameters**: 없음.

**Request** — multipart form fields

| 이름 | 타입 | 필수 | 설명 |
| -- | -- | -- | -- |
| presentation_title | string | 예 | 공백 제외 제목, 최대 200자 |
| topic_interest | string | 아니오 | `low/middle/high` 또는 `낮음/중간/높음`, 기본 `middle` |
| prior_knowledge | string | 아니오 | 위와 동일, 기본 `middle` |
| slide_file | file | 아니오 | PDF 권장, 기본 최대 25 MiB. PPT/PPTX는 텍스트 추출 미구현 |
| seed | int | 아니오 | 0~2147483647, 생략 시 서버 생성 |
| pre_session_pin | string | 아니오 | 유효한 waiting 상태의 4자리 PIN |

**Response**
```json
{"api_version":"2.0","session_id":"11111111-1111-4111-8111-111111111111","session_token":"<서버가 발급한 token>","step":0,"initial_evc_state":{"E":0.0,"V":0.0,"C":0.0},"topic_interest":0.5,"prior_knowledge":0.5,"expires_in_s":7200,"slide_count":0,"slides":[]}
```
추가 반환: `seed`, `presentation_title`, `audiences` 6개. audience는 `{agent_id, profile, state}`이며 ID는 `audience_01`~`audience_06`. profile의 `topic_interest`, `prior_knowledge`가 이번에 추가되었다.

**주요 오류**

| Status | 의미 |
| -- | -- |
| 404 / 409 | PIN·template 없음 / 이미 사용·실행 중인 PIN |
| 413 / 415 / 422 | 파일 용량 / 형식 / 설정값 오류 |
| 429 | 세션 수 제한 초과 |

**Unity 주의사항**: UUID/token을 이후 모든 호출에 유지한다. PIN만으로 제목·PDF·청중 설정이 자동 로드되지 않으므로 Unity가 전달한다. 질문 수는 시작 body가 아닌 2.3 API에 보낸다.

### 2.2 발표 음성 분석·reaction

**Method / Endpoint**
```text
POST /odi/xreal_rehear/evc/update
```
**역할**: 녹음된 발표 구간을 STT·평가하고 청중 상태와 실행 command를 반환한다.

**Headers**
```text
X-EVC-Session-Token: <session_token>
Content-Type: multipart/form-data; boundary=<Unity가 생성>
```
**Path / Query Parameters**: 없음.

**Request** — multipart form fields

| 이름 | 타입 | 필수 | 설명 |
| -- | -- | -- | -- |
| session_id | UUID string | 예 | 시작 응답 UUID |
| request_id | UUID string | 예 | 구간별 새 UUID; 동일 구간 재시도 시 유지 |
| expected_step | int | 예 | 마지막 응답의 step, 최초 0 |
| client_time_s | float | 예 | 세션 내 단조 증가 시간(초), 0 이상 |
| audio | file | 예 | 기본 최대 15 MiB; Azure 선택 시 mono PCM16 WAV |
| current_slide_index | int | 아니오 | 0-based, 기본 0; 슬라이드 없을 때도 0 |
| utterance_position | string | 아니오 | `during_speech`(기본), `utterance_boundary`, `silence_or_pause`, `slide_transition` |
| language | string | 아니오 | 기본 `ko-KR` |
| gaze_delivery_score | float | 아니오 | -1~1; 미측정 시 생략 |
| slide_reference | bool | 아니오 | 기본 false |
| event_signals | JSON string | 아니오 | 예: `{"information_dense":0.7}` |

event_signals 허용 키: `information_dense`, `slide_reference`, `repeated_disengagement`, `low_arousal`, `long_static_posture`, `tension`, `nearby_interaction`; 각 0~1, 생략값 0.

**Response**
```json
{"api_version":"2.0","session_id":"11111111-1111-4111-8111-111111111111","request_id":"22222222-2222-4222-8222-222222222222","step":1,"accepted_client_time_s":5.0,"latest_speech":"실험 결과를 설명하겠습니다.","evc_state":{"E":0.1,"V":0.0,"C":0.1},"commands":[{"agent_id":"audience_01","start_time":5.1,"layer":"Body","action_id":"body.neutral_listening","duration":2.0,"sync_group":"33333333-3333-4333-8333-333333333333","selected_behavior_id":"BL_01","selected_variation_id":"BL_01.neutral_listening","priority":50,"blend_mode":"override","intensity":1.0}]}
```
추가 반환: `current_slide_index`, `speech_metrics`, `evaluation`, `delta`, `behavior`, `audiences`, `warnings`, `no_op_reason`, `diagnostics`.

**주요 오류**

| Status | 의미 |
| -- | -- |
| 409 | step 불일치, client_time 0.25초 초과 역행, 발표 종료 이후 update |
| 413 / 415 / 422 | 업로드 용량 / 형식 / 입력값 오류 |
| 502 | STT 또는 발표 평가 provider 실패·timeout |

**Unity 주의사항**
- 응답 후 다음 구간을 전송하고 반환 step을 사용한다. 무음은 step 유지·`commands=[]`; 응답 재수신 시 command를 중복 실행하지 않는다.
- `start_time`은 client_time 기준 초다. layer는 `Face/Body/GazeHead`, 동일 `sync_group`은 동기화하며 core priority 50, action 100이다. blend_mode는 `override/additive`다.
- E/V/C 범위는 -1~1이다. action ID 매핑은 [clip_pool.json](../sushi-fast/odi/EVC/clip_pool.json)을 사용한다.

### 2.3 최초 질문 생성

**Method / Endpoint**
```text
POST /odi/xreal_rehear/evc/sessions/{session_id}/questions/generate
```
**역할**: 누적 발표 STT·슬라이드·청중 profile로 최초 N개 질문을 생성한다. 이 처리에 진입하면 발표 update가 종료된다.

**Headers**
```text
X-EVC-Session-Token: <session_token>
Content-Type: application/json
```
**Path / Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| -- | -- | -- | -- |
| session_id | UUID | 예 | Path, EVC 세션 |

**Request**
```json
{"request_id":"44444444-4444-4444-8444-444444444444","question_count":1}
```
`request_id` 필수. `question_count`는 1~5, 생략 시 3. Unity가 웹 `question_count`(Firebase `page_1.qa_count`)를 전달한다.

**Response**
```json
{"session_id":"11111111-1111-4111-8111-111111111111","status":"ready","generated_at":"2026-09-09T00:00:00Z","questions":[{"id":"q1","order":1,"question":"대조군은 어떻게 설정했나요?","intent":"검증 방법 확인","source_steps":[1]}]}
```
**주요 오류**

| Status | 의미 |
| -- | -- |
| 409 | 질문 생성 진행 중 |
| 422 | 누적 transcript가 기본 100자 미만, 질문 수·UUID 오류 |
| 502 | 질문 LLM 실패·timeout·질문 결과 검증 실패 |

**Unity 주의사항**: 마지막 update 완료 후 호출한다. 질문 수 0은 이 API를 생략하고 finish로 간다. 이미 생성된 상태의 재호출은 현재 질문 목록을 반환하며 질문 수를 바꾸지 않는다.

### 2.4 질문 목록 조회

**Method / Endpoint**
```text
GET /odi/xreal_rehear/evc/sessions/{session_id}/questions
```
**역할**: 답변 처리로 수정된 현재 질문 목록을 읽는다.

**Headers**
```text
X-EVC-Session-Token: <session_token>
```
**Path / Query Parameters**: `session_id` — UUID, Path 필수. Query 없음.

**Request**: body 없음.

**Response**
```json
{"session_id":"11111111-1111-4111-8111-111111111111","status":"ready","total":1,"questions":[{"id":"q1","order":1,"question":"대조군은 어떻게 설정했나요?","intent":"검증 방법 확인","source_steps":[1]}]}
```
**주요 오류**: 404 질문 미생성/생성 실패 상태, 409 생성 중. 공통 인증·UUID 오류 적용.

**Unity 주의사항**: 현재 answer index나 진행 중 Q&A history는 이 응답에 없다. 다음 진행은 `/answer` 응답으로 결정한다.

### 2.5 현재 질문 TTS

**Method / Endpoint**
```text
POST /odi/xreal_rehear/evc/sessions/{session_id}/questions/{index}/speech
```
**역할**: 서버에 저장된 현재 질문을 Azure로 합성한다. 질문 문자열을 body로 보내지 않는다.

**Headers**
```text
X-EVC-Session-Token: <session_token>
X-Speech-Voice: ko-KR-SoonBokNeural
X-Audience-Id: audience_02
```
**Path / Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| -- | -- | -- | -- |
| session_id | UUID | 예 | Path, EVC 세션 |
| index | int | 예 | Path, 현재 질문의 0-based index |

**Request**: body 없음. 세 header 모두 유효한 값이 필요하다.

허용 voice: `ko-KR-InJoonNeural`, `ko-KR-BongJinNeural`, `ko-KR-GookMinNeural`, `ko-KR-SunHiNeural`, `ko-KR-JiMinNeural`, `ko-KR-SeoHyeonNeural`, `ko-KR-SoonBokNeural`, `ko-KR-YuJinNeural`.

**Response**
```text
200 OK
Content-Type: audio/wav
Cache-Control: no-store

<RIFF WAV bytes: 24kHz / 16bit / mono PCM>
```
**주요 오류**

| Status | 의미 |
| -- | -- |
| 404 / 409 | 질문 없음 / 현재 turn이 아님 |
| 422 | 지원하지 않는 voice 또는 세션에 없는 audience |
| 502 / 503 | Azure 요청·응답 실패 / Azure 서버 설정 오류 |

**Unity 주의사항**: WAV를 AudioClip으로 디코딩해 해당 audience AudioSource/LipSync에 공급한다. 서버는 avatar↔voice 고정 매핑·QS 동작·viseme을 반환하지 않는다. 미래 질문 TTS 선요청은 409다.

### 2.6 답변 업로드 → STT → 다음 질문

**Method / Endpoint**
```text
POST /odi/xreal_rehear/evc/sessions/{session_id}/questions/{index}/answer
```
**역할**: 답변 WAV를 Azure STT로 인식하고, 실제 Q&A history와 다음 청중 상태를 기존 질문 LLM에 전달한다. 꼬리 질문 또는 다른 관련 질문으로 다음 slot 하나를 교체하며 전체 질문 수는 유지한다.

**Headers**
```text
X-EVC-Session-Token: <session_token>
X-Request-Id: 55555555-5555-4555-8555-555555555555
X-Next-Audience-Id: audience_03
Content-Type: audio/wav
```
**Path / Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| -- | -- | -- | -- |
| session_id | UUID | 예 | Path, EVC 세션 |
| index | int | 예 | Path, 답변할 질문의 0-based index |

`X-Request-Id`는 필수 UUID. `X-Next-Audience-Id`는 다음 질문이 있으면 필수(`audience_01`~`audience_06`), 마지막 답변에서는 생략한다.

**Request**
```text
<body 전체가 RIFF WAV bytes — multipart, JSON, base64 아님>
```
mono PCM16, 8,000~48,000Hz, 20,000,000bytes 이하. 녹음은 최대 10분으로 제한한다(서버 duration 검사 상한은 601초). STT 언어는 `ko-KR` 고정이다. `audio/wav` 전송을 사용하되 현재 router는 Content-Type 자체보다 실제 WAV 데이터를 검증한다.

**Response** — 3개 질문 중 첫 답변 성공
```json
{"question_index":0,"request_id":"55555555-5555-4555-8555-555555555555","saved":true,"transcript":"대조군 100명과 비교했습니다.","total":3,"next_question":{"id":"q2","order":2,"question":"두 집단의 초기 조건은 어떻게 맞췄나요?","intent":"비교 조건 확인","source_steps":[1]}}
```
마지막 답변 성공은 `saved=true`, `total=N`, `next_question=null`이다. 무음은 다음처럼 **total 없이** 반환한다.
```json
{"question_index":0,"request_id":"55555555-5555-4555-8555-555555555555","saved":false,"transcript":"","next_question":null}
```
**주요 오류**

| Status | 의미 |
| -- | -- |
| 404 | 질문 없음 |
| 409 | 답변 순서 오류, 다른 질문에 UUID 재사용, 같은 index에서 UUID/음성 bytes/다음 audience 변경, report 종료 처리 중/완료 |
| 413 / 422 | 20MB 초과 / WAV·UUID·다음 audience 오류 |
| 429 | Azure continuous 인식 lock 대기 초과 |
| 502 / 503 / 504 | STT·LLM 실패 / Azure 설정 오류 / Azure continuous 인식 timeout |

**Unity 주의사항**
- 재시도는 같은 index·UUID·WAV bytes·다음 audience를 유지한다. 완료된 동일 요청은 동일 응답을 반환한다. LLM 실패 후에는 저장된 transcript로 STT를 생략하고 재시도한다.
- `saved=false`면 진행하지 않고 새로 녹음한다. `saved=true`일 때만 다음 질문을 교체하고 `index=next_question.order-1`로 진행한다. TTS에는 선택했던 다음 audience와 해당 voice를 사용한다.
- 마지막도 답변을 제출한다. `saved=true && next_question==null`을 종료 조건으로 사용한다. `saved`는 메모리 저장이며 아직 DB 영구 저장이 아니다.

### 2.7 최종 report 생성·저장

**Method / Endpoint**
```text
POST /odi/xreal_rehear/evc/sessions/{session_id}/finish
```
**역할**: 발표 점수·분석·timeline·EVC graph·AI insight·Q&A history를 생성한다. PIN 연결 세션은 DB에 영구 저장한다.

**Headers**
```text
X-EVC-Session-Token: <session_token>
Content-Type: application/json
```
**Path / Query Parameters**: `session_id` — UUID, Path 필수. Query 없음.

**Request**
```json
{"request_id":"66666666-6666-4666-8666-666666666666","planned_seconds":120,"qa_seconds":45}
```
UUID 필수. 시간 두 값은 선택, 각각 기본 0·범위 0~86400초. Q&A 이력은 서버가 모으므로 body로 보내지 않는다.

**Response**
```json
{"session_id":"11111111-1111-4111-8111-111111111111","status":"ready","generated_at":"2026-09-09T00:05:00Z","persistent_session_id":"session_0123456789ab","report":{"version":"presentation-report-v1","score":{"overall_score":75,"percentile":null,"grade":"보통"},"qa_history":[{"question_index":0,"question":"대조군은 어떻게 설정했나요?","answer":"대조군 100명과 비교했습니다."}]}}
```
report에는 추가로 `generation`, `duration`, `score_card`, `detail_analysis`, `timeline`, `audience_analysis`, `ai_insight`가 있다. PIN 미연결 시 `persistent_session_id=null`. 생성 완료 후 응답하며 202 background job 응답이 아니다.

**주요 오류**

| Status | 의미 |
| -- | -- |
| 409 | report 생성 중, 답변 처리 중 또는 실패한 미완료 답변 존재 |
| 422 | 분석된 발표 구간 없음, 필수 저장 메타데이터 누락, 입력값 오류 |
| 500 | 저장 등 내부 처리 실패 |

**Unity 주의사항**: 모든 답변 성공 후 호출한다. 서버는 아직 제출하지 않은 답변 개수를 검사하지 않아 조기 finish가 가능하다. Q&A는 이력·insight 입력에 포함되지만 별도 Q&A 점수 및 종합 점수 계산은 없다.

### 2.8 report·Q&A history 조회

**Method / Endpoint**
```text
GET /odi/xreal_rehear/evc/sessions/{session_id}/report
```
**역할**: report 상태 및 생성 결과를 조회한다. 별도 Q&A history API는 없으며 완료 report의 `qa_history`로 확인한다.

**Headers**
```text
X-EVC-Session-Token: <session_token>
```
**Path / Query Parameters**: `session_id` — UUID, Path 필수. Query 없음.

**Request**: body 없음.

**Response** — 생성 전
```json
{"session_id":"11111111-1111-4111-8111-111111111111","status":"not_started","persistent_session_id":null,"error":null,"report":null}
```
status는 `not_started/generating/ready/failed`. ready의 report는 2.7과 같은 구조다.

**주요 오류**: 공통 401/404/422. 미생성 report 자체는 404가 아니라 위의 200 응답이다.

**Unity 주의사항**: 이 API도 살아 있는 메모리 session/token이 필요하다. 서버 재시작 후 DB 리포트 재조회는 웹의 별도 세션 조회 경로를 사용한다.

### 2.9 세션 상태 조회

**Method / Endpoint**
```text
GET /odi/xreal_rehear/evc/sessions/{session_id}
```
**역할**: 현재 step·발표/질문/report 상태와 청중 상태를 조회한다.

**Headers**
```text
X-EVC-Session-Token: <session_token>
```
**Path / Query Parameters**: `session_id` — UUID, Path 필수. Query 없음.

**Request**: body 없음.

**Response**
```json
{"api_version":"2.0","session_id":"11111111-1111-4111-8111-111111111111","step":1,"expires_in_s":7200,"presentation_status":"running","question_generation_status":"not_started","report_generation_status":"not_started","evc_state":{"E":0.1,"V":0.0,"C":0.1}}
```
추가 반환: 제목·생성/수정 시각·설정·`audiences`·슬라이드·notes·warnings. 발표 상태는 `running/finishing/finished`, 질문/report 상태는 `not_started/generating/ready/failed`.

**주요 오류**: 공통 401/404/422.

**Unity 주의사항**: token을 다시 발급하거나 반환하지 않으며 현재 Q&A answer index도 반환하지 않는다.

### 2.10 세션 삭제

**Method / Endpoint**
```text
DELETE /odi/xreal_rehear/evc/sessions/{session_id}
```
**역할**: 메모리 EVC 세션 및 연결된 임시 슬라이드 파일을 제거한다. DB 리포트 삭제 API가 아니다.

**Headers**
```text
X-EVC-Session-Token: <session_token>
```
**Path / Query Parameters**: `session_id` — UUID, Path 필수. Query 없음.

**Request**: body 없음.

**Response**: `204 No Content`, body 없음.

**주요 오류**: 공통 401/404/422.

**Unity 주의사항**: 진행 중 Q&A는 사라진다. 리포트가 필요하면 finish 성공 후 삭제한다.

## 3. API 호출 순서

`EVC = /odi/xreal_rehear/evc`, `{id} = session_id`.

```text
1. 세션 시작           POST EVC/smart-start
2. 발표 구간 반복       POST EVC/update → step 저장, commands 실행
3. 발표 녹음 종료       별도 endpoint 없음; 마지막 update 응답까지 대기
4. 최초 N개 질문 생성   POST EVC/sessions/{id}/questions/generate
5. 현재 질문 TTS        POST EVC/sessions/{id}/questions/0/speech → WAV 재생
6. 답변 녹음·업로드     POST EVC/sessions/{id}/questions/0/answer
7. next_question 확인   6의 응답 사용; 별도 endpoint 없음
8. 다음 질문 TTS        POST EVC/sessions/{id}/questions/{order-1}/speech
9. N개 답변까지 반복    POST .../{index}/answer → saved=true·next_question=null
10. 최종 report        POST EVC/sessions/{id}/finish
11. 필요 시 조회        GET EVC/sessions/{id}/report
```

웹 질문 수가 0이면 4~9를 생략한다. Q&A 전에는 `/finish`를 호출하지 않는다.

## 4. 환경변수와 Unity 보관값

`sushi-fast/main.py`가 서버 `sushi-fast/.env`를 로드한다. 아래는 **EVC 실행 경로에서 사용하는 서비스 설정 및 주요 운영 설정**이다. Gemini는 이 EVC router/service에서 호출하지 않는다.

| 환경변수 | 역할 | 필요한 기능 | Unity 필요 여부 |
| -- | -- | -- | -- |
| DEEPGRAM_API_KEY | Deepgram 인증 | 기본 발표 STT | 아니오, 서버 전용 secret |
| DEEPGRAM_PRIMARY_MODEL | 기본 `nova-3` | Deepgram 발표 STT | 아니오 |
| EVC_STT_PROVIDER | `deepgram`(기본) / `azure` | 발표 STT 선택 | 아니오 |
| AZURE_SPEECH_KEY | Azure 인증 | 답변 STT·질문 TTS·선택적 발표 STT | 아니오, 서버 전용 secret |
| AZURE_SPEECH_REGION | Azure 리전, 기본값 없음 | continuous STT·TTS | 아니오 |
| AZURE_STT_MODE | `continuous`(기본) / `fast` | 답변 STT만 선택; 발표 Azure는 continuous | 아니오 |
| AZURE_SPEECH_ENDPOINT | `https://<resource>.cognitiveservices.azure.com` | fast 답변 STT만 필요 | 아니오 |
| OPENAI_API_KEY | OpenAI 인증 | 발표 평가·최초/다음 질문·report insight | 아니오, 서버 전용 secret |
| OPENAI_EVC_MODEL | 기본 `gpt-4.1-nano` | 발표 평가·report insight | 아니오 |
| OPENAI_QUESTION_MODEL | 기본 `gpt-4.1-mini` | 최초/다음 질문 | 아니오 |
| EVC_STT_TIMEOUT_S | 기본 30초 | 발표 STT wrapper; 답변 STT 제한과 별개 | 아니오 |
| EVC_LLM_TIMEOUT_S / EVC_QUESTION_TIMEOUT_S | 기본 20초 / 30초 | 평가·insight / 질문 | 아니오 |
| EVC_PROVIDER_RETRIES | 기본 1회 재시도 | 발표 STT·평가·질문·insight | 아니오 |
| EVC_MIN_TRANSCRIPT_CHARS | 기본 100자 | 최초 질문 생성 | 아니오 |
| EVC_SESSION_TTL_S / EVC_MAX_SESSIONS | 기본 7200초 / 100개 | 메모리 세션 유지·한도 | 아니오 |
| EVC_MAX_AUDIO_BYTES / EVC_MAX_SLIDE_BYTES | 기본 15 MiB / 25 MiB | update 음성 / 슬라이드; answer 20MB는 별도 상수 | 아니오 |

`EVC_DEFAULT_QUESTION_COUNT`, `EVC_MAX_QUESTION_COUNT`는 config에 선언되어 있지만 현재 요청 schema에는 연결되지 않았다. API의 기본 3·범위 1~5를 바꾸는 설정으로 사용하지 않는다.

| Unity가 보관할 값 | 출처·용도 |
| -- | -- |
| 서버 Base URL | Unity 설정의 배포 origin; SDK/API secret과 무관 |
| session_id / session_token | smart-start 응답; EVC 세션 동안 안전하게 유지, token을 로그에 기록하지 않음 |
| request UUID·답변 원본 WAV·다음 audience | Unity 생성/선택; 동일 답변 재시도 시 유지 |
| step·질문 수·현재 index | 응답으로 갱신; 서버는 별도 Q&A 진행 조회 API를 제공하지 않음 |
| persistent_session_id | finish 응답의 웹/DB 세션 식별자; EVC UUID 자리에 사용하지 않음 |

Azure/OpenAI/Deepgram key는 서버 `.env` 또는 서버 secret 환경에만 둔다. Unity Resources/APK에 넣거나 클라이언트에 전달하지 않는다.

## 5. 이번 변경사항

| 변경사항 | Backend 상태 | Unity에서 필요한 작업 |
| -- | -- | -- |
| Azure 발표 STT 선택 | 구현 | Azure 선택 시 WAV 형식 준수 |
| 개별 청중 관심도·지식 | 구현 | 추가 profile 필드 허용; 청중은 6명 유지 |
| 질문 TTS API | 구현 | audience/voice header, WAV 디코딩·재생 |
| 답변 업로드·Azure STT | 구현 | 마이크 녹음, raw WAV, UUID/token 유지 |
| 답변 기반 다음 질문 | 구현, 기존 LLM 재사용 | 반환 질문으로 다음 slot 교체, 총수 유지 |
| SoonBok·YuJin voice 허용 | 구현, allowlist 총 8개 | 실제 6개 prefab의 voice 지정 |
| report Q&A history·insight 입력 | 구현 | 마지막 답변 후 finish; 필요 시 history 표시 |

별도 Q&A 점수·발표/Q&A 종합 점수·웹 Q&A 이력 UI는 현재 없다.

## 6. 미검증 사항

- 이 저장소에 Unity 소스/Quest APK가 없어 **실제 질문 WAV 재생·LipSync, Quest 마이크 답변 업로드, UUID/token 유지, 전체 Q&A 반복**은 코드 대조만으로 확인할 수 없다.
- 실제 Azure 및 운영 OpenAI LLM의 배포 인증·응답·질문 품질은 별도 E2E 검증이 필요하다. 앞선 감사의 29개 회귀 테스트 통과는 실제 기기·외부 API 성공을 뜻하지 않는다.
- EVC는 프로세스 메모리 세션이므로 단일 worker 운용이 전제다. 재시작/TTL 만료 전에 finish하지 않으면 진행 중 질문·답변이 사라진다.
- speech/answer의 지연을 감당하도록 Unity·proxy timeout을 맞춘다. Azure REST timeout은 150초, continuous 인식 완료 대기는 `max(60, 음성길이+60)`초이며 lock 대기·다음 질문 LLM 시간이 추가될 수 있다.

근거: [router](../sushi-fast/odi/EVC/router.py), [schema](../sushi-fast/odi/EVC/schema.py), [answer service](../sushi-fast/odi/EVC/answer_service.py), [Azure adapter](../sushi-fast/odi/EVC/azure_speech.py), [report schema](../sushi-fast/odi/EVC/report_schema.py), [report service](../sushi-fast/odi/EVC/report_service.py), [config](../sushi-fast/odi/EVC/config.py).
