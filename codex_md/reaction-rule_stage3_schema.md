# AI 청중 반응 파이프라인 3단계 스키마 정비 결과

> 선행 단계: `reaction-rule_stage2_contract.md` 완료  
> 단계 상태: 완료

## 구현 결과

- 기존 `AudienceState`, `BehaviorCommand`, `EVCUpdateResponse`를 유지해 현재 서비스 import를 보존했다.
- `sushi-fast/odi/EVC/schema.py`에 다음 v2 모델을 추가했다.
  - 프로파일/상태: `ChannelPreference`, `AudienceProfile`, `StateSensitivity`, `AudienceSnapshot`, `AudienceRuntimeState`
  - 이력/입력: `BehaviorHistoryEntry`, `EventSignals`, `SegmentContext`, `SmartStartOptions`, `UpdateRequestMetadata`
  - Clip: `StateCondition`, `SceneGate`, `UnityActionSpec`, `CoreClipSpec`, `ActionClipSpec`, `ClipPoolCatalog`
  - 선택/Unity: `BehaviorChoice`, `UnityCommand`, `AudienceDecision`, `StateDeltaBreakdown`
  - v2 응답: `SmartStartResponseV2`, `SessionResponseV2`, `EVCUpdateResponseV2`
- 모든 v2 모델은 unknown field를 거부하며 숫자의 범위와 finite 여부를 검증한다.
- agent ID, behavior/variation ID, Unity action namespace, channel/action layer 일치, Clip variation 전역 유일성을 스키마에서 검증한다.
- `sushi-fast/odi/EVC/ARCHITECTURE.md`에 모듈 책임, 의존 방향, 공개 인터페이스와 호환성 원칙을 고정했다.
- `sushi-fast/odi/EVC/tests/test_schema.py`에 정상/비정상 계약 검증 6개를 추가했다.

## 검증 결과

실행 환경은 프로젝트 루트의 Git 제외 `.venv`이며 Pydantic 2.13.4와 pytest 8.4.2를 사용했다.

```text
$env:PYTHONPATH='sushi-fast'
.\.venv\Scripts\python.exe -m pytest sushi-fast/odi/EVC/tests/test_schema.py -q

...... [100%]
6 passed
```

검증한 항목:

- E/V/C 유한값 clamp와 NaN 거부
- channel preference 합계 1.0 및 alias 직렬화
- 알 수 없는 사건과 범위 밖 strength 거부
- Clip ID namespace, Unity layer/action namespace, variation 중복 거부
- smart-start 응답의 정확히 6명·고유 agent ID
- Unity 명령의 v2 필드 및 UUID 직렬화

## 완료 판정

- 6명 상태, 프로파일, 이력, 사건 입력, Clip Pool, Unity 명령을 직렬화할 수 있다.
- 잘못된 enum, 범위, ID, 중복 및 알 수 없는 필드를 거부한다.
- 현재 서비스와 v2 전환 코드가 공존할 수 있다.
- 후속 모듈의 공개 책임과 의존 방향이 확정되었다.

따라서 `reaction-rule_plan.md`의 3단계 완료 기준을 충족한다. 다음 실제 작업은 4단계인 Clip Pool과 Unity 행동 매핑 데이터 구축이다.
