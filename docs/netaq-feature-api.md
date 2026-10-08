# 캘린더·게시판·채점 API 운영 안내

모든 경로는 `/api/personal` 기준이다. 웹 세션 쿠키로 현재 사용자를 확인하며, 요청 본문에 사용자 ID를 넣어서 다른 계정으로 작업할 수 없다. 쓰기 요청은 허용된 서비스 Origin을 검사한다. 비공개 파일은 인증된 URL로만 내려받고 외부 공개 URL로 바꾸지 않는다.

## 게시판과 채널

- `GET /boards`: 현재 계정이 접근할 수 있는 게시판과 채널.
- `GET /boards/{id}/posts?page=1&q=검색어`: 글 목록.
- `POST /boards/{id}/posts`: `{"title":"제목","document":{"version":1,"schemaVersion":2,"richContent":{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"본문"}]}]}}}`.
- 사진·파일은 먼저 `POST /resources?board_id={id}&name={파일명}`에 원본 바이트와 Content-Type으로 올리고, 응답의 URL을 문서에 사용한다. 다른 게시판의 비공개 파일을 그대로 가져올 수 없다.
- `GET /boards/{id}/management`: 게시판 관리자가 변경할 수 있는 회원 역할과 보관한 채널.
- `PUT /boards/{id}/managers/{memberId}`: `{"enabled":true}`. 일반 계정 권한과 전체 서비스 관리자 권한은 별개다.
- `POST /boards/{id}/channels/{channelId}/restore`: 채널 복구.
- `GET /admin/boards/{id}/posts?page=1`: 서비스 관리자의 별도 검토 화면. 일반 게시판 열람 권한을 부여하지 않으며 검토 기록을 남긴다.

외부 자동 게시에는 기존 게시판 연동용 제한된 API 키를 사용한다. 브라우저 세션 쿠키나 전체 관리자 인증을 외부 프로그램에 전달하지 않는다. 키는 관리자 화면의 연동·API에서 대상 게시판과 범위를 확인해 발급한다. DSHS 연동 절차와 중복 방지는 [DSHS 운영 안내](dshs-relay.md)를 따른다.

## 시간표·학점 분류

- 실제 학기의 시간표 저장 API가 연결 일정까지 갱신한다. UI는 변경 후 자동 저장하며 탐색 후보는 캘린더와 분리된다.
- 학년 버튼과 실제 학기의 연결은 `/documents/timetable-stage-map%3A{학교명}`의 revision 문서에 보관한다. 연도를 변경해도 입학 연도/규정 학번은 바뀌지 않는다.
- `GET /student/course-tags`, `PUT /student/course-tags/{과목코드}`: `{"tags":[{"kind":"major_required","major":"수학과"},{"kind":"general","area":"수학"}]}`. 사용자·학교·과목코드 단위이며 공식 규정 원본을 수정하지 않는다.
- Android 위젯 feed의 `view=plan`은 해당 계정의 일간 일정·장소·필기를 PNG로 제공한다. 공유하지 않는 위젯 토큰이 필요하다.

## 아우라 채점

- `POST /aura/grading`: `{"name":"1회차"}`.
- `POST /aura/grading/rounds/{id}/files`: multipart `file`에 PDF 또는 ZIP. PDF 파일은 50MB 이하, ZIP 업로드 100MB 이하, 압축 해제 후 PDF 100개/200MB 이하. 임의 경로는 저장 경로로 사용하지 않는다.
- `PUT /aura/grading/rounds/{id}`: `{revision,data:{answer,first,last,boxes}}`. 페이지 번호는 first/last가 1부터, box.page는 0부터. 박스 x/y/w/h는 회전 정규화된 PDF의 좌상단 기준 좌표다.
- `PUT /aura/grading/files/{id}`: `{revision,data:{ink,questions,feedback,feedbackReviewed}}`. revision 충돌은 409이며 덮어쓰지 않고 로컬 복구본을 남긴다.
- `POST /aura/grading/files/{id}/recognize-jobs` → `GET /aura/grading/jobs/{jobId}`. OCR은 Mac Vision에서 실행한다. 인식하지 못한 점수는 0으로 간주하지 않고 검수를 요구한다.
- `POST /aura/grading/files/{id}/feedback`: 검수 완료한 문항 코멘트만 설정된 Gemini 모델에 전송한다. 학생 이름·원본 PDF·이미지를 보내지 않는다. 생성된 피드백은 확인 후 사용한다.
- `GET /aura/grading/files/{id}/pdf`: 원본과 코멘트 필기를 유지한 사본. 화면용 문항 가이드와 감점 칸 안의 점수 필기는 제외한다.
- `GET /aura/grading/rounds/{id}/results`, `/xlsx`: JSON/엑셀. 미검수 문항이 있으면 최종 엑셀 내보내기를 차단한다.

OCR 설치: `sh ops/build_grading_ocr.sh`. 손글씨 인식 정확도는 실제 필기마다 다르므로 교사가 점수·코멘트를 확인한다. 제출된 기존 클리닉 리포트는 변환하지 않는다.

## Mac 카카오톡

Mac 로그인과 카카오톡 실행, 기존 손쉬운 사용 권한이 필요하다. 지정된 방 이름을 재확인하고, 수신자가 모호하면 보내지 않는다. 전송 여부가 불확실한 작업은 자동 재전송하지 않는다. 클리닉 방 검색은 학교+이름+생명클리닉 → 생명관리방 순서이며 두 검색 모두 결과가 없을 때만 지정된 대체 수신자를 사용한다.

현재 대화 읽기는 카카오톡이 메모리에 로드한 메시지 범위만 보장한다. 따라서 30분 간격으로 바꾸면 중간 메시지가 누락될 수 있어 기존 짧은 확인 간격을 유지한다. Mac 잠금·로그아웃·접근성 응답 지연 시에도 동작을 보장하지 않는다. DSHS 페이지 목록 조회의 30분 주기와는 별개다.
