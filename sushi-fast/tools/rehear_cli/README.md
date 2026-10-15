# Research16 offline tools

`sushi-fast`에서 기존 `.venv/bin/python`을 사용한다. fake는 점수를 만들지 않는 계약 검사용이다. 공식 Rubric/Policy와 Qwen 환경/가중치는 별도로 제공해야 한다. `odi`와 `rehear_ai`는 이 tools를 import하지 않는다.

```sh
make -f Makefile.ai ai-doctor
make -f Makefile.ai ai-contracts OUTPUT=/tmp/rehear-contracts.json
make -f Makefile.ai ai-eval INPUT=odi/EVC/tests/fixtures/TEST_ONLY-stage04-evidence.json RUBRIC=odi/EVC/tests/fixtures/TEST_ONLY-stage04-rubric.json OUTPUT=/tmp/rehear-eval.json EXTRA_ARGS=--allow-test-rubric
make -f Makefile.ai ai-repeat INPUT=odi/EVC/tests/fixtures/TEST_ONLY-stage04-evidence.json RUBRIC=odi/EVC/tests/fixtures/TEST_ONLY-stage04-rubric.json OUTPUT=/tmp/rehear-repeat.json EXTRA_ARGS='--allow-test-rubric --repeat 3'
make -f Makefile.ai ai-compare INPUT=odi/EVC/tests/fixtures/TEST_ONLY-stage04-evidence.json RUBRIC=odi/EVC/tests/fixtures/TEST_ONLY-stage04-rubric.json OUTPUT=/tmp/rehear-compare.json EXTRA_ARGS='--allow-test-rubric --other-engine fake'
make -f Makefile.ai ai-replay INPUT=odi/EVC/tests/fixtures/TEST_ONLY-stage04-evidence.json RUBRIC=odi/EVC/tests/fixtures/TEST_ONLY-stage04-rubric.json OUTPUT=/tmp/rehear-replay.json EXTRA_ARGS='--allow-test-rubric --result /tmp/rehear-eval.json'
make -f Makefile.ai ai-bench INPUT=odi/EVC/tests/fixtures/TEST_ONLY-stage04-evidence.json RUBRIC=odi/EVC/tests/fixtures/TEST_ONLY-stage04-rubric.json OUTPUT=/tmp/rehear-bench.json EXTRA_ARGS='--allow-test-rubric --repeat 3'
```

출력 경로는 새 파일이어야 한다. 예시 Rubric/Anchor/Policy는 모두 TEST_ONLY이며 연구 점수 정의가 아니다. `eval`은 AssessmentResult와 `OUTPUT.run.json` metadata를 남긴다. compare/repeat/bench는 명시된 파일에 모든 성공 결과와 run metadata를 저장한다. 일반 로그에는 raw 입력/reason/오류 원문이 없다. 실패 run은 failures/error_type/call_count를 기록하며 exit2다. 입력/config 자체가 유효하지 않으면 결과 파일 없이 exit2다.

`ENGINE=qwen_local CONFIG=LOCAL-CONFIG.json`을 명시하면 로컬 Qwen 경계를 사용한다. 기본은 fake다. 두 engine 비교에는 `EXTRA_ARGS='--other-engine qwen_local --other-config LOCAL-CONFIG.json'`을 사용한다. 두 engine 모두 같은 Research16 task와 bundle을 받는다. OpenAI의 기존 10개 설명 비교는 이 명령에 없다. 실제 Qwen 실행은 torch/transformers/필요 시 peft와 고정 runtime 버전, base/tokenizer/adapter 로컬 경로/revision을 요구하며 자동 다운로드하지 않는다.

`ai-replay`에는 모델 옵션이 없다. 기존 결과를 재검증할 때 `--result PATH`를 추가한다. 이전 text case를 사용하려면 `--input-format legacy-post`를 명시한다. 원본은 루트의 Git 제외 `artifacts/rehear-private/legacy-benchmarks/source-index.json`에서 새 위치를 찾는다. archive 자료는 실제 사용자 내용일 수 있으므로 public fixture/일반 로그에 복사하지 않는다. live case 설정/음성을 전사라고 import하지 않는다.

이전 hash inventory와 timing 정의·단위·한계는 루트 `docs/rehear-ai/MEASUREMENTS.md`에 있다. CLI를 지워도 제품 runtime과 기존 테스트는 동작한다. 제품의 clip catalog, playback scheduler, STT timestamps, observability와 제품 tests는 유지한다.
