# AI 청중 상태 및 백채널 반응 파이프라인 개발 계획

## 1. 계획의 목적과 적용 범위

이 문서는 `PROJECT_ONBOARDING.md`와 `reaction-rule.md`를 기준으로, XR 발표 훈련용 AI 청중 상태 및 백채널 반응 파이프라인을 기존 ODI/FastAPI 백엔드에 구현하고 Unity가 사용할 수 있는 출력 계약까지 완성하기 위한 순차 작업 계획이다.

구현 기준 경로는 현재 ODI에 등록된 `sushi-fast/odi/EVC/`이며, `sushi-fast/odi/EVC/EVCv1/`은 비교 참고용 레거시 구현으로만 취급한다. 주 실행 앱은 `sushi-fast/main.py`이고 API 기본 prefix는 현재의 `/odi/xreal_rehear/evc` 조합을 유지하되, 실제 라우터 등록 상태를 1단계에서 다시 검증한다.

프로토타입 범위는 다음과 같다.

- 고정 청중 6명의 개별 E/V/C 상태 초기화 및 갱신
- 음성/STT, 발표자료, 전달 지표를 이용한 내용 평가 `M_t`와 전달 평가 `D_t` 산출
- 우세축, 방향, 근사 동률 규칙을 이용한 상위 행동군 결정
- Core Behavior와 Action Clip 후보 필터링, 점수화, 확률 선택
- Face, Body, GazeHead 레이어용 Unity 명령 생성
- 세션, 행동 이력, 쿨다운, 재현 가능한 랜덤성 관리
- 실패 처리, 관측성, 자동 테스트 및 Unity 연동 문서화

## 2. 작업 진행 원칙

1. 이 계획 파일이 생성된 뒤의 실제 개발은 아래 단계를 **한 번에 한 단계씩**, 번호 순서대로 진행한다.
2. 현재 단계의 산출물과 완료 기준을 충족하고 검증 결과를 기록하기 전에는 다음 단계로 넘어가지 않는다.
3. 각 단계 시작 전 `git status`로 사용자 변경 사항을 확인하고, 해당 단계 범위 밖의 파일은 수정하지 않는다.
4. 명세의 수식, 임계값, 가중치와 API 계약은 코드 상수 또는 설정 데이터로 명시하며 암묵적인 값으로 남기지 않는다.
5. 외부 AI/STT 호출이 없어도 단위 테스트와 로컬 통합 테스트를 수행할 수 있도록 인터페이스와 테스트 대역을 둔다.
6. `.env`, 음성, 발표자료, DB, 디버그 로그에 포함될 수 있는 개인정보와 비밀값은 커밋하지 않는다.
7. 명세와 구현 사이에 해석이 필요한 경우 결정과 근거를 해당 단계의 설계 기록에 남기고, 이후 코드·테스트·Unity 계약에 동일하게 반영한다.

## 3. 사전 분석에서 확인된 핵심 차이와 위험

- 현재 `AudienceState`와 `EVCSession`은 세션 공통 단일 E/V/C 상태 중심이지만, 명세는 6명 각각의 `A_i,t`와 프로파일, 행동 이력, 쿨다운을 요구한다.
- 현재 행동 생성은 제한적인 규칙 분기이며, 명세의 Clip Pool 전체, 후보 집합, 점수식, Softmax/Categorical 선택, Action Overlay를 모두 표현하지 않는다.
- 현재 응답의 `BehaviorCommand`는 Unity가 요구하는 레이어별 `agent_id`, `start_time`, `layer`, `action_id`, `duration`, `sync_group` 명령 배열을 제공하지 않는다.
- `reaction-rule.md`에는 선택 점수 계수 `lambda`, Action Clip의 최종 선택/삽입 확률, 개별 행동의 실제 하위 `action_id`와 duration, 이벤트 검출 임계값이 확정되어 있지 않다.
- Core 표에서 같은 `clip_id`가 여러 variation에 반복되므로, `selected_behavior_id`와 variation/Unity action mapping을 구분하는 고유 식별자 규칙이 필요하다.
- EVC 세션이 프로세스 메모리에만 있어 재시작·멀티 프로세스·수평 확장에 취약하다. 프로토타입 저장 범위와 운영 전환 조건을 명시해야 한다.
- 외부 입력 중 발표자 시선, 발화 경계, 슬라이드 참조, 정보량, 반복 이탈, 저각성, 긴장, 주변 상호작용은 수집 주체와 판정 방식이 아직 명확하지 않다.

## 4. 단계별 개발 계획

### 1단계. 기준선 조사와 구현 대상 확정

작업:

- `sushi-fast/main.py`, `sushi-fast/odi/router.py`, `sushi-fast/odi/EVC/{router.py,schema.py,service.py,speech2text.py}`의 실제 데이터 흐름과 API 경로를 추적한다.
- `EVC/EVCv1`, `sushi-app/src/routes/odi/GITA`, 기존 Unity/XR 호출 흔적을 조사하여 유지할 현재 구현과 참조만 할 레거시 구현을 구분한다.
- 현재 세션 생성, STT, 슬라이드 추출, GPT 평가, EVC 갱신, 행동 생성, 로그 기록의 함수별 입력·출력·부작용을 목록화한다.
- 기존 응답 샘플과 `sushi-fast/odi/evc_logs`의 데이터 형식을 확인하되 개인정보는 복제하지 않는다.
- 현재 테스트 실행 가능 여부, Python 버전 및 누락 의존성을 기록한다.

산출물:

- 현행 파이프라인 흐름도와 재사용/교체 대상 목록
- 수정 예상 파일 목록 및 API 호환성 영향 목록
- 명세 대비 결손 항목 체크리스트

완료 기준:

- 현재 API의 시작→갱신→응답 흐름을 함수와 스키마 단위로 설명할 수 있고, `EVCv1`을 신규 구현 경로에 섞지 않는다는 경계가 확정되어야 한다.

### 2단계. 미확정 정책과 데이터 계약 결정

작업:

- 상태 구간을 낮음 `[-1.00, -0.34]`, 중간 `[-0.33, 0.33]`, 높음 `[0.34, 1.00]`으로 구현하고 경계 사이의 소수 공백 처리 원칙을 정한다.
- 근사 동률 임계값 `0.10`과 `-C → -V → -E → 직전축 → E → C → V` 우선순위를 정확한 알고리즘으로 확정한다.
- 중복 `clip_id` 문제를 해결하도록 `behavior_id`(행동군 ID)와 `variation_id`(고유 실행 변형 ID)를 분리하고 기존 명세 ID와의 추적성을 유지한다.
- 명세에 없는 `lambda_s/p/c/h/r`, Softmax temperature, Action 삽입 확률·충돌 우선순위, 빈 후보 fallback, duration, intensity, 랜덤 seed 정책의 프로토타입 기본값을 확정한다.
- 발표자 시선과 각 사건 신호를 Unity가 직접 제공할지, 서버가 파생할지, 입력이 없을 때 어떤 중립값/fallback을 쓸지 결정한다.
- API 버전 전략을 결정한다. 기존 클라이언트 호환이 필요하면 기존 필드를 보존하고 새 `audiences`와 `commands`를 추가한다.
- 메모리 세션을 프로토타입 기준으로 유지할지 SQLite 등 영속 저장으로 전환할지 결정하고, 최소한 재시작 시 소실됨을 API/문서에 명시한다.

산출물:

- 결정된 상수, 기본값, 식별자, 입력 누락/fallback, 호환성 정책을 담은 설계 결정 기록
- 요청/응답 JSON 예시와 필드별 단위·범위·필수 여부

완료 기준:

- 이후 단계에서 개발자가 임의의 수치나 식별자 규칙을 추가하지 않아도 모든 계산과 API 모델을 구현할 수 있어야 한다.

### 3단계. 모듈 구조와 도메인 스키마 정비

작업:

- STT/평가, 상태 모델, 프로파일, Clip Pool, 행동 선택, Unity 명령 조립, 세션 저장 책임을 분리하는 모듈 구조를 확정한다.
- Pydantic 모델로 세션 공통 설정, 6명 에이전트 프로파일, 개별 E/V/C 상태, 직전 우세축, 행동 이력, 쿨다운, 사건 입력, 발화 위치를 정의한다.
- `Topic Interest`, `Prior Knowledge`, `Responsiveness`, `Expressivity`, `ChannelPreference`, `CriticalBias`, `Has Laptop`, 좌석/행 제약을 타입과 범위 검증으로 표현한다.
- Core/Action Clip 메타데이터와 Unity 레이어 명령 모델을 정의하고, 알 수 없는 enum·범위 밖 수치·중복 고유 ID를 거부한다.
- 기존 단일 상태 응답을 유지해야 하는 경우 집계 상태의 정의와 deprecation 방식을 함께 정한다.

산출물:

- 검증 가능한 도메인/API 스키마
- 모듈 의존 방향과 공개 인터페이스

완료 기준:

- 정상/비정상 요청 샘플이 스키마 검증을 통과/실패하고, 6명 상태 및 레이어별 명령을 직렬화할 수 있어야 한다.

### 4단계. Clip Pool과 Unity 행동 매핑 데이터 구축

작업:

- `reaction-rule.md` 9장의 모든 Core Behavior와 `ACT_01`~`ACT_08`을 코드 외부의 검증 가능한 JSON/YAML 또는 명확한 상수 테이블로 옮긴다.
- 각 항목에 행동군, 상태 조건, 발화 위치, 채널, 쿨다운, 사건 gate, 변형 고유 ID를 기록한다.
- 각 variation을 Face/Body/GazeHead의 실제 또는 합의된 Unity `action_id`, 기본 duration, blend/intensity 범위로 분해한다.
- 노트북 보유, 맨 뒷줄 2명, 슬라이드 참조 등 장면 제약을 메타데이터에 표현한다.
- 시작 시 전체 Clip Pool을 검증하여 중복 ID, 알 수 없는 상태/채널, 빈 매핑, 잘못된 cooldown을 조기에 탐지한다.

산출물:

- 완전한 Core/Action Clip Pool 데이터
- behavior/variation→Unity layer action 매핑표

완료 기준:

- 명세의 모든 행이 정확히 한 고유 variation으로 조회되고 각 variation이 최소 하나의 실행 레이어 명령으로 분해되어야 한다.

### 5단계. 세션 및 6명 에이전트 초기화 구현

작업:

- `smart-start`에서 청중 수를 6명으로 고정하고 세션 공통 `Topic Interest`, `Prior Knowledge`를 `0.25/0.50/0.75`로 정규화한다.
- `E_initial=(TopicInterest-0.50)*2`, `C_initial=(PriorKnowledge-0.50)*2`, `V_initial=0.00`을 적용한다.
- E/C에만 `-0.05~+0.05` 초기 오프셋을 부여하고 clamp하며, seed를 저장해 테스트와 재현이 가능하게 한다.
- 각 에이전트에 행동 성향값을 허용 범위 내에서 생성하고 ChannelPreference, Has Laptop, 좌석 조건을 설정한다.
- 세션에 단계 번호, 이전 우세축, 최근 행동, clip별 last-used time, 요약, 슬라이드, 생성/수정 시각을 초기화한다.
- 동시 요청에서 같은 세션 상태가 덮어써지지 않도록 세션별 동기화 방식을 적용한다.

산출물:

- 6명 개별 상태/프로파일을 반환하는 세션 생성 및 조회 기능
- seed 기반 재현 가능한 초기화 테스트

완료 기준:

- 낮음/중간/높음 조합별 초기 E/C/V와 민감도가 명세대로 계산되고, 6명 모두 유효 범위와 고유 ID를 가져야 한다.

### 6단계. 입력 수집, STT 및 발표 구간 컨텍스트 정규화

작업:

- 오디오 형식·크기·길이를 검증하고 임시 파일이 성공/실패 모두에서 정리되게 한다.
- 기존 Deepgram STT 결과를 transcript, word timing, confidence의 내부 표준 모델로 정규화한다.
- 현재 슬라이드 인덱스, 텍스트/요약, 슬라이드 전환·참조 여부, 발화 위치를 하나의 구간 컨텍스트로 묶는다.
- Unity/클라이언트가 제공하는 gaze score와 사건 신호를 검증하고, 미제공 값은 2단계에서 정한 fallback으로 표시한다.
- 빈 음성, 낮은 STT 신뢰도, 잘못된 슬라이드 인덱스, STT timeout/키 미설정에 대한 오류 또는 안전한 no-op 정책을 구현한다.

산출물:

- 후속 평가기가 공급자별 세부 형식에 의존하지 않는 표준 입력 모델
- 입력 검증 및 실패 처리 테스트

완료 기준:

- 정상 음성, 빈 구간, 외부 서비스 실패, 부분 입력을 각각 예측 가능한 결과로 처리하고 임시 데이터가 남지 않아야 한다.

### 7단계. 내용 평가와 전달 평가 파이프라인 구현

작업:

- LLM은 Organization, Supporting Material, Central Message, CER Validity, Language Clarity, Slide-Speech Alignment만 구조화 평가하도록 제한한다.
- Vocal Delivery는 speech rate, pause, filler, repetition, STT confidence 등 결정적 음성 지표로 산출한다.
- Gaze Delivery는 입력값이 있으면 사용하고, 없으면 명시적인 neutral/fallback과 `missing_inputs`를 반환한다.
- 모든 요소를 `[-1,1]`로 검증·clamp하고 신뢰도와 짧은 평가 근거를 기록한다.
- LLM timeout, 형식 오류, 누락 필드, 키 미설정 시 재시도 횟수와 fallback을 구현하며 E/V/C나 행동을 LLM이 직접 생성하지 못하게 한다.
- 동일 입력에 대한 테스트 대역을 사용해 외부 비용 없이 평가 조립 로직을 검증한다.

산출물:

- 완전한 `M_t`, `D_t`, `MtDtEvaluation`
- LLM/STT 장애와 누락 입력을 포함한 평가 테스트

완료 기준:

- 각 평가 요소의 출처가 추적 가능하고, 외부 AI가 직접 상태·행동 ID를 출력하지 않으며, 모든 평가값이 유효 범위에 있어야 한다.

### 8단계. E/V/C 갱신 엔진 구현

작업:

- 내용 평가를 `ΔE_M`, `ΔV_M`, `ΔC_M`으로 변환하고 각 벡터를 clamp한다.
- 전달 평가를 `ΔE_D`, `ΔV_D`, `ΔC_D`으로 변환하고 각 벡터를 clamp한다.
- 차원별 `M:D` 가중치 E=`0.45:0.55`, V=`0.55:0.45`, C=`0.50:0.50`로 공통 `ΔA_t`를 계산한다.
- 각 에이전트에 대해 음수 E/C 변화에만 `1.20/1.00/0.80` 감소 민감도를 적용하고, 양수 변화와 V에는 `1.00`을 적용한다.
- `A_i,t = clamp(A_i,t-1 + η_i ⊙ ΔA_t, -1, 1)`을 적용하고 이전/갱신량/다음 상태를 추적 가능하게 남긴다.
- 기존 구현의 target toward 보간 방식이 명세의 가산 갱신식과 다르면 명세식으로 교체하고 회귀 영향을 테스트한다.

산출물:

- 외부 서비스와 분리된 순수 상태 계산 모듈
- 공식별 테이블 기반 단위 테스트와 경계값 테스트

완료 기준:

- 문서의 수식 예제를 코드로 재계산했을 때 일치하고, positive update 비증폭·V 독립성·최종 clamp가 모두 테스트로 보장되어야 한다.

### 9단계. 상위 행동군과 후보 집합 엔진 구현

작업:

- E/V/C 수준 분류, 모두 중간일 때 Baseline Listening, 절대값 우세축 판정을 구현한다.
- 근사 동률 판정과 음수축 우선·직전축 유지·최종 우선순위를 구현한다.
- 우세축/방향과 복합 상태 조건을 Clip Pool의 상위 행동군 및 variation 조건에 연결한다.
- Core 후보는 parent group, state match, utterance position, 장면 조건, cooldown으로 필터링한다.
- Action 후보는 event match, state gate, utterance position, 장면 조건, cooldown으로 별도 필터링한다.
- 후보가 비었을 때 안전한 Baseline/no-op fallback을 적용하고 그 원인을 기록한다.

산출물:

- 결정적 행동군 판정기와 Core/Action 후보 필터
- 모든 상태 구간, 동률 조합, 발화 위치, 장면 조건, cooldown에 대한 테스트

완료 기준:

- 선택된 행동이 항상 필터링된 후보 집합에 속하고, 금지된 발화 위치나 장면 조건의 행동은 후보에 포함되지 않아야 한다.

### 10단계. 확률 선택, 행동 이력 및 Action Overlay 구현

작업:

- `StateFit`, `Preference`, `ChannelPreference`, `History`, `Repetition`을 각각 독립 계산하고 2단계의 계수로 `z_core`를 산출한다.
- 수치적으로 안정적인 Softmax와 Categorical sampling을 구현하고 seed 주입을 지원한다.
- Responsiveness는 반응 빈도/no-op 확률, Expressivity는 intensity와 명시적 variation, CriticalBias는 V가 중립 이하일 때만 비판적 후보 가중치에 반영한다.
- Action 후보의 점수·삽입 확률과 Core 충돌 규칙을 적용해 최대 하나의 overlay를 선택하거나 `null`을 반환한다.
- 선택 직후 행동 이력과 cooldown timestamp를 원자적으로 갱신하고 반복 페널티를 적용한다.
- 동일 seed 재현성, seed 변화에 따른 분포, 장기 반복 편향, cooldown 준수를 통계 테스트한다.

산출물:

- 확률적 Core 선택기 및 optional Action Overlay 선택기
- 점수 구성요소와 최종 확률을 디버그 가능한 형태로 제공하는 진단 데이터

완료 기준:

- 동일 seed/입력은 동일 결과를 내고, 다수 샘플의 빈도가 계산된 확률과 허용 오차 내에서 일치하며, 잘못된 방향의 CriticalBias 영향이 없어야 한다.

### 11단계. Unity 출력 명령 조립 및 API 통합

작업:

- 선택된 Core와 optional Action을 Face, Body, GazeHead 명령 배열로 분해한다.
- 각 명령에 `agent_id`, `start_time`, `layer`, `action_id`, `duration`, `sync_group`, `selected_behavior_id`를 포함하고 intensity/blend 정보가 필요하면 명시 필드로 추가한다.
- `utterance_position`에 맞춰 start time을 결정하고 한 반응의 레이어 명령에 같은 `sync_group`을 부여한다.
- Core/Action이 같은 레이어를 사용할 때의 override/additive/queue 규칙과 GazeHead 조정 우선순위를 적용한다.
- 세션 update 응답에 6명 각각의 상태, 선택 근거, Core, Action, Unity commands를 포함한다.
- 기존 API 필드를 유지하기로 한 경우 호환 응답과 신규 응답을 동시에 직렬화하고 OpenAPI 예제를 갱신한다.

산출물:

- Unity 소비용 API 응답과 레이어별 실행 명령
- 직렬화, sync group, 레이어 충돌, 하위 action mapping 테스트

완료 기준:

- 한 번의 update로 6명 모두에 대해 유효한 상태와 실행 가능한 명령 또는 명시적 no-op을 반환하며, Unity가 서버 내부 규칙을 재구현하지 않아도 되어야 한다.

### 12단계. 세션 안정성, 오류 처리, 보안 및 관측성 보강

작업:

- 2단계에서 정한 저장 전략에 따라 세션 복구·만료·삭제 또는 메모리 전용 제한을 구현한다.
- 동시 update의 순서, idempotency/step 검증, 오래된 요청 거부, 세션별 lock을 검증한다.
- 인증 적용 범위와 Unity 클라이언트 인증 방식을 기존 `mainauth`/ODI 흐름에 맞게 정리하고 타 세션 접근을 차단한다.
- 오류를 입력 오류, 세션 없음, 외부 STT/AI 오류, 내부 계산 오류로 구분하고 비밀값·원문 음성·전체 발표문이 오류 응답에 노출되지 않게 한다.
- 구조화 로그에 session/step/latency/provider usage/fallback/선택 행동을 남기되 개인정보 최소화와 보존 기간을 적용한다.
- `DEBUG_EVC_LOG` 기본값과 로그 경로를 안전하게 조정하고 추적 중인 기존 로그의 보존/제거 여부를 별도 확인한다.

산출물:

- 세션 수명주기, 동시성, 인증, 오류 모델, 안전한 로그 정책
- 실패 복구 및 접근 통제 테스트

완료 기준:

- 재시도·동시 요청·외부 장애가 상태를 중복 갱신하거나 손상하지 않고, 다른 사용자의 세션 및 민감 데이터가 노출되지 않아야 한다.

### 13단계. 자동 테스트와 엔드투엔드 검증

작업:

- 순수 계산 단위 테스트: 초기화, 점수 변환, 통합 가중치, 민감도, clamp, 수준/우세축/동률, 후보 필터, Softmax, cooldown을 검증한다.
- 데이터 검증 테스트: Clip Pool 전체 로딩, ID 유일성, 모든 Unity mapping, 허용 enum/range를 검증한다.
- API 통합 테스트: smart-start→session 조회→복수 update→상태/이력 변화와 오류 응답을 테스트한다.
- 외부 STT/LLM은 mock으로 정상·timeout·잘못된 JSON·낮은 confidence를 검증하고, 자격 증명이 있을 때만 선택적 smoke test를 실행한다.
- 6명 청중, 네 발화 위치, 슬라이드 전환, 각 Action 사건, 긍정/중립/부정 E/V/C 시나리오를 fixture로 검증한다.
- 관련 Python 테스트와 FastAPI OpenAPI 생성을 실행하고, 프런트 타입이나 호출부를 수정했다면 `npm run check`와 관련 테스트도 실행한다.

산출물:

- 재현 가능한 테스트 fixture와 자동 테스트 모음
- 명령, 결과, 실패/제약을 포함한 검증 기록

완료 기준:

- 핵심 수식과 계약을 자동 테스트가 보호하고, 외부 키 없이 전체 결정 로직과 API 통합 테스트가 통과해야 한다.

### 14단계. 실제 Unity 연동 리허설과 승인 기준 확인

작업:

- Unity 테스트 클라이언트 또는 합의된 요청 샘플로 세션 시작과 연속 update를 재생한다.
- Unity의 agent/action ID, Animator layer, BlendShape, Gaze/Head IK, sync group, 시간 단위와 서버 출력의 일치를 확인한다.
- 발화 중 큰 행동 제한, 발화 경계 반응, 침묵/휴지 Action, 슬라이드 전환 동기화를 화면에서 확인한다.
- Core와 Action의 블렌딩, 레이어 충돌, cooldown, 6명 간 다양성, 재현 seed를 검증한다.
- 지연시간, 요청 빈도, 오디오 chunk 규격, timeout, 재연결, 중복/누락 step 처리의 허용 기준을 측정한다.
- 발견된 문제는 앞 단계의 코드·테스트·매핑에 반영한 뒤 동일 시나리오를 재검증한다.

산출물:

- Unity 연동 시나리오별 결과 및 잔여 제약 목록
- 프로토타입 승인 체크리스트

완료 기준:

- Unity에서 6명 청중의 상태 변화와 레이어 명령이 의도대로 재생되고, 알려진 제한이 문서화되며, 중대한 계약 불일치가 없어야 한다.

### 15단계. 최종 작업 문서 생성

이 단계는 계획의 **가장 마지막 단계**로 수행하며, 아래 두 파일을 반드시 생성한다.

1. `work_summary.md`
   - 파이프라인 개발을 위해 수행한 전체 작업을 단계 순서대로 요약한다.
   - 변경 파일, 구현한 계산/선택 규칙, API 변경, 테스트 결과, 외부 서비스 설정, 알려진 제한과 후속 과제를 정리한다.
   - 문서에 비밀값, 개인정보, 원본 음성·발표 내용은 포함하지 않는다.
2. `unity_spec.md`
   - Unity 개발자에게 전달할 AI 파이프라인 연동 요구사항 및 구현 명세서를 작성한다.
   - endpoint, 인증, 요청 주기, multipart/JSON 필드, enum, 단위, 필수/선택값, 6명 agent/profile/state 구조, Core/Action 선택 결과, 레이어별 명령, `sync_group`, timing, blend/충돌 규칙, cooldown, 오류 코드, 재시도·재연결, 예제 요청/응답, 버전 호환 정책을 포함한다.
   - Unity `action_id`/Animator/BlendShape/GazeHead 매핑표와 통합 확인 체크리스트를 포함한다.

완료 기준:

- `work_summary.md`와 `unity_spec.md`가 모두 저장소 루트에 존재하고 실제 최종 코드/API/테스트 결과와 일치해야 한다.
- 두 문서의 파일 경로, 예제 payload, enum 및 ID를 코드와 대조하고, Unity 개발자가 별도 구두 설명 없이 연동을 시작할 수 있어야 한다.
