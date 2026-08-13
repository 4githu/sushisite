# AI 청중 상태 및 백채널 반응 구현 명세서 v0.1

## 1. 문서 목적
* 본 문서는 XR 발표 훈련 환경에서 AI 청중 에이전트의 상태와 백채널 반응을 구현하기 위한 개발 명세서이다.
* 본 명세서는 발표자의 내용 및 전달 수행을 기반으로 AI 청중의 E/V/C 상태를 산출하고, 산출된 상태를 시선, 표정, 고개 움직임, 자세 변화로 구성된 비언어적 백채널 반응으로 전환하는 구현 기준을 정의한다.

## 2. 프로토타입 1차 구현 범위
* 프로토타입에서는 전체 AI 청중 상태 모델을 모두 정교하게 구현하기보다, 발표 훈련 흐름과 청중 반응 출력 구조를 검증하기 위한 핵심 항목을 우선 구현한다. 
* **프로토타입 구현 범위**
    1. **상태 모델**: Engagement, Evaluative Valence, Cognitive Clarity
    2. **상태값 형식**: 각 청중 에이전트는 `A_i,t = (E_i,t, V_i,t, C_i,t)` 형태의 상태 벡터를 가짐
    3. **상태값 범위**: 각 상태값은 `-1.00` ~ `+1.00` 범위의 float 값으로 관리
    4. **초기 상태값**: 발표 시작 시 각 청중 에이전트는 `A_i,0 = (E_i,0, V_i,0, C_i,0)`의 상태값을 가지며, 기본값은 청중 사전 설정값 `P_i`와 개별 편차에 따라 설정한다. `V_i,0`은 `0.00`을 기본으로 하되, `E_i,0`과 `C_i,0`은 주제 관심도와 사전 지식 수준에 따라 달라진다.
    5. **상태 해석 기준**: `-1.00` ~ `-0.34`는 부정 방향, `-0.33` ~ `+0.33`은 중립 범위, `+0.34` ~ `+1.00`은 긍정 방향으로 해석
    6. **Engagement 의미**: `-1.00`에 가까울수록 주의 이탈, `+1.00`에 가까울수록 주의 집중
    7. **Evaluative Valence 의미**: `-1.00`에 가까울수록 부정적 평가, `+1.00`에 가까울수록 긍정적 평가
    8. **Cognitive Clarity 의미**: `-1.00`에 가까울수록 혼란 또는 이해 부족, `+1.00`에 가까울수록 명료한 이해
    9. **백채널 구현 단위**: 상태값에 따라 선택되는 Face 출력, Body Animation Clip, Gaze/Head 제어
    10. **Face 출력**: 표정 반응을 위한 BlendShape 또는 Facial Animation
    11. **Body 출력**: 고개 움직임, 상체 반응, 자세 변화를 포함하는 Body Animation Clip
    12. **Gaze/Head 제어**: 발표자, 발표자료, 주변 방향을 바라보는 시선 및 머리 방향 제어
    13. **반응 방식**: 각 에이전트의 E/V/C 상태값은 최종 클립을 직접 결정하지 않는다. 상태값은 상위 행동군 `G_i,t`와 Core Behavior 후보 집합 `C_core_i,t`를 구성하는 기준으로 사용된다. 사건 조건이 발생한 경우에는 별도의 Action Clip 후보 집합 `C_action_i,t`를 구성한다. 최종 백채널 출력 `O_i,t`는 `C_core_i,t`에서 선택된 `B_core_i,t`를 기본으로 하며, `C_action_i,t`가 조건을 만족할 경우 `B_action_i,t`를 Core Behavior 위에 일시적으로 블렌딩한다.
* 본 프로토타입에서 AI 청중 상태는 `-1.00` ~ `+1.00` 범위의 연속 수치값으로 관리한다. 
* Low/Mid/High는 백채널 반응을 선택하기 위한 해석 구간으로 사용한다. 
* Unity 구현에서는 각 청중 에이전트가 Engagement, EvaluativeValence, CognitiveClarity의 세 float 값을 가지며, 이 값의 범위와 방향에 따라 Face 출력, Body Animation Clip, Gaze/Head 제어를 결정한다.

## 3. 시스템 처리 흐름

### 3.1. 생성 흐름
AI 청중 상태 및 백채널 반응 생성 흐름은 다음과 같이 구성한다.
1. 발표자 입력 수집
2. 발표 음성 STT 변환
3. 발표 내용 및 전달 평가
4. E/V/C 청중 상태 산출
5. 개별 청중 상태 갱신
6. 우세 축 및 방향 판별
7. 상위 행동군 `G_i,t` 결정
8. Core 후보 집합 `C_core_i,t` 및 Action 후보 집합 `C_action_i,t` 구성
9. 후보별 선택 점수 `z_core_i,t(b)` 및 선택 확률 `π_core_i,t(b)` 계산
10. 확률적 Core Behavior `B_core_i,t` 선택, optional Action Clip `B_action_i,t` 선택
11. Gaze/Head 목표 및 출력 시점 조정
12. Face, Body, Gaze/Head 출력 명령 `O_i,t` 실행

### 3.2. 처리 흐름 세부
1. **발표 입력 수집**
   * **입력**: 음성, 시선, 발표자료
   * **처리**: 발표 수행 데이터 수집
   * **출력**: Raw Input
2. **STT 변환**
   * **입력**: 음성 데이터
   * **처리**: 음성을 텍스트로 변환
   * **출력**: STT Text
3. **발표 평가**
   * **입력**: STT Text, 발표자료
   * **처리**: 전달 평가, 내용 평가
   * **출력**: `M_t`, `D_t`
4. **상태 산출**
   * **입력**: `M_t`, `D_t`, 청중 설정값
   * **처리**: E・V・C 상태 계산
   * **출력**: `A_i,t`
5. **행동 계획**
   * **입력**: `A_i,t`, `P_i`, `H_i,t`, Clip Pool `L`
   * **처리**: 우세 축 및 방향 판별 → `G_i,t` 결정 → `C_core_i,t` 구성 → `C_action_i,t` 구성 → `z_core_i,t(b)`, `π_core_i,t(b)` 계산 → `B_core_i,t` 선택 → optional `B_action_i,t` 선택 → 최종 백채널 출력 `O_i,t`
   * **출력**: `π_core_i,t`, `B_core_i,t`, optional `B_action_i,t`
6. **행동 출력**
   * **입력**: `B_core_i,t`, optional `B_action_i,t`
   * **처리**: 애니메이션 및 시선 제어 실행
   * **출력**: `O_i,t`

## 4. 청중 상태 모델

AI 청중 에이전트의 상태는 E・V・C 세 차원으로 구성한다.

### 4.1. 상태 차원 정의

| 상태 차원 | 의미 | 낮은 상태 | 높은 상태 |
| :--- | :--- | :--- | :--- |
| **Engagement** | 청중이 발표 상황과 발표자에게 주의를 기울이며 청취를 지속하려는 정도 | 무관심, 이탈 | 집중, 몰입 |
| **Evaluative Valence** | 청중이 발표 내용 또는 발표 수행을 긍정적 또는 부정적으로 평가하는 방향성 | 부정적 평가 | 긍정적 평가 |
| **Cognitive Clarity** | 청중이 발표 내용의 구조와 의미를 명확히 파악하는 정도 | 혼란, 불명확 | 이해, 명료 |

### 4.2. 상태값 구성

각 청중 에이전트는 다음 상태값을 가진다.

$$A_{i,t} = (E_{i,t}, V_{i,t}, C_{i,t})$$

| 변수 | 설명 |
| :--- | :--- |
| $i$ | 개별 청중 에이전트 ID |
| $t$ | 현재 평가 시점 |
| $E_{i,t}$ | $i$번째 청중의 Engagement 값 |
| $V_{i,t}$ | $i$번째 청중의 Evaluative Valence 값 |
| $C_{i,t}$ | $i$번째 청중의 Cognitive Clarity 값 |

### 4.3. 상태값 범위 및 해석

상태값은 **-1.00**에서 **+1.00** 범위로 관리한다.

| 값 범위 | 상태 수준 |
| :--- | :--- |
| -1.00 ~ -0.34 | 낮음 |
| -0.33 ~ +0.33 | 중간 |
| +0.34 ~ +1.00 | 높음 |

```markdown
## 5. 청중 사전 설정값 및 에이전트 프로파일

### 5.1. 사용자 설정값

프로토타입에서 사용자가 설정하는 청중 사전 설정값은 **주제 관심도(Topic Interest)**와 **사전 지식 수준(Prior Knowledge)** 두 가지이다.

이 두 값은 청중 반응을 직접 결정하는 값이 아니라, 청중 에이전트의 초기 상태와 상태 갱신 민감도를 조절하는 배경 조건으로 사용한다. 발표 중 실제 청중 상태 변화는 발표자의 내용 평가 및 전달 평가 결과를 중심으로 갱신된다. 
즉, 사용자가 설정한 값은 청중이 처음부터 얼마나 발표에 주의를 기울일 가능성이 있는지, 발표 내용이 불명확해졌을 때 얼마나 빠르게 주의나 이해가 저하되는지를 조절할 뿐 긍/부정적 평가를 직접 결정하지는 않는다.

**[주제 관심도 설정에 따른 역할]**

| UI 선택값 | 시스템 입력값 | 직접 영향 (초기 상태 및 민감도) | 간접 영향 (발표 중 반응 양상) |
| :--- | :--- | :--- | :--- |
| **낮음** | 0.25 | 초기 Engagement를 낮게 설정, Engagement 유지력 저하 | 발표 흐름이 약하거나 전달이 불안정할 때 주의 이탈 상태로 전환될 가능성 상승 |
| **중간** | 0.50 | 초기 Engagement와 감소 민감도를 기본값으로 설정 | 기본적인 주의 유지 흐름을 따름 |
| **높음** | 0.75 | 초기 Engagement를 높게 설정, Engagement 감소폭 완화 | 발표 흐름이 일시적으로 약해져도 주의 유지 가능성이 상대적으로 높음 |

**[사전 지식 수준 설정에 따른 역할]**

| UI 선택값 | 시스템 입력값 | 직접 영향 (초기 상태 및 민감도) | 간접 영향 (발표 중 반응 양상) |
| :--- | :--- | :--- | :--- |
| **낮음** | 0.25 | 초기 Cognitive Clarity를 낮게 설정, 불명확한 설명에 민감하게 반응 | 설명이 불명확하거나 논리 연결이 약할 때 이해 저하가 빠르게 나타남 |
| **중간** | 0.50 | 초기 Cognitive Clarity와 감소 민감도를 기본값으로 설정 | 기본적인 이해 흐름을 따름 |
| **높음** | 0.75 | 초기 Cognitive Clarity를 높게 설정, 감소폭 완화 | 복잡하거나 불완전한 설명에서도 이해 저하가 상대적으로 완만하게 나타남 |

* **청중 규모:** 프로토타입에서 6명으로 고정한다.
* **적용 범위:** 사용자가 설정한 두 값은 세션 공통 조건으로 적용된다.
* **개별 편차:** 6명의 청중이 동일하게 반응하지 않도록, 각 에이전트에는 제한적인 초기 상태 오프셋과 개별 행동 성향값이 부여된다. 이는 보조적 구현 장치일 뿐 상태를 임의로 결정하지 않는다.

---

### 5.2. 사용자 사전 설정값의 상태 적용 규칙

사용자 사전 설정값은 세 상태 차원(E, V, C)에 동일하게 적용되지 않는다.
* **주제 관심도** $\rightarrow$ Engagement에만 직접 적용
* **사전 지식 수준** $\rightarrow$ Cognitive Clarity에만 직접 적용
* **Evaluative Valence** $\rightarrow$ 사용자 사전 설정값으로 직접 결정하지 않음 (평가 결과에 따라 갱신)

**[상태값 적용 방식]**

| 상태값 | 적용 방식 |
| :--- | :--- |
| **초기 Engagement** | `E_initial = (TopicInterest - 0.50) * 2` |
| **Engagement 감소 민감도** | 주제 관심도가 낮을수록 감소폭을 크게, 높을수록 감소폭을 완화 |
| **초기 Cognitive Clarity** | `C_initial = (PriorKnowledge - 0.50) * 2` |
| **Cognitive Clarity 감소 민감도**| 사전 지식 수준이 낮을수록 감소폭을 크게, 높을수록 감소폭을 완화 |
| **초기 Evaluative Valence** | `V_initial = 0.00` 으로 고정 |
| **Evaluative Valence 갱신** | 사전 설정값의 영향을 받지 않으며, 발표 내용 및 전달 수행 평가 결과로만 갱신 |

**[UI 선택값의 내부 수치 및 초기 상태값 변환]**

| UI 상태값 | 내부 수치 | 초기 상태값 (E, C) |
| :--- | :--- | :--- |
| 낮음 | 0.25 | -0.50 |
| 중간 | 0.50 | 0.00 |
| 높음 | 0.75 | +0.50 |

---

### 5.3. 상태 갱신 민감도 적용 규칙

상태 갱신 민감도는 발표 평가로 산출된 상태 변화량(`ΔE`, `ΔC`)이 각 청중에게 얼마나 크게 반영되는지를 조절하는 계수이다. 
* 상태 변화의 **방향**은 오직 발표 수행 평가값에 의해 결정된다.
* 설정값이 높다고 해서 증가폭을 추가로 증폭시키지 않으며, 오직 **감소할 때의 감소폭(민감도)**에만 영향을 준다.

**[감소 민감도 계수]**

| UI 선택값 | 감소 민감도 계수 |
| :--- | :--- |
| 낮음 | 1.20 |
| 중간 | 1.00 |
| 높음 | 0.80 |

**1. Engagement 갱신 로직**
```text
if ΔE >= 0:
    E_next = E_current + ΔE
if ΔE < 0:
    E_next = E_current + (ΔE * EngagementSensitivity)

```

**2. Cognitive Clarity 갱신 로직**

```text
if ΔC >= 0:
    C_next = C_current + ΔC
if ΔC < 0:
    C_next = C_current + (ΔC * ClaritySensitivity)

```

**3. Evaluative Valence 갱신 로직**

```text
V_next = V_current + ΔV

```

* `ΔV`는 발표 내용의 타당성, 근거, 논리성 등에 대한 평가 결과를 바탕으로 산출된다.
* Cognitive Clarity의 지속적인 저하가 간접적으로 영향을 줄 수는 있으나, 직접 갱신 근거는 발표 평가 결과이다.

**4. 청중별 개별 편차 (초기 오프셋)**
청중들이 동일한 초기 상태를 갖지 않도록 `-0.05` ~ `+0.05` 사이의 작은 랜덤 오프셋(`δ`)을 부여한다. (최종 상태값은 `-1.00` ~ `+1.00`로 제한)

* `E_i,0 = E_initial + δE_i`
* `C_i,0 = C_initial + δC_i`
* `V_i,0 = 0.00`

---

### 5.4. 에이전트 프로파일의 구분

에이전트 프로파일은 다음 네 가지 요소로 구성된다.

| 구분 | 포함 값 | 역할 |
| --- | --- | --- |
| **고정 프로파일** | `Agent ID`, `Body Type` | 에이전트의 고정 정체성을 정의 |
| **세션 상태 조건** | `Topic Interest`, `Prior Knowledge` | 사용자 공통 설정. 초기 E/C 상태와 감소 민감도 조절 |
| **행동 성향값** | `Responsiveness`, `Expressivity`, `ChannelPreference`, `CriticalBias` | 동일 E/V/C 상태에서 어떤 백채널 행동이 선택될지 확률적 조정 (세션 시작 시 자동 부여) |
| **장면 조건** | `Has Laptop` | 해당 세션 내 특정 에이전트의 오브젝트 소유 여부로 시선/행동 후보군 확장 |

---

### 5.5. 상태 성향값과 행동 성향값의 구분

* **상태 성향값 (`P_i^state`)**: `P_session^state + δ_i^state`
* E/C 감소폭 및 초기 상태에 반영되는 값. 오프셋(`δ`)은 6명의 청중이 다르게 시작하도록 돕는 제한적 변수다.


* **행동 성향값 (`P_i^behavior`)**: `(Responsiveness, Expressivity, ChannelPreference, CriticalBias)`
* E/V/C 상태를 직접 갱신하지 않고, **후보 행동 집합 내부에서 최종 백채널 행동의 선택 확률을 계산**할 때만 사용된다.



---

### 5.6. 에이전트별 내부 행동 성향값 상세

| 내부 행동 성향값 | 의미 | 적용 위치 | 권장 랜덤 범위 |
| --- | --- | --- | --- |
| **Responsiveness_i** | 반응을 얼마나 자주 보이는가 | 후보 행동 집합 내 행동 선택 가능성(빈도)에 반영 | `0.40 ~ 0.75` |
| **Expressivity_i** | 반응을 얼마나 명시적으로 드러내는가 | 표현 강도(intensity) 및 움직임 폭이 큰 클립 변형 선택 점수에 반영 | `0.30 ~ 0.70` |
| **ChannelPreference_i** | 어떤 표현 채널을 선호하는가 | Face, Body, Gaze/Head 계열 클립의 선택 가중치에 반영 | - |
| **CriticalBias_i** | 평가적 반응에서 비판/수용적 경향 수준 | 비판적 백채널 후보군의 선택 확률에 반영 | `0.25 ~ 0.75` |

**[주의 사항: CriticalBias_i]**

* 이 값이 높다고 부정적 평가 상태가 되는 것이 아니다.
* Evaluative Valence가 중립 이하 또는 부정으로 산출된 경우, `skeptical_monitoring`, `restrained_disagreement` 등과 같은 **비판적 백채널 후보의 선택 확률을 높이는 조절 변수**일 뿐이다.
* 긍정 방향 산출 시 비판적 반응으로 전환하지 않는다.

---

### 5.7. 노트북 보유 여부와 시선 후보군

`Has Laptop` 조건은 평가 상태(E/V/C)에 영향을 주지 않으며, 시선 및 행동 후보군을 확장하는 데만 쓰인다.

* **노트북이 없는 청중 시선 후보**: 발표자 / 발표자료 / 주변, 딴 곳
* **노트북이 있는 청중 시선 후보**: 발표자 / 발표자료 / **노트북** / 주변, 딴 곳
* 조건 활성화 시 `Laptop Gaze`, `Typing`, `Laptop Checking` 등의 행동이 후보 집합에 포함된다. 실제 선택 여부는 상태, 이력 등에 따라 결정된다.



---

### 5.8. 설계상 통제 원칙

프로토타입이 사용자 설정값이나 랜덤 개별차에 의해 과도하게 좌우되는 것을 막기 위한 핵심 원칙이다.

1. **사용자 사전 설정값은 배경 조건일 뿐이다.** 청중 반응의 직접 원인이 아니며, 초기 상태 및 감소폭 민감도에만 관여한다.
2. **상태 변화의 주체는 발표자의 수행이다.** 실제 E/V/C 상태 변화는 발표 내용 평가 및 전달 평가 결과에 의해 갱신된다.
3. **Evaluative Valence는 사용자 설정값과 독립적이다.** 오직 발표 내용의 타당성, 근거, 논리성, 명료성 평가 결과로 갱신된다.
4. **개별 행동 성향값은 행동 선택 확률 조절용이다.** 상태 산출 요인이 아니며 동일 상태 내에서 외현화 방식(클립 선택)을 결정한다.
5. **장면 조건은 행동 확장용이다.** 노트북 보유 여부는 평가 상태를 뜻하지 않는다.
6. **긍정 방향 갱신은 증폭되지 않는다.** 사전 설정값(주제 관심도, 사전 지식)은 평가가 긍정적일 때 그 수치를 인위적으로 높이지 않으며, 단지 부정적 평가 시 감소폭을 제어하는 방어막 역할만 수행한다.

## 6. 발표 평가 입력값 및 갱신값 산출 규칙

발표 수행 평가는 **내용 평가(`M_t`)**와 **전달 평가(`D_t`)**로 구분한다. 
각 평가 요소는 `-1.00` ~ `+1.00` 범위의 평가값으로 산출되며, 이 값은 E/V/C 청중 상태 갱신값으로 변환된다.
* 평가값이 양수(+)이면 해당 상태를 긍정 방향으로 갱신한다.
* 평가값이 음수(-)이면 해당 상태를 부정 방향으로 갱신한다.

---

### 6.1. 내용 평가 (`M_t`)

내용 평가는 발표자가 '무엇을 말했는지'를 평가한다.

**[내용 평가 요소 및 갱신 대상]**

| 평가 요소 | 의미 | 1차 갱신 상태 | 2차 갱신 상태 |
| :--- | :--- | :--- | :--- |
| **Organization** (Org) | 발화가 구조적으로 정리되어 있는가 | Cognitive Clarity | Engagement |
| **Supporting Material** (Sup) | 근거, 예시, 자료가 적절히 포함되어 있는가 | Evaluative Valence | Cognitive Clarity |
| **Central Message** (Msg) | 핵심 메시지가 명확하게 드러나는가 | Cognitive Clarity | Engagement |
| **CER Validity** (CER) | 주장, 근거, 추론의 연결이 타당한가 | Evaluative Valence | Cognitive Clarity |

**[평가 요소별 갱신값 변환 규칙]**

| 평가 요소 | E 갱신 | V 갱신 | C 갱신 |
| :--- | :--- | :--- | :--- |
| **Organization** | `0.50 * Org` | `0.00` | `1.00 * Org` |
| **Supporting Material** | `0.00` | `1.00 * Sup` | `0.50 * Sup` |
| **Central Message** | `0.50 * Msg` | `0.00` | `1.00 * Msg` |
| **CER Validity** | `0.00` | `1.00 * CER` | `0.50 * CER` |

**[내용 평가 기반 갱신값 산출 로직]**
```text
ΔE_M = (0.50 * Org) + (0.50 * Msg)
ΔV_M = (1.00 * Sup) + (1.00 * CER)
ΔC_M = (1.00 * Org) + (0.50 * Sup) + (1.00 * Msg) + (0.50 * CER)

// -1.00 ~ +1.00 범위 제한 적용
ΔA_t^M = clamp((ΔE_M, ΔV_M, ΔC_M), -1.00, +1.00)

```

---

### 6.2. 전달 평가 (`D_t`)

전달 평가는 발표자가 '어떻게 전달했는지'를 평가한다.

**[전달 평가 요소 및 갱신 대상]**

| 평가 요소 | 의미 | 1차 갱신 상태 | 2차 갱신 상태 |
| --- | --- | --- | --- |
| **Language Clarity** (Lang) | 문장과 표현이 명확한가 | Cognitive Clarity | Engagement |
| **Vocal Delivery** (Voc) | 음성 전달이 안정적이고 청취 가능한가 | Engagement | Evaluative Valence |
| **Gaze Delivery** (Gaze) | 시선이 청중과 자료 사이에서 적절히 분배되는가 | Engagement | Evaluative Valence |
| **Slide-Speech Align** (Align) | 발화와 발표자료가 잘 정렬되어 있는가 | Cognitive Clarity | Evaluative Valence |

**[평가 요소별 갱신값 변환 규칙]**

| 평가 요소 | E 갱신 | V 갱신 | C 갱신 |
| --- | --- | --- | --- |
| **Language Clarity** | `0.50 * Lang` | `0.00` | `1.00 * Lang` |
| **Vocal Delivery** | `1.00 * Voc` | `0.50 * Voc` | `0.00` |
| **Gaze Delivery** | `1.00 * Gaze` | `0.50 * Gaze` | `0.00` |
| **Slide-Speech Align** | `0.00` | `0.50 * Align` | `1.00 * Align` |

**[전달 평가 기반 갱신값 산출 로직]**

```text
ΔE_D = (0.50 * Lang) + (1.00 * Voc) + (1.00 * Gaze)
ΔV_D = (0.50 * Voc) + (0.50 * Gaze) + (0.50 * Align)
ΔC_D = (1.00 * Lang) + (1.00 * Align)

// -1.00 ~ +1.00 범위 제한 적용
ΔA_t^D = clamp((ΔE_D, ΔV_D, ΔC_D), -1.00, +1.00)

```

---

### 6.3. 내용·전달 갱신값 통합

`ΔA_t^M`과 `ΔA_t^D`는 최종 상태가 아닌 **상태 변화를 유도하는 갱신 입력값**이다. 시스템은 두 갱신값을 차원별 통합 가중치에 따라 결합하여 공통 갱신값 `ΔA_t`를 산출한다.

**[통합 가중치 설정 근거]**

* **Engagement (`w_E = M:0.45 / D:0.55`)**: 음성, 시선 등 실시간 전달 단서에 민감하므로 전달 평가 비율을 높게 설정.
* **Evaluative Valence (`w_V = M:0.55 / D:0.45`)**: 근거, 논리성 등 타당성과 직결되므로 내용 평가 비율을 높게 설정.
* **Cognitive Clarity (`w_C = M:0.50 / D:0.50`)**: 구조의 명료성과 전달의 명료성이 함께 작용하므로 동일 비율로 반영.

**[공통 갱신값 산출 로직]**

```text
// 가중치 정의 (w_M: 내용 가중치, w_D: 전달 가중치)
w_M = (0.45, 0.55, 0.50)
w_D = (0.55, 0.45, 0.50)

// 차원별 통합 갱신값 산출 (⊙ : 원소별 곱셈)
ΔE_t = (0.45 * ΔE_M) + (0.55 * ΔE_D)
ΔV_t = (0.55 * ΔV_M) + (0.45 * ΔV_D)
ΔC_t = (0.50 * ΔC_M) + (0.50 * ΔC_D)

ΔA_t = (ΔE_t, ΔV_t, ΔC_t)

```

---

### 6.4. 에이전트별 민감도 및 이전 상태 반영

공통 갱신값 `ΔA_t`는 이전 상태(`A_i,t-1`) 및 에이전트별 상태 갱신 민감도(`η`)와 결합하여 최종 상태를 산출한다.

* 주제 관심도가 낮으면 `Engagement` 감소 시 더 크게 떨어지며, 높으면 감소폭이 완화된다.
* 사전 지식 수준이 낮으면 `Cognitive Clarity` 감소 시 더 크게 떨어지며, 높으면 감소폭이 완화된다.
* `Evaluative Valence`는 사전 설정값으로 조절되지 않으며 오직 발표 평가 결과로만 갱신된다(`η_V = 1.00`).

**[민감도 적용 및 최종 상태 갱신 로직]**

```text
// 1. 상태 갱신 민감도 계수(η) 결정 (감소 상황에서만 설정값에 따른 민감도 적용)
if ΔE_t < 0:
    η_E,i = EngagementSensitivity_i
else:
    η_E,i = 1.00

η_V,i = 1.00

if ΔC_t < 0:
    η_C,i = ClaritySensitivity_i
else:
    η_C,i = 1.00

// 2. 에이전트 i의 현재 상태 산출
E_i,t = E_i,t-1 + (η_E,i * ΔE_t)
V_i,t = V_i,t-1 + (η_V,i * ΔV_t)
C_i,t = C_i,t-1 + (η_C,i * ΔC_t)

```

---

### 6.5. 최종 상태값 제한 및 다음 단계 전달

최종 산출된 에이전트별 갱신 결과는 범위 제한(Clamp)을 거친 후 행동 계획 단계로 전달된다.

```text
// 상태값 유효 범위(-1.00 ~ +1.00) 제한
A_i,t = clamp((E_i,t, V_i,t, C_i,t), -1.00, +1.00)

```

* **데이터 흐름 참고**: 산출된 최종 청중 상태 `A_i,t`는 백채널 클립을 직접 결정하지 않는다. 이 값은 이후 단계에서 우세 축 및 방향 판별, 상위 행동군(`G_i,t`) 결정, 후보 행동 집합(`C_core_i,t`, `C_action_i,t`) 구성, 후보별 선택 확률 계산의 입력값으로 사용된다.

## 7. 상위 행동군 및 확률적 백채널 행동 선택 구조

### 7.1. 상위 행동군 및 후보 행동 집합 구성

E/V/C 상태값은 최종 애니메이션 클립을 직접 결정하지 않는다. 
먼저 개별 청중 상태 $A_{i,t} = (E_{i,t}, V_{i,t}, C_{i,t})$에서 현재 청중 상태를 가장 강하게 설명하는 우세 축(Dominant Axis)과 그 방향(Direction)을 판별한다. 

이후 판별된 결과를 바탕으로 상위 행동군 $G_{i,t}$를 결정하고, 해당 행동군 내부에서 Core Behavior 후보 집합 $C\_core_{i,t}$를 구성한다. 
사건(Event) 조건이 발생한 경우에는 별도의 Action Clip 후보 집합 $C\_action_{i,t}$를 구성한다.

최종 백채널 출력 $O_{i,t}$는 $C\_core_{i,t}$에서 선택된 $B\_core_{i,t}$를 기본으로 하며, 
$C\_action_{i,t}$가 비어 있지 않고 삽입 조건을 만족할 경우 $B\_action_{i,t}$를 Core Behavior 위에 일시적으로 블렌딩(Blending)한다.

---

#### 7.1.1. 상태 수준 판별

각 상태값은 다음 기준에 따라 해석한다.

| 값 범위 | 상태 수준 |
| :--- | :--- |
| -1.00 ~ -0.34 | 낮음 |
| -0.33 ~ +0.33 | 중간 |
| +0.34 ~ +1.00 | 높음 |

세 상태값($E_{i,t}$, $V_{i,t}$, $C_{i,t}$)이 모두 중간 범위에 있을 경우, 특정 상태 축이 우세하다고 보지 않고 **Baseline Listening**을 적용한다.

```text
if level(E_i,t) == middle 
   and level(V_i,t) == middle 
   and level(C_i,t) == middle:
   
    G_i,t = Baseline Listening

```

---

#### 7.1.2. 우세축 판별

세 상태값 중 하나 이상이 중간 범위를 벗어나는 경우, 절대값이 가장 큰 상태 차원을 우세축 후보로 판별한다.

```text
dominant_axis_i,t = argmax(|E_i,t|, |V_i,t|, |C_i,t|)

```

| 우세 조건 | 상위 행동군 ($G_{i,t}$) | 클립 선택 범위 |
| --- | --- | --- |
| E, V, C 모두 중간 범위 | **Baseline Listening** | 기본 청취 상태 클립 |
| Engagement 우세 | **Attentive Listening** | Engagement 관련 클립 |
| Evaluative Valence 우세 | **Evaluative Monitoring** | Evaluative Valence 관련 클립 |
| Cognitive Clarity 우세 | **Comprehension Tracking** | Cognitive Clarity 관련 클립 |

---

#### 7.1.3. 동률 및 근사 동률 처리 규칙

1순위 축과 2순위 축의 절대값 차이가 특정 기준값($\delta$) 이하인 경우, 안정적인 결정을 위해 근사 동률(Tie) 규칙을 적용한다.

* $\delta = 0.10$

```text
m1_i,t = max(|E_i,t|, |V_i,t|, |C_i,t|)
m2_i,t = second_max(|E_i,t|, |V_i,t|, |C_i,t|)

if (m1_i,t - m2_i,t) <= δ:
    tie_i,t = true
else:
    tie_i,t = false

```

**[근사 동률 발생 시 우선순위 규칙]**

```text
if tie_i,t == true:
    1. 후보 축 중 -C가 포함되어 있으면 C 선택
    2. 후보 축 중 -V가 포함되어 있으면 V 선택
    3. 후보 축 중 -E가 포함되어 있으면 E 선택
    4. 직전 우세축(dominant_axis_i,t-1)이 후보 축 중 하나와 같으면 직전 축 유지
    5. 위 조건에 모두 해당하지 않으면 E -> C -> V 순으로 우선 선택

```

---

#### 7.1.4. 방향 판별

우세축이 확정되면 해당 축 값의 부호에 따라 방향성을 판별한다.

```text
direction_i,t = sign(value(dominant_axis_i,t))

```

#### 7.1.5. 상위 행동군 결정

확정된 우세축과 방향을 기준으로 상위 행동군 $G_{i,t}$를 결정한다.

```text
G_i,t = group(dominant_axis_i,t, direction_i,t)

```

---

#### 7.1.6. Core Behavior 후보 집합 구성

결정된 상위 행동군을 기반으로, 전체 클립 풀($L\_core$)에서 조건(상태, 발화 위치, 이력, 쿨다운)을 모두 만족하는 후보 집합 $C_core_{i,t}$를 구성한다.

```text
C_core_i,t = { b ∈ L_core |
    parent_group(b) == G_i,t
    and state_match(b, A_i,t) == valid
    and utterance_position(b, U_t) == valid
    and cooldown_i(b,t) == valid
}

```

#### 7.1.7. Action Clip 후보 집합 구성

Action Clip은 Core Behavior 위에 삽입되는 사건형 반응이므로 `parent_group`으로 필터링하지 않는다. 대신 이벤트 발생, 상태 조건, 쿨다운 등을 기준으로 별도의 집합 $C_action_{i,t}$를 구성한다.

```text
C_action_i,t = { a ∈ L_action |
    event_match(a, X_t) == valid
    and state_gate(a, A_i,t) == valid
    and utterance_position(a, U_t) == valid
    and cooldown_i(a,t) == valid
}

```

---

### 7.2. 후보별 선택 점수 및 확률 계산

Core Behavior 후보 집합($C\_core_{i,t}$)에 속한 각 후보 클립 $b$에 대한 선택 점수 $z_core_{i,t}(b)$를 계산한다.

```text
z_core_i,t(b) = 
  λ_s * StateFit(A_i,t, b)         // 현재 E/V/C 상태와 클립 조건의 부합도
+ λ_p * Preference(P_i, b)         // 에이전트의 해당 클립 선호도
+ λ_c * ChannelPreference(P_i, b)  // 에이전트의 표현 채널 선호도
+ λ_h * History(H_i,t, b)          // 최근 행동 흐름 상의 자연스러움
- λ_r * Repetition(H_i,t, b)       // 최근 사용된 횟수 (반복 페널티)

```

---

### 7.3. 확률적 백채널 행동 선택

각 후보 클립의 선택 점수 $z_core_{i,t}(b)$에 **Softmax** 연산을 적용하여 선택 확률 $\pi_core_{i,t}(b)$로 변환한다.

$$ \pi_core_{i,t}(b) = \frac{\exp(z_core_{i,t}(b))}{\sum_{b' \in C_core_{i,t}} \exp(z_core_{i,t}(b'))} $$

변환된 확률 분포를 바탕으로 Categorical 분포에서 $B_core_{i,t}$를 샘플링(선택)한다.

* $B\_core_{i,t} \sim \text{Categorical}(\pi\_core_{i,t})$
* 선택 결과는 항상 $B_core_{i,t} \in C_core_{i,t}$를 만족한다.

**Action Clip 적용 규칙**
Action Clip은 $C_action_{i,t}$가 비어 있지 않고 특정 삽입 조건을 만족할 때만 선택된다. 조건을 만족하지 않으면 $B\_action_{i,t} = null$ 로 처리한다.

```

```

## 8. 백채널 출력 레이어 구조

프로토타입의 백채널 출력은 크게 **Face Layer**, **Body Layer**, **Gaze/Head IK** 세 가지 계층으로 분리하여 실행한다.

### 8.1. 출력 레이어 구성

| 출력 구분 | 구현 단위 | 설명 |
| :--- | :--- | :--- |
| **Face Layer** | Facial Animation Clip | 표정 반응을 제어한다. ARKit 기반 BlendShape 데이터를 사용하여 제작한 얼굴 애니메이션 클립을 Unity에서 재생한다. |
| **Body Layer** | Body Animation Clip | 고개 움직임, 상체 반응, 자세 변화를 포함한 신체 애니메이션 클립을 재생한다. |
| **Gaze/Head IK** | Script 기반 IK 제어 | 발표자, 발표자료, 주변 방향을 바라보도록 시선과 머리 방향을 동적으로 제어한다. |

### 8.2. 출력 계층 통합 및 실행 규칙

하나의 백채널 반응은 **Face Layer, Body Layer, Gaze/Head IK의 조합**으로 구성된다.

* **독립적 실행 환경**: Face와 Body는 각각 별도의 애니메이션 레이어(Animation Layer)에서 재생하며, Gaze/Head는 애니메이션 클립과 분리되어 스크립트 기반으로 별도 제어한다.
* **출력 명령 분해**: 확률적 행동 선택 단계에서 결정된 최종 백채널 행동 $B_{i,t}$ (Core Behavior 및 optional Action Clip 포함)는 실행 시점에 각 레이어의 복수 출력 명령 $O_{i,t}$로 분해되어 병렬적으로 실행된다.

**[명령 분해 구조]**
```text
B_i,t  ->  O_i,t = {
    Face_Command,
    Body_Command,
    Gaze_Head_Command
}

## 9. 백채널 Clip Pool L 구조

**Clip Pool L**은 후보 행동 집합 $C_{i,t}$를 구성하기 위해 참조되는 전체 백채널 클립 저장소이다. 
각 클립 $b$는 상위 행동군, 하위 행동 패턴, 클립 유형, 상태 조건, 출력 가능 시점, 사용 레이어, 최소 재사용 간격을 메타데이터로 가진다.

* **우세축 판정**: 기본적으로 절댓값이 가장 큰 축을 우세축(`dominant_axis`)으로 판정한다.
* **근사 동률 처리**: 단, 1순위 축과 2순위 축의 차이가 `threshold` 이하이면 근사 동률(Tie)로 처리한다.
  * `threshold = 0.10`

---

### 9.1. Core Behavior Clip Pool

| clip_id | parent_group | variation name | trigger_condition | utterance_position | channel | cooldown | 해석 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BL_01** | Baseline Listening | neutral_listening | E 중간<br>V 중간<br>C 중간 | During speech | Body + Gaze·Head | 2.0 | 평가, 이해, 집중이 모두 중간 수준에 있는 중립적 기본 청취 상태 |
| **BL_02** | Baseline Listening | neutral_gaze_shift | E 중간<br>V 중간<br>C 중간 | During speech<br>Slide reference | Gaze·Head | 4.0 | 특정한 긍정·부정·이해 반응 없이 발표자와 자료 사이를 오가는 기본 시선 반응 |
| **BL_03** | Baseline Listening | quiet_stable_posture | E 중간<br>V 중간<br>C 중간 | Silence or pause | Body | 3.0 | 발화가 잠시 멈춘 동안 자세를 안정적으로 유지하며 과도한 반응 없이 대기 |
| **AL_01** | Attentive Listening | stable_attention | +E 우세<br>V 중간·높음<br>C 중간·높음 | During speech | Body + Gaze·Head | 2.0 | 집중해서 듣고 있으며 평가와 이해가 안정적인 기본 집중 청취 상태 |
| **AL_01** | Attentive Listening | active_following | +E 우세<br>V 중간·높음<br>C 중간·높음 | Utterance boundary | Head + Gaze·Head | 3.0 | 발표 흐름을 적극적으로 따라가며 발표자 방향으로 시선과 고개가 반응 |
| **AL_01** | Attentive Listening | agreement_nod | +E 우세<br>V 중간·높음<br>C 중간·높음 | Utterance boundary | Head + Body | 3.5 | 이해하거나 몰입하고 있음을 나타내는 짧고 자연스러운 끄덕임 |
| **AL_02** | Attentive Listening | attentive_slide_check | +E 우세<br>V 중간·높음<br>C 낮음 | During speech<br>Slide reference | Gaze·Head | 4.0 | 발표자와 발표자료 사이를 오가며 내용을 확인하려는 집중 상태 |
| **AL_02** | Attentive Listening | slight_head_tilt_check | +E 우세<br>V 중간·높음<br>C 낮음 | Utterance boundary | Head + Face | 4.0 | 집중은 유지하지만 이해가 확정되지 않아 짧은 고개 갸웃이나 눈썹 반응 표시 |
| **AL_03** | Attentive Listening | low_engagement_positive | -E 우세<br>V 중간·높음<br>C 중간·높음<br>*(또는 +V 우세, E 낮음, C 중간·높음)* | During speech | Body + Gaze·Head | 5.0 | 내용은 긍정적으로 받아들이거나 이해했지만 청취 집중은 약해진 상태 |
| **AL_03** | Attentive Listening | passive_acceptance | -E 우세<br>V 중간·높음<br>C 중간·높음<br>*(또는 +V 우세, E 낮음, C 중간·높음)* | Silence or pause | Body + Face | 6.0 | 수용성은 유지되지만 반응 빈도와 신체적 관여가 낮아진 저관여 청취 상태 |
| **EM_01** | Evaluative Monitoring | positive_monitoring | +V 우세<br>E 중간·높음<br>C 중간·높음 | During speech | Face + Gaze·Head + Body | 2.5 | 발표 내용이나 전달 방식에 대해 긍정적으로 평가하며 안정적으로 관찰 |
| **EM_01** | Evaluative Monitoring | approving_smile | +V 우세<br>E 중간·높음<br>C 중간·높음 | Utterance boundary | Face + Gaze·Head | 3.5 | 발표 흐름에 수용적으로 반응하며 짧은 미소와 안정적 시선을 보임 |
| **EM_01** | Evaluative Monitoring | soft_approval_nod | +V 우세<br>E 중간·높음<br>C 중간·높음 | Utterance boundary | Head + Face | 4.0 | 긍정적 평가를 유지하며 부드러운 끄덕임으로 수용성을 드러냄 |
| **EM_02** | Evaluative Monitoring | positive_but_uncertain | +V 우세<br>E 중간·높음<br>C 낮음 | During speech | Face + Gaze·Head | 3.0 | 호의적 평가는 유지하지만 일부 내용을 이해하지 못해 확인하려는 상태 |
| **EM_02** | Evaluative Monitoring | smile_with_slide_check | +V 우세<br>E 중간·높음<br>C 낮음 | During speech<br>Slide reference | Face + Gaze·Head | 4.0 | 약한 미소를 유지한 채 발표자료를 확인하며 내용을 따라가려는 상태 |
| **EM_02** | Evaluative Monitoring | curious_head_tilt | +V 우세<br>E 중간·높음<br>C 낮음 | Utterance boundary | Head + Face | 4.5 | 긍정적 태도는 유지하지만 이해가 불완전해 눈썹 올림, 고개 갸웃 발생 |
| **EM_04** | Evaluative Monitoring | weak_positive_low_clarity | +V 우세<br>E 낮음<br>C 낮음 | During speech | Face + Body + Gaze·Head | 5.0 | 호의적 평가는 남았으나 집중/이해가 모두 낮아 반응 빈도가 감소 |
| **EM_04** | Evaluative Monitoring | fading_approval | +V 우세<br>E 낮음<br>C 낮음 | Silence or pause | Face + Body | 6.0 | 긍정적 태도가 희미하게 남아 있지만 자세와 표정 반응이 약해진 상태 |
| **EM_05** | Evaluative Monitoring | cold_monitoring | -V 우세<br>E 중간·높음<br>C 중간·높음<br>*(또는 +E 우세, V 낮음, C 가변)* | During speech | Face + Gaze·Head + Body | 3.0 | 내용은 이해하고 집중하지만 평가적으로 냉담하거나 부정적으로 관찰 |
| **EM_05** | Evaluative Monitoring | skeptical_monitoring | -V 우세<br>E 중간·높음<br>C 중간·높음<br>*(또는 +E 우세, V 낮음, C 가변)* | During speech | Face + Head + Body | 4.0 | 미간 긴장, 입술 압축, 뒤로 기댄 자세로 의심하거나 유보적으로 평가 |
| **EM_05** | Evaluative Monitoring | restrained_disagreement | -V 우세<br>E 중간·높음<br>C 중간·높음<br>*(또는 +E 우세, V 낮음, C 가변)* | Utterance boundary | Head + Face | 5.0 | 내용은 따라가나 동의하지 않는 태도가 짧은 고개 움직임/굳은 표정으로 나타남 |
| **EM_07** | Evaluative Monitoring | disengaged_negative | -V 우세, E 낮음, C 중간·높음<br>*(또는 +E 우세, V 낮음, C 낮음)*<br>*(또는 -E 우세, V 낮음, C 중간·높음)*<br>*(또는 +C 우세, E 낮음, V 낮음)* | During speech | Face + Gaze·Head + Body | 6.0 | 부정적 평가, 집중 저하, 이해 저하가 겹쳐 시선 이탈과 냉담한 표정 증가 |
| **EM_07** | Evaluative Monitoring | gaze_withdrawal_negative | -V 우세, E 낮음, C 중간·높음<br>*(또는 다른 복합 부정 조건)* | During speech | Gaze·Head + Body | 7.0 | 발표자 시선을 회피하거나 주변으로 시선이 빠지며 부정적 관여 저하 노출 |
| **EM_07** | Evaluative Monitoring | closed_posture_negative | -V 우세, E 낮음, C 중간·높음<br>*(또는 다른 복합 부정 조건)* | Silence or pause | Face + Body | 8.0 | 닫힌 자세, 무표정, 뒤로 기대기 등으로 냉담하고 부정적인 평가 지속 |
| **CT_01** | Comprehension Tracking | stable_comprehension | +C 우세<br>E 중간·높음<br>V 중간·높음 | During speech | Gaze·Head + Body | 2.5 | 내용을 안정적으로 이해하며 발표자와 자료를 자연스럽게 오가며 추적 |
| **CT_01** | Comprehension Tracking | comprehension_nod | +C 우세<br>E 중간·높음<br>V 중간·높음 | Utterance boundary | Head + Body | 3.5 | 내용을 이해하고 있음을 짧은 끄덕임으로 드러내는 상태 |
| **CT_01** | Comprehension Tracking | slide_speaker_tracking | +C 우세<br>E 중간·높음<br>V 중간·높음 | During speech<br>Slide reference | Gaze·Head | 3.5 | 발표자와 슬라이드 사이를 안정적으로 오가며 내용 구조를 추적 |
| **CT_02** | Comprehension Tracking | understood_but_reserved | +C 우세<br>E 중간·높음<br>V 낮음 | During speech | Face + Gaze·Head + Body | 3.5 | 내용은 이해하지만 평가적으로 유보적이거나 수용성이 낮은 상태 |
| **CT_02** | Comprehension Tracking | closed_comprehension | +C 우세<br>E 중간·높음<br>V 낮음 | During speech | Face + Body | 5.0 | 이해는 유지하지만 표정과 자세가 다소 닫혀 있는 상태 |
| **CT_02** | Comprehension Tracking | limited_nod_reserved | +C 우세<br>E 중간·높음<br>V 낮음 | Utterance boundary | Face + Head | 5.0 | 내용은 따라가지만 수용이 제한되어 약한 끄덕임이나 굳은 표정 발생 |
| **CT_03** | Comprehension Tracking | understood_low_engagement | +C 우세<br>E 낮음<br>V 중간·높음 | During speech | Gaze·Head + Body | 4.0 | 내용은 이해하나 청취 집중이 약해져 반응 빈도와 자세 안정성 저하 |
| **CT_03** | Comprehension Tracking | delayed_gaze_return | +C 우세<br>E 낮음<br>V 중간·높음 | During speech | Gaze·Head | 5.0 | 시선이 잠시 이탈한 뒤 발표자나 슬라이드로 늦게 복귀 |
| **CT_05** | Comprehension Tracking | trying_to_understand | -C 우세<br>E 중간·높음<br>V 중간·높음 | During speech | Face + Gaze·Head | 3.0 | 이해가 어렵지만 집중과 수용성을 유지하며 내용을 따라가려는 상태 |
| **CT_05** | Comprehension Tracking | confused_glance | -C 우세<br>E 중간·높음<br>V 중간·높음 | During speech<br>Slide reference | Gaze·Head + Face | 4.0 | 발표자와 슬라이드를 번갈아 보며 짧은 혼란 반응을 보임 |
| **CT_05** | Comprehension Tracking | head_tilt_recheck | -C 우세<br>E 중간·높음<br>V 중간·높음 | Utterance boundary | Head + Face | 4.5 | 이해가 불완전해 고개 갸웃, 눈썹 올림, 미간 반응으로 다시 확인하려 함 |
| **CT_06** | Comprehension Tracking | confused_skeptical | -C 우세<br>E 중간·높음<br>V 낮음<br>*(또는 -V 우세, E 중·높, C 낮)* | During speech | Face + Head + Body | 4.0 | 이해 어려움과 부정적 평가가 함께 나타나는 상태 |
| **CT_06** | Comprehension Tracking | skeptical_slide_check | -C 우세<br>E 중간·높음<br>V 낮음<br>*(또는 -V 우세, E 중·높, C 낮)* | During speech<br>Slide reference | Face + Gaze·Head | 5.0 | 내용을 이해하지 못한 상태에서 자료를 확인하며 의심/유보적 관찰 |
| **CT_06** | Comprehension Tracking | furrowed_head_tilt | -C 우세<br>E 중간·높음<br>V 낮음<br>*(또는 -V 우세, E 중·높, C 낮)* | Utterance boundary | Face + Head | 5.0 | 미간 긴장과 고개 갸웃이 함께 나타나 이해 어려움과 의심 표현 |
| **CT_07** | Comprehension Tracking | lost_understanding | -C 우세, E 낮음, V 중간·높음<br>*(또는 -E 우세, V 중·높, C 낮)* | During speech | Gaze·Head + Body | 5.0 | 이해를 놓치고 청취 집중도 약해진 상태 |
| **CT_07** | Comprehension Tracking | off_target_gaze | -C 우세, E 낮음, V 중간·높음<br>*(또는 -E 우세, V 중·높, C 낮)* | During speech | Gaze·Head | 6.0 | 발표자나 자료가 아닌 곳으로 시선이 빠지고 복귀가 늦어지는 상태 |
| **CT_07** | Comprehension Tracking | low_response_flat | -C 우세, E 낮음, V 중간·높음<br>*(또는 -E 우세, V 중·높, C 낮)* | Silence or pause | Face + Body | 6.0 | 무표정과 낮은 반응 빈도가 나타나며 이해 추적이 약해진 상태 |
| **CT_08** | Comprehension Tracking | strong_confusion_disengagement| -C 우세, E 낮음, V 낮음<br>*(또는 -E 우세, V 낮음, C 낮음)* | During speech | Face + Gaze·Head + Body | 6.0 | 이해 부족, 부정적 평가, 집중 저하가 함께 나타나는 강한 혼란/이탈 |
| **CT_08** | Comprehension Tracking | gaze_withdrawal_confusion | -C 우세, E 낮음, V 낮음<br>*(또는 -E 우세, V 낮음, C 낮음)* | During speech | Gaze·Head + Body | 8.0 | 시선을 피하거나 주변으로 시선이 빠지며 혼란과 이탈 동시 표출 |
| **CT_08** | Comprehension Tracking | collapsed_posture_confusion | -C 우세, E 낮음, V 낮음<br>*(또는 -E 우세, V 낮음, C 낮음)* | Silence or pause | Face + Body | 8.0 | 자세 무너짐, 표정 반응 감소 등 강한 이해 실패와 이탈 지속 |

---

### 9.2. Action Clip

| clip_id | action_name | event_trigger | state_gate | utterance_position | channel | cooldown | 해석 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ACT_01** | Laptop Typing | 정보량 많음 | C 낮음<br>E 중간·높음 | During speech<br>Slide reference | Body + Gaze·Head | 20.0 | 이해가 어려운 정보가 많으나 집중은 유지되어 자료/노트북으로 시선 이동 후 타이핑 |
| **ACT_02** | PhotoSlide | 정보량 많음 OR<br>Slide reference | C 낮음<br>E 중간·높음 | Slide transition<br>Slide reference | Body + Gaze·Head | 30.0 | 이해가 어렵거나 자료 참조 시 시선과 상체가 자료로 이동하며 촬영 동작 수행 |
| **ACT_03** | Device Checking | 반복적 이탈 | E 낮음 | During speech<br>Silence or pause | Body + Gaze·Head | 35.0 | 청취 집중이 낮아져 개인 기기로 시선/고개 이동 및 일시적 speaker gaze 감소 |
| **ACT_04** | DrowsyNod | 저각성 | E 낮음 | Silence or pause | Face + Body | 45.0 | 집중/각성 저하로 눈꺼풀이 처지고 고개가 떨어졌다가 들리는 졸음 반응 |
| **ACT_05** | Seat Adjust | 긴 정적 유지 | state 제한 없음 | Silence or pause | Body | 12.0 | 일정 시간 정적 자세 유지 후 몸의 위치를 짧게 조정하고 복귀 |
| **ACT_06** | Small Stretch | 긴 정적 유지 | state 제한 없음 | Silence or pause | Body | 18.0 | 일정 시간 정적 자세 유지 후 어깨, 팔, 상체를 짧게 움직여 정적 해소 |
| **ACT_07** | Self Contact | 긴장 | V 낮음 | During speech<br>Utterance boundary | Face + Body | 20.0 | 부정적 평가나 긴장 상태에서 손이 얼굴/입/팔 근처로 이동 (입술 긴장, 시선 회피 동반) |
| **ACT_08** | Side Conversation | 주변 상호작용 발생 | E 낮음 OR<br>V 낮음 | Silence or pause | Face + Body + Gaze·Head | 40.0 | 집중이나 수용성이 낮아 옆 사람을 바라보고 끄덕임/미소 등 비언어 반응 교환 (맨 뒷줄 2명만) |

```markdown
## 10. 행동 출력 명령 구조

백채널 출력은 확률적 행동 선택 단계에서 결정된 행동들을 레이어별 명령으로 분해하여 구성한다. 
기본적인 출력 명령 $O_{i,t}$는 Core Behavior에 선택적 Action Clip(Action Overlay)을 결합한 형태로 정의된다.

**[백채널 출력 명령 구조]**
```text
O_i,t = B_core_i,t + (optional) B_action_i,t

O_i,t = {
    core_behavior: B_core_i,t,
    action_overlay: B_action_i,t or null,
    gaze_head_adjustment,
    output_layers: Face + Body + GazeHead
}

```

### 10.1. 출력 명령 파라미터 상세

출력 시스템에 전달되는 개별 제어 명령은 다음과 같은 세부 파라미터를 포함한다.

| 항목 (`Field`) | 의미 |
| --- | --- |
| **agent_id** | 행동을 수행할 청중 에이전트 ID |
| **start_time** | 행동 시작 시점 |
| **layer** | 실행 레이어 (Face, Body, GazeHead 중 하나) |
| **action_id** | Face, Body, GazeHead 레이어에서 실제 실행할 개별 클립 또는 제어 동작 ID |
| **duration** | 행동 지속시간 |
| **sync_group** | Face, Body, GazeHead 출력을 하나의 반응으로 묶어주는 동기화 ID |
| **selected_behavior_id** | 확률적 행동 선택 단계에서 선택된 최종 백채널 행동($B_{i,t}$)의 ID |

### 10.2. 실행 분해 및 계층 간 참조 규칙

* `selected_behavior_id`는 [9. 백채널 Clip Pool L 구조]에서 최종 선택된 $B_{i,t}$ (예: `AL_01`, `ACT_03` 등)를 참조한다.
* 하나의 `selected_behavior_id`는 실행 시점에 Face, Body, GazeHead 레이어별로 실제 재생될 하위 `action_id`들로 분해(Decomposition)되어 병렬 실행된다.
* 분해된 복수의 명령들은 `sync_group` ID를 통해 하나의 통합된 백채널 반응으로 동기화 및 관리된다.

```

```
## 11. 백채널 출력 시점 규칙

백채널 행동은 발표 흐름을 방해하지 않도록 발화 위치에 따라 출력 가능 여부와 시작 시점을 조정한다. 
이 출력 시점 규칙은 후보 행동 집합 $C_{i,t}$ 구성과 최종 출력 명령 $O_{i,t}$ 생성에 함께 사용된다.

각 클립 $b$는 허용 가능한 발화 위치 조건인 `utterance_position`을 메타데이터로 가지며, 현재 발화 위치 $U_t$가 해당 조건을 만족할 때에만 후보 행동 집합 $C_{i,t}$에 포함될 수 있다.

### 11.1. 발화 위치별 출력 규칙

| 발화 위치 ($U_t$) | 허용되는 반응 | 제한되는 반응 | 적용 기준 |
| :--- | :--- | :--- | :--- |
| **During speech** (발화 중) | 발표자 응시, 작은 끄덕임, 약한 표정 변화, 안정적 자세 유지 | 큰 자세 변화, 하품, 기기 확인, 옆 사람 대화 | 발표자의 발화를 방해하지 않는 미세 반응만 허용 |
| **Utterance boundary** (발화 경계) | 고개 끄덕임, 고개 갸웃, 짧은 시선 전환, 표정 변화 | 긴 행동, 큰 제스처 | 의미 단위가 끝난 직후 평가 또는 이해 관련 반응 출력 |
| **Silence or pause** (침묵 및 휴지기) | 자료 재응시, 자세 조정, 혼란 표정, 시선 이탈 | 과도한 연속 반응 | 상태 변화가 클 때 비교적 명확한 반응 출력 |
| **Slide transition** (슬라이드 전환) | 발표자료 응시, 발표자-자료 간 시선 전환, 짧은 고개 움직임 | 발표 흐름과 무관한 Action Clip | 슬라이드 변화 또는 자료 참조 시점에 동기화 |

### 11.2. 출력 시점 조정 및 후보 집합 필터링

출력 시점 조정 단계에서는 선택된 최종 백채널 행동 $B_{i,t}$의 `utterance_position` 조건과 현재 발화 위치 $U_t$를 비교하여 행동 시작 시점(`start_time`)을 결정한다.

Core Behavior 후보 집합과 Action Clip 후보 집합은 모두 발화 위치 조건을 필수적으로 적용하여 필터링한다. 
* **Core Behavior**: 상위 행동군 $G_{i,t}$를 기준으로 구성
* **Action Clip**: 사건 조건 $X_t$와 상태 조건(State Gate)을 기준으로 구성

**[발화 위치 조건이 반영된 후보 집합 구성 로직]**
```text
// Core Behavior 후보 집합 필터링
C_core_i,t = { b ∈ L_core |
    parent_group(b) == G_i,t
    and state_match(b, A_i,t) == valid
    and utterance_position(b, U_t) == valid
    and cooldown_i(b,t) == valid
}

// Action Clip 후보 집합 필터링
C_action_i,t = { a ∈ L_action |
    event_match(a, X_t) == valid
    and state_gate(a, A_i,t) == valid
    and utterance_position(a, U_t) == valid
    and cooldown_i(a,t) == valid
}