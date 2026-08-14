# AI 청중 반응 파이프라인 13단계 종합 검증 결과

> 선행 단계: `reaction-rule_stage12_stability.md` 완료  
> 단계 상태: 완료

## 테스트 범위

- 스키마: range/finite/enum/ID/중복/Unity namespace
- Clip Pool: Core 44, Action 8, mapping/scene gate 완전성
- 초기화: 6명, seed, profile, laptop, 설정별 E/C/V
- 세션: token, TTL, 용량, lock, create/read/delete
- 입력/STT: 크기/형식/정리/context/Deepgram 정규화/retry
- 발표 평가: 음성 지표, M/D 조립, 누락, retry, AI 출력 제한
- 상태: 내용/전달 delta, 통합 가중치, 민감도, clamp
- 후보: 경계/tie/직전축/위치/scene/event/cooldown/fallback
- 선택: 점수, Softmax 분포, seed, CriticalBias, 이력, Action gate
- Unity/API: layer 명령, sync/priority/time, 원자 update, idempotency, step/time guard
- 보안/관측성: 원문 비기록, 오류 비노출, 로그 retention
- 시나리오: 4개 발화 위치와 `ACT_01~ACT_08` 각각의 유효 후보 진입
- OpenAPI: smart-start, read/delete session, update 및 v2 response schema

## 의존성 고정

- 운영: `sushi-fast/requirements-evc.txt`
- 테스트: `sushi-fast/requirements-evc-dev.txt`
- 프로젝트 `.venv`에서 `pip check`: `No broken requirements found.`
- Deepgram SDK 5.3.4의 `listen.v1.media.transcribe_file` 및 OpenAI 2.54.0의 structured `chat.completions.parse` 존재를 확인했다.

## 실행 결과

```text
$env:PYTHONPATH='sushi-fast'
.\.venv\Scripts\python.exe -m pytest sushi-fast/odi/EVC/tests -q

................................................................ [100%]
64 passed in 2.29s
```

추가 결과:

```text
all sushi-fast/odi/EVC Python files: SYNTAX_OK
catalog core=44 actions=8
pip check: No broken requirements found.
git diff --check: 오류 없음 (Windows CRLF 변환 안내만 존재)
```

상위 `odi.router` 조립을 통한 경로도 확인했다.

```text
/odi/xreal_rehear/evc/smart-start
/odi/xreal_rehear/evc/sessions/{session_id}  (GET, DELETE)
/odi/xreal_rehear/evc/update
```

## 실행하지 않은 검증과 이유

- `OPENAI_API_KEY`와 `DEEPGRAM_API_KEY`가 현재 환경에 없어 실제 외부 provider smoke test는 실행하지 않았다.
- 대신 같은 경계를 fake provider로 정상, retry, 실패 rollback까지 검증했다.
- 프런트 코드를 수정하지 않았으므로 `npm run check`는 대상이 아니다. `node_modules`도 현재 없다.
- 전체 `sushi-fast/main.py` 기동은 EVC 밖 Bommal의 추가 Python 의존성(numpy 등)이 현 `.venv`에 없어 수행하지 않았다. EVC가 포함되는 `odi.router` import와 OpenAPI 조립은 성공했다.
- 상위 ODI import에서 기존 `fitz` deprecated API 경고가 발생했으며 EVC 변경과 무관한 기존 파일 서비스 코드다.

## 완료 판정

외부 key 없이 핵심 수식, 전체 Clip 데이터, 6명 행동 결정, Unity 명령, API 수명주기와 장애 원자성을 자동 테스트가 보호한다. EVC 전용 의존성도 고정되고 상위 ODI 경로가 OpenAPI에 등록된다. 따라서 13단계 완료 기준을 충족한다. 다음 실제 작업은 14단계인 Unity 연동 리허설과 승인 기준 확인이다.
