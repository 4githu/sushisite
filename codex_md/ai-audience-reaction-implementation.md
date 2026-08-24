# AI 청중 상태 및 백채널 반응 구현 구조와 명세 대조 결과

> 기준 문서: [`reaction-rule.md`](./reaction-rule.md) v0.1  
> 조사 대상: `sushi-fast/odi/EVC`의 현재 v2 구현  
> 조사일: 2026-08-25

## 1. 결론

현재 구현은 `reaction-rule.md`의 핵심 설계를 대부분 코드로 옮겼다. 6명의 개별 청중, E/V/C 상태 초기화와 갱신, 우세축과 근사 동률 판정, Core/Action 후보 분리, 상태·시점·쿨다운 필터, 성향을 반영한 확률 선택, Face/Body/GazeHead 명령 분해가 모두 연결되어 있다.

정적 코드와 데이터 대조에서 확인되었던 발화 위치 차이는 해결되어, **백엔드 규칙 엔진은 현재 확인 범위에서 명세와 일치한다.** 다만 전체 XR 구현까지 완벽하다고 판정하려면 다음 외부 검증이 남아 있다.

1. 이 저장소는 Unity가 실행할 명령을 생성할 뿐 실제 Unity 컨트롤러, Animator/BlendShape 자산, 액션 ID 바인딩을 포함하지 않는다. 따라서 실제 표정·몸·시선 재생의 완전성은 이 코드만으로 증명할 수 없다.
2. `odi/EVC/service.py`와 `odi/EVC/EVCv1`에는 레거시 구현이 남아 있다. 현재 FastAPI 라우터는 v2 `pipeline.py`를 사용하므로 운영 경로에는 포함되지 않지만, 처음 보는 개발자가 현재 구현으로 오인할 위험이 있다.

따라서 현재 상태는 **“핵심 백엔드 설계와 명세의 정적 일치 및 전체 자동 테스트 통과 확인, Unity 실재생 검증 미완료”**로 보는 것이 정확하다.

## 2. 처음 보는 사람을 위한 한 장 요약

이 시스템은 평가 점수로 애니메이션 하나를 곧바로 고르지 않는다. 먼저 발표 구간을 평가하여 각 청중의 심리 상태에 해당하는 세 수치를 갱신하고, 그 상태에 맞는 행동 후보를 좁힌 뒤, 각 청중의 성향과 최근 이력을 반영해 확률적으로 행동을 고른다.

```text
발표 음성/슬라이드/시선 정보
        │
        ▼
STT + 발표 내용(M)·전달(D) 평가
        │
        ▼
공통 변화량 ΔE, ΔV, ΔC 계산
        │
        ▼
6명 각각의 E/V/C 상태 갱신
        │
        ▼
우세축(E/V/C)·방향(+/-) 결정
        │
        ├── Core 후보: 평상시 지속되는 청취 반응
        └── Action 후보: 특정 사건에서 잠깐 겹치는 행동
                    │
                    ▼
상태·발화 위치·장면·쿨다운 필터
                    │
                    ▼
성향·채널 선호·이력·반복을 점수화 → Softmax → 확률 선택
                    │
                    ▼
Face / Body / GazeHead별 UnityCommand 생성
```

핵심 구분은 다음과 같다.

| 개념 | 의미 |
| --- | --- |
| E (Engagement) | 발표에 얼마나 집중하고 있는지. `-1`은 이탈, `+1`은 몰입에 가깝다. |
| V (Evaluative Valence) | 발표를 얼마나 부정적/긍정적으로 평가하는지. |
| C (Cognitive Clarity) | 내용을 얼마나 혼란스럽게/명확하게 이해하는지. |
| Core Behavior | 현재 상태를 지속적으로 표현하는 기본 반응. 예: 안정적 청취, 회의적 관찰. |
| Action Clip | 사건이 발생했을 때 Core 위에 잠깐 얹는 행동. 예: 타이핑, 자세 조정. |
| variation | 같은 행동군 안의 실제 표현 방식. 확률 선택의 실제 단위이다. |

## 3. 실제 요청부터 출력까지

### 3.1. 세션 시작

클라이언트는 `POST /odi/xreal_rehear/evc/smart-start`로 발표 제목, 주제 관심도, 사전 지식, 선택적으로 슬라이드와 seed를 보낸다.

`router.py`가 입력을 검증하고 `pipeline.create_pipeline_session()`을 호출한다. `session_store.py`는 세션 토큰과 seed를 만들고 `state_engine.initialize_audiences()`로 정확히 6명의 청중을 생성한다.

초기 상태는 명세의 수식을 그대로 사용한다.

```text
E_initial = (topic_interest - 0.50) × 2
C_initial = (prior_knowledge - 0.50) × 2
V_initial = 0

각 청중:
E_i,0 = E_initial + random(-0.05, +0.05)
C_i,0 = C_initial + random(-0.05, +0.05)
V_i,0 = 0
```

각 청중은 상태 외에도 `responsiveness`, `expressivity`, `critical_bias`, 채널 선호도, 좌석, 노트북 보유 여부를 갖는다. 이 행동 성향은 E/V/C를 바꾸지 않고 나중의 행동 선택 확률에만 사용된다. seed가 같으면 프로파일과 이후 확률 선택도 재현 가능하다.

### 3.2. 발표 구간 업데이트

클라이언트는 `POST /odi/xreal_rehear/evc/update`에 음성과 현재 문맥을 보낸다. 중요한 문맥 값은 다음과 같다.

- `utterance_position`: 발화 중, 발화 경계, 침묵/휴지, 슬라이드 전환
- `slide_reference`: 현재 발화가 슬라이드를 참조하는지
- `event_signals`: 정보 밀도, 긴장, 주변 상호작용 등의 사건 강도
- `client_time_s`: 쿨다운과 출력 시작 시점의 기준 시간
- `request_id`, `expected_step`: 중복 처리와 순서 충돌 방지

`pipeline.update_pipeline()`의 처리 순서는 다음과 같다.

1. 세션 토큰, 요청 중복, step, 시간 역행을 검사한다.
2. 음성을 STT로 변환한다.
3. 발표 내용과 전달 방식을 평가한다.
4. 공통 E/V/C 변화량을 계산한다.
5. 6명 각각의 상태를 갱신한다.
6. 각 청중별 Core/Action 후보를 구성하고 행동을 선택한다.
7. 선택 결과를 Unity 레이어 명령으로 분해한다.
8. 모든 응답 모델이 만들어진 뒤에만 상태와 RNG를 세션에 반영한다.

STT나 평가 제공자에서 오류가 나면 복제본만 버리고 원래 세션은 변경하지 않는다. 동일한 `request_id`는 캐시된 동일 응답을 반환한다.

### 3.3. 발표 평가를 E/V/C 변화량으로 변환

`evaluation.py`는 STT, 음성 지표, 슬라이드 문맥을 조합하여 명세의 `M_t`와 `D_t` 형태를 만든다. `state_engine.compute_state_delta()`는 다음 가중치를 적용한다.

```text
내용 기반:
ΔE_M = clamp(0.50×Org + 0.50×Msg)
ΔV_M = clamp(1.00×Sup + 1.00×CER)
ΔC_M = clamp(1.00×Org + 0.50×Sup + 1.00×Msg + 0.50×CER)

전달 기반:
ΔE_D = clamp(0.50×Lang + 1.00×Voc + 1.00×Gaze)
ΔV_D = clamp(0.50×Voc + 0.50×Gaze + 0.50×Align)
ΔC_D = clamp(1.00×Lang + 1.00×Align)

통합:
ΔE = 0.45×ΔE_M + 0.55×ΔE_D
ΔV = 0.55×ΔV_M + 0.45×ΔV_D
ΔC = 0.50×ΔC_M + 0.50×ΔC_D
```

중요한 점은 내용 변화량과 전달 변화량을 각각 먼저 `[-1, 1]`로 제한한 뒤 통합한다는 것이다.

### 3.4. 청중별 상태 갱신

공통 변화량의 방향은 발표 평가가 결정한다. 주제 관심도와 사전 지식은 감소폭만 조절한다.

| 설정 | 음수 변화 민감도 |
| --- | ---: |
| 낮음 (`0.25`) | `1.20` |
| 중간 (`0.50`) | `1.00` |
| 높음 (`0.75`) | `0.80` |

```text
E_next = E_current + (ΔE가 음수면 관심도 민감도, 아니면 1.0) × ΔE
V_next = V_current + ΔV
C_next = C_current + (ΔC가 음수면 사전 지식 민감도, 아니면 1.0) × ΔC
```

`AudienceState` 모델이 생성될 때 각 축을 자동으로 `[-1, 1]`에 제한한다. V에는 사용자 사전 설정이나 행동 성향이 개입하지 않는다.

### 3.5. 상태 수준과 우세축

`behavior_engine.classify_level()`의 경계는 다음과 같다.

| 범위 | 코드 수준 |
| --- | --- |
| `E/V/C <= -0.34` | `low` |
| `-0.34 < E/V/C < 0.34` | `mid` |
| `E/V/C >= 0.34` | `high` |

세 축이 모두 `mid`면 우세축 없이 `Baseline Listening`을 사용한다. 그 외에는 절댓값이 큰 축을 고르며 1, 2위 차이가 `0.10` 이하면 근사 동률이다. 동률 우선순위도 명세와 같다.

```text
음수 C → 음수 V → 음수 E → 직전 우세축 → E → C → V
```

우세축은 행동군으로 연결된다.

| 우세축 | 행동군 |
| --- | --- |
| 없음 | Baseline Listening |
| E | Attentive Listening |
| V | Evaluative Monitoring |
| C | Comprehension Tracking |

### 3.6. Core 후보와 Action 후보

`clip_pool.json`은 코드에서 선택 가능한 데이터 카탈로그다. 현재 Core variation 44개와 Action variation 8개, 총 52개를 담고 있다. `clip_pool.py`는 개수, ID 형식, 중복, 레이어 매핑을 검증한다.

Core 후보는 다음 조건을 모두 통과해야 한다.

- 우세축에 해당하는 `parent_group`
- 현재 E/V/C 수준과 방향
- 현재 발화 위치
- 필요한 경우 슬라이드 참조 여부
- variation별 쿨다운

상태에 맞는 Core가 없으면 같은 발화 위치에서 안전한 Baseline 후보를 한 번 찾는다. 그것도 없으면 Core는 `null`이 된다. 이 fallback은 런타임 안전장치이며 명세의 집합식에 명시된 동작은 아니다.

Action 후보는 Core와 별도로 다음을 검사한다.

- 사건 신호가 실제로 발생했는지
- 상태 gate
- 발화 위치와 슬라이드 참조
- 노트북, 좌석, 허용 agent 같은 장면 gate
- 쿨다운

사건 신호 일부는 서버도 유도한다. 예를 들어 45단어 이상 또는 긴 슬라이드는 `information_dense`, E가 연속 두 번 낮으면 `repeated_disengagement`, 마지막 Body 명령 후 12초가 지나면 `long_static_posture`가 된다. 클라이언트 신호와 서버 유도 신호 중 큰 값을 사용한다.

### 3.7. 후보 점수와 확률 선택

Core 점수는 명세의 다섯 항을 구체적인 계수로 구현한다.

```text
score_core =
    2.00 × state_fit
  + 1.00 × preference
  + 0.75 × channel_preference
  + 0.50 × history
  - 1.25 × repetition
```

`preference`는 반응성 50%, 표현성 적합도 50%를 사용한다. 비판적 variation이고 V가 `0.33` 이하일 때만 `critical_bias` 보정이 들어가므로, critical bias가 긍정 상태를 부정 반응으로 뒤집지는 않는다.

점수는 Softmax 확률로 바뀌고 seed 기반 RNG의 categorical sampling으로 하나를 고른다. transient Core는 반응성에 따른 추가 출력 gate를 거치며, 실패하면 가능한 stable 후보로 대체하거나 no-op이 된다.

Action도 상태 적합도, 사건 강도, 채널 선호, 반응성, 반복을 점수화해 하나를 샘플링한 뒤 별도의 삽입 확률 gate를 통과할 때만 Core 위에 얹는다.

같은 순간 6명이 같은 Core variation을 수행하는 현상을 줄이기 위해 동일 variation은 최대 3명으로 제한한다. 포화되면 확률이 가장 높은 다른 후보로 바꾸고, 대안이 없으면 해당 청중은 Core no-op 처리된다. 이 역시 자연스러운 군중 표현을 위한 구현 확장이다.

### 3.8. Unity 출력 명령

선택 단위는 `behavior_id`와 `variation_id`이고, `command_builder.py`가 이를 실제 레이어 명령으로 분해한다.

```text
Core 선택 + optional Action 선택
    ├── Face 명령
    ├── Body 명령
    └── GazeHead 명령
```

한 variation에서 분해된 명령은 같은 `sync_group`을 공유한다. Core priority는 `50`, Action priority는 `100`이다. 시작 시점은 현재 발화 위치에 따라 수락 시간 뒤 `0.05`초 또는 `0.10`초로 조정된다. 모든 명령은 다음 정보를 가진다.

- `agent_id`, `start_time`
- `layer`, `action_id`, `duration`
- `sync_group`
- `selected_behavior_id`, `selected_variation_id`
- `priority`, `blend_mode`, `intensity`

현재 `intensity`는 같은 action의 재생 파라미터를 청중마다 다르게 만들지 않기 위해 항상 `1.0`이다. 표현성은 클립 자체의 강도를 바꾸는 대신 variation 선택 점수에만 반영된다.

## 4. 파일별 책임

| 파일 | 역할 |
| --- | --- |
| `sushi-fast/main.py` | FastAPI 앱에 ODI 라우터를 연결한다. |
| `sushi-fast/odi/EVC/router.py` | HTTP form/header를 검증하고 v2 파이프라인을 호출한다. |
| `schema.py` | API, 상태, 프로파일, 클립, Unity 명령의 Pydantic 계약이다. |
| `inputs.py` | 설정값, 업로드, 슬라이드, 이벤트 문맥을 정규화한다. |
| `speech2text.py` | 음성 제공자를 호출하고 공통 STT 결과로 변환한다. |
| `evaluation.py` | 음성 지표를 만들고 내용/전달 평가를 조립한다. |
| `state_engine.py` | 6명 초기화, 평가→상태 변화량, 민감도, 상태 갱신을 담당한다. |
| `clip_pool.json` | 52개 reaction variation의 조건과 Unity action 매핑 원본이다. |
| `clip_pool.py` | 카탈로그를 로드하고 구조와 개수를 검증한다. |
| `behavior_engine.py` | 우세축, 후보 필터, 점수, Softmax, sampling, 이력을 담당한다. |
| `command_builder.py` | 선택된 variation을 레이어별 Unity 명령으로 분해한다. |
| `session_store.py` | 6명 상태, RNG, 이력, 토큰, TTL, lock을 보관한다. |
| `pipeline.py` | 위 계산 단계를 순서대로 연결하고 원자적으로 commit한다. |
| `tests/` | 상태 수식, 후보, 선택, 카탈로그, API, 보안, 다양성, rehearsal 흐름을 검증한다. |
| `service.py`, `EVCv1/` | 호환/레거시 코드. 현재 `router.py`의 v2 업데이트 경로가 아니다. |

## 5. `reaction-rule.md` 대조표

| 명세 영역 | 판정 | 구현 근거와 비고 |
| --- | --- | --- |
| E/V/C 연속 상태와 `[-1, 1]` 제한 | 일치 | `AudienceState` validator가 모든 생성 시 clamp한다. |
| 6명 고정 청중 | 일치 | `AUDIENCE_LAYOUT`이 `audience_01`~`06`으로 고정되어 있다. |
| 관심도/사전 지식 초기값 | 일치 | `(setting - 0.5) × 2`, E/C 오프셋 `±0.05`, V=0이다. |
| 감소 민감도 1.2/1.0/0.8 | 일치 | E와 C의 음수 delta에만 적용한다. |
| 내용/전달 가중치와 통합식 | 일치 | 명세 6.1~6.3의 수식과 같다. |
| Low/Mid/High 경계 | 일치 | `<= -0.34`, `>= 0.34`, 나머지 mid이다. |
| 우세축, 방향, tie `0.10` | 일치 | 음수 C/V/E, 직전축, E/C/V 순서를 구현한다. |
| Core/Action 후보 분리 | 일치 | 별도 후보 집합과 별도 선택/이력을 사용한다. |
| 상태·발화 위치·쿨다운 필터 | 일치 | 두 AL_01 variation도 명세대로 발화 경계 전용이다. |
| 프로파일은 행동 선택에만 사용 | 일치 | 상태 갱신에는 행동 성향을 읽지 않는다. |
| Softmax + categorical 선택 | 일치 | 수치 안정화된 Softmax와 seed 기반 sampling을 사용한다. |
| Core 44 + Action 8 | 일치 | 로더가 정확한 개수를 강제한다. |
| 노트북/뒷줄 장면 gate | 일치 | ACT_01은 노트북 필수, ACT_08은 뒷줄 05/06으로 제한한다. |
| Face/Body/GazeHead 명령 분해 | 일치 | 레이어별 action, sync group, duration 등을 생성한다. |
| Core + optional Action overlay | 일치 | Action은 priority 100으로 Core 50 위에 전달된다. |
| 실제 Unity 재생 | 확인 불가 | 이 저장소에는 명령 소비 측 Unity 구현과 자산이 없다. |

## 6. 명세 차이 해결 및 구현 확장

### 6.1. 해결됨: AL_01 발화 위치 통일

`reaction-rule.md`는 아래 두 variation을 `Utterance boundary`로 정의한다.

- `AL_01.active_following`
- `AL_01.agreement_nod`

`clip_pool.json`의 두 variation을 `utterance_boundary` 전용으로 수정하여 명세와 통일했다. 발화 중에는 `AL_01.stable_attention`만 후보가 되며, 발화 경계에서만 아래 두 variation이 후보가 된다.

관련 후보 필터 테스트와 다양성 제한 테스트도 발화 경계 문맥을 사용하도록 수정했다. 이 항목은 더 이상 미해결 명세 차이가 아니다.

### 6.2. 안전·자연스러움용 구현 확장

다음은 명세를 깨는 오류라기보다 명세에 수치가 없거나 동작이 명시되지 않은 부분을 구체화한 것이다.

- 후보가 비면 발화 위치를 지키는 Baseline fallback을 시도한다.
- transient Core에 별도 출력 확률 gate를 둔다.
- Action에 별도 삽입 확률 gate를 둔다.
- 한 step에 같은 variation을 최대 3명까지만 허용한다.
- 서버가 정보 밀도, 연속 이탈, 저각성, 장시간 정적, 긴장 사건을 유도한다.
- 출력 start offset과 Core/Action priority를 정했다.

이 값들은 사용자 경험에 영향을 주므로 향후 `reaction-rule.md`의 구현 상수 부록으로 승격하면 코드와 명세의 추적성이 좋아진다.

### 6.3. 저장소 범위 밖의 Unity 검증

`clip_pool.json`에는 `body.stable_attention`, `face.approving_smile`, `gaze_head.neutral_listening` 같은 논리적 action ID가 있다. Pydantic은 이름 형식과 레이어 일치 여부까지 검증하지만 다음은 확인하지 못한다.

- Unity 프로젝트에 동일 ID의 Animator state/clip/BlendShape가 실제로 존재하는가
- `sync_group`, `priority`, `blend_mode`를 Unity 수신기가 올바르게 해석하는가
- Action이 Core와 겹칠 때 Body/Face/GazeHead 충돌이 의도대로 해결되는가
- duration과 start time이 실제 프레임에서 지켜지는가

따라서 백엔드 명령 생성 완료와 XR에서의 백채널 완성은 구분해야 한다.

## 7. 테스트 현황과 신뢰 범위

테스트 파일은 다음 범위를 다룬다.

- 초기 6명, seed 재현성, 오프셋과 행동 성향 범위
- E/V/C 수식, 민감도, clamp, 행동 성향과 상태의 독립성
- 경계값과 우세축/tie 우선순위
- Core/Action 후보와 쿨다운·장면 gate
- Softmax, 확률 sampling, critical bias, 반복/이력
- 52개 카탈로그와 Unity 레이어 매핑
- 명령 분해, 우선순위, sync group
- API 인증, idempotency, step/time 충돌, 실패 시 rollback
- 6명 다양성과 rehearsal 형태의 통합 흐름

2026-08-25에 Python 3.13.15와 저장소 전용 `.venv`를 구성한 뒤 전체 EVC 테스트를 실행했다. 사용자 Temp 폴더의 접근 제한을 피하기 위해 pytest 임시 폴더는 저장소 내부로 지정하고 캐시 플러그인은 비활성화했다.

```text
77 passed in 1.50s
```

실행 명령은 다음과 같다.

```powershell
.\.venv\Scripts\python.exe -m pytest odi\EVC\tests -q -p no:cacheprovider --basetemp=.pytest_tmp
```

이 테스트들은 STT와 평가 provider를 모의 객체로 대체하므로 API 키나 외부 네트워크 상태에 영향을 받지 않는다. 즉 **백엔드 규칙·API 계약·headless Unity 소비 흐름의 자동 테스트 통과**를 확인한 것이며, 실제 OpenAI/Deepgram 요청 성공이나 Unity 자산 재생까지 증명하는 것은 아니다.

개발 환경이 준비된 곳에서는 다음 명령으로 재검증한다.

```powershell
python -m pip install -r requirements-evc.txt -r requirements-evc-dev.txt
python -m pytest odi/EVC/tests -q
```

외부 STT/LLM을 쓰는 실제 통합 검증과 Unity 재생 검증은 별도로 수행해야 한다.

## 8. 유지보수 시 확인 순서

반응 규칙을 바꿀 때는 다음 순서로 보는 것이 안전하다.

1. `reaction-rule.md`에서 상태 조건, 발화 위치, 채널, 쿨다운을 결정한다.
2. `clip_pool.json`의 해당 variation 메타데이터와 Unity action 매핑을 수정한다.
3. 새 필드나 enum이 필요하면 `schema.py` 계약을 먼저 바꾼다.
4. 후보 규칙은 `behavior_engine.py`, 상태 수식은 `state_engine.py`에서만 수정한다.
5. `command_builder.py`에서 Unity 명령 의미가 유지되는지 확인한다.
6. 경계값, 후보 포함/제외, 확률 특성, API 통합 테스트를 함께 수정한다.
7. 동일 action ID가 Unity 자산과 실제로 연결되는지 rehearsal에서 확인한다.

특히 `service.py`나 `EVCv1`을 수정해도 현재 v2 API 동작은 바뀌지 않는다. 운영 경로를 변경하려면 `router.py → pipeline.py` 의존 흐름을 기준으로 작업해야 한다.

## 9. 최종 판정 체크리스트

- [x] 명세의 핵심 E/V/C 상태 모델 구현
- [x] 명세의 평가 가중치와 민감도 구현
- [x] 6명 개별 상태·성향·이력 구현
- [x] 우세축·동률·행동군 구현
- [x] Core 44개와 Action 8개 데이터화
- [x] 확률 선택과 Core/Action 결합 구현
- [x] Face/Body/GazeHead 출력 명령 구현
- [x] 두 AL_01 variation의 발화 위치를 명세에 맞춰 통일
- [x] 현재 환경에서 전체 테스트 실행 및 통과 확인 (`77 passed`)
- [ ] Unity action ID와 실제 자산 바인딩 검증
- [ ] XR 런타임에서 레이어 동기화·충돌·타이밍 검증

알려진 백엔드 명세 차이는 해결되었고 전체 자동 테스트도 통과했다. 남은 두 Unity 항목이 해결되기 전에는 전체 XR 시스템이 완벽하게 구현됐다고 단정하기보다 “백엔드 규칙 엔진은 명세와 일치하고 자동 테스트를 통과했으며, Unity 통합 검증이 남아 있다”고 표현하는 것이 정확하다.
