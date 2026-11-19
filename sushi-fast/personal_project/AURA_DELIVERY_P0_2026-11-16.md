# Aura 리포트 발송 P0 — 2026-11-16

## 변경과 이유
- 두 클리닉 방의 부재가 각각 확정되고 본계정이 유일 정확 일치한 경우, 승인된 본계정 대체 전달을 이미지 선행이 아닌 리포트 텍스트 단독으로 수행한다. 즉시·예약 경로 모두 PDF/이미지 생성이 대체 발송의 선행 조건이 아니다. 텍스트 응답이 엄격한 성공이 아니거나 예외인 경우 불확실 상태로 처리하고 자동 재시도하지 않는다.
- 불확실·부분 전송 뒤 재전송을 기대하던 합성 테스트를 최신 안전 조건에 맞췄다. 확인된 성공 뒤 첨부 정리도 별도 독립 시나리오로 유지한다. 공유 DB로 인해 결과가 섞이던 해당 테스트는 격리 SQLite를 사용한다.
- 기존 담당 작업의 공유 파일을 보존하면서 제한적으로 수정했다. 즉시/예약 원자 경합, 동일 요청, 응답 유실, 이미지 성공 후 텍스트 실패와 엄격한 receipt 검증은 격리 합성 테스트다.

## 검증
- `sushi-fast/.venv/bin/python -m pytest personal_project/tests -q --tb=short`: 465 passed, 경고 12건. 외부 카카오 호출이 아닌 합성 sender/격리 DB 검증이다.
- Playwright 로컬 빌드, mocked API의 일반 발송 경계와 본계정 텍스트 대체 결과: 2 passed. 실제 카카오 앱 발송이나 운영 화면 확인이 아니다.
- 원래 7개 실패 중 일부는 불확실·부분 발송 직후 재발송을 가정하는 구 테스트였고, 본계정 이미지 선행 가정도 최신 정책과 불일치했다. 나머지 공유 테스트 DB 상태 오염은 격리했다.

## 미확인 및 경계
- 특정 실제 요청을 식별할 요청 ID 또는 발생 시각과 로그 위치가 없어 동일 요청의 비식별 단계·실제 수신 결과를 확인하지 못했다. 불확실한 건은 재발송하지 않았다.
- 실제 전송, 운영 DB 변경, 운영 배포 및 실환경 end-to-end 확인은 하지 않았다. 공유 워크스페이스에 다수의 다른 미커밋 변경이 있어 전체 빌드 산출물을 운영 반영했다고 주장하지 않는다.
- 아래 후속 수정 전에는 동일 requestId 성공 replay에 destination이 없었다.

## 후속: 즉시 발송 결과 계약과 안전성
- `aura_clinic_immediate_requests`에 receipt_json을 추가하는 호환 마이그레이션을 구현했다. 요청 완료 결과에는 확인된 대상·대체 사유·형식과 recipient/images/text 단계만 저장하며 리포트 본문은 저장하지 않는다. 방 이름은 식별 가능하므로 인증된 소유자의 요청 결과 DB에만 저장하고 로그에 추가하지 않는다. 구 레코드에 없던 대상·단계는 추정하지 않는다.
- 최초 응답·같은 ID 성공 replay·GET이 동일한 발송/완료 상태와 보존된 receipt를 반환한다. 전송 성공 후 완료 저장 실패는 sent/verified + completionStatus=pending이다. 요청 미발견은 unknown이며 미발송 증거가 아니다. failed/not_started에만 retryable=true이고 수동 재시도는 새 UUID를 사용한다. partial/unknown/sending은 재전송하지 않는다.
- 격리 SQLite 및 합성 sender 전체 회귀: `.venv/bin/python -m pytest personal_project/tests -q --tb=short` → 470 passed, 12 warnings. 별도 신규 테스트 5개는 최초·replay·조회, 부분 결과, 완료 저장 실패, 확정 실패 후 동시 재시도와 합성 브리지 이미지 성공/안내문 실패의 단계 결과를 검증했다. 기존 테스트가 두 방 부재 대체, 불확실 응답, 즉시/예약 경합을 검증한다.
- 검토 수정: sender가 보류된 `state=sending` 동안 GET과 동일 ID replay는 `deliveryStatus=unknown`, `retryable=false`를 반환한다. 상태는 진행 중이지만 실제 외부 발송 여부는 확정할 수 없기 때문이다. 합성 경합 테스트에서 수정 전 `not_started` 실패를 재현하고 수정 후 조회·replay 및 단일 sender 호출을 확인했다. 전체 회귀 470 passed, 12 warnings.
- 공유 파일 `router.py`, `native_kakao.py`, `clinic_scheduled_delivery.py`의 기존 변경을 보존했다. UI 구현·통합 검증은 별도 기존 카드에서 진행된다. 실발송·운영 DB 마이그레이션·운영 배포는 하지 않았으며 기존 실제 사건의 수신 여부는 여전히 확인되지 않았다.
