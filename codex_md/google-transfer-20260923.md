# Google 캘린더 가져오기·내보내기 — 2026-09-23

Google 가져오기와 내보내기를 분리했다. 삼성 캘린더는 Google 계정을 연결하고 일정을 저장할 계정을 선택한다. 일방향 가져오기와 증분 동기화는 다른 개념이다.

- 가져오기: 지난 1년~앞으로 2년의 Google 일정을 5분마다 조회. 가져온 일정은 읽기 전용. 앱 수정·삭제를 Google에 자동 전송하지 않는다. 이전 양방향 모드에서 미해결 로컬 수정이 있으면 충돌로 보존한다.
- 내보내기: 프로젝트와 연결 → 캘린더 선택 → 내 캘린더 → Google 내보내기. 대상 캘린더·한국 시간 기준 시작/종료일을 선택하고 추가·덮어쓰기 건수를 미리 확인한 뒤 실행한다. 기간에 시작하는 본인 소유 일정만 포함하고 Google에서 가져온 일정은 제외한다.
- 덮어쓰기는 이전에 내보낸 사본의 제목·설명·시간·장소·원본 링크에 적용한다. Google에 별도로 만든 일정이나 삭제된 로컬 일정의 과거 사본을 지우는 전체 교체는 하지 않는다. 자동 내보내기도 하지 않는다.
- 실행 전에 로컬 스냅샷과 Google ETag를 다시 확인한다. 변경되면 재확인이 필요하다. 개별 PATCH도 If-Match 조건부 요청이다. 결정적 ID와 건별 연결 기록으로 부분 실패 후 재시도 시 중복 생성을 방지한다. 최대 200건/367일, 실패 시 처리 건수를 알린다. 초대 이메일은 전송하지 않는다.
- 기존 단일 일정 내보내기도 유지하며, 내보냈다는 이유로 가져오기를 자동 활성화하지 않는다.

## 범위와 한계

현재 가져오기는 기간 전체 조회다. syncToken 기반 증분 동기화는 이번 배포에 포함하지 않았다. 향후 도입 시 반복 일정과 조회 기간 이동, 토큰 만료(410), 페이지 처리 완료 후 토큰 저장을 함께 구현해야 한다. 실제 연결된 개인 Google 계정의 원본을 테스트 중에 변경하지 않았으며 API MockTransport로 프로바이더 동작을 검증했다.

## 검증

- 백엔드 workspace 테스트 22개 통과: 권한, 읽기 전용, 충돌 보존, 미리보기 변경 감지, 멱등성, 자동 쓰기 금지, 부분 실패 재시도 포함.
- Svelte 검사 오류·경고 0개. 프로젝트에서 요구하는 Svelte MCP 도구가 세션에 제공되지 않아 컴파일러와 브라우저 테스트로 검증했다.
- 캘린더 Playwright 테스트 13개 통과. 데스크톱·390px 모바일 화면과 가로 넘침 확인.
- 학생·프로젝트·위젯·필기 변경 범위는 `student-project-widget-20260923.md` 참고. 이 변경은 기존 PR #13의 캘린더 기반 구현을 사용한다.

## 근거

- https://www.samsung.com/uk/support/mobile-devices/how-to-sync-your-google-calendar-on-your-samsung-galaxy-device/
- https://developers.google.com/workspace/calendar/api/guides/sync

## 운영 배포

- 2026-09-23 adapter-node 프로덕션 빌드를 교체하고 기존 frontend/backend launchd 서비스를 재시작했다. DNS·터널 설정은 변경하지 않았다.
- 실제 서비스: https://chobab.app/personal-project/calendar/projects . calendar/calender 별도 도메인은 현재 DNS/터널에 설정되지 않았다.
- 운영 Google 전송 화면 브라우저 테스트 1개 통과(인증·Google 데이터만 모의 응답). 실제 개인 Google 일정에는 테스트 쓰기를 하지 않았다.
- chobab.app / aura.chobab.app / rehear.chobab.app 페이지 200, 비로그인 Google API 401. 새 전송 API 등록 확인, DB quick_check 정상.
- APK 다운로드 200, application/vnd.android.package-archive, attachment filename=ondo-widget.apk, 44,698바이트 확인.
- DB 백업 `/private/tmp/ondo-before-google-20260923.db`, 이전 프런트엔드 빌드 `/private/tmp/ondo-build-before-google-20260923` 보존. DB 복원은 후속 사용자 데이터를 잃을 수 있으므로 자동으로 하지 않는다.
- 이번 PR에는 캘린더·학생·프로젝트·위젯 관련 파일만 포함하며, 작업 공간에 있던 별도 Rehear/인증 변경은 커밋하지 않았다. 운영 빌드는 기존 작업 공간 상태 위에 생성했다.
