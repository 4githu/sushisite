# Mac mini 운영 안정화 — 2026-09-25

## 확인
- 전용 Mac mini, 유선 en0. `pmset`의 시스템 sleep=0. Node 프로덕션 서버와 백엔드 모두 정상 실행 중이었다. 초기 샌드박스 내 curl 실패는 서버 중단의 증거가 아니었다.
- cloudflared의 기존 연결 4개는 인천 접점이었다. 과거 QUIC 연결 교체 로그만으로 전체 서비스 중단을 판단할 수 없다.
- EVC SessionStore와 카카오 업로드 작업은 프로세스 메모리를 사용한다. 멀티 워커로 바로 변경하면 요청별 상태가 달라질 수 있어 단일 워커 유지. 워커 확장은 공유 상태/작업 큐 설계 후 해야 한다.
- 정적 자산은 이미 프로덕션 빌드 및 immutable 1년 캐시 헤더를 사용하고 있었다.

## 적용
- Homebrew cloudflared 2026.8.2 → 2026.9.3. 기존 버전은 cleanup 없이 남겼다.
- 임시 보조 터널(20242)을 먼저 연결하고 기존 launchd 터널에 SIGTERM을 보내 최신 바이너리로 재기동했다. 운영 연결 4개 확인 후 보조 터널 종료. 운영 터널 프로세스는 1개이다.
- Aura 첨부 및 카카오 이미지 업로드의 동기 저장 작업을 Starlette 스레드풀로 옮겼다. DB/파일 저장 대기가 이벤트 루프를 막는 것을 방지한다. 카카오 전송 자체를 실행하지 않았다.
- `runtime_health.py`: `/api/healthz` liveness (DB 검사 아님), `Cache-Control: no-store`, ASGI 스트리밍을 유지하는 Server-Timing 응답 헤더. 1초 이상 또는 5xx 응답은 route template·method·status·TTFB만 기존 백엔드 오류 로그에 기록한다. 쿼리/쿠키/요청 본문은 추가 로그에 기록하지 않는다.
- 백엔드 연결이 LISTEN만 남은 시점에 SIGTERM 정상 재기동. 프로세스 메모리 세션은 재시작으로 사라질 수 있다. 재시작 직후 첫 자동 점검에는 일시적인 502가 기록됐고 이후 점검은 정상이다.
- `ops/health_probe.py` 및 `app.sushisite.health` LaunchAgent: 300초 간격으로 프런트/백엔드/공개 도메인/공개 API와 터널 연결 수 확인. JSON 상태와 2MB × 최대 4개 회전 로그 저장. 지연 시 강제 재시작은 하지 않으며 사용자 알림 서비스는 별도로 만들지 않았다.
- 설치 파일: `/Users/sagi/Library/LaunchAgents/app.sushisite.health.plist`
- 상태: `/Users/sagi/Library/Logs/sushisite-health/status.json`
- 이력: `/Users/sagi/Library/Logs/sushisite-health/health.jsonl`
- 새 외부 계정/가입/결제 없음. 제공된 계정 비밀번호를 코드나 문서에 저장하지 않았다.

## 검증과 남은 한계
- `python -m pytest -q test_runtime_health.py personal_project/tests/test_upload_responsiveness.py personal_project/tests/test_native_kakao.py`: 8 passed. 업로드 저장이 대기 중일 때 이벤트 루프 진행 및 스트리밍 응답 유지 확인.
- plist 문법 검사, git diff --check 통과. 백엔드와 터널 launchd state=running.
- 임시 터널 종료 후 5회 × 6대상=30회 모두 기대 HTTP 상태. 중앙 TTFB: 로컬 프런트 2.8ms, 백엔드 1.4ms, chobab 294.1ms, Aura 루트 리다이렉트 433.5ms, Rehear 루트 리다이렉트 285.4ms, 공개 health API 217.2ms.
- 이 수치는 단기 점검이며 업데이트 전후 개선율을 의미하지 않는다. 로그인한 화면의 전체 로딩이나 실제 AI 처리 시간도 아니다.
- 이 Mac에서 공개 도메인 호출 시 HKG/NRT/LAX 접점이 관측됐다. LAX의 TLS 연결 완료까지 약 400ms, 전체 첫 응답 약 760~1020ms. Mac → 인천 Tunnel 구간과 방문자 → Cloudflare 접점 구간은 별개다. 모든 방문자가 동일 경로를 사용하는 것은 아니며 회선별 추가 관측이 필요하다.
- 이 기록으로 서버 처리 지연과 공개 네트워크 지연을 구분할 수 있다. 모든 체감 지연의 원인이 해결됐다고 단정하지 않는다.

## 운영 / 되돌리기
- 즉시 점검: `sushi-fast/.venv/bin/python ops/health_probe.py --samples 5` (프로젝트 루트에서).
- 자동 점검 중지: `launchctl bootout gui/$(id -u)/app.sushisite.health`. 다시 켜려면 설치된 plist를 bootstrap한다. launchd 작업은 로그인 사용자 세션에서 실행된다.
- 백엔드 변경 취소 시 main.py의 RuntimeHealthMiddleware import/add_middleware 두 줄을 제거하고 personal_project/router.py의 두 저장 호출을 원래 동기 호출로 복원한 다음 정상 재시작한다. 다른 사용자의 변경이 있는 작업트리이므로 파일 전체 git restore/reset은 사용하지 않는다.
- cloudflared 롤백이 필요하면 기존 `/opt/homebrew/Cellar/cloudflared/2026.8.2/bin/cloudflared` 바이너리로 tunnel LaunchAgent의 실행 경로를 변경해 정상 재기동한다. 그 전 보조 터널을 통한 교체 절차를 동일하게 사용한다.
