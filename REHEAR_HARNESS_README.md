# sushisite 수정용 Codex 하네스

이 묶음은 **Codex의 작업 지침·검증 경계·이어하기 기록·실행 도구**다. 완성된 백엔드 패치나 Qwen 모델이 아니다. 압축을 풀어도 서비스 코드는 바뀌지 않는다.

기준: 2026-10-15의 [노션 분석 문서](https://app.notion.com/p/AI-3fadfd91e6c681a2a8d4c1fe9da8b3c9)와 첨부 `sushisite(2).zip`. 문서 스냅샷을 포함해 Codex의 Notion 연결 없이도 사용할 수 있다.

## 1. 어디에 넣나?

`sushi-fast/`와 `sushi-app/`가 함께 보이는 **sushisite 루트**에 ZIP 안의 파일/폴더를 합쳐 넣는다. 기존 파일을 덮어쓰지 않는다.

```bash
cd /실제/경로/sushisite
unzip -n ~/Downloads/rehear_ai_harness.zip -d .
```

macOS Finder로 푼 경우 생성된 폴더의 **내용물**을 루트에 옮긴다. 결과적으로 루트에서 `REHEAR_AI_TASK.md`와 `tools/rehear_harness.py`가 보여야 한다. 문서의 `/실제/경로/`는 자신의 경로로 바꾼다.

기존 `AGENTS.md`는 대체하지 않는다. `REHEAR_AI_TASK.md`를 매 요청에서 읽게 하면 바로 사용할 수 있다. 자동 진입 규칙도 원하면 Codex에 `docs/rehear-ai/AGENTS.rehear-ai.fragment.md`의 연결 문구를 루트 AGENTS.md에 **중복 없이 추가**하도록 지시한다. 하위 `sushi-app/AGENTS.md`는 그대로 둔다.

## 2. Codex에 무엇을 입력하나?

Codex에서 sushisite 폴더를 연 후 아래를 붙여 넣는다. 명령의 실행 위치는 모두 sushisite 루트다.

```text
REHEAR_AI_TASK.md와 docs/rehear-ai/AGENT_RULES.md를 읽어.
이번에는 01-audience-count 단계만 구현해.
먼저 현재 HEAD/변경 파일/기존 AGENTS를 확인하고, 수정 전 baseline을 capture해.
기존 사용자 변경은 보존하고 Unity·sushi-app은 수정하지 마.
고정된 6명을 기존 template_snapshot의 audience_count=a로 연결해.
실패 재현 → 최소 구현 → 회귀 검증 순으로 진행하고,
docs/rehear-ai/PROGRESS.md에 실제 명령·결과·미검증 범위를 남겨.
하네스 guard와 이 단계 테스트를 실행한 뒤 결과를 알려줘.
```

1단계 결과를 확인한 후 다음 요청을 사용한다.

```text
REHEAR_AI_TASK.md와 docs/rehear-ai/PROGRESS.md를 다시 읽고 02-playback-clock 단계만 진행해.
Unity 소비자와 재생 시계를 알 수 없는 부분은 추측으로 해결했다고 하지 마.
기존 opt-in 및 request_id 재시도 계약을 유지하고 검증 결과를 기록해.
```

```text
REHEAR_AI_TASK.md와 docs/rehear-ai/PROGRESS.md를 다시 읽고 03-research-assessment 단계만 진행해.
Qwen은 16개 연구 Rubric용이며 기존 OpenAI 10개 설명을 구현할 필요는 없어.
공식 Rubric/Policy가 없으면 내용을 만들지 말고 필요한 자료를 정확히 알려줘.
독립 모듈·fake 검증·CLI는 진행하고, 실제 모델 실행 여부는 분리해서 기록해.
```

```text
REHEAR_AI_TASK.md와 docs/rehear-ai/PROGRESS.md를 다시 읽고 04-integrity-cleanup 단계만 진행해.
기존 case·과거 결과·측정 정의를 이전하고 검증한 뒤에만
두 임시 benchmark 폴더를 정리해. 마지막에 전체 회귀와 guard를 실행해.
```

한 번에 전체 구현을 원하면 단계 이름 대신 `01부터 04까지 순서대로 진행하고, 단계별 검증을 마친 뒤 다음 단계로 넘어가`라고 지시한다. 실제 모델·GPU·Unity가 없어 검증하지 못한 부분은 계속 미검증으로 남긴다.

## 3. 터미널에서 쓰는 명령

이미 백엔드 의존성을 설치한 가상환경의 Python을 사용한다. 아래는 하네스에 **지금 포함된 명령**이다.

```bash
python3 tools/rehear_harness.py doctor
python3 tools/rehear_harness.py capture
python3 tools/rehear_harness.py guard
python3 tools/rehear_harness.py test --suite original
python3 tools/rehear_harness.py test --suite audience
python3 tools/rehear_harness.py test --suite timing
python3 tools/rehear_harness.py test --suite assessment
python3 tools/rehear_harness.py test --suite integrity
python3 tools/rehear_harness.py test --suite all
```

| 명령 | 하는 일 |
|---|---|
| `doctor` | 폴더 구조와 pytest/FastAPI/httpx/Pydantic/numpy 준비 상태 확인. 준비 부족이면 종료 코드 2 |
| `capture` | 수정 **전** 프론트·Unity 파일·clip catalog·E/V/C 핵심 식·route의 기준값 저장. 기존 baseline 덮어쓰기 거부 |
| `guard` | 기준과 비교해 변경·삭제·추가를 탐지. 운영 코드가 tools를 import하는지도 검사 |
| `test --suite original` | 기존 EVC pytest 실행. 네트워크 연결을 차단한 별도 프로세스 사용 |
| 단계별 `test` | Codex가 추가해야 할 해당 단계 테스트 실행. 아직 없으면 종료 코드 2 |
| `test --suite all` | 기존 suite와 새 4개 테스트 파일을 모두 요구하고 실행 |

테스트가 빠졌거나 skip되면 완료로 표시하지 않는다. 종료 코드 **0=해당 검사 성공, 1=검사/테스트 실패, 2=준비 부족·미구현·불완전**이다. 결과 JSON은 `artifacts/rehear-harness/`에 쌓인다. 이 폴더는 로컬 실행 기록이며 필요하면 기존 `.gitignore`에 추가한다.

`guard`는 보호된 파일/코드가 바뀌었는지 확인하는 도구다. HTTP의 모든 의미·모델 품질·실제 Unity 렌더링을 증명하지는 않는다. 제품 회귀 테스트를 함께 실행해야 한다. baseline을 새로 만들어 실패를 숨기지 않는다.

GPU/모델 다운로드/실제 API 호출은 이 하네스의 오프라인 테스트가 수행하지 않는다. 연구용 `make ai-eval` 등의 명령은 **03/04 단계에서 구현할 대상**이며 아직 이 묶음에 있는 명령이 아니다.

## 4. 파일을 읽는 순서

사용자는 이 README와 `PROGRESS.md`만 읽어도 된다. Codex는 `REHEAR_AI_TASK.md`에서 상세 문서로 이동한다.

| 파일 | 역할 |
|---|---|
| `REHEAR_AI_TASK.md` | 매 작업의 진입점 |
| `docs/rehear-ai/AGENT_RULES.md` | 지켜야 할 범위·검증·작업 재개 규칙 |
| `docs/rehear-ai/SPEC.md` | 구현 목표·모듈 경계·결정된 값 |
| `docs/rehear-ai/CONTRACTS.md` | 유지할 계약과 청중 수 예외 |
| `docs/rehear-ai/plans/01…04-*.md` | 단계별 파일·인터페이스·검사·완료 조건 |
| `docs/rehear-ai/ACCEPTANCE.md` | 완료 증거 체크리스트 |
| `docs/rehear-ai/PROGRESS.md` | 실제 진행 결과·중단 지점, 초기에는 미실행 |
| `docs/rehear-ai/sources/` | 원본 Notion 스냅샷·출처 |
| `tools/rehear_harness.py` | 실행 가능한 준비/보호/테스트 도구 |
| `tools/tests/test_rehear_harness.py` | 하네스 자체의 표준 라이브러리 검사 |

제품 코드가 이 tools 폴더를 import하지 않게 검증하므로, 작업 도구를 삭제해도 운영 모듈이 영향을 받지 않도록 설계했다. 제품 테스트는 `sushi-fast/odi/EVC/tests/`에 남긴다.
