# AI 청중 반응 파이프라인 10단계 확률 선택 결과

> 선행 단계: `reaction-rule_stage9_candidates.md` 완료  
> 단계 상태: 완료

## 구현 결과

- 상태 수준 affinity와 조건별 `StateFit`을 구현했다.
- Responsiveness/Expressivity 기반 preference, channel preference, 최근 group 흐름, 최근 5개 반복 페널티를 계약 계수로 합산한다.
- CriticalBias는 critical clip이고 현재 V가 중립 이하일 때만 preference를 조절한다.
- overflow-safe Softmax와 agent RNG 기반 Categorical sampling을 구현했다.
- transient Core는 responsiveness emit gate를 거쳐 stable 대체 또는 no-op이 된다.
- Action은 상태/event/channel/responsiveness/repetition 점수와 최대 0.85 삽입 gate를 거쳐 agent당 최대 하나만 선택된다.
- 실제 선택만 최근 8개 이력과 variation cooldown을 갱신한다.
- 상태 기반 반복 이탈/저각성 카운터 갱신 함수를 추가했다.
- 후보별 점수 구성요소와 확률을 diagnostics로 보존한다.

## 검증 결과

```text
$env:PYTHONPATH='sushi-fast'
.\.venv\Scripts\python.exe -m pytest sushi-fast/odi/EVC/tests -q

........................................... [100%]
43 passed
```

추가 검증 항목:

- 큰 logit의 Softmax 안정성과 5,000회 표본 분포
- 동일 seed/입력의 동일 Core 결과
- 선택 결과가 후보 집합에 속함
- 실제 선택의 축/이력/cooldown 갱신 및 이력 8개 제한
- CriticalBias가 positive V에 영향 없음
- Action Overlay가 최대 하나이며 Action 후보에 속함

## 완료 판정

동일 seed와 요청 순서는 동일 선택을 만들고, 표본 분포가 계산 확률과 허용 오차 내에서 일치한다. cooldown과 반복 이력이 실제 선택에만 적용되고 CriticalBias 방향도 통제된다. 따라서 10단계 완료 기준을 충족한다. 다음 실제 작업은 11단계인 Unity 명령 조립 및 API 통합이다.
