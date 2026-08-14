# 맥 홈서버 이전 · Codex 인수인계

이 문서는 `sushisite`를 리눅스 개발 PC에서 맥 홈서버로 안전하게 옮기고, 맥의 Codex가 바로 이어서 작업할 수 있게 만든 기준 문서다.

## 절대 지킬 것

- 작업 범위는 `sushisite/sushi-app`(Svelte 프런트엔드)와 `sushisite/sushi-fast`(FastAPI 백엔드)다. 다른 프로젝트는 읽거나 수정하지 않는다.
- 데이터베이스, 업로드 파일, `.env`는 Git으로 옮겨지지 않는다. 삭제·초기화·새 DB 생성으로 기존 내용을 덮어쓰지 않는다.
- `node_modules`, Python `.venv`, `.svelte-kit`은 운영체제별 네이티브 바이너리를 포함한다. 리눅스에서 복사하지 말고 맥에서 재설치한다.
- 현재 Git 작업 트리에 커밋하지 않은 사용자 변경이 있을 수 있다. 되돌리거나 `git reset --hard`하지 않는다.

## 구성과 데이터 위치

| 구분 | 위치 | 이전 방법 |
| --- | --- | --- |
| 프런트엔드 | `sushi-app` | Git clone 후 `npm ci` |
| 백엔드 | `sushi-fast` | Git clone 후 Python venv 및 `pip install -r requirements.txt` |
| 공통 로그인 DB | `sushi-fast/DB/sushiusers.db` | 반드시 복사 |
| ODI DB | `sushi-fast/odi/db/odi.db` | 반드시 복사 |
| 개인 프로젝트/Aura DB | `sushi-fast/personal_project/personal_project.db` | 반드시 복사 |
| Aura 첨부 파일 | `sushi-fast/personal_project/uploads/` | 반드시 복사 |
| 기타 ODI 업로드 | `sushi-fast/storage/odi/` (있다면) | 복사 |
| 비밀값 | `sushi-fast/.env`, `sushi-app/.env` | 안전한 별도 전달로 복사 |

`personal_project.db`에는 Aura 클리닉과 리포트 기록이 있다. 소유자 ID를 포함해 **절대 삭제/초기화하지 않는다**. 로그인 DB도 같은 원칙이다.

## 맥에 설치할 것

먼저 Xcode Command Line Tools와 Homebrew를 설치한다.

```bash
xcode-select --install
```

Homebrew 설치 후:

```bash
brew install git node@22 python@3.12 ffmpeg sqlite cloudflared
```

`ffmpeg`는 발표 음성 파일을 분석하는 Legendaryvowels 기능에 필요하다. SQLite는 Python 기본 모듈만으로도 동작하지만, 백업/점검용 CLI도 설치해 둔다. `cloudflared`는 `chobab.app` 원격 공개를 이어갈 때 필요하다.

Node는 22 LTS 기준으로 맞춘다. `better-sqlite3` 등 네이티브 Node 모듈은 맥에서 `npm ci`로 빌드된다.

## VS Code 확장

VS Code에서 `Cmd+Shift+P` → `Shell Command: Install 'code' command in PATH`를 한 번 실행한 뒤 아래를 설치한다.

```bash
code --install-extension svelte.svelte-vscode
code --install-extension bradlc.vscode-tailwindcss
code --install-extension esbenp.prettier-vscode
code --install-extension dbaeumer.vscode-eslint
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension charliermarsh.ruff
```

앞의 네 개는 프로젝트 `.vscode/extensions.json`의 권장 확장이고, 뒤의 세 개는 FastAPI/Python 작업용이다. Docker를 실제로 사용할 때만 `ms-azuretools.vscode-docker`를 추가한다.

Codex는 VS Code 확장에서 로그인해 사용하거나 VS Code 터미널에서 CLI로 사용할 수 있다. ChatGPT 요금제 로그인으로도 Codex IDE/CLI를 사용할 수 있으며 VS Code와 호환 IDE를 지원한다. [공식 안내](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan/)

## 이전 순서

### 1. 현재 PC에서 코드와 데이터 분리

현재 작업을 먼저 Git에 커밋·push한다. 그런 다음 프런트/백엔드를 끄고, 아래의 데이터만 외장 SSD·암호화 아카이브 등 Git이 아닌 안전한 방식으로 맥에 옮긴다.

```bash
cd /home/a0104/mygit/sushisite
tar -czf ../sushisite-runtime-data.tar.gz \
  sushi-fast/.env sushi-app/.env \
  sushi-fast/DB/sushiusers.db \
  sushi-fast/odi/db/odi.db \
  sushi-fast/personal_project/personal_project.db \
  sushi-fast/personal_project/uploads
```

`sushi-fast/storage/odi` 또는 `sushi-fast/evc_uploads`가 실제로 사용 중이면 별도로 포함한다. 서버를 멈춘 뒤 복사해야 SQLite 파일과 첨부 파일의 시점이 일치한다.

### 2. 맥에서 복원 및 의존성 설치

```bash
git clone <본인-저장소-URL> ~/sushisite
cd ~/sushisite
tar -xzf ~/Downloads/sushisite-runtime-data.tar.gz

cd sushi-app
npm ci

cd ../sushi-fast
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Playwright E2E를 실행할 때만 다음을 추가한다.

```bash
cd ~/sushisite/sushi-app
npx playwright install
```

### 3. 실행과 기본 확인

터미널 두 개를 사용한다.

```bash
# Terminal 1
cd ~/sushisite/sushi-fast
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

```bash
# Terminal 2
cd ~/sushisite/sushi-app
npm run dev -- --host 0.0.0.0
```

확인 순서는 로그인 → Aura 학교/리포트 → 첨부 사진 → ODI 세션 순서다. 데이터가 비어 보이면 새로 만들지 말고 `.env`의 DB/API 경로와 복사한 DB의 위치부터 확인한다.

## 외부 도메인 전환 시 확인할 것

- 백엔드 `main.py`의 CORS 허용 목록에 `https://chobab.app`, `https://aura.chobab.app`을 추가한다.
- 프런트엔드 API URL 관련 `.env`가 `localhost:8000`만 가리키지 않게 공개 API 주소로 바꾼다.
- Kakao 설정의 Redirect URI도 새 공개 주소와 정확히 일치시킨다.
- Cloudflare Tunnel은 맥에서 `cloudflared`로 재로그인·재설치하고, 나중에는 `launchd`로 백엔드/프런트/tunnel을 자동 시작시킨다.

## 제품 맥락

- 개인 프로젝트의 **캘린더**와 **Aura**는 독립 시스템이다. Aura는 캘린더와 연동할 수 있지만 DB/화면/도메인을 합치지 않는다.
- Aura는 학교 → 회차 → 학생 구조이며, 다회차는 하나의 클리닉 리포트 안에 묶인다. 리치 에디터 JSON, 형광색, Ctrl/Cmd+Alt+Q의 질문 확인선, 첨부 이미지, PDF/Kakao 내보내기를 유지한다.
- ODI/Re:hear는 발표 연습·VR 청중 반응·세션 리포트 시스템이다. Aura와 공통 로그인만 공유한다.
- 최근 UI 작업은 사이드바/반응형 레이아웃과 리포트 UI에 집중돼 있었다. 특히 사이드바 확장 시 본문이 비어 보이던 CSS 클래스 충돌은 `odi/+layout.svelte`에서 `sidebar-expanded`로 분리해 수정했다. 변경을 되돌리지 말고 맥에서 `npm run build`로 확인한다.

## 맥의 Codex에 바로 붙여 넣을 요청

```text
이 저장소를 이어서 관리한다. 먼저 codex_md/MAC_HOME_SERVER_HANDOFF.md와 codex_md/PROJECT_ONBOARDING.md를 읽어라.

범위는 sushisite/sushi-app과 sushisite/sushi-fast뿐이다. 다른 프로젝트 폴더를 읽거나 수정하지 마라. DB, uploads, .env, node_modules, .venv는 사용자 데이터/로컬 런타임이므로 삭제·초기화·Git 커밋하지 마라. 특히 sushi-fast/personal_project/personal_project.db의 Aura 기록과 sushi-fast/DB/sushiusers.db를 절대 새 DB로 덮어쓰지 마라.

프런트는 SvelteKit/Vite, 백엔드는 FastAPI다. 의존성은 frontend에서 npm ci, backend에서 .venv를 만든 후 pip install -r requirements.txt로 설치한다. ffmpeg도 필요하다. 작업 전 git status를 확인해 기존 변경을 보존하고, 변경 후에는 npm run build 및 관련 백엔드 검사로 검증해라.

개인 프로젝트에서는 캘린더와 Aura를 독립적으로 유지하되 필요한 연동만 구현한다. ODI/Re:hear는 발표 연습 시스템으로 공통 로그인 외에 Aura 데이터와 섞지 마라. 외부 chobab.app 배포 작업에서는 CORS, 프런트 API URL, Kakao Redirect URI, Cloudflare Tunnel 설정을 함께 점검해라.
```
