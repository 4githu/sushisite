from datetime import datetime
from io import BytesIO
import os

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse

from auth import JMT

from . import ai_report, kakao, repository
from .schemas import (
    ClinicRoundCreate,
    ClinicRoundSeriesCreate,
    ClinicRoundUpdate,
    EventCreate,
    EventScopeUpdate,
    EventSeriesCreate,
    EventUpdate,
    ReportCreate,
    ReportUpdate,
    RoundTargetCreate,
    SchoolCreate,
    SchoolUpdate,
    SessionCreate,
    SessionSeriesCreate,
    SessionUpdate,
    StudentCreate,
    StudentUpdate,
    TargetReportUpdate,
    TemplateSave,
    AiReportGenerate,
    KakaoSendMe,
)
from .xlsx import settlement_workbook


router = APIRouter(prefix="/api/personal", tags=["personal-project"])


def current_user_id(request: Request) -> int:
    payload = JMT.check_jwt(request, "mainauth")
    return int(payload["data"]["id"])


@router.get("/kakao/status")
def kakao_status(user_id: int = Depends(current_user_id)):
    return kakao.status(user_id)


@router.get("/kakao/connect-url")
def kakao_connect_url(request: Request, return_to: str = "/personal-project/aura", user_id: int = Depends(current_user_id)):
    return kakao.create_connect_url(user_id, request, return_to)


@router.get("/kakao/callback", name="kakao_callback")
def kakao_callback(request: Request, code: str, state: str):
    return_to = kakao.finish_connect(code, state, request)
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    separator = "&" if "?" in return_to else "?"
    return RedirectResponse(f"{frontend}{return_to}{separator}kakao=connected")


@router.post("/kakao/send-me")
def kakao_send_me(data: KakaoSendMe, request: Request, user_id: int = Depends(current_user_id)):
    return kakao.send_me(
        user_id, request, data.title, data.description, data.link_url, data.image_urls
    )


@router.get("/calendar/events")
def events(
    start: str = Query(alias="from"), end: str = Query(alias="to"),
    event_type: str | None = Query(default=None, alias="type"),
    status: str | None = None, user_id: int = Depends(current_user_id),
):
    return repository.list_events(user_id, start, end, event_type, status)


@router.post("/calendar/events", status_code=201)
def create_event(data: EventCreate, user_id: int = Depends(current_user_id)):
    return repository.create_event(user_id, data)


@router.post("/calendar/events/series", status_code=201)
def create_event_series(
    data: EventSeriesCreate, user_id: int = Depends(current_user_id)
):
    return repository.create_event_series(user_id, data)


@router.get("/calendar/events/{event_id}")
def event(event_id: int, user_id: int = Depends(current_user_id)):
    return repository.get_event(user_id, event_id)


@router.patch("/calendar/events/{event_id}")
def update_event(event_id: int, data: EventUpdate, user_id: int = Depends(current_user_id)):
    return repository.update_event(user_id, event_id, data)


@router.patch("/calendar/events/{event_id}/scope")
def update_event_scope(
    event_id: int,
    data: EventScopeUpdate,
    user_id: int = Depends(current_user_id),
):
    return repository.update_event_scope(user_id, event_id, data)


@router.delete("/calendar/events/{event_id}", status_code=204)
def delete_event(event_id: int, user_id: int = Depends(current_user_id)):
    repository.delete_event(user_id, event_id)
    return Response(status_code=204)


@router.delete("/calendar/events/{event_id}/scope", status_code=204)
def delete_event_scope(
    event_id: int,
    scope: str = "this",
    user_id: int = Depends(current_user_id),
):
    repository.delete_event_scope(user_id, event_id, scope)
    return Response(status_code=204)


@router.get("/aura/students")
def students(
    active: bool | None = None, search: str | None = None,
    user_id: int = Depends(current_user_id),
):
    return repository.list_students(user_id, active, search)


@router.post("/aura/students", status_code=201)
def create_student(data: StudentCreate, user_id: int = Depends(current_user_id)):
    return repository.create_student(user_id, data)


@router.patch("/aura/students/{student_id}")
def update_student(student_id: int, data: StudentUpdate, user_id: int = Depends(current_user_id)):
    return repository.update_student(user_id, student_id, data)


@router.get("/aura/sessions")
def sessions(
    start: str | None = Query(default=None, alias="from"),
    end: str | None = Query(default=None, alias="to"),
    student_id: int | None = None, user_id: int = Depends(current_user_id),
):
    return repository.list_sessions(user_id, start, end, student_id)


@router.post("/aura/sessions", status_code=201)
def create_session(data: SessionCreate, user_id: int = Depends(current_user_id)):
    return repository.create_session(user_id, data)


@router.post("/aura/sessions/series", status_code=201)
def create_session_series(data: SessionSeriesCreate, user_id: int = Depends(current_user_id)):
    return repository.create_session_series(user_id, data)


@router.get("/aura/sessions/{session_id}")
def session(session_id: int, user_id: int = Depends(current_user_id)):
    return repository.get_session(user_id, session_id)


@router.patch("/aura/sessions/{session_id}")
def update_session(session_id: int, data: SessionUpdate, user_id: int = Depends(current_user_id)):
    return repository.update_session(user_id, session_id, data)


@router.delete("/aura/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, user_id: int = Depends(current_user_id)):
    repository.delete_session(user_id, session_id)
    return Response(status_code=204)


@router.post("/aura/sessions/{session_id}/report", status_code=201)
def create_report(session_id: int, data: ReportCreate, user_id: int = Depends(current_user_id)):
    return repository.create_report(user_id, session_id, data)


@router.patch("/aura/reports/{report_id}")
def update_report(report_id: int, data: ReportUpdate, user_id: int = Depends(current_user_id)):
    return repository.update_report(user_id, report_id, data)


@router.post("/aura/reports/{report_id}/submit")
def submit_report(report_id: int, user_id: int = Depends(current_user_id)):
    return repository.update_report(user_id, report_id, None, submit=True)


@router.get("/aura/settlements")
def settlements(year: int, month: int, user_id: int = Depends(current_user_id)):
    return repository.school_settlements(user_id, year, month)


@router.get("/aura/settlements/export.xlsx")
def export_settlements(year: int, month: int, user_id: int = Depends(current_user_id)):
    data = repository.school_settlements(user_id, year, month)
    filename = f"aura-settlement-{year:04d}-{month:02d}.xlsx"
    return StreamingResponse(
        BytesIO(settlement_workbook(data)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/aura/schools")
def schools(user_id: int = Depends(current_user_id)):
    return repository.list_schools(user_id)


@router.post("/aura/schools", status_code=201)
def create_school(data: SchoolCreate, user_id: int = Depends(current_user_id)):
    return repository.create_school(user_id, data)


@router.get("/aura/schools/{school_id}")
def school(school_id: int, user_id: int = Depends(current_user_id)):
    return repository.get_school(user_id, school_id)


@router.get("/aura/schools/{school_id}/export.json")
def export_school(school_id: int, user_id: int = Depends(current_user_id)):
    data = repository.export_school_archive(user_id, school_id)
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": (
                f'attachment; filename="aura-school-{school_id}.json"'
            )
        },
    )


@router.patch("/aura/schools/{school_id}")
def update_school(
    school_id: int, data: SchoolUpdate, user_id: int = Depends(current_user_id)
):
    return repository.update_school(user_id, school_id, data)


@router.post("/aura/schools/{school_id}/move")
def move_school(
    school_id: int,
    direction: str,
    user_id: int = Depends(current_user_id),
):
    return repository.move_school(user_id, school_id, direction)


@router.delete("/aura/schools/{school_id}", status_code=204)
def delete_school(school_id: int, user_id: int = Depends(current_user_id)):
    repository.delete_school(user_id, school_id)
    return Response(status_code=204)


@router.get("/aura/rounds")
def clinic_rounds(
    school_id: int | None = None,
    start: str | None = Query(default=None, alias="from"),
    end: str | None = Query(default=None, alias="to"),
    user_id: int = Depends(current_user_id),
):
    return repository.list_clinic_rounds(user_id, school_id, start, end)


@router.post("/aura/rounds", status_code=201)
def create_clinic_round(
    data: ClinicRoundCreate, user_id: int = Depends(current_user_id)
):
    return repository.create_clinic_round(user_id, data)


@router.post("/aura/rounds/series", status_code=201)
def create_clinic_round_series(
    data: ClinicRoundSeriesCreate, user_id: int = Depends(current_user_id)
):
    return repository.create_clinic_round_series(user_id, data)


@router.get("/aura/rounds/{round_id}")
def clinic_round(round_id: int, user_id: int = Depends(current_user_id)):
    return repository.get_clinic_round(user_id, round_id)


@router.patch("/aura/rounds/{round_id}")
def update_clinic_round(
    round_id: int,
    data: ClinicRoundUpdate,
    user_id: int = Depends(current_user_id),
):
    return repository.update_clinic_round(user_id, round_id, data)


@router.delete("/aura/rounds/{round_id}", status_code=204)
def delete_clinic_round(round_id: int, user_id: int = Depends(current_user_id)):
    repository.delete_clinic_round(user_id, round_id)
    return Response(status_code=204)


@router.post("/aura/rounds/{round_id}/targets", status_code=201)
def add_round_target(
    round_id: int, data: RoundTargetCreate, user_id: int = Depends(current_user_id)
):
    return repository.add_round_target(user_id, round_id, data)


@router.delete("/aura/targets/{target_id}", status_code=204)
def delete_round_target(target_id: int, user_id: int = Depends(current_user_id)):
    repository.delete_round_target(user_id, target_id)
    return Response(status_code=204)


@router.get("/aura/targets/{target_id}/report")
def target_report(target_id: int, user_id: int = Depends(current_user_id)):
    return repository.get_or_create_target_report(user_id, target_id)


@router.get("/aura/targets/{target_id}/attachments")
def target_report_attachments(target_id: int, user_id: int = Depends(current_user_id)):
    return repository.list_target_report_attachments(user_id, target_id)


@router.post("/aura/targets/{target_id}/attachments", status_code=201)
async def upload_target_report_attachment(
    target_id: int,
    request: Request,
    kind: str = Query(...),
    filename: str = Query("image"),
    user_id: int = Depends(current_user_id),
):
    payload = await request.body()
    return repository.save_target_report_attachment(
        user_id, target_id, kind, filename, request.headers.get("content-type", ""), payload
    )


@router.get("/aura/report-attachments/{attachment_id}")
def report_attachment_file(attachment_id: int, user_id: int = Depends(current_user_id)):
    path, mime_type, _filename = repository.read_target_report_attachment(user_id, attachment_id)
    return FileResponse(path, media_type=mime_type)


@router.delete("/aura/report-attachments/{attachment_id}", status_code=204)
def delete_report_attachment(attachment_id: int, user_id: int = Depends(current_user_id)):
    repository.delete_target_report_attachment(user_id, attachment_id)
    return Response(status_code=204)


@router.get("/aura/ai/models")
def aura_ai_models(user_id: int = Depends(current_user_id)):
    return ai_report.available_models()


@router.get("/aura/targets/{target_id}/ai-reports")
def target_ai_reports(target_id: int, user_id: int = Depends(current_user_id)):
    return ai_report.saved_generations(user_id, target_id)


@router.post("/aura/targets/{target_id}/ai-reports/generate")
def generate_target_ai_report(
    target_id: int,
    data: AiReportGenerate,
    user_id: int = Depends(current_user_id),
):
    return ai_report.generate(
        user_id,
        target_id,
        model=data.model,
        score_mode=data.score_mode,
        assessment_items=data.assessment_items,
        force=data.force,
    )


@router.patch("/aura/target-reports/{report_id}")
def update_target_report(
    report_id: int,
    data: TargetReportUpdate,
    user_id: int = Depends(current_user_id),
):
    return repository.update_target_report(user_id, report_id, data)


@router.post("/aura/target-reports/{report_id}/submit")
def submit_target_report(
    report_id: int, user_id: int = Depends(current_user_id)
):
    return repository.update_target_report(user_id, report_id, None, submit=True)


@router.post(
    "/aura/schools/{school_id}/rounds/{round_number}/template",
    status_code=201,
)
def save_round_template(
    school_id: int,
    round_number: int,
    data: TemplateSave,
    user_id: int = Depends(current_user_id),
):
    return repository.save_round_template(
        user_id, school_id, round_number, data
    )
