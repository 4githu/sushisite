# Google OAuth 관리자 설정

2026-10-02 운영 확인 결과 로그인은 `redirect_uri_mismatch`에서 중단됩니다. 콘솔 설정은 서비스 소유자가 진행합니다.

1. Google Cloud에서 현재 서버의 OAuth 클라이언트와 같은 프로젝트를 선택합니다. Google Auth Platform → Clients에서 해당 **웹 애플리케이션** 클라이언트를 엽니다. 새 클라이언트를 만들 필요는 없습니다.
2. 승인된 리디렉션 URI에 **`https://chobab.app/auth/google/callback`**을 추가합니다. 기존 URI는 유지하세요. 끝에 `/`를 붙이지 않습니다. NETAQ 로그인은 이 콜백을 거쳐 일회성 연결로 NETAQ로 돌아옵니다. `netaq.chobab.app`만 등록하면 현재 오류가 해결되지 않습니다.
3. 캘린더 연동을 사용할 프로젝트에서 **Google Calendar API**를 활성화합니다.
4. 동의 화면의 앱 이름, 지원 이메일, 홈페이지·개인정보처리방침, 승인된 도메인을 실제 운영 정보로 설정합니다. 테스트 상태라면 사용할 Google 계정을 테스트 사용자에 추가합니다. 외부 공개와 민감 범위 검증은 콘솔의 요구사항을 따릅니다.
5. 현재 로그인 요청 범위는 `openid email profile`입니다. 캘린더 연결 때만 `https://www.googleapis.com/auth/calendar.calendarlist.readonly`와 `https://www.googleapis.com/auth/calendar.events`를 추가 요청합니다.
6. 저장 후 NETAQ에서 로그인을 새로 시작하고, 캘린더 연결도 별도로 확인합니다. 기존 오류 페이지를 새로고침하는 것만으로는 만료된 로그인 요청을 복구하지 못할 수 있습니다.

서버의 기존 클라이언트 ID/Secret을 바꾸지 않았다면 코드나 환경변수 변경은 필요 없습니다. 교체할 때만 서버의 `CALANDER_OATHID`와 기존 Secret 설정을 함께 맞춥니다. Secret은 브라우저 코드, 문서, 게시글, Git에 넣지 않습니다. 현재 방식은 서버 리디렉션 OAuth이므로 JavaScript 원본 등록만으로 콜백 오류를 해결할 수 없습니다.

근거: [Google 웹 서버 OAuth 안내](https://developers.google.com/identity/protocols/oauth2/web-server).
