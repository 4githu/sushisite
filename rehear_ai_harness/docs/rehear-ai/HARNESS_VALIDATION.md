# 하네스 자체 검증 · 2026-10-15

이 기록은 하네스 도구의 검증이며 **sushisite 제품 수정 완료 기록이 아니다.**

## 수행한 것

- `python3 -m unittest discover -s tools/tests -v`: 하네스 자체 검사 **12개 통과**. baseline 덮어쓰기 거부, 파일 추가/수정/삭제·Unity·route·EVC 식 변경 탐지, 의존 방향, symlink 거부, 없는 단계 테스트, socket 연결 차단, runner 결과 분류를 확인했다.
- 첨부 source의 임시 복사본에서 capture/guard 성공: 보호 파일344개·EVC route11개·핵심 함수5개. runtime→tools 정적 import 위반0개.
- 임시 복사본의 프론트에 의도적으로 파일 추가 후 guard 종료1·ADDED 탐지.
- audience 신규 테스트가 없는 현재 source에 stage 실행 시 종료2·미구현 표시.
- 현재 조사 환경의 pytest/FastAPI/httpx 미설치 시 doctor와 original 테스트가 종료2·환경 미준비 표시.
- 원본 source의 보호 기준은 전후 동일. 제품 파일은 수정하지 않았다.

## 수행하지 않은 것

기존 backend pytest 전체 suite는 의존성 미설치로 미실행이다. runner의 pytest 결과 처리 자체는 stub process/report로 검사했고, socket 차단 hook은 별도 Python 프로세스로 확인했다. pytest plugin과 전체 프로젝트를 결합한 실행은 사용자 개발 환경에서 확인해야 한다.

실제 OpenAI/STT/TTS·GPU Qwen·Unity·Firebase·웹 build·모델 품질 검증은 수행하지 않았다. offline hook은 우발적 Python socket 연결을 막는 개발 도구이며 보안 격리 sandbox가 아니다. 외부 실행 파일이나 이미 로딩된 원격 runner까지 완전히 차단한다고 주장하지 않는다.
