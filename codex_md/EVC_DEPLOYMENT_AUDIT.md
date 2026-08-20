# EVC 배포 점검 결과

점검일: 2026-08-15 (Asia/Seoul)

Unity base URL: `https://rehear.chobab.app/odi/xreal_rehear/evc`

## 확인 완료

- 공개 `https://rehear.chobab.app/openapi.json`에 Smart Start, Session GET/DELETE, Update가 노출됨
- `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`가 Git에서 제외된 `sushi-fast/.env`에 주입됨 (값은 점검 출력에 노출하지 않음)
- uvicorn이 `--workers` 없이 단일 프로세스로 실행됨
- Cloudflare Tunnel HTTPS를 사용하며 외부에서 Mac으로 여는 인바운드 포트 없이 outbound tunnel로 연결됨
- 공개 터널을 통한 실제 WAV multipart smoke test 통과
  - Smart Start `200`
  - Update `200`, step `0 → 1`
  - Session GET `200`, step `1`
  - Delete `204`
- EVC 로그는 session ID, request ID, step과 집계 메타데이터만 기록하며 token, transcript, 음성 원본, 임시 업로드 경로를 기록하지 않음
- `EVC_DEBUG_LOG=false`, `EVC_INCLUDE_DIAGNOSTICS=false` 확인
- EVC 테스트 `66 passed`, compileall 성공, pip check 성공

## 운영 전 팀 결정 필요

- EVC 경로에는 현재 기존 서비스 로그인 인증/API gateway 정책이 적용되지 않음. Smart Start는 공개이고 이후 요청만 EVC session token으로 보호됨. Unity 배포 방식에 맞춰 Cloudflare Access, 별도 API key 또는 기존 인증 적용 여부를 확정해야 함.
- 세션 저장소는 현재 프로세스 메모리 기반임. 서버 재시작 시 세션이 사라지며 수평 확장이 불가능하므로 확장 전 Redis/DB 전환 결정을 해야 함.
- 실제 WAV 업로드는 통과했지만 운영에서 허용할 최대 크기는 애플리케이션 기준 audio 15 MiB, slide 25 MiB임. Unity의 chunk 크기를 이 범위 아래로 고정해야 함.

## 공개 경로

- OpenAPI: `https://rehear.chobab.app/openapi.json`
- Swagger UI: `https://rehear.chobab.app/docs`
- Smart Start: `POST /odi/xreal_rehear/evc/smart-start`
- Update: `POST /odi/xreal_rehear/evc/update`
- Session: `GET/DELETE /odi/xreal_rehear/evc/sessions/{session_id}`
