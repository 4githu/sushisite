# Windows 서명 업데이트 운영

0.11.0 이상은 Tauri 공식 updater를 사용한다. 기존 0.10 이하 버전은 updater가 없으므로 0.11.0을 한 번 설치해야 한다. 최신 버전의 위젯 설정에서 업데이트 확인을 누르면 서명 검증 후 설치를 진행한다. 설치 과정에서 프로그램이 종료되고 다시 시작될 수 있다.

서명 키는 `/Users/sagi/.config/netaq/windows-updater.key`에 보관한다. 저장소에 넣거나 공개하지 않는다. 이 키를 잃으면 이미 배포한 앱을 같은 신뢰 체인으로 자동 업데이트할 수 없다. 소유자가 안전한 곳에 백업해야 한다. `*.pub`는 공개 키다.

새 릴리스: `rust-app/src-tauri/Cargo.toml`과 `tauri.conf.json`의 버전을 함께 올린다. 현재 배포와 같은 키로 Tauri 빌드를 실행하면 NSIS 설치 파일과 `.sig`가 생성된다. `TAURI_SIGNING_PRIVATE_KEY`에 키 파일 경로를 지정하고 `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`를 설정한다. 빌드·검증 후 `windows-widget` 디렉터리에서 `node scripts/stage-update.mjs VERSION /absolute/path/to/setup.exe`를 실행한다. 이 명령은 서명과 설치 파일을 버전별 주소에 게시하고 메타데이터를 마지막에 교체한다. 같은 버전 파일을 덮어쓰지 않는다. 일반 설치 경로와 버전 알림도 새 버전에 맞게 갱신해 배포한다.

업데이터 서명과 Windows Authenticode 서명은 다르다. 현재는 전자만 적용되어 Windows 설치 시 SmartScreen 경고가 나타날 수 있다. 실제 Windows 업데이트 및 기존 연결 보존 여부는 Windows 기기에서 확인해야 한다.
