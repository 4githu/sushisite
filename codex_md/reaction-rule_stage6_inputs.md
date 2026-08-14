# AI 청중 반응 파이프라인 6단계 입력/STT 결과

> 선행 단계: `reaction-rule_stage5_session.md` 완료  
> 단계 상태: 완료

## 구현 결과

- `config.py`에 파일 제한, provider timeout/retry, session, 로그 관련 환경 설정을 검증 가능한 상수로 모았다.
- `inputs.py`에 chunk 단위 업로드, audio/slide 확장자·MIME·크기 검증, 빈 파일 거부를 구현했다.
- 임시 오디오는 성공과 모든 예외 경로에서 삭제된다.
- PDF/PPT/PPTX 슬라이드 저장과 PDF 지연 import 추출 경계를 추가했다.
- 슬라이드 인덱스, BCP-47형 언어 태그, gaze, 발화 위치, slide reference, 사건 JSON을 `SegmentContext`로 정규화한다.
- `speech2text.py`의 Deepgram SDK import를 호출 시점으로 늦추고 provider Protocol과 async timeout/retry 경계를 추가했다.
- Deepgram 응답을 transcript/word timing/confidence 표준 모델로 변환한다.
- `SpeechWord`는 유한 범위, confidence, `end>=start`를 검증한다.

## 검증 결과

```text
$env:PYTHONPATH='sushi-fast'
.\.venv\Scripts\python.exe -m pytest sushi-fast/odi/EVC/tests -q

........................ [100%]
24 passed
```

추가 검증 항목:

- 임시 audio 생명주기와 크기 초과 정리
- 지원하지 않는 slide 형식 거부 및 잔여 파일 없음
- slide 없는 index, 언어 태그, 사건 key/range 검증
- slide transition의 slide reference 파생
- Deepgram 정상 응답 정규화와 빈/잘못된 응답 거부
- 잘못된 word timing 거부
- 외부 SDK 없이 fake provider retry 실행

## 완료 판정

정상 음성, 빈/과대/미지원 파일, 잘못된 context, 공급자 형식 오류를 예측 가능한 예외 또는 표준 모델로 처리하고 임시 파일을 남기지 않는다. 후속 평가기는 Deepgram 세부 형식에 의존하지 않는다. 따라서 6단계 완료 기준을 충족한다. 다음 실제 작업은 7단계인 내용/전달 평가 파이프라인 구현이다.
