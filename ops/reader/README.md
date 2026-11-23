# 홈서버 Reader 화면 배포

Reader는 기존 Sushi 인증·API를 사용한다. 화면 빌드는 `READER_ISOLATED_BUILD=1 BUILD_TARGET=node BUILD_OUT=build-reader npm run build`로 만들며 앱 자산 경로는 `/__paiper/`다. 빌드에는 공개 프런트 설정과 합성 build-only DB만 제공하고 런타임 비밀을 넘기지 않는다.

검증한 소스와 산출물을 저장소 밖의 버전별 릴리스 폴더에 보존한 뒤 기존 python-dotenv 환경에서 `ops/reader/install_frontend.py --home <private-runtime> --release <release> --revision <full-sha> --legacy-frontend <existing-sushi-app>`를 실행한다. 현재 런타임은 `~/Library/Application Support/PaiperReader`, LaunchAgent는 `app.paiper.reader`, loopback 포트는 5194다.

이 설치는 기존 5173 프런트의 빌드를 다시 만들지 않는다. 기존 gateway에 Reader 경로와 별도 자산 경로만 추가하고 API·NETAQ·Aura·기존 노트 경로를 유지한다. 비공개 설정은 런타임 JSON에 두며 버전 확인은 `/personal-project/reader/_release`다. Reader 백엔드 모듈·개인 소유자 설정과 실제 인증된 GPT 검증은 별도 반영해야 한다. 이 화면 배포기가 임의로 API 키나 공급자를 생성하지 않는다.

실패하면 이전 Reader 화면 릴리스로 복구하고, 첫 설치라면 gateway와 Reader 활성화를 되돌린다. 메모·PDF는 브라우저의 사용자별 저장이며 이 배포기는 사용자 데이터를 이전·복원·삭제하지 않는다.

API는 기존 Backend 환경에서 `ops/reader/install_backend.py --source <accepted-release>/sushi-fast --backend <existing-sushi-fast> --home <private-runtime> --owner-id <confirmed-id>`로 반영한다. 두 Reader 경로와 모듈만 추가하며 다른 API 코드는 보존한다. 필요한 비밀이 아닌 제공자 설정을 기존 `.env`에 반영한 뒤 기존 서비스 한 개를 재시작한다. 실패 시 Reader 변경과 그 설정만 복구한다. 이미 Reader 경로가 존재하는 후속 배포는 중복 추가하지 않고 명시적인 통합 검토를 요구한다.
