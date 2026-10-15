# 완료 증거

체크는 실제 제품 수정/검증 후에만 한다. 2026-10-15 현재 01·02 backend/headless, 03 독립 core/fake/CLI, 04 무결성·private 이전·정리를 검증했다. 실제 Unity 동기화·legacy 지연 보정·공식 Rubric/Qwen 품질 완료를 의미하지 않는다. 명령·실패 재현·환경·한계는 `PROGRESS.md`에 기록했다.

| ID | 요구사항 | 필요한 증거 |
|---|---|---|
| A01 | 기존 snapshot count→세션 | PIN-bound 변경 시험·pinless default6·invalid422 |
| A02 | 실제 a명 | 1/3/6/12/50 목록·ID·평균·RNG·없는짝 검사 |
| A03 | 6명 회귀 | seeds0/1/2026 수정 전후 golden |
| A04 | 질문/명령 membership | valid형식이지만 세션밖인 ID 거부 |
| T01 | 근거·재생 clock 구분 | delayed fake provider+clock, 원래근거 보존 |
| T02 | stale event | 만료 slide/pause action 미발행·delta1회 |
| T03 | 모드·재시도·시계 | 기본false·동일요청동일명령·pause/jump 정책 |
| T04 | a명 배포 | 1/6/12/50 대기·공정성·budget 측정 |
| Q01 | 연구16 계약 | 실제 Rubric 출처/버전·정확한ID·score/null/근거 검사 |
| Q02 | 모듈 교체 | fake/Qwen 경계·선택적OpenAI동일Task·기존10무변경 |
| Q03 | 로컬 실행 | CLI subprocess·OpenAI키불필요·loader재사용 |
| Q04 | 실모델 품질 | 실제 가중치/환경·전문가자료·추론결과; fake로 대체 불가 |
| R01 | 보고서 의미 | missing gaze/null pronunciation·cache isolation |
| R02 | 복구/저장 | QA recovery·DB실패·재시도 정확성 |
| C01 | 도구 제거 가능 | tools 없는 core/backend import·운영 역의존 없음 |
| C02 | 이전 후 삭제 | case/result inventory·측정 정의·새명령 실행 |
| G01 | 클라이언트 무변경 | 보호 hash/route/식 guard·실제 diff 검토 |
| G02 | 회귀 | 전체 테스트 수·실패·skip·환경 제한 |
| X01 | 실제 XR | Unity actor 매핑·수신/재생시계 관측; 첨부 C# 없음 |

- [x] 01 구현·오프라인 검증 (A01–A04: 단계 50개, 기존 129개 성공; G01 guard 성공)
- [x] 02 backend/headless 구현·검증 (T01–T04: timing 27개, 기존 129개, audience 50개 성공; guard 성공. 실제 Unity/legacy 한계는 PROGRESS 참조)
- [x] 03 core/fake/CLI 구현·검증 (assessment 29개, 현재 EVC 통합 235개 및 guard 성공. Q01 공식 자료 미확보; Q02/Q03은 fake/주입 loader 연결·CLI 증거이며 실제 Qwen 실행 아님)
- [ ] 03 실제 Qwen·Rubric 품질 검증
- [x] 04 보완·이전·정리·전체 회귀 (R01/R02/C01/C02: integrity 25개를 포함한 전체 260 passed, 0 failed/skipped/error. CLI 제거 복사본의 기존 제품 129개도 통과. 127개 원본/새 archive hash 대조 후 두 임시 폴더 삭제, 삭제 후 archive 재검증. 7개 Make 명령 실행 및 guard 성공. 실제 Qwen 시도는 exit2/call_count0이며 품질 증거 아님)
- [ ] 실제 웹/XR 확인

G01 guard 성공은 X01 완료가 아니다. Q03 fake 연결 성공은 Q04 품질 증거가 아니다.
