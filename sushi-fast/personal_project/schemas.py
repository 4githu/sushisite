from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


EventStatus = Literal["passive", "todo", "done"]
AttendanceStatus = Literal["scheduled", "completed", "cancelled", "absent"]
ReportStatus = Literal["draft", "ready", "submitted"]


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = ""
    start_time: datetime
    end_time: datetime | None = None
    is_all_day: bool = False
    status: EventStatus = "todo"
    type: str = Field(default="personal", max_length=40)
    group_name: str | None = Field(default=None, max_length=80)
    category_name: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("종료 시간은 시작 시간보다 빠를 수 없습니다.")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_all_day: bool | None = None
    status: EventStatus | None = None
    group_name: str | None = None
    category_name: str | None = None


class EventSeriesCreate(EventCreate):
    repeat_count: int = Field(default=4, ge=2, le=365)
    interval_weeks: int = Field(default=1, ge=1, le=52)
    repeat_until: datetime | None = None


class EventScopeUpdate(EventUpdate):
    scope: Literal["this", "following"] = "this"


class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    school_name: str = Field(default="", max_length=120)
    affiliation: str = Field(default="", max_length=120)
    memo: str = ""
    is_active: bool = True


class StudentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    school_name: str | None = None
    affiliation: str | None = None
    memo: str | None = None
    is_active: bool | None = None


class SessionCreate(BaseModel):
    student_id: int
    title: str | None = Field(default=None, max_length=120)
    start_time: datetime
    end_time: datetime | None = None
    report_required: bool = True
    hourly_rate: int = Field(default=30000, ge=0)
    allow_overlap: bool = False
    description: str = ""

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("종료 시간은 시작 시간보다 빠를 수 없습니다.")
        if self.end_time and self.end_time - self.start_time > timedelta(hours=12):
            raise ValueError("클리닉 일정은 12시간을 넘을 수 없습니다.")
        return self


class SessionUpdate(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None
    attendance_status: AttendanceStatus | None = None
    report_required: bool | None = None
    hourly_rate: int | None = Field(default=None, ge=0)
    allow_overlap: bool = False
    payment_status: Literal["pending", "paid"] | None = None


class ReportCreate(BaseModel):
    content_json: dict[str, Any] = Field(
        default_factory=lambda: {"type": "doc", "content": []}
    )
    source_notes: str = ""


class ReportUpdate(BaseModel):
    content_json: dict[str, Any] | None = None
    source_notes: str | None = None
    status: ReportStatus | None = None


class SessionSeriesCreate(BaseModel):
    student_id: int
    first_start_time: datetime
    duration_minutes: int = Field(default=60, ge=10, le=480)
    repeat_count: int = Field(default=4, ge=1, le=52)
    interval_weeks: int = Field(default=1, ge=1, le=8)
    report_required: bool = True
    hourly_rate: int = Field(default=30000, ge=0)
    allow_overlap: bool = False
    description: str = ""


class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    default_hourly_rate: int = Field(default=30000, ge=0)
    memo: str = ""
    priority: int = Field(default=0, ge=0, le=999)


class SchoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    default_hourly_rate: int | None = Field(default=None, ge=0)
    memo: str | None = None
    is_active: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=999)
    term_status: Literal["active", "ended"] | None = None


class ClinicRoundCreate(BaseModel):
    school_id: int
    round_number: int = Field(ge=1)
    student_names: list[str] = Field(min_length=1, max_length=100)
    start_time: datetime
    end_time: datetime
    hourly_rate: int | None = Field(default=None, ge=0)
    report_required: bool = True
    description: str = ""
    allow_overlap: bool = False

    @model_validator(mode="after")
    def validate_round(self):
        self.student_names = [name.strip() for name in self.student_names if name.strip()]
        if not self.student_names:
            raise ValueError("학생 이름을 한 명 이상 입력해주세요.")
        if self.end_time <= self.start_time:
            raise ValueError("종료 시간은 시작 시간보다 늦어야 합니다.")
        if self.end_time - self.start_time > timedelta(hours=12):
            raise ValueError("클리닉 일정은 12시간을 넘을 수 없습니다.")
        return self


class ClinicRoundSeriesCreate(ClinicRoundCreate):
    repeat_count: int = Field(default=4, ge=1, le=52)
    interval_weeks: int = Field(default=1, ge=1, le=8)
    round_numbers: list[int] | None = Field(default=None, min_length=1, max_length=52)
    round_numbers_by_occurrence: list[list[int]] | None = Field(
        default=None, min_length=1, max_length=52
    )

    @model_validator(mode="after")
    def validate_numbers(self):
        if self.round_numbers_by_occurrence:
            cleaned = []
            flattened = []
            for occurrence in self.round_numbers_by_occurrence:
                numbers = [number for number in occurrence if number >= 1]
                if not numbers:
                    raise ValueError("각 반복 일정에 회차를 한 개 이상 입력해주세요.")
                cleaned.append(numbers)
                flattened.extend(numbers)
            if len(set(flattened)) != len(flattened):
                raise ValueError("같은 회차를 중복 입력할 수 없습니다.")
            self.round_numbers_by_occurrence = cleaned
            self.repeat_count = len(cleaned)
            return self
        if self.round_numbers:
            if any(number < 1 for number in self.round_numbers):
                raise ValueError("회차는 1 이상이어야 합니다.")
            if len(set(self.round_numbers)) != len(self.round_numbers):
                raise ValueError("같은 회차를 중복 입력할 수 없습니다.")
            self.repeat_count = len(self.round_numbers)
        return self


class ClinicRoundUpdate(BaseModel):
    school_id: int | None = None
    round_number: int | None = Field(default=None, ge=1)
    round_numbers: list[int] | None = Field(default=None, min_length=1, max_length=52)
    student_names: list[str] | None = Field(default=None, min_length=1, max_length=100)
    start_time: datetime | None = None
    end_time: datetime | None = None
    description: str | None = None
    attendance_status: Literal["scheduled", "completed", "cancelled"] | None = None
    hourly_rate: int | None = Field(default=None, ge=0)
    payment_status: Literal["pending", "paid"] | None = None
    allow_overlap: bool = False
    scope: Literal["this", "following"] = "this"

    @model_validator(mode="after")
    def validate_student_names(self):
        if self.round_numbers is not None:
            if len(set(self.round_numbers)) != len(self.round_numbers):
                raise ValueError("같은 회차를 중복 입력할 수 없습니다.")
        if self.student_names is not None:
            self.student_names = [
                name.strip() for name in self.student_names if name.strip()
            ]
            if not self.student_names:
                raise ValueError("학생 이름을 한 명 이상 입력해주세요.")
        return self


class RoundTargetCreate(BaseModel):
    student_name: str = Field(min_length=1, max_length=80)


class TemplateSave(BaseModel):
    content_json: dict[str, Any]


class TargetReportUpdate(BaseModel):
    content_json: dict[str, Any] | None = None
    source_notes: str | None = None
    question_checks: dict[str, bool] | None = None
    status: ReportStatus | None = None
    lecture_progress: int | None = Field(default=None, ge=1, le=5)
    lecture_comprehension: int | None = Field(default=None, ge=1, le=5)
    memory_before: int | None = Field(default=None, ge=1, le=5)
    memory_after: int | None = Field(default=None, ge=1, le=5)
    assessment_json: dict[str, Any] | None = None
    generated_report_json: dict[str, Any] | None = None
    ai_model: str | None = Field(default=None, max_length=100)


class AiReportGenerate(BaseModel):
    model: str | None = Field(default=None, max_length=100)
    score_mode: Literal["auto", "none"] = "auto"
    assessment_items: list[dict[str, Any]] | None = Field(default=None, max_length=20)
    force: bool = False
    highlight_semantics: dict[str, Literal["fixed", "unfixed", "not_reasked"]] | None = None
    include_question_checks: bool = False


class KakaoSendMe(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    link_url: str = Field(min_length=1, max_length=2000)
    image_urls: list[str] = Field(default_factory=list, max_length=20)
