NETAQ Windows Widget 1.0.0

Windows 10/11 x64용 독립 바탕화면 앱입니다. Win+W 위젯 보드 공급자가 아닙니다.
설치: https://netaq.chobab.app/downloads/windows-widget
연결: https://netaq.chobab.app/personal-project/calendar/widgets

오늘/주간/월간/할 일, 메모 보기와 웹 편집 연결, 빠른 기록과 할 일 완료를 지원합니다.
설정에서 창 고정, 항상 위, 자동 시작, 테마를 바꿀 수 있습니다.
토큰·오프라인 자료·임시 입력은 운영체제 safeStorage로 암호화합니다.
연결 만료·해제 시 개인 캐시를 지우며, 통신 실패 시 마지막 자료와 입력을 보존합니다.

개발: npm ci / npm start / npm test
Windows 배포: npm run dist:win
완성된 EXE와 ZIP은 dist/에 게시됩니다. 빌드 중 파일은 build-release/에만 생성합니다.
직접 배포 설치 파일이며 코드 서명은 적용하지 않았습니다.
네이티브 UI 검증: sushi-app/tests/netaq-windows-widget.e2e.ts
이 검증은 Mac Electron에서 격리 저장소와 가상 서버 응답으로 수행했습니다.
실제 Windows PC 설치와 자동 시작 동작은 아직 확인하지 않았습니다.
