# 주간 위젯과 학생별 물어봤음 표시 수정

## Android 1.2.0 / versionCode 3
- 기본 위젯과 주간 위젯을 일~토 7열 시간표로 변경. 종일 일정 행, 시간 눈금, 시작/종료 시각에 비례하는 블록, 겹치는 일정의 별도 열을 표시한다. 빈 시간은 간격으로 유지하고 자정을 넘는 일정은 날짜별로 나눈다.
- 날짜를 누르면 해당 일별 화면, 일정 블록을 누르면 날짜와 event ID를 포함한 일정 링크를 연다. 위젯 크기 변경 시 다시 배치한다.
- HTTPS 주소를 처리하는 설치된 앱을 조회하고, 동일 출처의 NETAQ WebAPK를 우선 지정한다. 기존 Aura/Calendar 웹앱의 넓은 scope가 겹치면 WebAPK 시작 경로가 맞는 앱을 우선한다. 새 탭 강제 플래그 대신 기존 Android 작업 재사용 플래그를 사용한다. 일치하는 설치 앱이 없거나 단순 홈 화면 바로가기만 있는 경우 기본 브라우저로 연다. 다른 출처에 설치된 앱으로 계정 주소를 임의 변경하지 않는다.
- 기존 APK와 서명 인증서 일치를 확인했다. 새 APK를 기존 앱 위에 업데이트할 수 있다. 작은 기존 위젯은 크기를 늘려야 시간표를 읽기 쉽다.

## Aura
- 학생 전환 시 target ID로 편집기 인스턴스를 다시 만들어 체크 DOM, 선택 범위, 실행 취소 기록이 넘어가지 않도록 한다.
- Ctrl/Cmd+Alt+Q 체크 변경도 자동저장한다. 한글 입력 상태에서도 KeyQ 물리 키를 인식하고 길게 누르기의 반복 토글을 막는다.
- 저장을 직렬화하고 자동저장 타이머를 취소/학생 ID에 연결한다. 이전 학생 저장 응답은 현재 학생 report를 덮어쓰지 않는다. 학생 전환 중에는 편집을 잠그고 저장 완료 후 이동한다.
- 폐기된 편집기의 지연 렌더 콜백을 무시한다. 모바일 도구 모음과 사이드바 접기 버튼의 가로 넘침도 수정했다.

## 검증
- Svelte 오류·경고 0개. 제공되지 않은 Svelte MCP 대신 컴파일러/브라우저 검증 사용.
- 학생별 체크 왕복/자동저장 및 늦은 저장 응답 테스트 2개 통과. 390px 모바일과 데스크톱 스크린샷 확인, 가로 넘침 없음. 기존 캘린더 브라우저 테스트 13개 통과.
- Android assembleDebug/lintDebug 성공, 동일 APK 서명 확인. 시간표 배치 계산 4개 검증(겹침, 접한 경계, 30분 위치, 자정 경계/빈 날짜).
- adb 연결 기기가 없어 실제 런처의 위젯 렌더링과 설치된 PWA로의 전환은 실기기 미검증이다. 시스템/브라우저의 웹앱 설치 및 링크 처리 상태에 따라 전환 동작은 달라질 수 있다.

## 참고
- https://developer.android.com/guide/components/intents-filters
- https://developer.android.com/training/package-visibility/declaring
- https://chromium.googlesource.com/chromium/src/+/master/chrome/android/webapk/shell_apk/AndroidManifest.xml

## 운영 반영
- 2026-09-25 프런트엔드 배포 완료. 이전 빌드는 `/private/tmp/ondo-build-before-widget-20260925`에 보존했다. 백엔드/DB 변경은 없다.
- 운영 aura.chobab.app에서 학생 전환 회귀 테스트 2개 통과(모의 API 사용, 실제 학생 데이터 변경 없음).
- 공개 `/downloads/android-widget?v=1.2.0` 응답 200 및 설치용 MIME/파일명 확인. 빌드 산출물과 바이트 일치, 58,569바이트.
- APK SHA-256: `af07184782a0df6f07787e234f74eedc8284f9182ebe5cbce9d3999bf6eac3b7`.
