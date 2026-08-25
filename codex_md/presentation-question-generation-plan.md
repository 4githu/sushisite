# 발표 종료 후 AI 질문 생성 기능 구현 계획

## 1. 목적

발표 중 Deepgram STT로 변환한 발표 내용을 누적하고, 발표 종료 시 누적 전사문과 발표 자료를 바탕으로 ChatGPT API가 질문 3개를 생성한다. 생성된 질문은 세션에 저장하며 Unity가 HTTP API로 안정적으로 조회할 수 있어야 한다.

이 문서의 기본 범위는 다음과 같다.

- 발표 세션 하나당 질문 3개 생성
- 질문은 실제 발표에서 언급된 내용에 근거
- 동일 세션에 대한 중복 생성 방지
- Unity의 재요청 및 네트워크 재시도에 안전한 API 제공
- 기존 Deepgram → 발표 평가 → EVC/청중 행동 파이프라인 유지

## 2. 현재 구현 상태

현재 백엔드에는 다음 흐름이 구현되어 있다.

```text
Unity 오디오 구간 업로드
→ POST /odi/xreal_rehear/evc/update
→ 임시 오디오 파일 생성
→ Deepgram STT
→ latest_speech 반환
→ OpenAI 발표 구간 평가
→ segment_notes 누적
→ EVC 상태 및 Unity 행동 명령 반환
→ 임시 오디오 파일 삭제
```

현재 구조의 제약은 다음과 같다.

- 오디오 파일은 STT 처리 후 삭제된다.
- 전체 전사 원문은 저장하지 않고, 구간별 짧은 `segment_notes`만 메모리에 보관한다.
- EVC 세션은 인메모리 저장소이며 기본 TTL은 2시간이다.
- `question_count` 설정값은 존재하지만 실제 질문 생성 로직과 연결되어 있지 않다.
- 질문 생성 및 질문 조회 API가 없다.

따라서 질문 품질을 확보하려면 먼저 각 `latest_speech`를 순서대로 누적하는 기능이 필요하다.

## 3. 권장 동작 방식

질문 생성과 조회를 분리한다.

```text
발표 중
Unity ──오디오 구간──▶ /evc/update
                        ├─ Deepgram STT
                        ├─ transcript_segments 누적
                        └─ 기존 EVC 처리

발표 종료
Unity ──POST─────────▶ /sessions/{session_id}/questions/generate
                        ├─ 발표 종료 상태 확인
                        ├─ 전체 전사문 구성
                        ├─ ChatGPT API 1회 호출
                        ├─ 질문 3개 검증
                        └─ 세션에 결과 저장

질문 사용
Unity ──GET──────────▶ /sessions/{session_id}/questions
                        └─ 저장된 질문 3개 반환
```

Unity의 GET 요청이 들어올 때마다 ChatGPT API를 호출하는 방식은 권장하지 않는다. GET은 조회 전용이어야 하며 Unity 또는 프록시의 재시도, 중복 요청, 새로고침 때문에 질문이 반복 생성될 수 있다. 이는 응답 지연, 비용 증가, 질문 내용 변경, 순서 꼬임으로 이어질 수 있다.

권장 방식은 발표 종료 시 `POST`로 질문 3개를 한 번에 생성하고, 이후 `GET`으로 저장된 결과를 조회하는 것이다. Unity에서 질문을 한 개씩 표시하더라도 서버 생성은 한 번만 수행한다.

## 4. 전체 데이터 흐름

### 4.1 발표 중 전사 누적

기존 `/evc/update`의 Deepgram 처리 직후, 빈 문자열이 아닌 전사 결과를 세션의 `transcript_segments`에 추가한다.

각 구간은 문자열 하나만 저장하지 않고 최소한 다음 메타데이터를 포함한다.

```json
{
  "step": 12,
  "client_time_s": 65.4,
  "slide_index": 3,
  "text": "이번 실험에서는 세 가지 청중 반응을 비교했습니다.",
  "word_count": 8
}
```

권장 규칙:

- `expected_step` 검증과 STT 성공이 끝난 뒤 추가한다.
- 동일 `request_id`가 재전송되면 기존 응답 캐시를 반환하고 전사를 다시 추가하지 않는다.
- 빈 전사문은 저장하지 않는다.
- 질문 생성에 필요한 원문은 보존하되 API 로그에는 기록하지 않는다.
- 질문 생성 완료 후에도 보고서 저장 정책이 정해질 때까지는 세션 TTL 안에서만 유지한다.

### 4.2 발표 종료 및 질문 생성

Unity가 발표 종료 이벤트를 감지하면 질문 생성 API를 한 번 호출한다.

서버는 다음 순서로 처리한다.

1. 세션 토큰과 세션 존재 여부를 확인한다.
2. 세션을 `finishing` 상태로 전환하거나 질문 생성 잠금을 획득한다.
3. 누적된 전사 구간을 시간/step 순서로 결합한다.
4. 전사 분량과 유효 문장 수가 최소 기준을 만족하는지 확인한다.
5. 발표 제목, 슬라이드 개요, 전체 전사문, 청중 persona를 질문 생성 입력으로 구성한다.
6. ChatGPT API를 구조화 출력 방식으로 한 번 호출한다.
7. 정확히 3개인지, 빈 질문이나 중복 질문이 없는지 검증한다.
8. 생성 결과와 생성 상태를 세션에 저장한다.
9. 같은 요청이 다시 들어오면 저장된 결과를 그대로 반환한다.

### 4.3 Unity 질문 표시

가장 단순한 방식은 Unity가 전체 배열을 한 번에 받아 로컬에서 인덱스를 증가시키는 것이다.

```text
GET questions → [질문 1, 질문 2, 질문 3]
Unity 현재 인덱스 0 → 1 → 2
```

Unity 재접속 후에도 서버가 현재 진행 위치를 관리해야 한다면 별도의 소비 API를 추가한다. 다만 초기 구현에서는 Unity가 인덱스를 관리하는 편이 서버 복잡도가 낮다.

## 5. API 설계

### 5.1 질문 생성

```http
POST /odi/xreal_rehear/evc/sessions/{session_id}/questions/generate
X-EVC-Session-Token: {session_token}
Content-Type: application/json

{
  "question_count": 3,
  "request_id": "UUID"
}
```

`question_count`는 템플릿의 설정값을 기본으로 사용하고, 서버에서 허용 범위를 예를 들어 `1~5`로 제한한다. 이번 기능의 기본값은 3이다.

성공 응답 예시:

```json
{
  "session_id": "UUID",
  "status": "ready",
  "generated_at": "2026-08-25T12:34:56Z",
  "questions": [
    {
      "id": "q1",
      "order": 1,
      "question": "실험에서 세 가지 청중 반응을 선택한 기준은 무엇인가요?",
      "intent": "연구 설계의 근거 확인",
      "source_steps": [10, 11, 12]
    }
  ]
}
```

동일 `request_id` 또는 이미 생성이 완료된 동일 세션에 대해서는 ChatGPT를 다시 호출하지 않고 기존 결과를 반환한다.

권장 상태 코드는 다음과 같다.

- `200`: 기존 결과 반환 또는 동기 생성 완료
- `202`: 비동기 생성을 선택했을 때 생성 접수
- `401`: 세션 토큰 누락 또는 불일치
- `404`: 세션 없음
- `409`: 발표가 아직 종료되지 않았거나 생성 중
- `422`: 전사문이 없거나 질문 생성에 충분하지 않음
- `502`: OpenAI 제공자 오류

초기 구현은 구조가 단순한 동기식 `200` 응답으로 시작한다. 실제 호출 시간이 Unity 타임아웃을 초과한다면 이후 `202 + 상태 조회` 방식으로 전환한다.

### 5.2 질문 전체 조회

```http
GET /odi/xreal_rehear/evc/sessions/{session_id}/questions
X-EVC-Session-Token: {session_token}
```

이 API는 질문을 생성하지 않고 저장된 결과만 반환한다.

```json
{
  "session_id": "UUID",
  "status": "ready",
  "total": 3,
  "questions": [
    { "id": "q1", "order": 1, "question": "..." },
    { "id": "q2", "order": 2, "question": "..." },
    { "id": "q3", "order": 3, "question": "..." }
  ]
}
```

아직 생성되지 않았으면 `404 questions_not_generated`, 생성 중이라면 `202 generating`을 반환한다.

### 5.3 선택 사항: 질문 하나 조회

Unity가 배열 처리보다 단건 조회를 선호하면 다음 조회 API를 추가할 수 있다.

```http
GET /odi/xreal_rehear/evc/sessions/{session_id}/questions/{order}
```

이 API 역시 조회만 수행한다. GET 호출 횟수에 따라 자동으로 다음 질문으로 넘어가게 하지 않고, `order=1`, `order=2`, `order=3`처럼 명시적으로 요청해야 재시도에 안전하다.

## 6. 데이터 모델 변경

### 6.1 EVC 세션 모델

`SessionRecord`에 다음 필드를 추가한다.

```python
transcript_segments: list[TranscriptSegment] = field(default_factory=list)
presentation_status: Literal["running", "finishing", "finished"] = "running"
question_generation_status: Literal[
    "not_started", "generating", "ready", "failed"
] = "not_started"
generated_questions: list[GeneratedQuestion] = field(default_factory=list)
question_generated_at: datetime | None = None
question_generation_request_id: UUID | None = None
question_generation_error: str | None = None
```

필요한 Pydantic 스키마:

- `TranscriptSegment`
- `QuestionGenerationRequest`
- `GeneratedQuestion`
- `QuestionGenerationResponse`
- `QuestionListResponse`

### 6.2 영구 저장 정책

초기 MVP에서는 기존 EVC 구조에 맞춰 인메모리 세션에 저장할 수 있다. 단, 서버 재시작 또는 2시간 TTL 만료 시 전사와 질문이 사라진다.

운영 단계에서는 ODI DB에 다음 중 하나를 적용한다.

- `session_transcripts` 테이블에 구간별 전사 저장
- `session_questions` 테이블에 생성 질문 저장
- 또는 기존 `sessions.feedback` JSON에 최종 질문만 저장하고 전사문은 보존 기간 후 삭제

권장안은 전사 구간과 생성 질문을 별도 테이블로 분리하는 것이다. 전사는 개인정보와 발표 기밀을 포함할 수 있으므로 보존 기간 및 삭제 정책을 질문 데이터와 다르게 설정할 수 있기 때문이다.

## 7. ChatGPT 질문 생성 로직

기존 `OpenAISegmentEvaluationProvider`와 동일한 OpenAI 클라이언트 패턴을 사용하되, 질문 생성 책임은 별도 모듈로 분리한다.

권장 파일 구조:

```text
sushi-fast/odi/EVC/
├─ question_generation.py   # provider, prompt, 검증, 재시도
├─ question_service.py      # 세션 상태 및 생성 orchestration
├─ schema.py                # 질문 관련 요청/응답 모델
├─ router.py                # generate/get 엔드포인트
├─ pipeline.py              # transcript 누적
└─ config.py                # 모델/timeout/count 설정
```

환경 변수 예시:

```text
OPENAI_QUESTION_MODEL=gpt-4.1-mini
EVC_QUESTION_TIMEOUT_S=30
EVC_DEFAULT_QUESTION_COUNT=3
EVC_MAX_QUESTION_COUNT=5
EVC_MIN_TRANSCRIPT_CHARS=100
```

질문 생성 모델은 구조화 출력을 강제한다.

```python
class GeneratedQuestionSet(BaseModel):
    questions: list[GeneratedQuestion]
```

프롬프트 핵심 규칙:

- 실제 발표에서 언급된 주장, 근거, 방법, 결과를 바탕으로 질문한다.
- 슬라이드에만 있고 발표자가 언급하지 않은 내용을 사실처럼 전제하지 않는다.
- 세 질문의 목적이 겹치지 않게 한다.
- 단순 확인 질문보다 설명, 근거, 한계, 적용 가능성을 묻는 질문을 우선한다.
- 발표 내용으로부터 답변 가능한 질문과 확장 질문을 균형 있게 만든다.
- 공격적이거나 발표자 개인정보를 추론하는 질문을 만들지 않는다.
- 질문마다 근거가 된 `source_steps`와 간단한 `intent`를 반환한다.
- 설정된 언어를 따른다. 기본값은 한국어다.

권장 질문 구성은 다음과 같다.

1. 핵심 주장 또는 방법을 명확히 하는 질문
2. 근거, 한계 또는 검증 방법을 묻는 질문
3. 실제 적용이나 확장 가능성을 묻는 질문

질문 생성 입력에는 다음 정보를 넣는다.

```json
{
  "presentation_title": "...",
  "slides_outline": [],
  "transcript_segments": [],
  "recent_segment_notes": [],
  "audience_profiles": [],
  "question_count": 3,
  "language": "ko-KR"
}
```

전사문이 모델 컨텍스트 한도를 넘으면 앞부분을 단순 삭제하지 않는다. 구간별 핵심 요약과 중요 구간을 먼저 구성한 뒤, 질문의 근거 추적을 위해 원본 step 번호를 유지한다.

## 8. 발표 종료 판정

질문 생성은 명시적 발표 종료 요청을 기준으로 한다. STT의 침묵이나 특정 문장인 “감사합니다”만으로 종료를 추론하지 않는다.

두 가지 구현 선택지가 있다.

### 선택 A: 질문 생성 API가 종료까지 담당

Unity가 발표 종료 버튼을 누르면 바로 `questions/generate`를 호출한다. MVP에 적합하다.

### 선택 B: 별도의 종료 API 제공

```http
POST /odi/xreal_rehear/evc/sessions/{session_id}/finish
```

종료 API가 마지막 오디오 처리 완료 여부를 확인하고 질문 생성을 시작한다. 이후 피드백, 리포트 등 발표 종료 작업이 늘어날 가능성이 높다면 이 방식이 더 적합하다.

권장 구현은 선택 B이다. `finish`를 발표 종료 작업의 단일 진입점으로 두고, 내부에서 질문 생성 서비스를 호출하면 향후 최종 피드백 생성과 DB 저장도 같은 흐름에 연결할 수 있다. 다만 첫 번째 구현 단계에서는 `questions/generate`만 만들어도 기능 검증이 가능하다.

## 9. 동시성 및 실패 처리

- 세션별 lock 안에서 생성 상태를 `generating`으로 변경한다.
- 외부 OpenAI 호출 중에는 전체 세션 lock을 계속 점유하지 않도록 상태 변경 후 잠금을 해제한다.
- 호출 완료 후 다시 lock을 획득하여 결과를 저장한다.
- 동시에 들어온 두 번째 생성 요청은 `generating` 상태를 보고 중복 호출하지 않는다.
- `request_id`로 재시도 요청을 멱등 처리한다.
- OpenAI 타임아웃과 일시 오류는 기존 EVC 제공자 정책과 동일하게 제한 횟수만 재시도한다.
- 실패 시 상태를 `failed`로 저장하되 사용자에게 내부 프롬프트나 전사문을 오류 메시지로 노출하지 않는다.
- 실패 후 같은 `request_id` 재시도 정책과 새 `request_id` 재생성 정책을 명확히 분리한다.

## 10. 개인정보 및 로깅

- 전체 전사문을 일반 애플리케이션 로그에 출력하지 않는다.
- OpenAI/Deepgram 오류에 원문이 포함될 가능성이 있으므로 외부 예외를 그대로 API 응답에 노출하지 않는다.
- 관측 로그에는 세션 ID, step, 글자 수, 모델, 지연 시간, 성공 여부만 남긴다.
- 전사문과 질문의 보존 기간을 설정하고 사용자 세션 삭제 시 함께 삭제한다.
- 발표 자료 삭제 로직과 동일하게 EVC 세션 만료 시 관련 전사 데이터도 정리한다.
- 운영 저장 시 DB 접근 권한과 사용자/세션 소유권 검증을 적용한다.

## 11. 테스트 계획

### 단위 테스트

- Deepgram 전사가 step 순서대로 누적되는지 확인
- 빈 전사문이 저장되지 않는지 확인
- 동일 `request_id` 재전송 시 전사가 중복되지 않는지 확인
- 정확히 3개의 구조화된 질문이 생성되는지 확인
- 중복/빈 질문/잘못된 `source_steps`를 거부하는지 확인
- 전사 분량 부족 시 OpenAI를 호출하지 않는지 확인
- 질문 생성 provider의 timeout/retry 처리 확인

### API 테스트

- 유효한 세션 토큰으로 생성 및 조회 성공
- 토큰 누락/불일치 시 `401`
- 존재하지 않는 세션 `404`
- 실행 중인 발표를 종료하지 않고 생성할 때 `409`
- 생성 전 GET 처리 확인
- 동일 생성 요청을 여러 번 보내도 OpenAI 호출이 한 번인지 확인
- 동시에 생성 요청 두 개가 들어와도 결과가 하나만 저장되는지 확인

### 통합 테스트

```text
smart-start
→ update(audio 1)
→ update(audio 2)
→ update(audio 3)
→ finish 또는 questions/generate
→ GET questions
→ 질문 3개 및 source_steps 확인
→ 동일 GET 반복 시 동일 결과 확인
```

OpenAI와 Deepgram은 테스트 provider로 대체하여 외부 API 호출 없이 결정적으로 검증한다.

### Unity 연동 테스트

- 발표 종료 버튼이 마지막 오디오 업로드 완료 후 호출되는지 확인
- 생성 응답 대기 중 로딩/실패/재시도 UI 확인
- 질문 3개가 순서대로 표시되는지 확인
- Unity 재접속 후 GET으로 동일 질문을 복구하는지 확인
- GET 재시도 때문에 질문 순서가 건너뛰지 않는지 확인

## 12. 구현 순서

### 1단계: 전사 누적 기반 마련

- `TranscriptSegment` 스키마 추가
- `SessionRecord.transcript_segments` 추가
- `/evc/update` 성공 경로에서 전사 구간 누적
- 중복 request 및 빈 전사 테스트 추가

### 2단계: 질문 생성 서비스

- 질문 요청/응답 스키마 추가
- `OpenAIQuestionGenerationProvider` 구현
- 구조화 출력, 프롬프트, 검증 및 retry 구현
- provider 단위 테스트 작성

### 3단계: API 및 세션 상태

- 질문 생성 상태와 결과 필드 추가
- `POST questions/generate` 구현
- `GET questions` 구현
- 멱등성 및 동시성 테스트 추가

### 4단계: Unity 연동

- 발표 종료 시 POST 호출
- 생성 완료 결과 또는 GET 조회 처리
- Unity 내부 질문 인덱스 관리
- 오류 및 재접속 처리

### 5단계: 운영 저장

- DB 스키마 결정 및 마이그레이션
- 질문/전사 저장소 인터페이스 추가
- 세션 종료, 만료 및 사용자 삭제 시 정리
- 최종 리포트의 질문/답변 기록과 연결

## 13. 완료 기준

다음 조건을 모두 만족하면 MVP 완료로 본다.

- 발표 중 모든 유효 STT 구간이 순서대로 누적된다.
- 발표 종료 요청 한 번으로 ChatGPT API가 최대 한 번 호출된다.
- 발표 내용에 근거한 서로 다른 질문 3개가 생성된다.
- Unity가 GET으로 동일 질문 목록을 반복 조회할 수 있다.
- 네트워크 재시도에도 전사와 질문이 중복되지 않는다.
- 전사 원문이 일반 로그에 남지 않는다.
- 외부 API 실패가 기존 발표 세션 데이터를 손상시키지 않는다.
- 단위/API/통합 테스트가 모두 통과한다.

## 14. 향후 확장 항목

- 청중 persona별 질문 담당자 지정
- 난이도 및 질문 유형 설정
- 발표자의 답변 음성 STT 및 후속 질문 생성
- 질문별 답변 평가와 피드백
- EVC 상태가 낮았던 구간을 우선 질문 대상으로 선택
- 질문과 근거 발표 구간을 리포트에서 함께 표시
- 발표 종료 후 전체 transcript 다운로드 및 사용자 삭제 기능

