# 배포 담당자 전달사항: 청중 수 및 GPT/Jev 선택

## 배포 대상
- 저장소: https://github.com/4githu/sushisite.git
- 브랜치: fix/pin-audience-jev-validation
- sushi-app(웹)과 sushi-fast(서버)를 함께 반영한다. 이 문서는 배포 완료를 뜻하지 않는다.
- 일반·체험 모두 웹 설정으로 실제 PIN을 생성한다. 기존 가짜 PIN 1234/고정 체험 시나리오 대신 실제 발표 자료와 PIN을 사용한다.

## 서버 설정
기존 sushi-fast/.env에 아래 항목을 추가/수정한다. 기존 DB/Firebase/음성인식 등 설정은 유지한다. 실제 키는 저장소나 전달 문서에 기록하지 않는다.

### GPT 모드 (기본)
```dotenv
EVC_EVALUATION_PROVIDER=gpt
OPENAI_EVC_MODEL=gpt-4.1-mini
OPENAI_API_KEY=<기존 OpenAI 키 유지>
```

### Jev 모드
```dotenv
EVC_EVALUATION_PROVIDER=jev
TYPESAFE_API_KEY=<발급받은 TypeSafe 키>
TYPESAFE_JEV_MODEL=jev-latest
OPENAI_EVC_MODEL=gpt-4.1-mini
OPENAI_API_KEY=<결과지 작성을 위해 유지>
```

- 선택값이 없으면 GPT. openai도 GPT의 호환 별칭이다.
- 기본 모델은 gpt-4.1-mini. 기존 .env의 gpt-4.1-nano 값이 남아 있으면 명시적으로 변경한다.
- 발표 중 평가는 선택 모델, 발표 후 결과지 생성은 항상 OpenAI이다.
- Jev 실패 시 GPT로 자동 우회하지 않는다.
- 설정 변경 후 모든 서버 worker/process를 재시작한다. GPT 복귀는 선택값을 gpt로 변경 후 재시작한다.
- main.py가 sushi-fast/.env를 로드한다. Docker/서비스 관리자/셸에서 이미 주입한 동일 환경변수가 있으면 그 값이 .env보다 우선하므로 함께 확인한다.
- .env.evc.example은 참고 파일이며 자동으로 읽히지 않는다. 실제 .env에 필요한 값만 반영한다.

## 배포 후 확인
1. 일반 및 체험에서 각각 청중 수 1~10명으로 실제 PIN을 생성한다.
2. Firebase presentation_data/{pin}/page_3/audience_scale과 PIN template_snapshot.audience.audience_count가 선택값과 같은지 확인한다.
3. Unity가 같은 PIN을 smart-start의 pre_session_pin으로 전달하는지 확인한다.
4. 서버 청중별 판단 배열과 Unity 캐릭터 수가 선택 인원과 같은지 확인한다. commands 수는 청중 수와 다를 수 있다.
5. GPT/Jev 각 모드에서 음성 업데이트가 성공하고, 종료 후 GPT 결과지 작성이 되는지 확인한다.

## 검증 근거와 남은 확인
- 로컬 서버 자동 테스트 314개, 웹 전달 테스트 22개 통과.
- 180초 동일 녹음 1회/6구간 실측: 로컬 명령 응답 평균 GPT 4.379초, Jev 2.818초. 전사문 모두 일치.
- GPT는 요약/이유도 생성하므로 순수 동일 작업량 비교는 아니다.
- Unity 실제 인원 생성과 백채널 재생 지연은 미검증. 실측에 ACT 백채널이 없어 동일 행동의 재생 속도 비교는 아직 완료되지 않았다.
