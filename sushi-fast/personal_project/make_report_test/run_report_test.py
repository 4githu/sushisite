"""이 파일을 IDE에서 ▶ 실행하면 경승현 6회차 테스트 리포트를 생성한다."""

from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
SUSHI_FAST = HERE.parents[1]
if str(SUSHI_FAST) not in sys.path:
    sys.path.insert(0, str(SUSHI_FAST))

from personal_project.make_report_test.test_report import main  # noqa: E402


if __name__ == "__main__":
    output = HERE / "output" / "경승현_6회차.json"
    sys.argv = [sys.argv[0], "--output", str(output)]
    raise SystemExit(main())
