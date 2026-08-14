# AI 청중 반응 파이프라인 9단계 후보 엔진 결과

> 선행 단계: `reaction-rule_stage8_state.md` 완료  
> 단계 상태: 완료

## 구현 결과

- `behavior_engine.py`에 연속 경계 수준 분류와 모두 mid인 Baseline 판정을 구현했다.
- 우세축 절대값, `0.10` 근사 동률, `-C→-V→-E→직전축→E→C→V` 우선순위를 구현했다.
- 명세 Clip 표의 대체 조건을 명시적 group routing rule로 사용하여 복합 상태도 원래 parent group 후보가 된다.
- Core는 상태 조건, 발화 위치, slide reference, cooldown으로 필터링한다.
- Action은 사건, 상태 gate, 발화 위치, scene gate, cooldown으로 필터링한다.
- 정보량, slide reference, 반복 이탈, 저각성, 장기 정적, 긴장 사건을 계약 임계값으로 파생하고 client strength와 max 결합한다.
- Core가 비면 같은 위치의 안전한 Baseline을 찾고, 없으면 빈 집합을 유지해 후속 no-op 선택을 보장한다.

## 검증 결과

```text
$env:PYTHONPATH='sushi-fast'
.\.venv\Scripts\python.exe -m pytest sushi-fast/odi/EVC/tests -q

...................................... [100%]
38 passed
```

추가 검증 항목:

- `-0.34/-0.339/+0.339/+0.34` 경계
- Baseline, 단일 우세축, 음수 tie, 직전축 유지
- 상태/발화 위치/slide/cooldown Core 필터
- 복합 조건의 Evaluative group routing
- 정보량 Action과 laptop gate
- rear Side Conversation gate
- 안전한 fallback이 없는 위치의 빈 후보/no-op 유지

## 완료 판정

후보는 항상 전체 Clip Pool의 조건을 충족하며 금지된 발화 위치·장면·cooldown 행동은 포함되지 않는다. 모든 후보가 없을 때 안전한 baseline/no-op 경로가 있다. 따라서 9단계 완료 기준을 충족한다. 다음 실제 작업은 10단계인 확률 선택, 행동 이력 및 Action Overlay 구현이다.
