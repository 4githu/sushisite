# 아우라 클리닉 리포트 JSON 생성 테스트

기존 `personal_project.db`의 아우라 에디터 JSON을 Gemini에 입력하고 결과도 JSON으로 저장한다. 이미지, PDF, 문서 변환은 처리하지 않는다. Python 외부 패키지는 필요 없고 `sushi-fast/.env`의 `GEMINI_API_KEY`만 읽는다.

## 기본 테스트

```bash
python -m personal_project.make_report_test.migrate
python -m personal_project.make_report_test.test_report --dry-run
python personal_project/make_report_test/run_report_test.py
```

마지막 명령은 DB에서 `경승현 6회차`를 찾아 `output/경승현_6회차.json`에 저장한다.

## 입력 JSON

DB 대신 파일을 넣을 수도 있다.

```bash
python -m personal_project.make_report_test.test_report \
  --input-json /경로/input.json \
  --output personal_project/make_report_test/output/result.json
```

입력은 다음 세 형태를 모두 받는다.

- 표준 입력: `target`, `editorDocument`, `questionChecks`, `sourceNotes`
- 현재 아우라 API 리포트 응답: `contentJson`, `questionChecks`, 학생·학교 정보
- 에디터 원본 문서: `version`, `documentId`, `blocks`

에디터 문서는 `version/documentId/blocks`와 각 텍스트 조각의 `highlightColor`를 그대로 보존한다.

## 평가 모드

```bash
# 기존 학교 평가 양식이 있으면 재사용하고, 없으면 생성 후 DB에 저장
python -m personal_project.make_report_test.test_report --score-mode auto

# 점수 평가 없이 학습 내용만 생성
python -m personal_project.make_report_test.test_report --score-mode none
```

명시한 모드는 학교별 설정으로 저장된다. `auto`에서 처음 생성한 평가 항목은 `clinic_report_score_formats`에 `학교 + 회차 조합`별로 저장되어 같은 범위의 다음 리포트부터 이름과 순서를 재사용한다. 요청 JSON의 `options.scoreMode` 또는 `scoreFormat`으로 한 요청의 동작을 직접 지정할 수도 있다.

출력 스키마 버전은 `aura.clinic-report-output.v2`다. 출력에는 평가 항목의 이름·점수와 `learningContent.paragraphs`만 포함하며, 점수 근거·개선 주제·추후 점검 목록은 포함하지 않는다. 생성 이력에는 입력 JSON, 출력 JSON, 평가 모드와 평가 양식 ID가 기록된다. 명시적 Gemini 캐시를 쓸 수 없는 무료 등급에서는 일반 요청으로 자동 전환한다.

## 모델 비교와 캐시

기본 모델은 `gemini-3.6-flash`이며 화면에서 3.5 Flash와 3.5 Flash-Lite를 함께 선택할 수 있다. CLI 비교는 다음과 같다.

```bash
python -m personal_project.make_report_test.compare_models \
  --models gemini-3.6-flash gemini-3.5-flash-lite
```

결과는 `output/model-comparison/<model-id>.json`에 각각 저장된다. Gemini 명시적 캐시는 다른 모델과 공유할 수 없으므로 `(cache_key, model, prompt_hash)`별로 분리한다. 동일한 `target + model + input_hash + prompt_hash`의 완성 결과가 DB에 있으면 API를 다시 부르지 않고 재사용한다. 에디터 JSON이나 프롬프트가 바뀌면 해시가 달라져 새 결과를 만든다. `--force`는 비교 실험 때만 강제로 다시 생성한다.
