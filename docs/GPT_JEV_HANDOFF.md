# 청중 수 및 GPT/Jev 작업 정리

## 작업 브랜치
- 원격: https://github.com/4githu/sushisite.git
- 브랜치: fix/pin-audience-jev-validation
- 웹과 서버 변경을 함께 배포한다. 배포 절차는 DEPLOY_GPT_JEV.md 참고.

## 평가 모델 선택
서버 프로세스를 시작하는 터미널에서 설정한다. 웹 UI의 사용자 선택 기능은 아니다.

```sh
export EVC_EVALUATION_PROVIDER=gpt
export OPENAI_EVC_MODEL=gpt-4.1-mini
```

Jev를 사용하려면 다음을 설정하고 서버를 재시작한다.

```sh
export EVC_EVALUATION_PROVIDER=jev
```

미설정 기본값은 GPT이며 openai도 호환 별칭으로 허용한다. 잘못된 값이나 Jev 실패를 GPT 성공으로 숨기지 않는다. GPT에는 OPENAI_API_KEY, Jev에는 TYPESAFE_API_KEY가 필요하다. 음성인식 키는 별도로 필요하다. 키는 저장소에 넣지 않는다. sushi-fast/.env.evc.example은 참고용이며 자동 로드하지 않는다.

발표 중에는 선택한 모델로 평가하고 기존 청중 상태/애니메이션 선택 로직을 실행한다. 발표 후 결과지 작성은 선택값과 관계없이 OpenAI를 사용하므로 Jev 실행에도 결과지용 OPENAI_API_KEY가 필요하다.

## 요구사항별 상태
| 요구사항 | 상태 및 근거 |
|---|---|
| PIN의 청중 수를 서버에서 읽기 | 기존 서버 기능 확인. 웹 체험 경로의 고정 시나리오/가짜 PIN 우회를 제거하고 실제 PIN 생성과 Firebase 전달로 연결 |
| 선택 인원과 판단 결과 수 일치 | 1~10명 PIN 저장 및 서버 시작/조회/업데이트 계약 테스트 통과 |
| 일반/체험 모두 웹 설정 전달 | 각 1~10명 웹 테스트 통과. 실제 선택한 템플릿으로 세션 생성 및 Firebase audience_scale 기록 검증 |
| GPT/Jev 선택, 기본 GPT | 환경변수 선택 및 기본값/호환 별칭/잘못된 값 테스트 통과 |
| 실시간 판단과 사후 결과지 분리 | 실시간 선택자와 OpenAI 결과지 경로 분리 확인 |
| 동일 음원 실제 API 비교 | 180초 음원, 30초 6구간, 1회 완료. 전사문 6/6 동일. GPT 평균4.379초, Jev2.818초 |
| 같은 발화의 백채널 지연 비교 | 부분 완료. 로컬 명령 응답까지 측정. ACT 백채널 행동 미관찰, 동일 동작 지연 비교 및 실제 재생 미검증 |
| 실제 Unity 인원수 반영 | 미검증. Unity 담당자가 실제 PIN/동적 청중 생성 확인 필요 |

## 검증
2026-11-19 최종 수정 후:
- 서버: odi/EVC/tests + odi/db/tests/test_template_lifecycle.py — 314 passed.
- 웹: session.handoff.test.ts — 22 passed. 외부 Firebase/API는 모의 처리, 세션/Firebase 전달 코드는 실제 실행.
- 실측 API 비교는 위 자동 테스트와 별도이며 1회 측정이다. GPT는 요약/이유도 생성하므로 작업량이 동일하지 않다.
- commands 개수는 청중 수가 아니다. 실측 양쪽 판단 배열은 6명, 명령 수는 GPT8/Jev6이다.

## 디렉토리 정리 원칙
- 사용하지 않는 고정 데모 템플릿의 불필요한 수정은 원복했다.
- 테스트용 node_modules 연결 및 임시 .svelte-kit 설정은 제거했다.
- 구현/테스트/운영 도구는 작업 저장소에 유지했다.
- 원본 음원 및 실측 JSON 로그는 outputs에 보존했다. 실패 실험 로그도 진단 근거로 보존한다.
- 검색 목록, 테스트 의존성, 보고서 생성 스크립트 등은 work에 두고 배포 코드와 구분한다.

## Unity 담당자 확인
1. 웹에서 받은 실제 PIN을 smart-start의 pre_session_pin으로 전달하는지 확인.
2. Firebase presentation_data/{pin}/page_3/audience_scale과 PIN의 audience_count가 같은지 확인.
3. 고정6명 배열/프리팹 생성/표시 로직 대신 서버 청중 registry/ID를 반영하는지 확인.
4. 일반·체험 각각 1~10명에서 생성된 캐릭터 수와 판단 배열 수를 확인. commands 수를 청중 수로 사용하지 말 것.
5. 실제 백채널 비교에는 같은 발화의 끝 시각, 명령 수신 시각, 동일 행동 재생 시작 시각을 기록할 것.
