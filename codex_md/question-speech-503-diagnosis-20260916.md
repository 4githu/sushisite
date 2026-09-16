# 질문 음성 API 503 진단 — 2026-09-16

## 확인된 원인

운영 백엔드의 Azure Speech 환경변수 누락이다. PSA 리소스 또는 구독의 활성 상태와 별개로, 서버가 Azure에 요청하기 위한 키와 리전을 전달받지 못했다.

- 운영 서버는 이 Mac의 `app.sushisite.backend` LaunchAgent이며 `sushi-fast/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000`으로 실행된다.
- 실제 Cloudflare Tunnel 설정(`/Users/sagi/.cloudflared/config.yml`)은 `rehear.chobab.app/odi/xreal_rehear`를 이 백엔드로 전달한다.
- 조사 시 운영 PID 1553의 시작 환경에 `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`이 모두 없었다. `main.py`가 읽는 `sushi-fast/.env`에도 두 값이 없었다. 프로세스 환경 확인에서는 값이나 다른 비밀정보를 출력하지 않았다.
- 운영 접근 로그 `/Users/sagi/Library/Logs/sushisite-backend.log`의 41240, 42218, 44563, 44567, 44571행에 `POST .../questions/0/speech`의 503이 기록돼 있다. 접근 로그에는 응답 본문이 기록되지 않는다.
- 운영 공개 `/openapi.json`은 HTTP 200으로 응답했다.

## 재현 및 인과관계

운영과 동일한 소스 및 `.env`를 사용하는 별도 프로세스에서 FastAPI ASGI 라우터를 호출했다. 합성 질문 2개와 유효한 테스트 세션·청중·목소리를 설정했으며 실제 사용자 세션은 변경하지 않았다.

결과: HTTP 503, `Server configuration missing: AZURE_SPEECH_REGION`.

`azure_speech.synthesize()`는 리전을 먼저 읽고 이후 키를 읽는다. 값이 없으면 `setting()`에서 503을 발생시켜 Azure 네트워크 요청에 도달하지 못한다. Azure가 반환하는 비정상 HTTP 응답은 이 코드에서 502로 변환된다. 따라서 확인된 설정 누락은 질문 생성 성공 이후 음성 요청 단계만 실패하는 현상을 설명한다.

## 수행한 변경

서버 비밀 설정 파일 `sushi-fast/.env`에 `AZURE_SPEECH_REGION='koreacentral'`을 저장했다. 파일 권한은 0600이며 Git 제외 대상으로 확인했다. 키를 임의로 생성하거나 소스에 기록하지 않았다.

리전 저장 후 별도 프로세스의 음성 어댑터 재검증 결과는 HTTP 503, `Server configuration missing: AZURE_SPEECH_KEY`이다.

## Git 저장소 대조

`9e115a6` (`Add Azure speech and answer-driven audience questions`)와 현재/원격의 모든 참조를 검사했다.

- `odi/EVC/AZURE_QA.md`는 서버 비밀 환경에 `AZURE_SPEECH_KEY=<server secret>`, `AZURE_SPEECH_REGION=koreacentral`을 설정하라고 명시하며, Azure 연속 인식이 PSA F0 리소스와 호환된다고 명시한다.
- `azure_speech.py`는 이 키를 `Ocp-Apim-Subscription-Key` HTTP 헤더와 Azure Speech SDK의 `subscription` 값으로 사용한다. 따라서 필요한 값은 Azure OpenAI, 앱 등록, 구독 ID의 키가 아니라 **PSA Azure AI Speech 리소스의 Keys and Endpoint 화면에 있는 Key 1 또는 Key 2**다.
- `.gitignore`는 `*.env`와 `sushi-fast/.env`를 제외한다. Git 이력과 모든 로컬/원격 브랜치에 실제 `AZURE_SPEECH_KEY` 값은 없었다. 이는 비밀값을 저장소에 남기지 않는 의도된 구조다.
- 현재 운영 `.env` 대조 결과: `AZURE_SPEECH_REGION=koreacentral`, `AZURE_SPEECH_KEY` 미설정. 그러므로 현재 키가 PSA 키와 일치하는지의 결과는 “불일치”가 아니라 **키가 없어서 대조 불가이며, 요청 시 누락 오류가 발생**이다.

## 2026-09-16 설정 재검증

서버 `.env`의 설정을 비밀값 노출 없이 재검증했다.

- `AZURE_SPEECH_KEY`는 올바른 형식으로 설정돼 있다.
- `AZURE_SPEECH_REGION=koreacentral`, `AZURE_STT_MODE=continuous`, `EVC_STT_PROVIDER=azure`, `EVC_STT_TIMEOUT_S=120` 및 기존 `OPENAI_API_KEY`가 모두 설정돼 있다.
- 파일 권한은 0600이다.
- Azure 제공자 구성 검증과 관련 회귀 테스트 13개가 통과했다.
- 실제 Azure TTS 요청으로 190,244바이트 WAV를 생성하고 WAV 형식을 검증했다. 따라서 설정된 키는 `koreacentral` Azure Speech 리소스에서 유효하며, 질문 TTS에 사용할 수 있다.

하지만 실행 중 Uvicorn 백엔드는 `.env`가 수정된 2026-09-16 16:15:50 KST보다 앞선 10:55:34 KST에 시작됐다. `main.py`는 시작 때만 `.env`를 읽으므로 공개 API에 새 키를 적용하려면 백엔드 재시작이 필요하다. EVC 세션은 메모리에 있으므로 재시작은 진행 중 세션을 지운다.

## 아직 완료되지 않은 작업

1. 현재 EVC 세션에 영향이 없는 시점에 백엔드를 재시작해 새 환경을 적용.
2. 공개 질문 음성 API와 APK의 손들기·질문 재생 단계 검증.
3. 실제 답변 STT, 다음 질문 갱신, 최종 리포트의 문답 기록을 검증.

운영 EVC 세션은 메모리에 있으므로 재시작하면 진행 중 세션이 소실된다. 키 확보 후 재시작 전 현재 사용 상태를 확인해야 한다. 현재 상태를 해결 완료로 간주하지 않는다.
