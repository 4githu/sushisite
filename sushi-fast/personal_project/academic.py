from datetime import date, datetime
import re


PROGRESS_STAGES = (
    "accepted",
    "grade1_winter",
    "grade1_semester1",
    "grade1_summer",
    "grade1_semester2",
    "grade2_winter",
    "grade2_semester1",
    "grade2_summer",
    "grade2_semester2",
    "grade3_winter",
    "grade3_semester1",
    "deep",
)

STAGE_LABELS = {
    "accepted": "합격자반",
    "grade1_winter": "1학년 겨울방학",
    "grade1_semester1": "1학년 1학기",
    "grade1_summer": "1학년 여름방학",
    "grade1_semester2": "1학년 2학기",
    "grade2_winter": "2학년 겨울방학",
    "grade2_semester1": "2학년 1학기",
    "grade2_summer": "2학년 여름방학",
    "grade2_semester2": "2학년 2학기",
    "grade3_winter": "3학년 겨울방학",
    "grade3_semester1": "3학년 1학기",
    "deep": "심층",
}

STAGE_TERM_PERIOD = {
    "accepted": "semester_2",
    "grade1_winter": "winter",
    "grade1_semester1": "semester_1",
    "grade1_summer": "summer",
    "grade1_semester2": "semester_2",
    "grade2_winter": "winter",
    "grade2_semester1": "semester_1",
    "grade2_summer": "summer",
    "grade2_semester2": "semester_2",
    "grade3_winter": "winter",
    "grade3_semester1": "semester_1",
    "deep": "summer",
}


def normalize_admission_year(value: int) -> int:
    return 2000 + value if 0 <= value < 100 else value


def canonical_school_name(admission_year: int, school_name: str) -> str:
    return f"{normalize_admission_year(admission_year) % 100:02d}{school_name.strip()}"


def parse_legacy_school_name(name: str, today: date | None = None) -> tuple[int, str]:
    """Read both 서울26 and 26서울-style legacy names and drop old term suffixes."""
    value = re.sub(r"\s+(?:1|2|3)-(?:1|2)\s+.*$", "", name.strip())
    leading = re.fullmatch(r"(\d{2})(?:\s*)(.+)", value)
    if leading:
        return 2000 + int(leading.group(1)), leading.group(2).strip()
    trailing = re.fullmatch(r"(.+?)(?:\s*)(\d{2})", value)
    if trailing:
        return 2000 + int(trailing.group(2)), trailing.group(1).strip()
    if value == "심층":
        current = today or date.today()
        return current.year - 2, value
    current = today or date.today()
    return current.year, value


def stage_for_date(admission_year: int, value: date | datetime) -> str:
    admission_year = normalize_admission_year(admission_year)
    current = value.date() if isinstance(value, datetime) else value
    offset = current.year - admission_year
    month = current.month
    if offset < 0:
        return "accepted"
    if offset >= 3:
        return "deep"
    grade = offset + 1
    if grade == 3 and month >= 7:
        return "deep"
    season = (
        "winter" if month <= 2 else
        "semester1" if month <= 6 else
        "summer" if month <= 8 else
        "semester2"
    )
    return f"grade{grade}_{season}"


def next_stage(stage: str) -> str:
    try:
        index = PROGRESS_STAGES.index(stage)
    except ValueError:
        return PROGRESS_STAGES[0]
    return PROGRESS_STAGES[min(index + 1, len(PROGRESS_STAGES) - 1)]
