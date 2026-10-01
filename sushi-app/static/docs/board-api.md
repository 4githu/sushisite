# NETAQ 게시글 자동 등록 API

기준 URL: `https://chobab.app/api/personal/board-api`

## 1. 키 발급

로그인 → 게시판 선택 → ‘게시글 자동 등록 · API 키’에서 발급합니다. 키는 선택한 게시판에만 적용됩니다. 읽기(read), 글 작성·수정(post), 댓글(comment), 파일 업로드(upload)를 필요한 만큼만 선택하세요. 유효기간은 7/30/90일이며 언제든 같은 화면에서 폐기할 수 있습니다. 원문 키는 발급 직후 한 번만 표시됩니다.

요청 헤더: `Authorization: Bearer YOUR_API_KEY`. 키를 URL, 게시글, Git 저장소, 프런트엔드 코드에 넣지 마세요. 서버 환경변수 `NETAQ_BOARD_API_KEY`에 보관하세요. 이 키는 개인 캘린더·아우라·개인 자료·카카오톡 제어 API에 사용할 수 없습니다. 게시판 ID는 주소의 `?board=숫자`에서 확인합니다.

## 2. Python으로 사진과 글 올리기

Python 3와 `requests`가 필요합니다. 문서는 Tiptap JSON을 `richContent`에 넣습니다. 단순 글도 아래처럼 문단으로 만들면 됩니다. 이미지 대신 파일을 첨부하려면 이미지 노드 대신 `attachment` 노드의 `attrs`에 `href`, `name`을 넣으세요.

```python
import os, uuid, requests
from pathlib import Path

base = 'https://chobab.app/api/personal/board-api'
board_id = 1  # 발급 시 선택한 게시판
session = requests.Session()
session.headers['Authorization'] = 'Bearer ' + os.environ['NETAQ_BOARD_API_KEY']

photo = Path('photo.png')
with photo.open('rb') as stream:
    response = session.post(
        f'{base}/boards/{board_id}/resources', params={'name': photo.name},
        data=stream, headers={'Content-Type': 'image/png'}, timeout=60)
response.raise_for_status()
attachment = response.json()

content = [
    {'type': 'paragraph', 'content': [{'type': 'text', 'text': '오늘 공유할 자료입니다.'}]},
    {'type': 'image', 'attrs': {'src': attachment['url'], 'alt': photo.name}},
]
payload = {'title': '자료 공유', 'document': {
    'version': 1, 'schemaVersion': 2, 'documentId': str(uuid.uuid4()),
    'blocks': [], 'richContent': {'type': 'doc', 'content': content}
}}
# 실제 자동화에서는 키와 payload를 작업 DB에 먼저 저장하세요.
# 네트워크 오류 시 동일 키 + 동일 payload로 재시도해야 중복을 막습니다.
request_key = str(uuid.uuid4())
response = session.post(f'{base}/boards/{board_id}/posts', json=payload,
    headers={'Idempotency-Key': request_key}, timeout=30)
response.raise_for_status()
post = response.json()
print('https://chobab.app' + post['url'])

# comment 권한이 있는 키만 사용할 수 있습니다.
response = session.post(f"{base}/posts/{post['id']}/comments",
    json={'content': '추가 설명입니다.'},
    headers={'Idempotency-Key': str(uuid.uuid4())}, timeout=30)
response.raise_for_status()
```

업로드는 multipart가 아닌 파일 원문(body)입니다. 반환 `url`은 로그인 브라우저에서 사용할 첨부 주소이며 공개 링크가 아닙니다. 자동화로 내려받으려면 Bearer 헤더를 붙여 `/resources/{id}`를 요청하세요. 다른 게시판이나 개인 자료를 첨부하면 거절됩니다. 업로드 재시도는 새 파일을 만들므로 성공 응답의 ID를 보관하세요.

## 3. 엔드포인트

| 메서드·경로 | 권한 | 내용 |
|---|---|---|
| GET `/boards/{id}/posts?q=&page=1` | read | 제목·본문 검색, 30개 단위 목록 |
| GET `/posts/{id}` | read | 문서, revision, 댓글 |
| POST `/boards/{id}/posts` | post | `{title, document}`; Idempotency-Key 필수 |
| PUT `/posts/{id}` | post | `{title, document, revision}`; 작성자 또는 관리 권한 필요 |
| POST `/posts/{id}/comments` | comment | `{content, parent_id?}`; 답글은 댓글 ID 지정; Idempotency-Key 필수 |
| POST `/boards/{id}/resources?name=...` | upload | 파일 원문, 올바른 Content-Type |
| GET `/resources/{id}` | read | 같은 게시판 첨부파일 다운로드 |

글 수정은 먼저 GET으로 최신 revision을 읽고 PUT에 넣습니다. 409이면 최신 글과 작성 중인 글을 보존한 뒤 병합하세요. 자동 덮어쓰기를 하지 마세요. 공지·삭제·복구·권한 관리는 로그인 웹 화면에서 수행합니다. API 키로 관리자 권한을 새로 만들 수 없습니다.

## 4. 오류·한도·재시도

- 400: 잘못된 댓글 대상, 누락된 Idempotency-Key 등.
- 401: 키 누락, 만료, 폐기. 새 키를 발급하세요.
- 403: 키의 게시판/작업 범위 또는 계정의 현재 접근 권한 부족.
- 404: 글이나 파일 없음, 삭제된 글.
- 409: revision 충돌 또는 같은 Idempotency-Key에 다른 본문 사용.
- 413: 파일 50MB, 문서 500KB, 계정 자료 총량 기본 1GB 제한.
- 422: 요청 형식 오류. 응답 `detail` 확인.
- 429: 키당 분당 120회 초과. `Retry-After`만큼 기다리세요.

Idempotency-Key는 8~120자입니다. 글·댓글 생성은 키와 결과를 같은 DB 트랜잭션으로 저장합니다. 범위는 계정·작업·대상입니다. 같은 키/내용의 재요청은 기존 ID를 반환합니다. 타임아웃·5xx 재시도에도 원래 키와 본문을 유지하세요. 댓글 하나마다 별도 키를 쓰세요. 개인정보·토큰·첨부 원문을 오류 로그에 남기지 마세요.

## 5. 보안 및 운영

- 서버는 키 원문 대신 SHA-256 해시를 저장하고 매 요청 만료·폐기·현재 ACL을 검사합니다. 명시적인 접근 거부가 허용보다 우선합니다.
- 파일은 인증된 경로로만 제공되며 비공개 파일 URL만 알아서는 열 수 없습니다. HTML/SVG 등 실행 가능한 형식은 원본 다운로드로 제공하고 nosniff/sandbox 헤더를 사용합니다. 악성코드 검사 기능은 별도로 제공하지 않습니다.
- 로그인 쿠키를 사용하는 키 관리/게시판 쓰기는 다른 출처의 요청을 거절합니다. 자동화 API는 쿠키 대신 Bearer를 요구합니다.
- DB와 첨부 저장소는 접근을 제한하고 함께 백업해야 합니다. 키 유출 시 즉시 폐기하고 대체 키를 발급하세요.
- 운영자 환경변수: `COMMUNITY_ADMINS`(쉼표로 구분한 사용자 ID), `PERSONAL_RESOURCE_QUOTA_BYTES`(기본 1073741824). 관리자 지정은 기존 계정을 확인한 뒤 운영자가 수행합니다.

## 6. 카카오톡 연결과의 차이

Mac 브리지는 공식 카카오 API가 아니라 로그인된 Mac 앱의 보조 접근 자동화입니다. 자료 화면에서 허용된 소유자만 사용하며 게시판 API 키로 원격 조작할 수 없습니다. 정확한 방 이름을 확인하고, 이미 전송됐는지 불확실한 작업은 자동 재전송하지 않습니다.

멘션 감지는 현재 로드된 대화에 한정되며 공식 메시지 ID나 과거 전체 수집을 보장하지 않습니다. 바로 다음 사진만 연결하고, 다른 발신자/중간 메시지가 있으면 연결하지 않습니다. 사진은 앱에서 복사한 PNG이며 원본 파일의 인코딩을 보장하지 않습니다. 수집함은 개인용이고 게시판 공개는 별도 게시 동작입니다. 현재 Mac 어댑터는 지정 테스트 방에서 검색·글/사진 전송·멘션 다음 사진 가져오기를 확인했습니다. 새 Mac이나 다른 실행 계정에서는 보조 접근 권한과 동작을 다시 확인해야 합니다. 로그인 HTTP 요청부터 운영 대기열 워커까지의 무인 연속 동작 검증은 별도입니다.
