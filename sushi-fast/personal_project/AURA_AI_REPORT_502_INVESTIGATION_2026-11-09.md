# Aura AI 리포트 502 조사 — 2026-11-09

## 범위와 안전 조건
- 승인 범위에 따라 한승철 대상 실제 생성 요청을 1회 실행하고, 관련 이력은 SQLite `PRAGMA query_only=ON`으로만 확인했다.
- 학생 원문·인증정보는 출력·기록하지 않았고 카카오 전송은 하지 않았다.
- 실제 생성은 재시도하지 않았다. 이번 1회 허용량을 사용했다.

## 실제 요청 결과
- 실제 백엔드 경로: `personal_project/ai_report.py` → Gemini 서비스 생성 경계.
- 실제 요청은 HTTP 502로 실패했고 `GeminiReportError`가 `provider_generate` 단계에서 발생했다. 생성 결과는 확인되지 않았다.
- 실제 오류 응답의 공급자 원문/상세 코드와 공급자 요청 ID는 해당 실행에서 안전한 관측값으로 보존되지 않아, HTTP 상태·차단 이유·네트워크 원인 중 무엇인지 확정할 수 없다.
- 기존 이력도 생성 오류였지만 이번 요청과 상관시킬 요청 ID/시간 근거는 없다. 과거 오류의 메타데이터만으로 이번 실패의 세부 원인을 추정하지 않았다.

## 코드 변경
- `make_report_test/gemini_report_service.py`에 제한된 `diagnostic_code`를 추가해 HTTP 상태, 네트워크, 빈 응답, JSON/출력 검증 실패를 구분하도록 했다.
- `ai_report.py`는 생성 단계와 예외 클래스 및 허용된 진단 코드만 DB 오류 필드와 502 오류에 기록한다. 공급자 응답 본문이나 예외 원문은 오류 메시지로 내보내지 않는다.
- 기존 변경을 보존했다. 기존 `score_format_snapshot`/정산 조건 변경과 Gemini 프롬프트의 형광색 기준 문구는 diff에 그대로 남아 있다.
- 변경은 로컬 작업 트리에만 있다. 운영 배포는 하지 않았다.

## 검증
- 새 합성 테스트: 빈 Gemini 응답이 `empty_response`로 분류되고, 오류 본문에 포함될 수 있는 학생 텍스트/민감한 원문은 502 응답과 저장 오류값에서 제외됨을 확인했다.
- 관련 테스트 및 전체 `personal_project/tests`: **296 passed**, 12 warnings, 종료 코드 0.
- `py_compile` 대상 3개 파일 통과, `git diff --check` 통과.
- 위 테스트는 합성/로컬 코드 검증이며 실제 요청의 공급자 원인 확정, 운영 반영 또는 배포 검증이 아니다.

## 미해결 및 다음 단계
- 502의 공급자 측 세부 원인은 미확정이다. 한 번의 실제 호출에서 확보된 근거는 `provider_generate` 단계의 `GeminiReportError`까지다.
- 다음 실제 생성 요청은 별도 승인 전에는 실행하지 않는다. 진단 코드가 포함된 변경을 운영에 반영한 뒤 사용자가 다음 시도를 허용하면, 그 한 건의 sanitized code와 해당 공급자 측 기록/요청 식별자를 대조해야 원인 분류를 완료할 수 있다.

## 후속 코드 검토 및 로컬 검증 — 2026-11-09
- 사용자가 제공한 새 메타데이터 사실: 같은 대상의 과거 실패 저장 기록 3건에서 `promptFeedback.blockReason=PROHIBITED_CONTENT`, 후보 없음, `promptTokenCount=39688`이 확인됨. 학생 원문 없이 메타데이터만 추출한 자료다. 이는 **과거 3건의 공급자 차단** 근거이지, 10:37 실제 생성 1회의 원인을 소급 확정하지 않는다. 해당 실제 생성은 이미 소비됐으며 상세 원인은 알 수 없다.
- 모델 metadata GET 200 및 `gemini-3.5-flash-lite`의 `generateContent` 지원은 사용자 제공 관찰이다. 이 검토에서 추가 생성·카카오 전송·운영 반영은 하지 않았다.
- 코드를 직접 검토한 결과, Gemini 응답 JSON의 `promptFeedback.blockReason` 및 후보 `finishReason` 중 허용된 차단 enum을 `provider_blocked_*`로 분류하는 방향을 유지했다. 차단 피드백/응답 원문은 진단 문구에 복사하지 않고, `ai_report.py`에서는 422와 제한 사유 안내를 반환하며 저장 오류도 stage·예외 종류·진단 코드만 남긴다. 차단이 아닌 빈 응답 등은 기존 일반 실패(502) 경로를 유지한다. 필터 완화나 우회는 하지 않았다.
- 회귀 테스트를 보강해 `PROHIBITED_CONTENT`, 후보 없음, `promptTokenCount=39688`인 합성 응답이 안전한 코드로 분류되고 토큰 수·피드백 원문이 노출되지 않는지, 422 안내와 일반 실패 분류를 확인한다.
- 실제 실행: `sushi-fast/.venv/bin/python -m pytest -q personal_project/tests/test_ai_report_safe_errors.py` → **6 passed**; 같은 인터프리터의 3개 대상 파일 `py_compile` 통과; 대상 파일 `git diff --check` 통과. 테스트는 합성 로컬 코드 검증이며 실제 생성/운영 동작 검증이 아니다.
- 정정: 앞서 이 문서에 있던 전체 296건 통과 문구는 이전 조사 기록이다. 최신 보고에서는 전체 테스트가 환경 오류와 실패를 보였으므로 전체 통과를 주장하지 않는다. 자동 승인 검토에서 전체 재실행이 거절되어 이번에도 재실행하지 않았고, 명령 변경으로 우회하지 않았다. 이 작업은 최소 관련 테스트만 실행했다.

## 로컬 DB 직접 대조 및 운영 반영 — 2026-11-09
- 서비스와 같은 가상환경의 `db_repository.DB_PATH` (`personal_project/personal_project.db`)를 `.venv/bin/python` 및 SQLite URI `mode=ro`로 열어 학생 원문/오류 본문을 출력하지 않고 run 메타데이터만 추출했다. run 237은 `failed`; 동일 target의 직전 실패 236, 235, 234는 모두 `promptFeedback.blockReason=PROHIBITED_CONTENT`, JSON에 `candidates` 필드 없음, `usageMetadata.promptTokenCount=39688`이었다.
- run 237의 저장 오류 필드에는 구조화된 공급자 메타데이터가 없어 해당 실행의 blockReason·후보·토큰 수를 판정할 수 없다. 과거 세 실패의 원인을 run 237에 소급하지 않는다. 추가 유료 생성·카카오 전송은 하지 않았다.
- 시스템 Python의 SQLite read-only 조회는 `sqlite3.OperationalError`로 실패했으나 같은 파일을 서비스 `.venv` (SQLite 3.54.1)에서 읽는 데 성공했다. 시스템 인터프리터의 SQLite는 3.51.0이었다. OS 권한 차단으로 결론내리지 않았고, 이후 증거 조회는 서비스 venv를 사용했다.
- 운영 적용 전 launchd `app.sushisite.backend`의 실제 프로세스/작업 디렉터리와 `uvicorn main:app`, 포트 8000, `--reload` 미사용을 확인했다. 프로세스 시작 시각과 dirty runtime Python의 수정 시각을 대조한 결과, 시작 이후 바뀐 실행 Python은 `personal_project/ai_report.py`와 `personal_project/make_report_test/gemini_report_service.py` 두 파일뿐이었다. 나머지 dirty backend Python 44개는 현재 프로세스 시작 시각 이전 수정이고 프런트/문서 변경은 backend 재시작 변경 범위가 아니다.
- 재시작 startup 영향 확인: `practice_attempts`의 `queued/analyzing` 0건, 10분 이상 `generating`인 presentation report job 0건. 따라서 startup 복구가 현재 진행 중인 이 유형의 작업을 실패/재큐잉할 대상은 없었다. 재시작은 공유 backend의 Aura·Calendar·Player 및 다른 라우트에 짧은 연결 단절을 일으킬 수 있어 이를 감안해 한 번만 실행했다.
- 실제 반영: `launchctl kickstart -k gui/<uid>/app.sushisite.backend` 실행. 새 PID 60155가 두 수정 파일보다 나중에 시작했고 127.0.0.1:8000 listener를 보유한다. `GET /openapi.json`은 HTTP 200, Aura AI report generate route가 노출되는 것을 확인했다. 기존 프런트 코드도 백엔드 `detail.message`를 `PersonalApiError.message`로 전달하고 생성 화면의 `.error-banner`에 표시하도록 연결되어 있음을 소스에서 확인했다. 이는 backend 코드 로드·API route 가용성 및 UI 연결 경로 확인이며, 실제 브라우저 화면이나 실제 보고서 생성 성공 확인은 아니다.
- 재검증(이전 시점): 포커스 회귀 테스트 6개 통과. 당시에는 전체 suite·추가 생성이 미실행 상태였다. 아래 최종 검증 섹션이 이후 결과를 갱신한다.

## 최종 live HTTP 검증 — 2026-11-09
- 현재 소스에 오류 분류·422 안내·안전 진단 변경이 이미 있어 패치를 재적용하지 않았고, 다른 변경은 그대로 보존했다.
- 전체 회귀: `sushi-fast/.venv/bin/python -m pytest -q personal_project/tests` → exit 0, **299 passed, 12 warnings**. 카카오 관련 테스트는 mock/test double/subprocess 대체 또는 disabled-transport gate로 검증됐고 실제 카카오 전송은 없었다.
- `app.sushisite.backend` 재시작 전 PID **60155**, 재시작 후 PID **61885**. 새 프로세스가 `127.0.0.1:8000`을 듣고, OpenAPI GET은 **200**이며 Aura 생성 API 경로가 노출됨을 확인했다.
- 승인된 로그인 브라우저 세션에서 same-origin model/history GET **200** 후 생성 API를 한 번만 POST했다. 응답은 **HTTP 200**, 모델 `gemini-3.5-flash-lite`, `score_mode=auto`, `force=true`, run **238**이며 오류/진단 코드는 없었다. 요청 원문과 보고서·학생 내용은 기록하지 않았다.
- 저장 재조회 GET **200**에서 결과 수가 1→2로 증가했고 run 238이 확인됐다. 읽기 전용 DB 메타데이터에서도 generation run `completed`, report record `submitted`였다.
- 이 성공은 run 238의 새 실제 HTTP 검증이다. 과거 run 237의 상세 원인은 여전히 미확정이며, 그 원인을 과거 세 건에 귀속하지 않는다. 과거 세 실패의 `PROHIBITED_CONTENT` 분류는 사용자가 확인한 별도 사실로 유지한다.
- 런타임 재시작과 브라우저 API 검증은 완료했지만 별도 배포 파이프라인 실행은 하지 않았다. 상세 비식별 결과는 `AURA_AI_REPORT_502_LIVE_VERIFICATION_2026-11-09.md`에 기록했다.

## Run 237/238 인과 귀속 검토 — 2026-11-10
- 동일 서비스 가상환경의 SQLite DB를 `mode=ro` 및 `PRAGMA query_only=ON`으로 읽고, 원문·ID·응답 본문은 출력하지 않았다. run 237과 238은 모델, 공급자, score mode, prompt hash가 같지만 대상 ID와 저장 input hash가 다르며, 기존 평가 양식 스냅샷도 다르다. 따라서 run 238은 동일 입력의 재현/대조 실행이 아니며 성공 원인을 분리할 수 없다.
- 코드 diff에서 `ai_report.py`의 오류 분류/안전 진단 변경은 실패 경로 처리이고, 성공 응답을 만드는 공급자 요청을 직접 바꾸는 변경은 아니다. `gemini_report_service.py`의 현재 요청 투영·형광색 지시 변경 파일 시각은 run 238 실행 시각보다 뒤다. run 레코드에 코드 revision이 없어 정확한 로드 버전을 확정할 수는 없다. 종합하면 run 238만으로 코드 변경 효과나 일시적 공급자 응답 어느 쪽도 입증되지 않는다.
- run 237 저장 기록에는 안전한 공급자 차단 이유가 없어, 과거 동일 대상에서 나온 별도 `PROHIBITED_CONTENT` 3건을 run 237의 원인으로 소급할 수 없다.
- Google Gemini 안전 설정 문서(https://ai.google.dev/gemini-api/docs/safety-settings, 2026-11-10 확인)는 Gemini 2.5 이상에서 지정하지 않은 조정 가능 유해 콘텐츠 필터의 기본 임계값이 `OFF`라고 설명한다. 현재 경로의 모델은 `gemini-3.5-flash-lite`다. `PROHIBITED_CONTENT`는 조정 가능한 카테고리 임계값이 아니므로, 이를 우회하는 설정은 추가하지 않았다. 현재 모델에서 실효성이 입증된 안전 필터 완화 변경은 없음.
- 추가 생성 없이 read-only 메타데이터, 기존 코드 diff, 공식 문서만 확인했다. 새 카카오 전송·운영 변경·모델 호출은 하지 않았다.
