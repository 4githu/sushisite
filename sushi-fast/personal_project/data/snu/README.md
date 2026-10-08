# 서울대 강의·이수규정 스냅샷

출처: https://github.com/Rekhet/class-checker 의 `data/classes` 및 `data/grad_req`.
원본 데이터의 날짜, 커밋과 가져온 시점은 `index.json`에 기록된다. 강의 내용은 원본 그대로 JSON gzip으로 저장하며, 이수규정은 원본의 학과/학번 인덱스와 문서 200개를 묶었다. 원본 서비스는 서울대학교 수강편람을 가공한 비공식 서비스다. 실시간 정원이나 학교의 공식 졸업 판정으로 취급하지 않는다.

- 2020~2026, 비어 있지 않은 27개 학기, 강좌 레코드 110,162개
- 2026년 2학기 8,652개 강좌
- 서버가 학기별 검색·필터·페이지네이션을 수행하며 검색할 때마다 학교를 크롤링하지 않는다.
- 데이터 갱신: 공개 저장소를 새로 내려받아 내용을 확인한 다음 저장소 루트에서 `python3 ops/update_snu_catalog.py /path/to/class-checker` 실행. 생성된 데이터 차이를 검토하고 백엔드를 재시작한다.
- 학교별 검색 어댑터를 늘릴 경우 `snu_catalog.py`와 정규화된 Course/Slot 경계를 사용한다. 현재 다른 학교는 직접 입력을 지원한다.

참고한 SNUTT 프로젝트: https://github.com/wafflestudio/snutt (MIT), 웹 프런트엔드: https://github.com/wafflestudio/snutt-frontend . 이번 구현은 기존 Svelte/FastAPI 앱의 인증·일정 저장소에 연결하며 SNUTT 계정/API 인증정보를 요구하지 않는다.
