# 진행 기록

## 현재 상태

**01·02 backend/headless와 03 독립 core/fake/CLI 구현·오프라인 검증 완료.** 03의 공식 Rubric/Policy·실제 Qwen 검증은 자료/환경 미확보로 남아 있으며 04는 미실행이다. 실제 Unity·웹 실행 및 실서비스 DB·외부 STT/LLM/TTS 검증은 수행하지 않았다. 실제 Unity 시계/actor 동기화와 legacy 지연 보정은 해결됐다고 주장하지 않는다.

| 단계 | 구현 | 검증 | 남은 것 |
|---|---|---|---|
| 01-audience-count | 완료 | 단계 50 passed / 기존 129 passed / guard 성공 | 실제 Unity actor 매핑·운영 DB 확인 |
| 02-playback-clock | backend/headless 완료 | timing 27 passed / 기존 129 passed / audience 50 passed / guard 성공 | 실제 Unity 시계·actor·pause·부하 및 legacy 동기화 미검증 |
| 03-research-assessment | 독립 core/fake/CLI 및 local loader 경계 구현 | assessment 29 passed / 현재 EVC 통합 235 passed / guard 성공 | 공식 16개 Rubric·Policy, 가중치·검증된 ML 환경·실제 모델/품질 |
| 04-integrity-cleanup | 미실행 | 미실행 | report/QA/DB·측정이전·삭제 |
| 실제 Unity 검증 | 미실행 | 미실행 | C#·실행 환경·시계/actor 관측 |

## 작업 회차마다 덧붙일 내용

```markdown
### 회차 날짜 · 단계
- 시작 HEAD/branch 또는 Git없음:
- 시작할 때 이미 있던 사용자 변경:
- 변경 파일과 이유:
- 실행 명령 / exit code / passed·failed·skipped:
- guard 결과:
- 데이터·Rubric·모델·adapter·prompt 버전:
- 코드로 확인 / fake 실행 / 실제 모델 / 실제 Unity 중 수행 범위:
- 남은 실패·자료 부족·한계:
- 다음 시작 위치:
```

baseline을 재생성해 실패를 덮지 않는다. 환경 미설치/skip/자료 미확보는 완료로 체크하지 않는다. 신뢰할 수 없는 clocks나 미측정 지표에 합성 값으로 실성능을 주장하지 않는다.

### 2026-10-15 (Asia/Seoul) · 01-audience-count

시작 상태와 보존:

- HEAD: `9eb86b09ea7e1ff1f4be5fc3508bbff60e8ff125`, branch: `feature/ai-pipeline`.
- 시작 시 tracked 사용자 변경: `sushi-fast/odi/EVC/question_generation.py`, `sushi-fast/odi/EVC/tests/test_question_generation.py`. 두 파일은 이번 작업에서 수정하지 않았고, 종료 시 시작 SHA-256과 일치했다.
- 시작 시 untracked: `.DS_Store`, `docs/` (기존 `EVC_API_SPEC.md`), `rehear_ai_harness/`, `sushi-fast/.DS_Store`, `sushi-fast/latency_benchmark_with_outputs/`, `sushi-fast/live_latency_benchmark/`. 기존 파일/폴더는 삭제하거나 덮어쓰지 않았다.
- 해당 경로와 상위에서 적용할 기존 `AGENTS.md`는 발견되지 않았다. `sushi-app/AGENTS.md`와 클라이언트 파일은 수정하지 않았다.
- 하네스가 루트가 아닌 `rehear_ai_harness/`에 있어 README의 배치 지침대로 없는 파일만 루트에 복사했다. 원래 묶음은 그대로 보존하고 이후 작업/기록은 루트 `docs/rehear-ai/`와 `tools/`를 기준으로 한다.
- 제품 수정 전 capture: `artifacts/rehear-harness/baseline.json` (보호 파일 1,136개, E/V/C 핵심 함수 AST 5개, route 집합). baseline 재생성 없음.
- 사용자 변경 원본/해시/patch/status: `artifacts/rehear-harness/user-changes/`, `starting-user-hashes.json`, `starting.diff`, `starting-status.txt`. 보존 확인 결과는 `user-changes-preserved.json`.

변경 파일과 동작:

- `sushi-fast/odi/EVC/audience_config.py` 신규: snapshot resolver, strict int 1–50 검증, logical layout, 세션용 ACT08 catalog 사본의 gate 구성.
- `router.py`: count는 PIN-bound `template_snapshot.audience.audience_count`에서만 읽는다. snapshot/count 누락과 pinless는 6; 명시 null/bool/float/string/범위 밖 및 잘못된 audience 구조는 기존 `validation_error` 422로 변환하고 PIN claim 전에 거부한다. 기존 title/자료/관심/전문성의 최신 template fallback은 유지하지만 count에는 사용하지 않는다. 외부 form 필드 추가 없음.
- `schema.py`: 내부 `SmartStartOptions.audience_count=6`, element ID 01–50, 응답 1–50명 및 순서대로 연속된 고유 registry 검증, update 명령의 registry 소속 검증.
- `session_store.py`: count 저장 및 동일 count의 audience/RNG registry 생성.
- `state_engine.py`: optional count의 기본값 6 유지. 순수 layout은 0-based index `i`의 row를 `floor(3*i/a)`로 front/middle/rear에 배정하고 각 row 안에서 left/right 교대. 중복 row/seat 분류는 실제 Unity 좌표가 아니다. 6명은 기존 01/02 front, 03/04 middle, 05/06 rear 그대로다.
- 특성은 기존 세 개 offset 구간을 순환하는 대칭쌍과 홀수의 중앙값으로 평균을 보존한다. 기존 per-agent seed 파생과 6명 RNG 소비 순서는 유지했다. 6명의 노트북은 기존 front/middle 1명+rear 1명 선택을 보존하고, 나머지는 `floor(a/3)`명을 seed RNG로 중복 없이 선택한다. 1명은 노트북 없음.
- `pipeline.py`, `reaction_scheduler.py`: 원본/캐시 catalog는 바꾸지 않고 a≠6인 세션의 사본에서 ACT08 gate를 실제 짝이 있는 rear ID로 연결한다. scheduler는 rear ID 정렬 후 인접쌍 (0,1), (2,3), …을 정하고 홀수 마지막은 짝 없음. 상대의 상태/scene/cooldown gate와 동일 sync_group을 유지한다. 6명의 기존 pairing과 명령 의미/시간/재시도는 보존한다. 02의 freshness/clock/throughput 변경은 하지 않았다.
- `answer_service.py`: 마지막 답변에서도 잘못된 nonempty next audience ID를 거부한다. 기존 speech와 중간 answer의 registry 검증은 유지한다.
- 신규 `tests/test_audience_count_contract.py`, `tests/fixtures/audience_six_golden.json`: 합성 입력만 사용. 테스트 fixture의 ASGI EVC 라우터는 실제 시작/조회/update/reactions/speech/answer를 실행하고 DB·STT·평가·질문·TTS는 fake를 주입한다.

수정 전 golden:

- 제품 수정 전에 seeds 0/1/2026의 6명 초기 profile/state 전체와 초기화 후 RNG 4회 출력, 합성 4구간 update의 행동/명령 및 최종 runtime state hash·RNG 4회 출력, scheduler 50 tick의 반응 hash를 확보했다.
- fixture 생성은 당시의 `six_golden(seed)`를 `PYTHONPATH=sushi-fast sushi-fast/.venv/bin/python`에서 실행해 JSON으로 저장했다 (exit 0). 이후 재생성하지 않았다.
- 랜덤 session/request/sync UUID와 created/updated 시각, optional diagnostics는 비교에서 제외한다. UUID 값 자체는 비결정적이며 그룹/타이밍/명령 계약은 별도 기존 검사와 rear-pair 테스트로 확인한다. 특성·E/V/C·behavior/variation·명령 시간/필드·RNG 출력은 비교에 남긴다.

실제 실행과 결과 (명령은 레포 루트 기준):

| 명령/순서 | exit | 실제 결과 |
|---|---:|---|
| `git status --short`, `git rev-parse HEAD`, `git branch --show-current` | 0 | 시작 변경/HEAD/branch 확인. macOS xcrun cache 쓰기 경고가 있었지만 Git 조회 성공 |
| `python3 tools/rehear_harness.py doctor` | 2 | 기본 Python 3.13.15에 pytest/FastAPI/httpx/Pydantic 없음 |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py doctor` (최초) | 2 | 기존 가상환경에는 pytest만 없음 |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py capture` | 0 | 제품 수정 전 baseline 저장 |
| `sushi-fast/.venv/bin/python -m pip install pytest==8.4.2` (sandbox) | 1 | DNS 제한으로 다운로드 실패, 테스트 성공으로 처리하지 않음 |
| 같은 pip 명령 (승인된 sandbox 외 실행) | 0 | 기존 `requirements-evc-dev.txt`의 pytest 8.4.2 설치; requirements 파일 변경 없음 |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py doctor` (설치 후) | 0 | READY; pytest 8.4.2/FastAPI 0.141.1/httpx 0.28.1/Pydantic 2.13.4/numpy 2.4.3 |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite original` (수정 전) | 0 | 129 passed, 0 failed/skip/error (`original-before.log`) |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite audience` (구현 전) | 1 | 41 collected: 38 failed, 3 passed, 0 skip/error (`audience-before.log`). resolver 미존재 1건 외에도 실제 ASGI count12→6, invalid count의 HTTP 200(기대 422), count 옵션 부재 등을 재현 |
| 같은 audience 명령 (첫 구현 후) | 1 | 39 passed, 2 failed. Q&A fixture의 전사 근거 누락으로 fake provider 검증 실패 (`audience-after-first.log`); 합성 transcript 추가 후 41 passed (`audience-after.log`) |
| 같은 audience 명령 (질문 총수/응답 경계 추가) | 0 | 48 passed, 0 skip/error |
| 같은 audience 명령 (자체 검토 후 홀수 rear 사례 추가) | 1 | 48 passed, 2 failed (`audience-unpaired-before.log`). 일반 후보 gate가 3/15명에서 짝 없는 rear를 허용함을 재현 |
| 같은 audience 명령 (최종) | 0 | **50 passed**, 0 failed/skipped/error/xfail/xpass (`audience-final.log`) |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite original` (최종) | 0 | **129 passed**, 0 failed/skipped/error/xfail/xpass (`original-final.log`). schema/session/state/behavior/reactions/questions/answer 및 기존 headless Unity 검사 포함 |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py guard` (최종) | 0 | PASS_PROTECTED_BOUNDARIES_ONLY, violations=[] |
| `sushi-fast/.venv/bin/python -m unittest discover -s tools/tests -v` | 0 | 하네스 자체 검사 12개 성공 |
| 시작 SHA-256과 두 사용자 파일 비교 | 0 | 두 파일 모두 동일 (`user-changes-preserved.json`) |
| `git diff --check` | 0 | whitespace 오류 없음 |

하네스의 각 실행 JSON은 `artifacts/rehear-harness/*-{doctor,capture,test,guard}.json`에 남아 있다. suite 실행은 socket network를 차단한다. 기존 129개와 단계 50개는 각각 실행했으며 선택 검사 합계는 179개다. `--suite all`은 02–04 테스트 파일도 요구하므로 이번 01 단독 작업에서는 실행하지 않았다.

검증 범위와 한계:

- 코드 확인 + 자체 diff 검토 + fake provider/저장소를 쓰는 오프라인 ASGI/headless 검증이다. 독립 검토는 수행하지 않았다.
- 1/3/6/12/50 초기화, 범위/평균/결정성/노트북, 1/6/12/50 양 모드의 시작·조회·update 및 reaction registry, count12 vs 최신 template50, 누락 default6, invalid422, 질문 audience_02(1명 세션) 거부/audience_12(12명 세션) 허용, 청중 수와 독립적인 질문 총수 1/3/5, 홀수 rear/실제 짝의 동일 sync_group을 확인했다.
- 실제 DB/PIN 발급·claim·템플릿 수정 트랜잭션, 전체 backend 서버 기동, 실 STT/LLM/TTS API, 실제 웹/XR 실행은 미검증이다. PIN-bound 입력 선택은 fake DB 조회를 통한 EVC 라우터에서 확인했다.
- Unity·sushi-app·원본 clip catalog hash, E/V/C 핵심 AST, route 집합 무변경을 guard로 확인했다. guard는 동적 의미 전체를 보증하지 않는다. Unity actor 01–50 생성/매핑·물리 좌석·수신/재생 시계는 관측하지 않았다.
- 50명 polling은 registry와 존재하는 ID만 확인하며 실성능/공정성/budget 완료 증거가 아니다. 02의 clock/freshness/부하 보완은 미실행이다.
- 데이터는 합성 fixture와 기존 테스트만 사용했다. Rubric/모델/adapter/prompt 버전 변경 없음; Qwen/연구16/보고서 수정과 benchmark 이전·삭제는 하지 않았다.
- 다음 시작 위치: 사용자 승인 범위가 확장되면 `02-playback-clock.md`와 이 기록을 읽고 실제 diff 및 기존 baseline에 대한 guard부터 확인한다. 01 baseline은 재생성하지 않는다.

### 2026-10-15 (Asia/Seoul) · 02-playback-clock

시작 상태와 보존:

- HEAD/branch는 01과 동일: `9eb86b09ea7e1ff1f4be5fc3508bbff60e8ff125` / `feature/ai-pipeline`. 이전 사용자 변경과 01 구현이 미커밋 상태로 존재했다. 기존 untracked 하네스/문서/benchmark 폴더도 유지했다.
- 시작에 루트 진입점·규칙·SPEC·CONTRACTS·PROGRESS·02 계획 및 실제 diff를 다시 확인했다. 적용할 별도 상위/수정 경로 `AGENTS.md`는 발견되지 않았다.
- 기존 `artifacts/rehear-harness/baseline.json`에 대한 guard 성공 후 작업했다. baseline을 재생성하지 않았다. 02 시작 EVC 소스/문서/fixture의 사본·해시와 Git status/diff는 `artifacts/rehear-harness/stage02-start/`에 보관했다.
- 기존 사용자 `question_generation.py`와 `tests/test_question_generation.py`는 시작 SHA-256과 동일하다. 기존 테스트/01 golden은 전혀 수정하지 않았다. Unity·sushi-app·clip catalog 및 E/V/C 핵심 식은 무변경이다.

구현과 정책:

- 신규 `sushi-fast/odi/EVC/playback_policy.py`: 주입 가능한 `PlaybackPolicy`, `TimingTrace`, `PlaybackClockError`. source client time과 서버 monotonic·poll time을 별개로 다룬다. 정책 기본값과 근거는 `sushi-fast/odi/EVC/AUDIENCE_REACTIONS.md`에 문서화했다.
- `pipeline.py` / `session_store.py` / `observability.py`: pipeline 진입·lock 획득·STT 종료·평가 종료·commit 종료·response-ready를 관측하고 lock 대기/STT/평가/총 시간을 기록한다. 마지막 성공 요청 32개 trace를 내부에 유지하고 텍스트 없는 로그에 포함한다. HTTP 업로드 이전·응답 wire send/Unity 수신 시각은 측정하지 않는다. 기존 근거 시각·전사/STT 시점·report context를 덮어쓰지 않는다.
- legacy의 실제 Unity 시계와 evidence age는 `None`/`unobserved`. 독립 모드의 마지막 poll 관측이 있으면 `client_poll_unverified`로 표시하고 선언된 client clock 도메인 안의 age만 기록한다. 이 경우에도 `unity_clock_s=None`이다. monotonic 경과를 발표 시계에 더하지 않는다.
- `reaction_scheduler.py`: 과거 context의 event age를 poll과 비교한다. 기본 TTL은 slide 6초, pause/boundary 각 2초, 기타 contextual signal 6초다. slide/기타 6초는 첨부 과거 CLI 처리 최대 약 5.53초에 여유를 둔 정책이며 Unity 허용치 측정이 아니다. pause/boundary 2초는 순간 이벤트를 과거 사건으로 보는 보수적 설계값이다. 테스트의 slide TTL 2초는 주입값으로 구분했다.
- 만료 context는 `during_speech`로 중립화하고 slide reference/event signals를 제거한다. 과거 metrics에서 action이 다시 생성되지 않도록 action 후보도 막는다. source timestamp가 poll보다 앞서면 age는 unknown이며 순간 문맥을 막되 현재 누적 상태에서 유도한 ACT03은 유지한다. 이로써 기존 6명 golden의 상태 기반 행동/RNG를 보존했다.
- 전체 playback age 한도는 15초다 (과거 처리 약 6초 + 합성 50명 배포 약 6초 + 여유). 넘으면 `stale_playback`으로 명령만 억제한다. unseen delta는 원래 순서대로 정확히 한 번 적용하고 보고서/질문 근거는 보존한다. source_step/event age/drop reason·청중별 wait·pending depth를 내부 관측과 reaction 로그에 남긴다. 이것은 실제 소비자 freshness 증명이 아니다.
- 같은 poll clock은 state/deadline/RNG를 전진시키지 않는다. 0.25초 이하 jitter 허용은 유지한다. 큰 역행 또는 이전 poll 대비 서버 elapsed+30초를 넘는 미래 점프는 HTTP 409 `playback_clock_discontinuity`이며 accepted clock·pending·sequence를 전진시키지 않는다. 이전 clock을 재개하거나 새 세션이 필요하며 서버가 새 epoch를 만들지 않는다. 첫 poll의 offset은 비교 관측이 없으므로 검증할 수 없다.
- 6명 이하는 기존 1명/요청·0.35초 간격을 보존한다. 7명 이상은 `min(4, ceil(a/6))`개 primary 결정, 전체 24개 command 예산, 오래된 deadline 우선이다. budget을 넘는 다음 선택은 partner/state/RNG/pending까지 되돌려 다음 poll로 미룬다. command layer를 잘라 보내지 않는다. batch 중 오류는 전체 tick을 rollback한다.
- 세션별 active+waiting update 상한 `EVC_MAX_PENDING_UPDATES=3`, listener당 미소비 Evidence 상한 64. backlog가 찼으면 STT 전 429로 새 분석 입장을 거부하며 이미 수락한 delta는 버리지 않는다. 소비 후 같은 step으로 재시도할 수 있다. 완료된 update 캐시는 포화된 대기열도 우회해 원래 응답을 돌려준다.
- 신규 `provider_execution.py`와 `config.py` / `speech2text.py` / `evaluation.py`: 기존 provider seam/모델은 유지하고 실제 STT·segment 평가 thread를 프로세스당 `EVC_PROVIDER_WORKERS=4`로 제한한다 (answer의 공통 STT도 같은 실행기). asyncio timeout/cancel 뒤에도 실제 thread 종료 전까지 슬롯을 점유한다. 신규 capacity 거부는 429이며, 이미 발생한 timeout/error 뒤 retry가 capacity에 막히면 원래 provider 오류/502 의미를 보존한다. 강제 thread 중단은 구현하지 않았다.
- `router.py`: 기존 opt-in=false 및 API/필드/명령의 시간 단위를 유지한다. reaction cache는 finish 이후 재시도에도 원래 UUID/time/sequence를 반환하고 신규 poll만 빈 명령을 반환한다. 시계 오류는 409, capacity는 429로 처리한다. request_id 재시도 명령을 retime하지 않는다.
- `AUDIENCE_REACTIONS.md`: 실제 `/update` route, 새 정책/제한/검증 한계를 반영했다. 기존 문서의 8초 예시와 Unity 시험 수치를 이번 작업의 실행 증거로 인용하지 않는다.
- 신규 `tests/test_playback_freshness.py`: fake clock/provider·실제 EVC ASGI 경로로 검증했다. 의존성 설치/모델·prompt·Rubric·adapter 변경은 없다. 독립 검토 없이 자체 diff 검토를 수행했다.

실패 재현과 실행 결과 (루트 기준, 로그는 `artifacts/rehear-harness/`):

| 명령/검사 | exit | 실제 결과 |
|---|---:|---|
| `sushi-fast/.venv/bin/python tools/rehear_harness.py doctor` 및 시작 `guard` | 0 | 기존 환경 READY, 기존 baseline 보호 경계 통과 |
| `git status --short`, `git rev-parse HEAD`, `git branch --show-current` / 시작 사본·해시 저장 | 0 | 기존 변경 보존; macOS xcrun cache 경고는 있었지만 Git 조회 성공 |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite original` (수정 전) | 0 | 129 passed, 0 failed/skipped/error (`stage02-original-before.log`) |
| 같은 하네스 `test --suite audience` (수정 전) | 0 | 50 passed, 0 failed/skipped/error (`stage02-audience-before.log`) |
| 같은 하네스 `test --suite timing` (구현 전) | 1 | 17 collected: 12 failed, 5 passed, 0 skip/error. 주입/관측 인터페이스 부재와 함께 실제 clock HTTP 200(기대409), 12/50명 대기 한도 초과를 재현 (`stage02-timing-before.log`) |
| 수정 전 all-due 250ms synthetic poll 스크립트 | 0 | 1/6/12/50명 first wait=0, last wait=0/2.5/5.5/24.5초. 청중별 wait 포함 `stage02-due-before.json` |
| 첫 구현 후 timing | 0 | 17 passed (`stage02-timing-first.log`) |
| 첫 구현 후 original / audience | 1 / 1 | 128 passed+1 failed / 48 passed+2 failed. stale 경로의 선택 오류 검사 생략, 앞선 timestamp에서 ACT03까지 억제해 golden 반응 hash 변경. 제품 코드를 수정했고 기존 assertion/golden은 보존 (`stage02-{original,audience}-first.log`) |
| 위 보완 후 original / audience / timing | 0 / 0 / 0 | 129 / 50 / 17 passed (`stage02-*-second.log`) |
| batch rollback/budget/관측/입장/seam 검사 확장 | 1 | 24개 중 23 passed, 1 failed. budget fixture에서 synchronization 제한이 먼저 선택을 바꿈. 해당 제한을 fixture에서 고정해 budget rollback만 분리 검증; assertion 유지 (`stage02-timing-expanded.log`) |
| HTTP admission/cache 검사 추가 후 timing | 0 | 25 passed |
| timeout 후 capacity retry의 오류 의미 검사 추가 | 1 | 27개 중 25 passed, 2 failed. 최초 timeout이 capacity 오류로 바뀌는 STT/평가 문제를 재현 (`stage02-timing-timeout-before.log`) |
| 최종 `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite timing` | 0 | **27 passed**, 0 failed/skipped/error/xfail/xpass (`stage02-timing-final.log`) |
| 최종 `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite original` | 0 | **129 passed**, 0 failed/skipped/error/xfail/xpass (`stage02-original-final.log`) |
| 최종 `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite audience` | 0 | **50 passed**, 0 failed/skipped/error/xfail/xpass. 6명 golden 그대로 (`stage02-audience-final.log`) |
| 현재 존재하는 전체 EVC tests를 단일 프로세스에서 socket 차단 plugin으로 실행 | 0 | **206 passed**, 0 failed/skipped/error/xfail/xpass (`stage02-combined-final.log/json`). 실행 명령은 아래 참조 |
| 최종 `sushi-fast/.venv/bin/python tools/rehear_harness.py guard` | 0 | PASS_PROTECTED_BOUNDARIES_ONLY, violations=[] |
| 사용자 SHA-256·02 시작 사본 비교 / `git diff --check` | 0 | 사용자 두 파일 및 모든 기존 tests/01 fixture 동일; whitespace 오류 없음 |

단일 프로세스 통합 검사는 하네스의 `OFFLINE_PLUGIN`을 임시 디렉터리에 쓰고 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, 임시 plugin+`sushi-fast`의 PYTHONPATH, 임시 `REHEAR_HARNESS_TEST_REPORT`를 설정해 `sushi-fast`에서 `.venv/bin/python -m pytest -p rehear_harness_offline_plugin -q --tb=short odi/EVC/tests`를 실행했다. provider 실행기가 여러 asyncio loop/테스트 사이에 공유되는 경우도 함께 검사하기 위해 수행했다. 하네스 `--suite all`은 아직 없는 03/04 단계 파일을 요구하므로 실행하지 않았으며, 이를 전체 01–04 완료로 표시하지 않는다.

지연·stale 동작은 보존한 02 시작 소스도 별도 import로 재실행해 확인했다 (`stage02-preserved-source-replay.json`, exit 0). 이는 **구현 후 저장 사본을 replay한 증거**다. 합성 처리 5초·원본 근거30초에서 기존 명령30.1초/가정 응답시계35초이면 4.9초 늦는다. 과거 pause30초→poll35초에서 기존 scheduler는 ACT08을 냈고 새 scheduler는 순간 action을 내지 않았다. 실 Unity 관측값이 아니다.

합성 부하 전후 (seed2026, 모든 actor deadline=10초, 하나의 evidence time=10초, 250ms poll):

| 청중 수 | 수정 전 first / last wait (초) | 수정 후 first / last wait (초) | 수정 후 poll당 최대 command 수 |
|---:|---:|---:|---:|
| 1 | 0 / 0 | 0 / 0 | 2 |
| 6 | 0 / 2.5 | 0 / 2.5 | 2 |
| 12 | 0 / 5.5 | 0 / 2.5 | 4 |
| 50 | 0 / 24.5 | 0 / 6.0 | 6 |

측정 정의는 첫 primary 결정까지의 `dispatch_time - due_time`이며 렌더링/수신 지연이 아니다. `stage02-due-after.json`에도 모든 청중별 wait를 저장했다. 강제 다중-layer 후보 검사에서는 별도의 9-command 예산으로 8개만 보내고 다음 actor의 delta/RNG를 보존함을 확인했다. 지속 evidence 입력에서도 50명 모두 dispatch되는 것을 확인했다. 이 측정은 실제 production throughput/자연스러움의 증명이 아니다.

미검증/남은 제한:

- legacy의 30.0→30.1 명령이 처리 후 과거가 되는 문제는 정확한 소비자 시계가 없어 남아 있다. 서버 elapsed만 더해 해결했다고 주장하지 않는다. 30초 수집 자체의 초기 발화 지연도 제거하지 않았다.
- Unity 시계/epoch/actor mapping, 실제 consumer opt-in 여부·pause·취소·네트워크 수신/재생 시각은 관측하지 않았다. 문서의 과거 Unity 시험 주장도 이번 실행 증거가 아니다. 실제 Unity·웹·전체 backend 서버 배포/실서비스 DB·외부 STT/LLM/TTS는 실행하지 않았다. ASGI EVC 라우터+fake provider/저장소 및 headless 검사 범위다.
- freshness는 evidence 끝 시각과 선언된 poll clock의 비교이며 실제 사건 발생 시점/수집 시작 시점은 모른다. 기본 TTL/slack/budget은 문서화한 backend 정책값이며 실제 소비자 관측에 따라 조정이 필요하다. 새 epoch/정확한 client clock을 합성하지 않는다.
- 관측 trace는 성공한 pipeline 요청의 내부 처리 시각이다. HTTP 업로드/응답 전송/Unity receive·render 시간이나 실패한 모든 provider 호출의 전체 타임라인을 수집한 것은 아니다.
- thread는 강제 종료하지 않는다. 영구 정지 worker는 슬롯을 소진할 수 있다. 정책 한도는 프로세스별이며 여러 서버의 전역 limit은 미구현이다. 모든 부하·시계·provider 시험은 합성/fake이며 실모델 실행이 아니다.
- 이미 알려진 DB 실패 시 메모리 commit 순서/보고서 recovery 등의 04 문제는 이번 단계에서 수정하지 않았다. benchmark 폴더/관측 코드/STT timestamp는 삭제하지 않았다.
- 03/04는 미실행이다. 다음 작업은 사용자 요청 시 `03-research-assessment.md`와 이 기록/실제 diff를 먼저 확인하고, 기존 baseline에 guard를 적용하는 지점부터 시작한다.

### 2026-10-15 (Asia/Seoul) · 03-research-assessment

범위와 시작 상태:

- 루트 진입점·PROGRESS·03 계획·SPEC·CONTRACTS·규칙 및 실제 파일을 다시 확인했다. HEAD/branch는 계속 `9eb86b09ea7e1ff1f4be5fc3508bbff60e8ff125` / `feature/ai-pipeline`이다. 사용자 변경·01·02 구현이 미커밋 상태로 존재했으며 별도 적용할 상위/수정 경로 AGENTS는 발견되지 않았다.
- 기존 baseline을 재생성하지 않고 시작 guard로 비교했다. 03 시작 EVC 75개 소스/문서/fixture 사본과 SHA-256, Git status/diff는 `artifacts/rehear-harness/stage03-start/`에 저장했다. 종료 시 **이 75개 기존 파일 모두 동일**했다. 사용자 질문 생성 변경·모든 기존 테스트/01 golden·01/02 구현을 보존했다. baseline 자체 해시도 02 종료 기록과 동일했다 (`stage03-preservation-final.json`).
- Unity·sushi-app·clip catalog·E/V/C 식·API route·기존 provider/모델 기본값·공개 10개 보고서는 변경하지 않았다. 04의 보고서 수정/DB 복구/benchmark 이전·삭제도 하지 않았다.

공식 자료와 환경 확인:

- `rg`로 관련 문서/경로와 Rubric/Anchor/Policy/Qwen 자료를 확인했다. 로컬 묶음의 `sources/README.md`도 공식 16개 원문·학습 데이터·가중치가 없다고 명시한다. `notion-ai-design.md`의 잠정 ID 범위는 공식 정의로 간주하지 않고 기준 ID를 하드코딩하지 않았다.
- 스냅샷이 연결한 [연구 원문](https://app.notion.com/p/Re-hear-Qwen-3f3dfd91e6c681db8d73c8056788577a)은 웹 도구에서 접근 불가였다. 공식 16개 기준/Anchor/Policy와 모델 위치·revision의 경로/문서 링크를 사용자에게 비동기로 요청했으나, 이 회차 종료까지 확정 자료를 받지 못했다. **이 자료/실제 품질 검증만 미확보이며 계약/fake/CLI 작업은 진행했다.**
- 실제 환경: Darwin arm64, Python 3.13.15, Pydantic 2.13.4, OpenAI SDK 2.54.0 설치. torch/transformers/peft/accelerate/safetensors 미설치. 새 의존성·가중치 다운로드/설치는 수행하지 않았다. core용 `rehear_ai/requirements.txt`는 확인된 Pydantic 2.13.4만 고정했다. 검증되지 않은 ML 버전 조합을 실제 lock이라고 만들지 않았다.

변경 파일과 동작:

- 신규 `sushi-fast/rehear_ai/{__init__,contracts,evidence,validation,config,factory}.py` 및 `engines/{__init__,base,fake,qwen_local}.py`. 독립 core는 stdlib/Pydantic만 사용하고 odi/FastAPI/DB/Unity/web/tools를 import하지 않는다. 로컬 ML 의존성은 실제 loader 호출 때만 import한다.
- 계약 버전: `evidence-pack.v1`, `rubric-bundle.v1`, `research-assessment.v1`; 패키지 `0.1.0`, 공통 prompt `research16-json-v1`. RubricBundle은 출처·Rubric/Policy 버전·purpose·정확히 16개 고유 ID와 각 1–5 Anchor를 받는다. Policy는 제공된 JSON을 보존하며 항목 정의·가중치·평균/0–100 변환을 발명하지 않는다. 모든 toy Rubric은 테스트 함수/임시 파일/`TEST_ONLY` demo artifact에만 존재한다.
- 결과는 같은 16개 ID, strict int 1–5/null, 이유, 존재하는 Evidence ID, abstention/null/사유의 일관성을 검사한다. schema/source/prompt/Rubric/Policy·base/tokenizer/adapter revision·runtime binding/버전·추론 설정·coverage/call count를 기록한다. canonical Evidence/Rubric/Policy digest로 같은 version 문자열의 내용 변경도 구분한다. 참조의 **존재**는 검증하지만 **의미적 지지/정답성**은 검증했다고 주장하지 않는다.
- `evidence.py`: 원전사 공백까지 보존하고, STT 상대 시간·명시된 관측 segment offset·client observation time을 분리한다. offset 없으면 절대 word time은 null/누락으로 남긴다. end time에서 duration을 빼 start를 추정하지 않는다. 슬라이드는 구간 관측 정밀도, 알려진 축약/미확인 완전성, QA 미확보/명시적 빈 이력, 누락 source와 coverage를 기록한다. F0·음량·시선 시계열·정확한 슬라이드 이력·외부 사실 자료는 생성하지 않는다. measurement allowlist로 기존 모델/보고서 점수를 raw metric처럼 넣는 경로를 거부한다.
- 신규 `odi/EVC/assessment_adapter.py`: 기존 `ReportSegmentRecord`와 전처리 결과를 neutral Evidence로 변환한다. report DTO에 STT words가 없으면 없다고 기록하고, 원래 `SpeechTextResult`가 있는 호출자만 step별 words/offset을 추가로 제공한다. 현재 계산된 음성 지표는 재사용하지만 기존 LLM 점수/설명·vocal delivery 점수·E/V/C·AI 반응·보고서 점수는 기본 연구 입력에서 제외한다. 별도 provenance의 `excluded_inputs`로 제외 사실을 기록한다.
- 내부 저장은 `store_internal_result(caller_owned_mapping, run_id=..., result=..., evidence=..., rubric=...)`의 명시적 opt-in 함수다. 검증한 16개 결과를 JSON 형태로 보관하고 충돌 run ID를 거부한다. 서비스 기본 hook/DB persistence/recovery/public projection에 자동 연결하지 않았다. Evidence와 Rubric 보관은 호출자 책임이다. 실제 DTO→Evidence→fake→내부 mapping→기존 세션 조회 경로를 fake pipeline으로 검사했다.
- fake는 점수를 만들지 않고 16개 모두 null+abstention으로 반환한다. `identity.provider=fake`, model `fake-abstain`, revision `builtin-v1`, binding `builtin_fake`로 명시한다. fake call count는 실제 LLM 추론 수가 아니라 fake 호출 수다.
- Qwen 경계는 loader 한 번 로드·연속 generate 두 번을 fake로 검사했다. model/tokenizer/LoRA identity를 따로 기록하며 주입 로더는 `injected_loader`, 기본 로더는 `transformers_local`로 구분한다. 실제 local loader는 명시된 로컬 디렉터리/revision·family(qwen2/qwen3)·정확한 설치 버전 lock을 요구하고, local-files-only/remote-code 금지로 tokenizer/base/LoRA를 연결한다. chat template, Qwen3 non-thinking, 새 토큰만 decode, input/token/time budget 전달은 fake ML 모듈로 확인했다. 이것은 실제 family/template 호환 검증이 아니다.
- 추론은 engine당 한 번만 실행하며 경쟁 호출은 입장 거부한다. 기본 cache off, temperature0, input 16384/new4096 tokens, timeout120초, retry0(설정 범위0–2). optional cache는 instance별 128개이며 provider/model/base/tokenizer/adapter/prompt/Rubric/Policy/추론 설정과 실제 payload 전체를 key에 넣는다. invalid/late 결과는 cache하지 않고 deadline 이후 retry를 시작하지 않는다. generation max_time은 cooperative이며 모델 로딩/진행 중 device 작업을 강제 종료하는 hard timeout이 아니다.
- 선택적 OpenAI 연구 비교 engine은 이번 요청에 필요하지 않아 구현하지 않았다. 기존 서비스의 OpenAI 10개 설명을 Qwen에 요구하거나 기본 provider를 교체하지 않았다.
- 신규 `sushi-fast/tools/{__init__,rehear_cli/__init__,rehear_cli/__main__}.py`, `sushi-fast/Makefile.ai`: `python -m tools.rehear_cli eval --input EvidencePack --rubric BUNDLE --engine fake|qwen_local --output RESULT`, config·repeat 지원. TEST_ONLY는 명시 flag가 필요하다. 기존 결과 파일은 덮어쓰지 않고 오류에 raw 입력/모델 출력을 노출하지 않는다. 개발 tools를 제거한 복사본에서 core/backend adapter/state 모듈 import도 확인했다.
- 신규 `rehear_ai/README.md`, `rehear_ai/requirements.txt`, 단계 테스트 `odi/EVC/tests/test_rehear_assessment_boundary.py`. 독립 검토는 없으며 자체 import/diff/contract 검토다.

실행한 검사와 결과 (루트 기준):

| 명령/검사 | exit | 실제 결과 |
|---|---:|---|
| 기존 가상환경 `python tools/rehear_harness.py doctor` / 시작 `guard` | 0 / 0 | READY, 기존 baseline 보호 경계 통과 |
| Git 상태/HEAD/branch 및 03 시작 사본·해시 저장 | 0 | 사용자/01/02 변경 보존. macOS xcrun cache 경고는 있었지만 조회 성공 |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite original` (수정 전) | 0 | 129 passed, 0 failed/skipped/error (`stage03-original-before.log`) |
| 같은 하네스 `test --suite assessment` (구현 전) | 1 | 17 collected, **17 failed**, 0 skip/error. 아직 없는 core/adapter/CLI 계약의 실패 (`stage03-assessment-before.log`) |
| `PYTHONPATH=sushi-fast sushi-fast/.venv/bin/python -m tools.rehear_cli --help` (구현 전) | 1 | CLI 모듈 부재 (`stage03-cli-before.log`) |
| 첫 구현 후 assessment | 1 | 16 passed, 1 failed. 새 테스트가 payload와 제외 목록의 `evc_state` 이름까지 구분 없이 검색해 false positive. 실제 payload 부재 및 exclusion provenance 존재를 각각 assertion하도록 수정 (`stage03-assessment-first.log`) |
| 보완 후 assessment / loader·출력·무결성 검사 확장 | 0 / 0 | 17 passed / 24 passed (`stage03-assessment-second.log`, `stage03-assessment-expanded.log`) |
| 실제 DTO 연결·CLI 반복/보존 검사 및 concurrency/retry/deadline 추가 | 0 | 25개 및 28개 검사 성공. 이후 deadline 이후 retry 사례 추가로 아래 실패를 재현 |
| deadline 경계 assessment | 1 | 29개 중 28 passed, 1 failed. 기한이 지난 뒤 retry=1이 generate를 한 번 더 호출함 (`stage03-assessment-deadline-before.log`). 제품 코드에 retry 전 deadline 확인 추가 |
| 최종 `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite assessment` | 0 | **29 passed**, 0 failed/skipped/error/xfail/xpass (`stage03-assessment-final.log`) |
| 최종 같은 하네스 `test --suite original` | 0 | **129 passed**, 0 failed/skipped/error (`stage03-original-final.log`) |
| 최종 같은 하네스 `test --suite audience` | 0 | **50 passed**, 0 failed/skipped/error (`stage03-audience-final.log`) |
| 최종 같은 하네스 `test --suite timing` | 0 | **27 passed**, 0 failed/skipped/error (`stage03-timing-final.log`) |
| 현재 존재하는 전체 EVC tests, 단일 프로세스/socket 차단 | 0 | **235 passed**, 0 failed/skipped/error/xfail/xpass (`stage03-combined-final.log/json`) |
| 최종 `sushi-fast/.venv/bin/python tools/rehear_harness.py guard` / `git diff --check` | 0 / 0 | PASS_PROTECTED_BOUNDARIES_ONLY, violations=[] / whitespace 오류 없음 |
| 03 시작 75개 파일 및 원 baseline SHA-256 비교 | 0 | 모두 동일. 사용자 변경/기존 테스트/01·02 소스 무변경 (`stage03-preservation-final.json`) |

단일 프로세스 통합 실행은 root 하네스 파일을 importlib로 로드해 `OFFLINE_PLUGIN`을 임시 파일로 쓰고, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, 임시 plugin+backend PYTHONPATH, 임시 `REHEAR_HARNESS_TEST_REPORT`를 설정해 `sushi-fast`에서 `.venv/bin/python -m pytest -p rehear_harness_offline_plugin -q --tb=short odi/EVC/tests`를 실행했다. `--suite all`은 아직 없는 04 테스트까지 요구하므로 실행하지 않았다. 각 단계 suite/통합은 socket 차단 상태이고 실모델 검증은 false다.

실제 CLI/Make 실행:

- demo artifact는 `artifacts/rehear-harness/stage03-demo/TEST_ONLY-{evidence,rubric,qwen-config}.json`과 fake 결과뿐이다. 모든 Rubric/Policy/모델 라벨은 합성이며 공식 자료로 저장하지 않았다.
- `PYTHONPATH=sushi-fast sushi-fast/.venv/bin/python -m tools.rehear_cli eval --input artifacts/rehear-harness/stage03-demo/TEST_ONLY-evidence.json --rubric artifacts/rehear-harness/stage03-demo/TEST_ONLY-rubric.json --engine fake --allow-test-rubric --repeat 2 --output artifacts/rehear-harness/stage03-demo/TEST_ONLY-fake-result.json`: **exit0**, fake_contract_only, 16개 모두 null/기권, call_count2, cache_enabled=false.
- 위 입력으로 `--engine qwen_local --config artifacts/rehear-harness/stage03-demo/TEST_ONLY-qwen-config.json --allow-test-rubric --output artifacts/rehear-harness/stage03-demo/TEST_ONLY-qwen-result.json`: **exit2**, `LocalRuntimeUnavailable: missing local dependency: torch`. 결과 파일 없음. 가중치 로딩/실제 generate에 도달하지 않았으며 성공이나 skip으로 계산하지 않는다.
- `sushi-fast`에서 `make -f Makefile.ai ai-eval INPUT=../artifacts/rehear-harness/stage03-demo/TEST_ONLY-evidence.json RUBRIC=../artifacts/rehear-harness/stage03-demo/TEST_ONLY-rubric.json OUTPUT=../artifacts/rehear-harness/stage03-demo/TEST_ONLY-make-result.json EXTRA_ARGS='--allow-test-rubric --repeat 2'`: **exit0**, 동일한 fake 호출2/cache off/16개 기권 결과. xcrun cache 경고는 있었으나 명령 성공.

남은 자료/미검증 범위:

1. **공식 Rubric**: 승인된 정확한 16개 criterion ID·정의와 80개(16×5) 점수 Anchor, 원문 출처·고정 버전. Q01의 실제 연구 자료 검증은 미완료다.
2. **공식 Policy**: 입력 결측/coverage·기권·근거 인정·가중치/집계 규칙과 출처·버전. 이 내용을 코드/fixture로 임의 생성하지 않았다.
3. **모델 artifacts**: 정확한 Qwen family/base·tokenizer revision/hash, LoRA 디렉터리/가중치·revision 또는 LoRA 없이 실행한다는 결정. 로컬 디렉터리의 revision 표기는 호출자가 제공한 provenance이며 파일 내용이 실제 그 commit인지 독립 검증하지 않는다.
4. **검증 환경/정답 자료**: 실제로 호환 확인된 torch/transformers/peft lock·hardware/inference 설정, 사용 가능한 전문가 채점 사례·동의된 평가 기준. Qwen 설치/실행·structured JSON 신뢰성·GPU 성능·실제 채점 품질은 미검증이다. fake loader/가짜 ML 모듈 시험을 Qwen 실행으로 바꾸어 표시하지 않는다.

기타 한계: structural reference/coverage 검증은 의미적 지지·외부 사실 확인이 아니다. 자동 source 전처리/오디오 STT 실행을 CLI에서 다시 구현하지 않고 기존 DTO/전처리 결과를 export해 재사용한다. 기존 DB에 저장되지 않은 STT words/정확한 slide timeline·QA 복구는 되살릴 수 없다. 내부 mapping 보관은 durable DB/recovery/public report 통합이 아니다. 선택적 OpenAI 연구 비교 엔진·다중 프로세스의 전역 추론 제한·강제 device 작업 중단도 이번 구현 범위에 포함하지 않았다.

다음 시작 위치: 공식 자료/모델 환경이 제공되면 이 패키지 계약과 `rehear_ai/README.md`의 준비 목록부터 검증한다. 04 진행은 별도 사용자 요청 시 `04-integrity-cleanup.md`와 실제 diff를 먼저 읽고 기존 baseline guard를 확인하는 지점부터 시작한다. benchmark나 baseline을 삭제/재생성하지 않는다.

### 2026-10-15 (Asia/Seoul) · 04-integrity-cleanup

범위와 보존:

- 루트 REHEAR_AI_TASK/PROGRESS/SPEC/CONTRACTS/AGENT_RULES/04 계획과 실제 코드·diff를 확인했다. 루트/상위/수정 경로에 추가 AGENTS는 없었다. HEAD/branch는 이전 단계와 같은 `9eb86b09ea7e1ff1f4be5fc3508bbff60e8ff125` / `feature/ai-pipeline`이며 기존 사용자·01–03 변경은 미커밋 상태였다.
- 시작 doctor와 기존 baseline guard를 통과한 뒤 제품 수정 전에 `artifacts/rehear-harness/stage04-start/`에 94개 기존 코드/fixture/SQL/설정 파일의 사본·SHA-256, Git status/diff/HEAD를 저장했다. baseline을 재생성하지 않았다.
- 종료 비교에서 시작 94개 중 81개는 동일하고 아래 범위의 13개만 의도적으로 변경됐다. 최초 사용자 변경 `question_generation.py`와 `tests/test_question_generation.py`는 둘 다 원래 해시와 동일하다. baseline SHA-256도 계속 `361158becbb43b4189ff9b8637f1794719717329fab5dbdedbae502cd995aefb`다. 결과는 `stage04-preservation-final.json`과 `stage04-only.patch`에 있다.
- Unity/sushi-app/catalog/EVC 고정 식/명령 필드/기존 route 집합/independent_reactions 기본 false/동일 request_id 응답 시각 계약은 유지했다. `rehear_ai` 연구 core는 이번 단계에서 변경하지 않았다. 독립 검토는 없으며 자체 diff/의존/계약 검토다.

보고서·지속 저장 변경:

- `report_v2/report_aggregation.py`: missing_inputs의 `gaze_delivery_score`가 있는 구간을 report 시선 집계에서 제외한다. 모두 누락이면 gaze.score=null, coaching=null, evidence_ids=[]와 미측정 이유를 반환한다. 일부 유효하면 기존 confidence×word_count 가중치를 **유효 구간에만** 적용하고 해당 구간의 참조만 사용한다. 이유와 기존 generation.warnings에 `gaze_coverage:유효수/전체수:valid_segments_only`를 기록한다. realtime 중립0.0과 계산식은 유지한다. compatibility-only 분석에서 누락 gaze=50을 만들지 않는다.
- `report_v2/report_service.py`: 모든 score=null 카드의 기존 이유/무코칭 상태를 LLM으로 덮어쓰지 않는다. 부분 시선의 결정적 coverage/참조도 보존하며, 완전히 관측된 시선과 다른 유효 카드의 narrative는 기존처럼 적용한다. finish/recovery에 QA 이력을 연결하고, QA 자료가 전혀 없는 과거 복구에는 `qa_history_unavailable`를 기록한다. 저장 중인 답변은 완료 QA처럼 복구하지 않는다. report job 시작 실패 전에 메모리 generating 상태를 확정하지 않는다.
- `report_v2/report_generation.py`: provider class/instance namespace·model/revision·adapter/revision·prompt/Rubric/Policy 버전·inference_settings·실제 payload를 cache identity에 반영했다. custom provider 인스턴스는 같은 class/model이어도 격리된다. 기본 OpenAI는 키의 hash로 namespace를 구분하며 키를 로그/공개 결과에 넣지 않는다. 존재하지 않는 evidence reference는 cache 전에 거부하고 정해진 `ai_insight_fallback`으로 드러낸다. timeout/retry/provider seam과 기본 OpenAI는 유지했다. **참조 존재 검사는 의미적 지지/정확성의 증명이 아니다.**
- `odi/db/schema.sql`, `odidb.py`: 기존 init_db/ensure_report_schema와 SQLite transaction 방식으로 `presentation_qa` 내부 snapshot 테이블을 추가했다. server-bound owner/PIN을 확인한 뒤 질문 목록/ID/order/source_steps·답변·request/audio hash·duration·청중 연결·완료 응답을 원자적으로 저장한다. 다른 owner/PIN의 snapshot 조회/덮어쓰기는 거부한다. QA 원문도 기존 source 삭제/세션 삭제/retention 정리 대상이다. 기존 retention 반환 필드와 public report schema는 유지했다.
- 신규 `qa_persistence.py`, `question_service.py`, `answer_service.py`, `session_store.py`: 최초 질문과 인식 transcript를 저장하고, 최종 답변/적응 질문 snapshot의 DB commit 뒤에만 완료 response와 질문 목록을 반영한다. 최종 commit 실패 시 같은 프로세스에서 만든 적응 후보를 보존해 동일 답변 재시도에서 STT/질문 생성을 중복하지 않는다. 완료 snapshot을 복원한 뒤에도 동일 답변 요청은 저장된 응답을 재사용한다. 질문 timestamp/최초 generation request ID와 청중 binding도 복원한다.
- `router.py`의 기존 `/speech` body에서 이미 검증한 선택 청중을 내부 snapshot에 보존한다. 첫 질문도 실제 전달된 X-Audience-Id가 있으면 연결하며, 관측되지 않은 첫 청중을 만들어 내지 않는다. 이는 **선택된 청중**이며 TTS가 실제 Unity에서 재생됐다는 관측이 아니다. route/요청/응답 필드는 추가하지 않았다.
- `pipeline.py`: 분석/RNG/응답을 작업 사본에서 만든 뒤 PIN-bound segment upsert가 commit된 후 메모리 audiences/RNG/step/time/notes/transcript/report/scheduler/cache를 반영한다. fake 실패뿐 아니라 SQLite AFTER INSERT trigger의 ABORT→rollback→동일 ID 재시도에서 legacy/opt-in 모두 DB 구간 1개와 응답 1회 반영을 확인했다.

CLI와 이전/정리:

- `tools/rehear_cli/{__main__,runs,legacy_cases,migration}.py`, 도구 README, `Makefile.ai`를 보완했다. `ai-doctor|ai-contracts|ai-eval|ai-compare|ai-repeat|ai-replay|ai-bench`가 모두 존재한다. fake가 기본이고 API/마이크 자동 실행은 없다. compare는 같은 Research16 Evidence/Rubric/Policy를 두 engine에 전달하고 criterion별 score/null을 비교한다. 기존 OpenAI 10개 설명을 연구16 task로 혼합하지 않는다.
- run metadata는 run_id/input hash/task/engine/identity/revision/adapter/Rubric·Policy digest/version/prompt/settings/실제 호출/retry/cache hit/failed attempts/최종 failure/elapsed를 기록한다. repeat/compare/bench와 eval repeat>1은 cache off다. bench는 cold load, 첫 generation, 이후 warm generation, 전체 처리시간을 구분한다. 기기 kernel 시간이나 실제 사용자 지연이라고 부르지 않는다. eval의 기존 AssessmentResult 파일은 유지하고 `OUTPUT.run.json` metadata sidecar를 추가했다. 파일 덮어쓰기는 거부하고 일반 로그에는 원문/모델 reason/오류 원문을 쓰지 않는다.
- 신규 `TEST_ONLY-stage04-{evidence,rubric,legacy-post}.json` fixture는 전부 합성이다. 공식 Rubric/Anchor/Policy를 만든 것이 아니다. `--input-format legacy-post`는 예전 text case의 명시적 text/time/slide 연결만 재사용하며, 관측 시계·음성 지표·질문 없는 답변 pairing을 생성하지 않는다.
- 두 원본 폴더를 hidden/ignored 파일까지 조사했다. **127개 / 64,424,320 bytes**: case 7개, 과거 결과 20개, 측정 정의/코드/README 14개, 녹음 WAV 75개, 지원 metadata/pycache 등 11개다. 전부 `artifacts/rehear-private/legacy-benchmarks/`에 byte 단위로 보존했다. 실제 상대 경로 대응은 private `source-index.json`에만 있고, 공개 `legacy-benchmark-inventory.json`에는 hash/크기/분류/새 위치만 있다. `.gitignore`에 private archive 경로를 추가하고 git check-ignore exit0을 확인했다. credential 패턴 후보 파일은 0개였지만 이 검색이 비밀/개인정보 부재 증명은 아니다. 녹음을 청취하거나 익명화하지 않았고 모든 원본을 private 사용자 자료로 취급한다.
- `MEASUREMENTS.md`에 기존 post/live wrapper의 시간 정의·단위·합계·retry/late/누락 정책과 새 Research16 측정의 차이를 옮겼다. 원본 측정 코드/문서 자체도 hash 검증한 archive에 남아 있다. 과거 결과를 새 실행/품질 결과로 표시하지 않았다.
- 최초 복사 후 **127개 원본↔archive hash와 전체 파일 집합을 대조**했다. 7개 새 Make 명령, 보존 text case 3개 replay, 삭제 전 전체 260개 회귀를 확인한 후 다시 원본 127개 hash를 검증하고 **그때만** `sushi-fast/latency_benchmark_with_outputs/`, `sushi-fast/live_latency_benchmark/`를 삭제했다. 삭제 후 archive 127개 hash를 다시 확인했다 (`stage04-migration-before-delete.json`, `stage04-cleanup.json`). catalog/운영 playback/STT timestamps/observability/제품 tests는 삭제하지 않았다.
- `rg --hidden -l 'latency_benchmark_with_outputs|live_latency_benchmark' --glob '!artifacts/**' --glob '!.git/**' --glob '!node_modules/**' .`로 삭제 후 README/파일 경로 참조까지 검색했다. 남은 것은 migration.py의 원본 이름 constants, inventory, SPEC/과거 PROGRESS/Notion source 및 수정하지 않은 원본 하네스 묶음의 역사 참조다. 활성 backend의 import/실행 경로 참조는 없다. 문자열 참조가 완전히 0이라고 주장하지 않는다.

실제 명령과 검증 결과 (루트 기준, 기존 가상환경):

| 실행 | exit | 실제 결과 / artifact |
|---|---:|---|
| 시작 doctor / 기존 guard | 0 / 0 | offline 환경 READY / 보호 경계 통과, baseline 재생성 없음 |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite integrity` (구현 전) | 1 | 10 collected, **9 failed / 1 passed**, 0 skip/error. missing gaze·null narrative·provider 격리·invalid reference·QA 부재·저장 순서·이전 부재 재현 (`stage04-integrity-before.log`) |
| 최초 보고서/DB 보완 후 같은 integrity | 1 | 9 passed / 1 failed; 미구현 migration 검사만 남음 (`stage04-integrity-first.log`) |
| CLI 6개 검사를 추가한 구현 전 integrity | 1 | 16개 중 9 passed / 7 failed; 새 CLI 및 manifest 부재 (`stage04-cli-before.log`) |
| 최초 전체 `test --suite all` | 0 | 251 passed (`stage04-all-first.log`) |
| SQLite rollback·CLI 제거 제품 회귀 등 확장 integrity | 0 | **21 passed**, 0 skip/error (`stage04-integrity-expanded.log`) |
| 청중 binding·metadata·QA transaction 검사 추가 integrity | 1 | 25개 중 24 passed / 1 failed. 새 테스트가 기존 wrong-token HTTP를 403으로 잘못 예상했으며 실제 계약은401이었다. 제품 권한/오류를 바꾸지 않고 assertion을401로 바로잡음 (`stage04-integrity-storage.log`) |
| 삭제 전 최종 `test --suite all` | 0 | **260 passed**, 0 failed/skipped/error/xfail/xpass. integrity 25 + 이전 stage 106 + 기존129 (`stage04-all-precleanup-final.log`) |
| `sushi-fast/.venv/bin/python tools/rehear_harness.py doctor` (최종) | 0 | READY_FOR_OFFLINE_TESTS. Python3.13.15 / pytest8.4.2 / FastAPI0.141.1 / httpx0.28.1 / Pydantic2.13.4 / numpy2.4.3 (`stage04-doctor-final.json`) |
| **삭제 후 최종 `sushi-fast/.venv/bin/python tools/rehear_harness.py test --suite all`** | **0** | **260 passed**, 0 failed/skipped/error/xfail/xpass, socket 차단, 13.73초 (`stage04-all-final.log`) |
| 그 뒤 `sushi-fast/.venv/bin/python tools/rehear_harness.py guard` | **0** | **PASS_PROTECTED_BOUNDARIES_ONLY, violations=[]** (`stage04-guard-final.json`) |
| 사용자2개/시작94개/baseline 해시 확인 | 0 | 사용자 변경 그대로, 13개 의도 변경 외 차이 없음 (`stage04-preservation-final.json`) |
| `git diff --check` | 0 | 신규 SQL EOF 빈 줄을 정리한 뒤 whitespace 오류 없음. Git/Make의 macOS xcrun temp-cache 경고는 명령 성공과 구분함 |

전체 260개에는 독립 도구를 복사하지 않은 환경에서 core/backend를 import하고 **기존 제품 129개 전체를 별도 pytest/socket 차단으로 실행한 검사**가 포함돼 있다. 내부 129개를 바깥 collected260에 다시 더해 합산하지 않는다. 하네스 all은 EVC의 모든 지정 stage/기존 suite이며 repository 모든 앱의 전체 테스트라는 뜻은 아니다.

새 명령 실제 실행 (`sushi-fast` cwd):

- `make -s -f Makefile.ai ai-doctor|ai-contracts`와 나머지 각 target을 실제로 하나씩 실행했다. 각 명령/인자/exit은 `artifacts/rehear-harness/stage04-demo/commands.json`, stdout/stderr는 같은 경로의 target별 log에 있다. 입력은 fixture의 TEST_ONLY Evidence/Rubric, 명시 flag `--allow-test-rubric`, 결과는 같은 demo 디렉터리의 새 파일이다.
- **7개 모두 exit0**: eval fake 호출1, repeat `--repeat 3` 호출3/cache off, compare fake/fake 호출합2·동일 task·16개 모두 기권, replay `--result eval.json` 호출0, bench `--repeat 3` 호출3/cache off. doctor/contracts는 모델을 로드하지 않았다. bench의 실제 시간은 `stage04-demo/bench.json`의 cold/first/warm/elapsed에 기록돼 있으며 fake 시간이다. fake clock 검사에서는 load5초/first2초/warm[2,2]초/total11초를 각각 분리함도 확인했다.
- archive text case 3개에 `python -m tools.rehear_cli replay --input ARCHIVED_CASE --input-format legacy-post --rubric TEST_ONLY_BUNDLE --allow-test-rubric --output NEW_PATH` 실행: **3개 모두 exit0/call_count0**, 원문 stdout/stderr 없음 (`archived-case-replays.json`). 당시 실사용 세션의 실제 시간/품질을 재현한 것이 아니다. live case/config 2개와 대본 등은 원본대로 archive했으며 녹음/STT/TTS를 다시 실행하지 않았다.
- `python -m tools.rehear_cli eval ... --engine qwen_local --config ../artifacts/rehear-harness/stage03-demo/TEST_ONLY-qwen-config.json --allow-test-rubric --output .../qwen-not-executed.json`: **exit2 / LocalRuntimeUnavailable / call_count0 / failures1**, AssessmentResult 파일 없음, 실패 run metadata sidecar 있음 (`stage04-demo/qwen-attempt.json`). torch/transformers/peft 미설치 환경이며 실제 weights load/generate/모델 품질 검증에 도달하지 않았다. 성공/skip으로 바꾸지 않았다.

미검증/실용적 한계:

1. 실제 운영 DB에 migration/deploy/restart를 적용하지 않았다. 검증은 임시 SQLite와 ASGI EVC 라우터/fake provider다. `restore_qa_state`는 server-bound 내부 복원 경계이며 소실된 세션 token을 되살리는 새 공개 API가 아니다. PIN 없는 세션의 기존 memory-only 수명은 유지된다.
2. 성공 commit된 QA는 복원/응답 재사용되며, commit 실패 시 같은 프로세스의 적응 후보를 재사용한다. **모델 생성 후 DB commit 전 프로세스가 죽는 경우까지 LLM 호출 exactly-once를 보장하지 않는다.** 미완료 QA가 있으면 recovery는 완료를 가장하지 않고 in-progress를 반환한다. 저장하지 않았던 과거 질문/청중/답변을 새로 만들어 복구하지 않는다.
3. 참조 존재/ID·schema·출처·coverage 검증은 의미적 사실성/코칭의 정확성이나 공식 I4 등 연구 기준 평가가 아니다. 기존 평가의 missing flag가 없는 오래된 gaze 0을 새로 누락이라고 추측하지 않는다. 부분 coverage의 count는 구간 개수이며 gaze 시계열/관측 시간 비율이 아니다.
4. 공식16 Rubric의 정확한 ID·정의·80개 Anchor, 승인 Policy와 버전/출처, Qwen base/tokenizer/adapter artifacts·runtime lock·전문가 참조 자료는 이전 단계처럼 미확보다. fake/CLI/loader 연결을 실제 연구 품질로 표시하지 않는다. 새 ML 의존성/가중치 다운로드나 API 호출은 없었다.
5. Unity·웹 browser/e2e·실제 마이크/STT/TTS/서비스 전체 서버/배포·GPU를 실행하지 않았다. Unity 소비자/재생 시계·렌더 시각·actor mapping의 미관측과 30초 수집/legacy 지연 한계는 그대로다. headless 테스트와 guard가 실제 웹/XR 완료를 의미하지 않는다.
6. 개인 archive는 Git 제외 **로컬 보존본**이다. 별도 원격 백업/암호화/익명화·내용의 사실성 검증은 수행하지 않았다. public checkout에는 hash inventory만 존재한다. archive 유실을 대비한 외부 보관은 별도 사용자 운영 범위다. portable inventory 테스트는 합성 이전/변조 검사를 항상 실행하고, 실제 개인 archive가 로컬에 있을 때 추가 hash 검사를 수행한다. 이번 환경에서는 실제127개 검사까지 실행했다.

04의 지정 구현·이전·정리·오프라인 회귀는 완료했다. 후속 실제 연구/웹/XR 작업은 위 자료와 환경을 확보해 별도로 검증해야 하며 이 기록을 완료 증거로 대체할 수 없다.
