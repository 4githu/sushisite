# 학생서비스·메모·위젯 개선 (2026-09-27)

## 구현

- `/personal-project/calendar/student/timetable`: 실제 서울대 강의 검색(강의명/교수명/과목번호, 학과/이수구분/요일), 주간 그리드, 중복 담기·시간 충돌 방지, 학기별 서버 저장 및 수정 충돌 감지. 다른 학교의 수업은 직접 입력한다.
- 공휴일/휴강일 미리보기 후 학기 수업을 캘린더로 가져오기. 미리보기 이후 변경 시 가져오기 비활성화, 이미 가져온 동일 수업은 추가 선택 후 재실행해도 중복 생성하지 않는다. 시간표에서 빼는 동작은 기존 캘린더 일정을 삭제하지 않는다. NETAQ JSON 파일 가져오기/내보내기를 지원한다.
- `/student/plan`: Class Checker의 이수규정 200개. 실제 자료에 있는 학과·학번·트랙만 선택하며 복수전공/부전공 필수 과목과 인정 조건 및 원문 설명을 보존한다. 졸업 충족 자동 판정은 하지 않는다.
- `/student/meals`: 서울대 생협 공식 식단을 서버에서 조회, 15분 캐시, 날짜 확인, 식당별 펼침/접힘. 네트워크 실패 시 캐시를 오래된 자료로 명시하고, 캐시도 없으면 오류와 재시도를 제공한다. 외부 HTML을 그대로 렌더링하지 않는다.
- 사이드바에 학생서비스 하위 목적지를 직접 노출. 학교 설정과 게시판을 별도 화면으로 분리한다.
- 일간 메모의 서식 편집기에서 토글 목록을 추가한다. 제목 수준에 따라 다음 제목 전까지 내용을 접고 펼치며, 접힘 상태와 숨긴 내용 모두 저장/복원한다. 필기판 전체를 접을 수 있고 손가락 그리기 방지 및 펜 지우개 신호(32/2)를 처리한다.
- Android 1.3.0 (versionCode 4): 각 위젯의 이전/다음/오늘 이동 상태 분리, 날짜 기준 API 조회, 일간 위젯에 일정과 할 일 두 영역. 설치된 WebAPK를 우선 열고 없으면 앱 내부 WebView로 연다. 내부 화면에서는 처음에 별도로 로그인해야 한다. 위젯 조회 토큰을 웹 로그인 토큰으로 전환하지 않는다. 외부 사이트는 브라우저로 연다.
- PWA manifest scope를 해당 서비스 경로로 좁혔다. Aura/Calendar의 설치 범위 중첩을 줄인다.

## 검증

- 실제 2026-2 자료구조(강유, M1522.000900/001) 검색, 월/수 09:30~10:45 배치, 저장/재접속, 충돌 안내, 캘린더 등록/재등록 확인.
- 신규 학생서비스 브라우저 4개, 기존 캘린더/아우라 15개 항목 검증. 기존 펜 테스트는 스크롤 후 좌표를 다시 읽도록 수정하고 소프트웨어 지우개와 Surface/S펜 신호를 검증했다.
- 백엔드 신규 8개 + 기존 워크스페이스 22개, 총 30개 통과. 강의 원본 레코드 수, 학번별 규정, 사용자 분리, 동시 수정, 가져오기 중복 방지, 식단 파싱·캐시·장애, 위젯 주 이동, 파일 가져오기 충돌 방지.
- 공식 식단 API 실조회 성공: 2026-09-27, 식당 2곳(추석 연휴), 날짜 일치 및 캐시 상태 정상.
- Svelte 검사 오류·경고 0. 프런트엔드 프로덕션 빌드 성공.
- Android assembleDebug/lintDebug 성공(기존 API 호환·번역 관련 경고와 WebView JavaScript 사용 안내 있음), 시간 배치 계산 4개 검증.
- APK 서명이 기존 배포본과 일치한다. 새 APK는 `sushi-app/static/downloads/ondo-widget.apk` 및 서버 asset에 복사했다.
- 연결된 Android 기기가 없으므로 런처 위젯 크기, WebAPK/WebView 실제 전환, Surface/S펜 하드웨어의 신호 전달은 실기기 미검증이다. Google 등의 외부 OAuth 흐름은 내부 WebView에서 별도 검증이 필요하다.
- 화면 캡처: `codex_md/student-services-review/` (데스크톱·390px 모바일). 모바일에서 주중 5열이 모두 보이며 문서 전체 가로 넘침이 없다.

## 재현

저장소 루트에서 임시 DB 서버를 실행한다 (개발 검증용이므로 운영에 배포하지 않는다):

```sh
PYTHONPATH=sushi-fast:sushi-app/tests/support PERSONAL_PROJECT_DB_PATH=/private/tmp/student-review.db sushi-fast/.venv/bin/python -m uvicorn student_test_server:app --host 127.0.0.1 --port 18761
```

별도 프런트 개발 서버를 5187에서 실행한 후 `sushi-app` 폴더에서:

```sh
STUDENT_TEST_API_URL=http://127.0.0.1:18761 PLAYWRIGHT_BASE_URL=http://127.0.0.1:5187 npx playwright test tests/student-services.e2e.ts tests/calendar-workspace.e2e.ts tests/aura-student-checks.e2e.ts --workers=1
```

학식 UI 테스트는 공식 페이지에서 확인한 고정 데이터를 사용하며 파서는 공식 HTML 스냅샷으로 별도 검증한다. 강의 검색/저장은 실제 스냅샷·실제 API와 임시 DB를 사용한다. 운영 사용자 데이터는 테스트에 사용하지 않는다.

## 반영 상태

소스와 설치 APK 준비 완료. 이번 작업에서 운영 프로세스 재시작 또는 배포는 수행하지 않았다. 운영 반영에는 새 프런트 빌드와 백엔드 재시작이 모두 필요하다. 새 DB 테이블은 사용자별 시간표 초안 저장을 위해 초기화 시 생성된다. 앱 외부 계정(SNUTT/에브리타임) 연동은 포함하지 않는다.

## 참고

- https://github.com/Rekhet/class-checker
- https://github.com/wafflestudio/snutt
- https://snuco.snu.ac.kr/foodmenu/
- https://developer.android.com/develop/ui/views/layout/webapps/webview
- https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events

APK SHA-256: `9e90449c3f0fec9efff2e6ca0c525e8a36d5d88f7739c82f4fb7517282896d3d`.
임시 검수 API와 개발 서버는 종료했다.
