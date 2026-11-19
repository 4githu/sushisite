> 운영 현황 갱신 — 2026-11-05: `classroom_delivery.py`가 기존 운영 백엔드 프로세스에서 매일 09:00 KST에 실행되며, 서버의 Kakao 작업 잠금을 공유합니다. 소유자 전용 `/api/personal/aura/classroom-requests/{status,preview,automation}` API에 연결됐습니다. 사용자가 지정 조교방으로 매일 09시 자동 발송을 허용해 활성화했습니다. 미확정 modality는 임의 추정하지 않으며 발송을 차단합니다. 아래 합성 전용/미설치 기록은 과거 이력입니다. 최종 전송의 중복·불확실 상태는 자동 재시도하지 않습니다.

# Aura 강의실 요청: 비활성 아웃박스·스케줄 설치 게이트

## 현 상태 (2026-10-27)

`personal_project/aura_classroom_outbox.py`는 **합성 입력 전용** 선택기와 SQLite 멱등 아웃박스 코어다. 실제 스케줄 실행기, 운영 DB 입력 어댑터, live 카카오 브리지 연결은 없다. `approved=False`가 기본이며 코드 어디에도 자동 시작 등록을 하지 않았다. `tick(..., approved=True)`는 *테스트가 주입하는 mocked bridge 전용 경로*로 사용했다. 이를 운영에서 승인 토글로 오해하면 안 된다. 카카오톡 메시지는 보내지 않았고 launchd 등록도 하지 않았다.

- 로컬 실행일 `D` 13시대 Asia/Seoul → `D+1` 시작 시각의 취소되지 않은 회차. 시작의 현지 날짜로 선별하며 naive legacy는 서울 벽시계, offset/Z는 instant로 변환한다. 종료 시각 누락·역전, ID/대상 누락, 중복 ID, modality 없음은 발송 차단. 대면 0건은 건너뜀.
- 모든 대면을 강의실 배정 요청 대상으로 포함하고, 비대면은 어느 대면과도 끝↔시작 간격이 3600초 미만이면 같은 단일 요청문의 **배정 요청 대상 회차로** 한 번만 포함한다. 정확히 3600초 이상은 제외한다. 원격 회차에는 `(비대면)`만 표시하며 `강의실 불필요`라고 쓰지 않는다. 별도 경고/알림/발송 채널은 없다. 내부 진단용 `nearbyRemoteRounds`에는 원격 회차 ID, 인접 대면 회차 ID, 최소 초 간격만 보관한다. 요청문은 기존 UI `roomRequestText`의 날짜/시간/학교/학생 구조를 참고하지만 UI의 description 정규식과 원격만 있는 날 발송 문구는 재사용하지 않는다. 말미는 `위 일정의 강의실 배정 부탁드립니다.`이며 **문구 자체는 실제 발송 전 사용자 확인이 필요**하다.
- `(user_id, run_date, purpose=classroom_request)` UNIQUE 선점. 실행 중 재시작은 `unknown`, 같은 날 재호출은 상태만 반환한다. 최초 실행이 13시대를 넘기면 `missed_window`; 잠금·창 부재·확정 부재는 결코 김지후라는 제목만으로 fallback하지 않는다. 방은 `unique_exact` 검색 근거와 동일 제목을 확인하며 메시지 전 일정 재조회. 결과의 `targetRoom`, `selectedRoom`, `fallbackReason`, `reason`, `deliveryStatus`를 `status(db,user_id,run_date)`로 조회한다. 메시지 본문·학생 이름은 아웃박스에 남기지 않는다. unknown/partial은 수동 확인 전 자동 재발송하지 않는다.

## 활성화 **이전** 통합 게이트

### 최종 재조회→GUI 클릭 경합 및 잠금 경계 검토 (합성 fixture 한정)

- 합성 SQLite에서 검색 직후 재조회 이후, 주입된 `bridge('send')`의 mock 클릭 직전에 **별도 SQLite writer가 동일 회차 modality를 변경·commit**하도록 재현했다. 이전 코드는 GUI mock이 `sent=True`를 반환하면 오래된 문구에도 `succeeded`를 기록했다(RED 테스트에서 `succeeded != unknown`). 현재는 send 반환 직후 selected-day 계획을 다시 읽어 다르면 `schedule_changed_during_send`/`unknown`으로 **감지하고 재시도하지 않는다**. 다만 mock 클릭은 이미 발생했다. 추가 재조회도 마지막 읽기와 실제 클릭/관찰 사이 틈을 없애지 못한다. GUI와 SQLite 사이 단일 원자 트랜잭션·Kakao의 조건부 전송 API가 없으므로 **송신 시점 일관성은 보장 불가**다. DB 쓰기 잠금을 GUI 조작 전체에 걸쳐 유지하는 방식도 독립 UI/다른 DB writer/타임아웃·장애에 대한 원자성 증명이 아니며 채택하지 않았다.
- 실제 브리지 코드 정적 검토(`ops/kakao_bridge.swift`): 진입 때 `sessionLocked()` 검사(명시적 잠금 또는 세션 사전 자체 조회 실패 시 중단), 검색 반복 중 재검사. 다만 `CGSSessionScreenIsLocked` 키가 없거나 Bool 변환이 실패하면 현재 구현은 `false`로 취급하므로 그 경우 잠금 fail-closed가 증명되지 않는다. 메인 창 8초 이내 부재 중단, `roomWindow()` 정확한 제목·composer 창 1개 검사, 검색 `unique_exact` 근거 요구. send는 창·빈 composer·본문 입력·전송 버튼을 확인한 뒤 클릭하고 결과를 관찰한다. **send 진입 이후 클릭 직전에는 세션 잠금 재검사/DB 스냅샷 검사가 없고 GUI와 DB는 결합되지 않는다.** 창 재확인은 recipient/title만 다루며 일정 변경을 검증하지 않는다. `caffeinate`는 잠금 해제나 회차 잠금이 아니다. 실제 GUI 상태·권한·Kakao 화면은 검사하지 않았다.
- mock 검색에서 잠금·메인 창 부재·다른 방의 `confirmed_absent`는 모두 `blocked`/`recipient_unverified`, 전송 호출 0회로 검증했다. 정확한 **원래 방**의 확정 부재여도 신원 미확인 fallback을 막는다. 기존 Swift `search-simulation` 잠금/창 부재 및 중복 검색 테스트는 실제 Swift 소스의 순수 검색 판정만 확인하며 실제 GUI 경합 증명은 아니다.
- 운영 기준: 회차 편집과 전송을 원자적으로 직렬화할 검증 가능한 설계(혹은 변경 가능한 회차에 대한 수동 동결·사람의 직전 일정/대상/본문/방 확인과 전송 책임)가 승인되기 전 **스케줄 및 실제 브리지 연결 금지**. 경합·잠금·창 부재·검색 지연·unknown/partial/성공 이후에는 같은 날짜/목적 키를 자동 재시도하지 않고 상태를 보존해 사람이 일정 및 대화방 결과를 확인한다. 누락/불확실성을 방 부재로 추정하거나 이름만 같은 개인 채팅에 대체 발송하지 않는다. 사용자 별도의 외부 메시지 승인과 자동화 승인 모두 필요하다.
- 변경: `aura_classroom_outbox.py`(사후 감지, 확정 부재의 방 ID 확인), `tests/test_aura_classroom_input.py`(실제 합성 DB writer 경합), `tests/test_aura_classroom_outbox.py`(잠금/창 부재/잘못된 방 mock), 이 문서. 집중 회귀 41 passed/7 warnings, 백엔드 전체 `personal_project/tests` 219 passed/12 warnings. 모두 deprecation 경고이며 운영 DB·실제 카카오 세션·실제 전송·launchd·송신 시각 일관성은 미검증이다.

1. 별도 카드 `t_f26a1cf3`에서 권위 있는 회차별 modality 저장 및 API 조회 계약을 합성 DB로 구현·재조회 확인했다. 다만 기존 회차는 `unverified`로 이관되고 운영 DB 입력 어댑터는 없다. 학교 ID·회차 ID·대상 ID의 운영상 매핑 및 혼합 회차 정책을 사용자가 검증하기 전 미래 일정에 기본 대면을 부여하지 않는다. 미확인 회차가 있는 날은 막힌다.
2. 사용자로부터 외부 톡 실제 전송과 매일 자동화 활성화를 **별도로 승인**받는다. 김지후 개인 1:1은 자기채팅이 아닌 대화 유형/안정된 신원 식별 근거가 확보될 때까지 무조건 차단. 현재 코어는 group primary만 합성 구현했고 확정 부재 시 fallback 자체가 없다. 실패 때의 수동 확인 채널과 알림 담당도 확정한다.
3. 합성 SQLite 범위 읽기 어댑터 `aura_classroom_input.read_owner_rounds(user_id, now)`를 구현했다. **인증된 소유자 ID를 호출자가 주입**해야 하며 어댑터가 신원을 검색하거나 운영 ID를 하드코딩하지 않는다. `r.user_id`로 범위를 제한하고 학교/이벤트 소유자가 다르면 실패한다. 단일 SQLite `BEGIN` 읽기 스냅샷에서 대상 ID를 포함한 회차를 조립한다. 문자열 `from/to` SQL 비교 대신 소유자 회차의 시작 instant를 해석해 D+1 KST 날짜로 필터한다(naive는 서울 현지 벽시계, offset/Z는 UTC instant). 이는 합성 DB 테스트 전용 계약이며 운영 DB 접속·자동 호출 경로는 없다. 별도 테스트 서버의 mock tick만 이 어댑터를 사용한다. 다수 회차 계정의 무제한 전체 읽기 비용은 운영 연결 전 인덱스/범위 전략 검토가 필요하다. UI와 동일 fixture의 텍스트·선택 ID는 Playwright 통합 테스트로 비교한다. 프리뷰와 검색 직후 재조회 계획에는 회차/학교/대상 ID·이름·시각·modality·상태를 해시한 비영속 스냅샷을 비교하여 **본문이 같아도 대상 ID가 바뀌면 전송을 차단**한다. 해시와 학생 이름은 outbox에 저장하지 않는다. 단, 최종 재조회와 GUI 클릭 사이 원자적 트랜잭션은 성립하지 않으므로 실제 GUI 전송 활성화의 승인 근거가 아니다. 혼합 학생별 모드는 미확정이며 회차별 modality만으로 개별 학생 모드를 추론하거나 발송하지 않는다. 운영 소유자 ID 매핑·혼합 정책·UI 문구·대상 방은 사용자 확인 전 미승인이다.
4. 실제 Kakao GUI에서 잠금/메인 창 부재·지연 검색·중복·전송 직후 timeout을 검증하되 승인 전 실제 대화 열람·발송 금지. 합성 브리지는 실제 전송 확인을 보장하지 않는다. 화면 깨우기/caffeinate는 잠금 해제가 아니며 비밀번호/OTP 우회 금지.
5. 사용자 GUI 세션이 필요한 만큼 서버 daemon보다 `~/Library/LaunchAgents`의 **로그인 사용자 LaunchAgent**가 적합하다. 운영 어댑터를 별도 명령으로 만든 뒤에만 `StartCalendarInterval`의 Hour=13 Minute=0과 `RunAtLoad=false`, `KeepAlive=false`, 표준 출력/오류 경로 및 최소 권한 파일 경로를 설정한다. launchd 캘린더 시각은 **호스트 현지 시간대**이므로 호스트가 Asia/Seoul인지 별도 확인하고 코드도 `zoneinfo`로 재검증한다. 절전/로그아웃/잠금으로 못 보낸 것은 catch-up 자동 발송하지 않고 `missed_window` 또는 실패 알림으로 수동 복구한다. `caffeinate`나 전역 sleep 해제 설정을 설치에 포함하지 않는다.
6. 설치 전 합성 시간 이동/동시 실행/중단 재개/외부 UI mock 검증과 수동 승인을 마친 뒤 plist를 별도 심사한다. 그때 승인된 plist만 `launchctl bootstrap gui/$(id -u) <plist>`로 등록하고 `launchctl print gui/$(id -u)/<label>`에서 상태를 확인한다. **이 문서는 설치 명령 실행 승인이 아니다.**

## 조회·수동 복구·롤백

합성 테스트: `cd sushi-fast && PYTHONPATH=. .venv/bin/pytest -q personal_project/tests/test_aura_classroom_input.py personal_project/tests/test_aura_classroom_outbox.py` 및 `PYTHONPATH=. .venv/bin/pytest -q personal_project/tests`; 브라우저 동일 fixture 게이트: `cd sushi-app && npx playwright test tests/aura-classroom-integration.e2e.ts --reporter=line`. `approved=True`는 격리 테스트 서버 mock에만 쓰고 실제 실행 권한으로 사용하지 않는다.

운영 어댑터 설치 후 장애 시에는 우선 GUI 잠금/메인 창 상태를 사용자가 직접 확인하고, **대화방 실제 발송 여부를 사람이 확인**한다. `status`의 `unknown`, `partial`, `running`을 임의 `queued`로 바꾸거나 동일 key를 지우지 않는다. 수동 재발송은 별도 사용자 승인과 새로운 수동 목적 키로 감사 기록을 남겨야 한다. 개인 대화 내용을 로그에 남기지 않는다. 롤백은 먼저 `launchctl bootout gui/$(id -u) <plist>`로 작업을 중지하고 plist를 격리/제거, 이전 코드를 되돌리되 outbox DB와 감사 상태는 보존한다. 사용자가 전송 결과를 확인하기 전에는 삭제/초기화하지 않는다. 현재는 등록된 plist/운영 DB 변경이 없어 롤백 대상이 없다.
