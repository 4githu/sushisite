import json

from .db_repository import recent_targets


def main() -> None:
    print("target-id | 학교 | 회차 | 학생 | 시작")
    for target in recent_targets():
        rounds = ",".join(map(str, json.loads(target["round_numbers_json"] or "[]")))
        print(
            f"{target['id']:>9} | {target['school_name']} | {rounds}회차 | "
            f"{target['student_name']} | {target['start_time']}"
        )


if __name__ == "__main__":
    main()
