# 학교 목록·한양대 강의 연동 — 2026-10-02

- 기본 학교 11개, 학교별 학과 부분 이름·초성 선택. 다른 학교 추가 경로 유지.
- 학교 포털 입력 제거, 강의·학식·공식 규정 연동 여부 분리 표시.
- 한양대 공식 비로그인 수강편람: 2026-1 5483개, 2026-2 4961개 고유 강좌. 캠퍼스와 수업번호 구분, 중복 설강학과 병합, 버전 캐시와 기존 Worker 검색 연결.
- 비서울대 수강 이력은 해당 학교의 실제 시간표에서 계산하며 서울대 동등 과목·교양 분류를 적용하지 않음.
- 공개 원천, 운영자 갱신 명령, 아직 미연동인 학교와 에브리타임 제한은 `sushi-app/static/docs/campus-course-research.md` 참고.

## 검증

- pytest: test_campus_catalog / test_netaq_relay_campuses / test_workspace_upgrade / test_student_catalog, 32 passed.
- Svelte check: 0 errors, 0 warnings. Node production build 성공. Svelte MCP 미제공으로 compiler 및 브라우저 검수 사용.
- 격리된 QA 계정에서 한양대 선택, 컴퓨터 부분 검색 → 서울/ERICA 학과 제안, 저장 성공 및 실제 연동 상태 확인.
- 390px 모바일과 데스크톱 화면 검수. 초성 정규화 오류 발견·수정 후 `ㅋㅍㅌ`로 두 학과 검색 확인.
- 한양대 시간표 4961건 표시 및 미분 검색 66건 확인. UI의 담기 클릭은 검수 브라우저에서 상태 변경을 확인하지 못했으므로 클릭→자동 저장의 전체 UI 검증은 미완료. 실제 강좌 저장·캘린더 생성·재저장 중복 방지 및 학교별 이력 격리는 백엔드 통합 테스트로 통과.

## 배포

- 백업: `/Users/sagi/Documents/sushisite-deploy-backups/20261002-145414-campus-catalog` (DB 3개와 이전 build-node).
- 이전 immutable 해시 파일 보존 후 새 Node 빌드로 교체, 기존 frontend/backend launch agent 재시작.
- 전송 중 카카오 outbox 0개를 확인한 뒤 재시작. 카카오 동작 변경 없음.
- 운영 학교 목록 11개, DB quick_check=ok.
- 운영 `/docs/campus-course-research.md` HTTP 200, 보호된 `/api/personal/student/schools` 비로그인 HTTP 401 확인.
- 한양대는 가져온 학기 스냅샷 제공이며 실시간 인원 추이와 정기 자동 갱신은 미구현. 다른 9개 학교는 카탈로그 미연동으로 표시.
