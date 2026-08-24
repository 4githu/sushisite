# 전체 발표 분석 리포트 생성 기능 구현 계획

## 1. 조사 결론

현재 저장소에는 **전체 발표 내용을 종합 분석하여 최종 리포트를 생성하는 로직이 없다.**

다만 기능 구현에 활용할 수 있는 구성요소는 이미 일부 존재한다.

- `sushi-fast/odi/EVC/pipeline.py`
  - 발표 구간마다 STT를 수행한다.
  - 구간별 내용/전달 평가와 음성 지표를 계산한다.
  - 유효한 전사를 `SessionRecord.transcript_segments`에 누적한다.
  - 청중별 E/V/C 상태를 갱신한다.
- `sushi-fast/odi/EVC/question_service.py`
  - 발표 종료 시 누적 전사와 슬라이드를 사용해 질문을 생성한다.
  - 이는 질문 생성 기능이며 최종 발표 리포트 생성 기능은 아니다.
- `sushi-fast/odi/db/*`
  - `sessions.feedback` JSON을 저장하고 조회할 수 있다.
  - 서버가 `feedback`을 계산하지 않고 요청자가 완성된 JSON을 넘기는 구조다.
- `sushi-app/src/lib/odi/components/report/*`
  - 점수, 세부 요소, 타임라인, 청중 반응, AI 인사이트를 표시하는 리포트 UI가 구현되어 있다.
- `sushi-app/src/lib/odi/demo/fixedPresentationScenario.ts`
  - 프론트엔드가 고정된 `fixedDemoFeedback`을 서버에 전달해 데모 리포트를 만든다.
  - 실제 발표 데이터 분석 결과가 아니다.

따라서 현재 흐름은 다음과 같이 분리되어 있다.

```text
실시간 발표 처리
STT → 구간 평가 → E/V/C 갱신 → 메모리 세션에 전사 누적 → 질문 생성

리포트 화면
호출자가 만든 feedback JSON → ODI DB 저장 → Svelte 리포트 컴포넌트 표시
```

두 흐름 사이에 다음 단계가 빠져 있다.

```text
누적된 전체 전사 + 모든 구간 평가 + 음성 지표 + E/V/C 이력 + 발표 자료
→ 전체 발표 종합/집계
→ ReportFeedback 생성
→ 영구 세션 저장
→ 프론트엔드 조회
```

## 2. 프론트엔드 확인 결과

프론트엔드에는 최종 리포트를 **표시하는 기능**이 있다.

- 리포트 목록: `sushi-app/src/routes/odi/report/+page.svelte`
- 리포트 상세: `sushi-app/src/routes/odi/report/[session_id]/+page.svelte`
- 리포트 조합 화면: `sushi-app/src/lib/odi/components/report/ReportPageView.svelte`
- 표시 데이터 타입: `sushi-app/src/lib/odi/components/report/reportTypes.ts`
- DB 조회/종료 요청: `sushi-app/src/lib/odi/stores/session.ts`

현재 UI가 기대하는 `feedback` 주요 구조는 다음과 같다.

- `score`: 종합 점수, 백분위, 등급
- `duration`: 계획/실제 발표/Q&A 시간
- `score_card`: engagement, clarity, credibility 점수와 설명
- `detail_analysis`: 내용 및 전달 세부 지표
- `timeline`: 시점별 긍정/주의/부정 피드백
- `audience_analysis`: E/V/C 그래프와 주요 이벤트
- `ai_insight`: 전체 발표를 종합한 핵심 코칭

하지만 프론트엔드는 이 값을 분석하거나 생성하지 않는다. `session.getReport()`로 저장된 세션을 조회해 렌더링할 뿐이다. 실제 종료 호출도 `finishPreSession(pinCode, feedback)`처럼 완성된 `feedback`을 인자로 요구한다. 현재 저장소 내부에서 확인되는 호출은 고정 데모 데이터 전달뿐이다.

또한 `sushi-app/src/routes/report/[sessionId]/+page.svelte`와 `$lib/api/sessionApi.js`에는 별도의 구형 결과 화면/API 호출이 있으나, 현재 FastAPI ODI 리포트 생성 흐름과 연결된 종합 분석 구현은 확인되지 않는다.

## 3. 구현 목표

발표 종료 요청 한 번으로 해당 EVC 세션에 누적된 전체 데이터를 바탕으로 최종 리포트를 생성하고 영구 저장한다.

필수 목표:

1. 모든 유효 전사 구간과 구간 평가 결과를 순서대로 보존한다.
2. 전체 발표 수준의 결정적 집계와 LLM 기반 종합 코칭을 분리한다.
3. 기존 프론트엔드 `ReportFeedback` 구조와 호환되는 응답을 만든다.
4. 동일한 종료 요청이 반복되어도 리포트를 한 번만 생성한다.
5. 생성 상태와 실패 상태를 조회할 수 있게 한다.
6. 메모리 EVC 세션이 만료되기 전에 결과를 ODI DB에 영구 저장한다.

## 4. 권장 아키텍처

### 4.1 종료 오케스트레이션

질문 생성 전용 엔드포인트를 최종 종료 진입점으로 사용하지 말고 다음 API를 추가한다.

```http
POST /odi/xreal_rehear/evc/sessions/{evc_session_id}/finish
X-EVC-Session-Token: ...
Idempotency-Key 또는 request_id
```

처리 순서:

1. 세션 토큰과 현재 상태를 검증한다.
2. 진행 중인 마지막 오디오 요청이 끝났는지 확인한다.
3. 세션을 `finishing`으로 원자적으로 변경한다.
4. 전체 발표 분석 입력을 스냅샷으로 만든다.
5. 질문 생성과 리포트 생성을 수행한다.
6. ODI의 사용자/템플릿 세션과 EVC 세션을 연결한다.
7. 완성된 `ReportFeedback`을 `sessions.feedback`에 저장한다.
8. EVC 세션을 `finished`로 변경하고 저장된 `session_id`를 반환한다.

긴 LLM 호출로 HTTP 타임아웃 가능성이 있다면 생성 요청은 `202 Accepted`를 반환하고 별도 상태 조회 API를 제공한다.

```http
GET /odi/xreal_rehear/evc/sessions/{evc_session_id}/report
```

상태 응답은 `not_started | generating | ready | failed`를 구분한다.

### 4.2 수집 데이터 확장

현재 `transcript_segments`만으로는 UI의 타임라인, 상세 분석, 청중 그래프를 신뢰성 있게 복원하기 어렵다. `SessionRecord`에 구간 결과를 추가한다.

```python
report_segments: list[ReportSegmentRecord]
evc_timeline: list[EVCTimelinePoint]
report_generation_status: Literal["not_started", "generating", "ready", "failed"]
report_generation_request_id: UUID | None
report_feedback: ReportFeedback | None
persistent_session_id: str | None
```

`ReportSegmentRecord`에는 최소한 다음을 저장한다.

- `step`, `client_time_s`, `slide_index`
- 전사문과 단어 수
- 전체 `MtDtEvaluation`
- `SpeechMetrics`
- 집계 E/V/C 값
- 경고 및 신뢰도

`pipeline.update_pipeline()`에서 응답을 확정한 직후 전사와 함께 동일한 step의 구간 결과를 저장한다. 빈 전사 구간은 리포트 점수에서는 제외하되 시간/무음 관련 분석 정책이 필요하면 별도 이벤트로 보존한다.

### 4.3 리포트 생성기

새 모듈을 다음처럼 분리한다.

```text
sushi-fast/odi/EVC/report_schema.py       # 엄격한 출력 스키마
sushi-fast/odi/EVC/report_aggregation.py  # 수치 집계 및 타임라인 선별
sushi-fast/odi/EVC/report_generation.py   # LLM 호출과 검증
sushi-fast/odi/EVC/report_service.py      # 상태, 멱등성, DB 저장 오케스트레이션
```

역할 분리는 다음과 같다.

- 결정적 집계
  - 내용/전달 지표의 신뢰도 가중 평균
  - 전체 발화 속도, 필러, 반복, 휴지 통계
  - 실제 발표 시간
  - E/V/C 시계열 다운샘플링
  - 점수 정규화와 종합 점수 산식
  - 주요 긍정/주의 구간 후보 선별
- LLM 종합
  - 전체 전사와 슬라이드 흐름을 바탕으로 발표의 구조적 일관성 평가
  - 점수별 짧은 설명
  - 타임라인 후보의 사람이 이해하기 쉬운 피드백 문구
  - 전체 발표를 관통하는 `ai_insight`

LLM이 종합 점수 자체를 자유롭게 만들게 하지 않는다. 점수는 서버 집계 규칙으로 만들고, LLM은 근거 기반 설명과 전체 맥락 평가에 집중시킨다. 이렇게 해야 같은 입력에 대한 점수 안정성과 테스트 가능성을 확보할 수 있다.

### 4.4 긴 전사 처리

전체 전사가 모델 컨텍스트를 넘을 수 있으므로 단순 앞부분 삭제는 금지한다.

1. 발표 구간을 슬라이드 또는 시간 창 단위로 묶는다.
2. 각 묶음의 요약과 핵심 주장/근거/문제 구간을 생성한다.
3. 원본 `step`과 시간 범위를 유지한다.
4. 최종 생성에는 계층 요약, 중요 원문 구간, 결정적 집계값을 함께 넣는다.
5. 최종 타임라인 항목은 반드시 존재하는 step/time 범위를 참조하도록 검증한다.

## 5. 데이터 계약

백엔드에 프론트엔드 타입과 대응하는 Pydantic 모델을 정의한다. `dict[str, Any]`만 허용하는 현재 종료 스키마는 생성 결과의 누락과 오타를 막지 못하므로 최종 리포트에는 엄격한 모델을 사용한다.

기존 `ReportFeedback`과 호환하되 다음 메타데이터를 추가하는 것을 권장한다.

```json
{
  "version": "presentation-report-v1",
  "generation": {
    "generated_at": "...",
    "model": "...",
    "source_segment_count": 0,
    "transcript_word_count": 0,
    "warnings": []
  },
  "score": {},
  "duration": {},
  "score_card": {},
  "detail_analysis": {},
  "timeline": [],
  "audience_analysis": {},
  "ai_insight": {}
}
```

백분위는 비교 모집단 데이터가 없으면 생성하지 않거나 `null`로 반환한다. 임의의 백분위를 LLM이 만들어서는 안 된다.

## 6. 세션 연결과 영구 저장

현재 EVC의 UUID 세션과 ODI DB의 `pre_sessions/sessions`는 별도 체계다. 종료 전에 명시적으로 연결해야 한다.

권장안:

- EVC 시작 요청에 `pin_code` 또는 `pre_session_id`를 전달한다.
- 서버가 로그인 사용자 소유권과 템플릿 연결을 확인한다.
- EVC `SessionRecord`에 `pre_session_pin`과 `user_id`를 보관한다.
- 리포트 생성 성공 시 서버 내부 서비스가 ODI 세션을 만들고 `feedback`을 저장한다.
- HTTP 라우터 함수를 내부에서 재호출하지 않고 공용 애플리케이션 서비스/리포지토리를 사용한다.

가능하면 전사와 구간 평가는 `sessions.feedback`에 모두 넣지 말고 별도 테이블에 저장한다.

```text
presentation_report_jobs
presentation_segments
presentation_reports
```

MVP에서는 기존 JSON 컬럼을 사용할 수 있지만, 최소한 생성 상태/오류/요청 ID는 별도 컬럼 또는 작업 테이블로 관리해야 프로세스 재시작과 재시도에 안전하다.

## 7. 프론트엔드 변경 계획

기존 리포트 컴포넌트는 최대한 재사용한다.

1. `reportTypes.ts`
   - 백엔드 Pydantic 스키마와 동일하게 타입을 보강한다.
   - `generation` 메타데이터와 nullable 필드를 명확히 한다.
2. EVC 세션 API 클라이언트 추가
   - `finishPresentation(evcSessionId, token, requestId)`
   - `getReportGenerationStatus(evcSessionId, token)`
3. 발표 종료 UX
   - 마지막 오디오 업로드 완료를 기다린다.
   - 종료 API를 한 번 호출한다.
   - `generating` 동안 진행 화면을 표시한다.
   - 성공 시 반환된 ODI `session_id`로 `/odi/report/{session_id}`에 이동한다.
   - 실패 시 발표 데이터가 보존되었음을 알리고 재시도 버튼을 제공한다.
4. 리포트 상세
   - 누락된 선택 데이터에 0점을 표시하지 말고 “분석 데이터 없음” 상태를 구분한다.
   - 생성 경고가 있으면 낮은 STT 신뢰도, 시선 데이터 미수집 등을 표시한다.
5. 데모 경로
   - `fixedDemoFeedback`은 UI 확인용 fixture로 명확히 분리한다.
   - 실제 발표 종료 경로에서는 사용하지 않는다.

## 8. 보안 및 운영 고려사항

- 전사문과 슬라이드는 개인정보 또는 기밀을 포함할 수 있으므로 보존 기간과 삭제 정책을 정의한다.
- EVC 토큰뿐 아니라 ODI 로그인 사용자와 세션 소유권도 검증한다.
- 로그에 전체 전사나 LLM 입력을 그대로 남기지 않는다.
- LLM 실패 시 원본 구간 데이터와 결정적 집계 결과는 보존한다.
- 동일 `request_id` 재호출은 동일 결과를 반환한다.
- 프로세스 재시작 후에도 생성 상태를 복구할 수 있도록 작업 상태를 메모리에만 두지 않는다.
- 모델명, 타임아웃, 재시도 횟수, 최대 전사 길이를 환경변수로 관리한다.

## 9. 테스트 계획

### 단위 테스트

- 구간 점수의 신뢰도 가중 평균
- `[-1, 1]` 평가값에서 `[0, 100]` 점수 변환
- 전체 발표 시간과 음성 통계 집계
- E/V/C 그래프 다운샘플링
- 타임라인 후보 정렬/중복 제거/최대 개수 제한
- 빈 전사, 일부 누락 입력, 낮은 STT 신뢰도 처리
- Pydantic 리포트 응답 검증
- 존재하지 않는 step을 참조한 LLM 결과 거부

### 서비스/API 테스트

- 정상 종료 후 리포트 1회 생성 및 DB 저장
- 동일 `request_id` 재호출의 멱등성
- 생성 중 동시 종료 요청의 `409` 또는 기존 작업 반환
- 이미 종료된 세션에 업데이트 요청 시 거부
- LLM 타임아웃/실패 후 재시도
- 짧은 전사에 대한 명확한 `422` 또는 제한 리포트 정책
- 잘못된 EVC 토큰/다른 사용자 접근 거부
- 질문 생성 실패와 리포트 생성 실패의 독립 처리
- 메모리 세션 만료 전에 영구 결과가 저장되는지 확인

### 프론트엔드/E2E 테스트

- 종료 버튼 연속 클릭 시 요청 1회
- 마지막 오디오 요청 이후 종료 요청 순서 보장
- 생성 중/성공/실패 상태 표시
- 성공 후 상세 리포트 이동
- 실제 생성 응답으로 모든 카드 렌더링
- 부분 데이터에서 0점 오인 표시가 없는지 확인
- 리포트 목록에 새 세션이 노출되는지 확인

## 10. 구현 순서

### Phase 1 — 계약과 수집 완성

- 백엔드 `ReportFeedback` Pydantic 모델 정의
- `ReportSegmentRecord`와 E/V/C 이력 추가
- `update_pipeline()`에서 모든 분석 원천 데이터 누적
- 단위 테스트 작성

### Phase 2 — 결정적 리포트 집계

- 점수 산식과 시간/발화/EVC 집계 구현
- 타임라인 후보 생성
- 고정 fixture 기반 스냅샷 테스트 작성

### Phase 3 — 전체 맥락 LLM 분석

- 계층 요약과 최종 프롬프트 구현
- 구조화 응답 검증, 타임아웃, 재시도 구현
- 점수 설명과 AI 인사이트 생성

### Phase 4 — 종료/저장 오케스트레이션

- EVC와 ODI 세션 연결
- 멱등 종료 및 리포트 상태 API 추가
- DB 작업 상태와 완성 리포트 영구 저장
- 질문 생성과 종료 흐름 통합

### Phase 5 — 프론트엔드 연결

- 종료 및 상태 조회 API 클라이언트 추가
- 생성 대기/실패/재시도 화면 연결
- 완성된 ODI 리포트로 이동
- 데모 fixture와 실제 경로 분리

### Phase 6 — 통합 검증

- 실제 오디오 여러 구간을 사용한 E2E 테스트
- 긴 발표와 부분 입력 누락 테스트
- 재시작/재시도/동시 요청 테스트
- 보존 및 삭제 정책 검증

## 11. 완료 기준

- 발표 중 생성된 모든 유효 전사와 구간 분석이 최종 리포트 입력에 포함된다.
- 발표 종료 요청 한 번으로 최종 리포트 생성 작업이 시작된다.
- 동일 종료 요청은 리포트를 중복 생성하지 않는다.
- 생성된 결과가 현재 프론트엔드 리포트의 모든 주요 섹션을 채운다.
- 결과가 ODI DB에 저장되어 EVC 메모리 세션 만료 후에도 조회된다.
- 타임라인 피드백은 실제 발표 시점과 근거 구간을 참조한다.
- 누락 데이터와 낮은 신뢰도가 사용자에게 명확히 표시된다.
- 외부 AI 호출 실패가 누적 발표 데이터나 기존 세션을 손상시키지 않는다.
