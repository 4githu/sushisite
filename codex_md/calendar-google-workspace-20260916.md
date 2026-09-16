# Google 로그인 · 캘린더 · 공유 프로젝트 · Android 위젯

## 적용 내용

- Re:hear 게스트/로그인 모달 및 로그인 페이지에서 Google 로그인. 검증된 Google 계정의 최초 로그인 시 초밥 계정과 Re:hear 프로필 자동 생성. 기존 Gmail/Workspace 이메일은 기존 초밥 계정에 연결.
- Aura/캘린더의 Google 로그인, 로그인 계정과 별개인 여러 Google 캘린더 계정 연결.
- 연결·공유에서 계정별 캘린더 선택, 가져오기, 수동 동기화, 연결 해제. 연결된 계정은 5분 간격 서버 동기화.
- 일정 편집창의 ‘구글로 보내기’로 대상을 명시적으로 선택. 이미 가져오거나 내보낸 일정의 이후 수정/삭제 연동. 모든 개인 일정을 자동으로 외부 공개하지 않음.
- Google ETag를 이용한 동시 수정 보호. 연결 패널에서 앱 내용 유지 / Google 내용 사용으로 충돌 해결.
- 월/주/할 일 공통 화면. 날짜/30분 시간대를 눌러 생성. 주간 겹치는 일정은 나란히 표시. 같은 편집창에서 수정/삭제/장소/웹페이지/메모/반복 범위 관리.
- Aura 일정 클릭 시 다른 페이지로 이동하지 않고 편집창 표시. ‘클리닉 상세 수정’은 기존 학교·학생·회차 편집창. 날짜별 강의실 요청문 유지.
- 카테고리 표시/숨기기, 검색, 프로젝트 필터, 완료한 할 일 표시, 전체 할 일 모아보기.
- 프로젝트 생성 및 특정 이메일에 묶인 7일 일회용 초대 링크. 구성원은 일정을 함께 편집. 완료 상태는 `(event_id,user_id)`별로 저장하며 다른 구성원의 완료 여부는 반환하지 않음.
- PWA manifest, 192/512 PNG 아이콘, 설치 버튼, 개인정보를 캐시하지 않는 오프라인 안내. 오프라인 일정 편집은 지원하지 않음.
- Android 8+ 네이티브 일정 위젯. 5분 일회용 코드로 연결하고 30분 간격 또는 수동 새로고침. 일정 탭 시 웹앱 해당 일정 편집. Android Keystore 암호화, 읽기 전용 토큰, 서버에서 전체 기기 연결 철회.

## 사용하는 설정

기존 환경변수 이름을 호환한다. 값을 이 문서/로그에 기록하지 않는다.

| 서비스 | Client ID | Client Secret |
|---|---|---|
| Re:hear | `REHEAR_OATHID` | `REHEAR_OATHKEY` |
| Aura / Calendar | `CALANDER_OATHID` | `CLADNDER_OATHKEY` 또는 `CALANDER_OATHKEY` |
| 공통 대체값 | `GOOGLE_CLIENT_ID` | `GOOGLE_CLIENT_SECRET` |

갱신 토큰은 Fernet 암호화 후 서버 DB에 저장. `GOOGLE_TOKEN_ENCRYPTION_KEY`가 있으면 사용하며 없으면 기존 `JWT_SECRET_KEY`에서 서비스 전용 키를 파생한다. 이 키를 바꾸면 기존 Google 계정의 재연결이 필요하다.

OAuth는 서버 리디렉션 + PKCE + 일회용 state + 브라우저 nonce를 사용한다. 연결 콜백은 최초 연결을 요청한 초밥 로그인 계정도 다시 확인한다. 승인된 JavaScript 원본 없이 동작한다.

요청한 호스트의 `https://<host>/auth/google/callback`을 사용하므로 실제 이용하는 호스트별 정확한 URI가 Google Console에 있어야 한다. `chobab.app`에서도 직접 Google 로그인을 사용할 경우 그 주소의 callback도 추가해야 한다.

현재 공개 배포 주소 `rehear.chobab.app`, `aura.chobab.app`의 OAuth 시작 307 / 비로그인 계정 API 401 확인. 스크린샷의 `calender.chobab.app`(calender 철자) 새 DNS/터널 연결은 자동 승인 검토에서 명시적 승인 필요로 차단되어 사용자 승인 대기. 설정 패치는 `calendar-tunnel.patch`에 준비됨. `calendar.chobab.app`과 서로 다른 주소임.

Google Calendar API 활성화가 필요하다. Gemini API 키 및 SMTP 앱 비밀번호는 사용하지 않는다. OAuth Testing 상태에서 Calendar 권한을 요청하면 갱신 토큰이 7일 만료될 수 있으므로 운영 공개 전 OAuth 배포 상태/검증을 확인한다.

## 사용 순서

1. Aura 또는 캘린더에서 Google로 로그인.
2. ‘연결·공유 → 계정 추가’에서 캘린더 권한 동의.
3. 계정의 ‘캘린더 선택 → 선택한 캘린더 가져오기’.
4. 로컬 일정을 Google에 연결하려면 일정 클릭 → 구글로 보내기 → 계정/캘린더 선택.
5. 공유 프로젝트는 연결·공유에서 생성하고 초대받을 이메일 지정 후 생성된 링크를 직접 전달. 메일은 자동 발송하지 않는다.
6. 새 일정의 프로젝트 필드에서 공유 프로젝트 선택. 할 일은 각자 완료 체크.
7. Android Chrome에서 ‘앱으로 설치’. 실제 위젯은 연결·공유에서 APK 다운로드 후 설치 → 웹앱에서 코드 발급 → 위젯 앱에서 같은 서비스 주소와 코드 입력 → 홈 화면에 위젯 추가.

## 제한과 보존 규칙

- Google 실제 권한 승인 및 실계정 왕복 동기화는 사용자의 Google 로그인 후 확인해야 한다. API 동작은 모의 Google 서버로 테스트했다.
- Google에서 가져오는 범위: 지난 1년부터 향후 2년. 반복 일정은 개별 발생 일정으로 가져온다.
- 읽기 전용 Google 캘린더는 로컬에서 수정·삭제하지 못한다.
- Google에서 삭제한 외부 가져오기 일정은 앱에서도 제거한다. Google에서 삭제한 앱 원본/Aura 일정은 클리닉·리포트 보호를 위해 원본을 유지하고 연결만 제거한다.
- 연결 해제는 Google 원본을 삭제하지 않는다. 이미 가져온 로컬 복사본은 개인 일정으로 유지한다.
- Google Tasks API는 사용하지 않는다. 초밥의 할 일 완료 상태는 Google 이벤트/다른 사용자에게 전파하지 않는다.
- APK는 직접 설치용 **debug 서명 테스트 빌드**이며 Play Store 배포용으로 서명하지 않았다. 실제 Android 기기/에뮬레이터 화면 검증은 아직 수행하지 않았다.
- 위젯은 다음 일정을 조회하며 클릭 시 웹앱으로 이동한다. 위젯 자체에서 할 일을 완료 처리하지 않는다.
- 사용자 인증 쿠키의 기존 만료 시간(1시간)을 유지했다.

## 검증과 백업

- `sushi-fast/.venv/bin/python -m pytest personal_project/tests/test_workspace.py auth/tests/test_password_reset.py -q`: 14 passed.
- 브라우저 E2E: 4 passed (주간 추가/수정/삭제, Aura 편집, 할 일, 필터, 모바일 폭, manifest).
- `npm run check`: 0 errors / 0 warnings.
- `npm run build`: 성공.
- Android `assembleDebug lintDebug`: 성공. 문자열 리소스/새 Android 백업 설정 등의 비치명적 Lint 경고는 남아 있음.
- DB 백업: `/Users/sagi/Documents/sushisite-oauth-backup-ai0Tjo/` 안에 `personal_project.db`, `sushiusers.db`, `odi.db`.
- 새로운 테이블/열을 추가하는 비파괴 마이그레이션. 기존 계정/일정 삭제나 덮어쓰기 없음.
- 기존 작업 트리의 Re:hear 기능 변경은 보존. 서비스 인증 교환 `/odi/db/login`, `/join`에는 주 인증 계정 검증 추가.
- 프로젝트가 지시한 Svelte MCP 도구는 이 세션에서 제공되지 않아 Svelte 컴파일러/타입 검사/Playwright로 검증.

## Android 재빌드

소스: `android-widget/`. Gradle 8.11.1, Java 17, Android SDK 35.

```
JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home \
ANDROID_HOME=/Users/sagi/Documents/ondo-android-sdk \
GRADLE_USER_HOME=/Users/sagi/Documents/ondo-gradle-cache \
/private/tmp/ondo-gradle-runtime/gradle-8.11.1/bin/gradle assembleDebug lintDebug --no-daemon
```

빌드 APK: `android-widget/app/build/outputs/apk/debug/app-debug.apk`.
웹 다운로드 복사본: `sushi-app/static/downloads/ondo-widget.apk`.

## 참고한 설계 자료

- [Google Calendar: 할 일 관리](https://support.google.com/calendar/answer/9901136)
- [Samsung Calendar: 날짜 선택과 일정 관리](https://www.samsung.com/ae/support/mobile-devices/how-to-use-the-samsung-calendar-app/)
- [NN/g: 필요한 정보에 집중하는 UI](https://www.nngroup.com/articles/aesthetic-minimalist-design/)
- [Android App Widgets](https://developer.android.com/develop/ui/views/appwidgets)
- [Google OAuth 서버 흐름](https://developers.google.com/identity/protocols/oauth2/web-server)
