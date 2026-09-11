from datetime import datetime


def duration_hours(start: datetime, end: datetime | None) -> float:
    if end is None:
        return 1
    # 클리닉은 30분 단위다. 반 시간 단위로 확정해 부동소수점/시간대 계산의
    # 잔차가 정산과 엑셀에 섞이지 않게 한다.
    half_hours = max(0, round((end - start).total_seconds() / 1800))
    return half_hours / 2


def clinic_hourly_cost(progress_stage: str, student_count: int) -> int:
    """Total clinic cost per hour, which is also the assistant's hourly pay."""
    student_count = max(1, student_count)
    if progress_stage == "deep":
        return 40_000
    return max(30_000, student_count * 10_000)


def clinic_settlement_amount(
    progress_stage: str, start: datetime, end: datetime | None, student_count: int
) -> int:
    return round(clinic_hourly_cost(progress_stage, student_count) * duration_hours(start, end))


def parent_charge_per_student(
    progress_stage: str,
    start: datetime,
    end: datetime | None,
    student_count: int,
    parent_free_for_three_plus: bool,
) -> int:
    count = max(1, student_count)
    if parent_free_for_three_plus and count >= 3:
        return 0
    return round(clinic_settlement_amount(progress_stage, start, end, count) / count)


def parent_group_charge(
    progress_stage: str,
    start: datetime,
    end: datetime | None,
    student_count: int,
    parent_free_for_three_plus: bool,
) -> int:
    if parent_free_for_three_plus and student_count >= 3:
        return 0
    return clinic_settlement_amount(progress_stage, start, end, student_count)
