# 진행 기록

## 현재 상태

하네스만 준비됨. **제품 코드 01–04 미구현.** 아래 항목을 시작 시 실제 작업 레포에 맞춰 갱신한다. upstream SHA/branch는 첨부 참고값일 뿐 현재 작업 HEAD라고 가정하지 않는다.

| 단계 | 구현 | 검증 | 남은 것 |
|---|---|---|---|
| 01-audience-count | 미실행 | 미실행 | snapshot→a명·회귀 |
| 02-playback-clock | 미실행 | 미실행 | stale/clock/부하·소비자 확인 |
| 03-research-assessment | 미실행 | 미실행 | 실제 Rubric·모듈/CLI·가중치 |
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
