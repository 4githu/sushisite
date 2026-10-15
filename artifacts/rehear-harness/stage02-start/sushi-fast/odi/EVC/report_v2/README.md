# 실행 중인 리포트 V2 코드

현재 서버가 사용하는 `presentation-report-v2` 구현입니다.

- 이전 원본: `../legacy_report_v1/`
- 이 폴더: evidence·Q&A·훈련 추천·5+5 상세 지표가 포함된 V2 실행 코드
- 상위 `../report_*.py`: 기존 import를 유지하는 얇은 호환 진입점

다음 리포트 버전을 추가할 때는 새 폴더를 만들고 상위 호환 진입점의 대상만 바꾸면 됩니다.

## V2 피드백 계약

- 전체 실데이터 예시: `../../../../../rehear-docs/examples/presentation-report-v2-example.json`
- 상세 지표는 `content_metrics` 5개와 `delivery_metrics` 5개입니다.
- 각 지표의 저장 필드는 `id`, `score`, `reason`, `coaching`, `evidence_ids`입니다.
- 화면용 `label`, `rank_label`, `status`는 저장하지 않습니다.
- 사용자 평균과 이전 세션 비교는 피드백이 아니라 세션 조회 응답의 `comparison`에 들어갑니다.
- 질문·답변 원문은 `qa_feedback.questions`에 한 번만 저장합니다. 초기 V2의
  `qa_history`는 읽기 호환용이며 새 V2 JSON에는 출력하지 않습니다.
