# Personal Project API

개인 캘린더와 아우라 클리닉 기능을 기존 `mainauth` 쿠키 인증에 연결하는 독립 FastAPI 패키지입니다. 아우라는 학생 회원관리 방식이 아니라 `학교 → 회차 → 학생 이름 → 리포트` 구조를 사용합니다.

## 실행

기존 FastAPI 앱을 실행하면 `main.py`가 이 패키지의 라우터를 자동으로 포함합니다.

```bash
uvicorn main:app --reload
```

DB 파일은 최초 실행 시 `personal_project/personal_project.db`로 생성됩니다. 모든 API는 요청 본문의 사용자 ID가 아닌 `mainauth` 쿠키에서 확인한 사용자 ID만 사용합니다.

## 주요 API

- `GET|POST /api/personal/calendar/events`
- `POST /api/personal/calendar/events/series`
- `PATCH|DELETE /api/personal/calendar/events/{id}`
- `PATCH|DELETE /api/personal/calendar/events/{id}/scope`
- `GET|POST /api/personal/aura/students`
- `GET|POST /api/personal/aura/sessions`
- `PATCH /api/personal/aura/sessions/{id}`
- `POST|PATCH /api/personal/aura/.../report`
- `GET /api/personal/aura/settlements`
- `GET /api/personal/aura/settlements/export.xlsx`

학교 중심 API:

- `GET|POST /api/personal/aura/schools`
- `GET /api/personal/aura/schools/{id}`
- `GET /api/personal/aura/schools/{id}/export.json`
- `GET|POST /api/personal/aura/rounds`
- `POST /api/personal/aura/rounds/series`
- `POST /api/personal/aura/rounds/{id}/targets`
- `GET /api/personal/aura/targets/{id}/report`
- `PATCH|POST /api/personal/aura/target-reports/{id}`
- `GET /api/personal/aura/ai/models`
- `GET /api/personal/aura/targets/{id}/ai-reports`
- `POST /api/personal/aura/targets/{id}/ai-reports/generate`

AI 리포트 생성은 기본 `gemini-3.6-flash`와 비교용 Gemini 모델을 지원한다. 시스템 지침 캐시는 모델별로 분리하고, 동일한 대상·모델·입력 JSON·프롬프트 조합의 완성 결과는 DB에서 재사용한다.
- `POST /api/personal/aura/schools/{id}/rounds/{number}/template`

학생 리포트 임시저장은 기본 양식을 변경하지 않습니다. 사용자가 명시적으로 기본 양식 저장 API를 호출할 때만 새 버전이 생성되며 기존 리포트의 스냅샷은 그대로 유지됩니다.

한 클리닉에서 `4,5회차`를 함께 진행하면 하나의 일정과 하나의 학생별 리포트로 저장합니다. 리포트 최초 생성 시 4회차 기본 양식 뒤에 5회차 기본 양식을 이어 붙입니다. 학교는 우선순위와 학기 종료 상태를 가지며, 학교 내 일정·학생 이름·리포트·양식을 JSON으로 일괄 내보낼 수 있습니다.

같은 학교의 같은 회차 번호도 날짜가 다른 별도 클리닉으로 다시 등록할 수 있습니다. 일정의 회차 구성을 수정하면 사용자가 아직 편집하지 않은 자동 생성 리포트만 제거되며, 다음 열기에서 변경된 회차 기본 양식으로 다시 생성됩니다.

학교 순서는 위/아래 이동으로 인접 학교와 우선순위를 교환합니다. 학교 완전 삭제는 연결된 클리닉 일정, 학생 이름, 리포트, 기본 양식을 함께 삭제합니다. 일반 캘린더 반복 일정은 횟수 대신 종료 날짜를 받을 수 있습니다.

일정 시간은 ISO 8601 UTC 오프셋을 포함해 저장하고 화면에서 브라우저 로컬 시간으로 변환합니다. 반복 일정과 반복 클리닉은 그룹 ID와 순번을 저장하므로 한 일정만 수정하거나 선택한 일정부터 이후 일정을 함께 수정할 수 있습니다.

## Paiper Reader

`/personal-project/reader`는 브라우저에서 PDF 텍스트를 추출하고 원문·번역·계정/PDF별 로컬 메모를 제공한다. 메모에는 기존 PersonalTextEditor를 재사용한다. 번역은 사용자가 동의한 뒤 기존 쿠키 인증의 `POST /api/personal/reader/translate`를 사용한다. 원본 PDF는 이 경로로 업로드하지 않는다.

기본 번역 제공자는 비활성(503)이다. 서버가 다음 설정을 명시해야 활성화한다.

- 개인 소유자 모드: `READER_TRANSLATION_PROVIDER=hermes_personal_owner`, `READER_TRANSLATION_PERSONAL_OWNER_ID=<확인된 Sushi 사용자 ID>`, `READER_TRANSLATION_HERMES_EXECUTABLE=<절대 경로>`, `READER_TRANSLATION_HERMES_HOME=<기존 개인 프로필 절대 경로>`. 기존 mainauth로 확인한 소유자만 해당 프로필을 호출하며 클라이언트는 소유자·프로필을 선택할 수 없다.
- 별도 작업자 모드: `READER_TRANSLATION_PROVIDER=hermes_plugin`과 위 실행 파일·프로필 설정. 별도 프로필의 `.paiper-reader-worker` 표식과 플러그인 설치가 필요하다. 개인 계정을 다른 사용자에게 공유하는 기본값은 없다.

플러그인은 `reader_translation/hermes_plugin/`에 있다. 인증정보를 코드나 요청에 복사하지 않고 Hermes의 공식 `paiper-reader-translate` 플러그인 명령으로 호출한다. 서버는 입력 크기·응답 ID·시간 제한을 검사하고 요청 본문·공급자 오류 원문을 저장하거나 출력하지 않는다. 공급자 보관·플랜 비용에 대해서는 무보관·무료를 보장하지 않는다. 이전 localhost 9011 보조 서버는 선택적 개발 도구이며 웹 제품의 로그인 경로가 아니다.

검증: 합성 인증의 HTTPS 후보 서버에서 실제 GPT 번역 200, 비인증 401·다른 사용자 503·빈 입력 400을 확인했다. 제품 화면은 합성 로그인/PDF로 텍스트 추출·메모 복구·내려받기와 모바일 표시를 검사했다. 이는 실제 운영 로그인·번역과 동일한 검증이 아니며, 이 구현은 운영 배포하지 않았다.
