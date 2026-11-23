from datetime import datetime
from io import BytesIO
from typing import Literal
import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from auth import JMT

from . import ai_report, kakao, native_kakao, repository, report_pdf
from . import workspace
from .reader_translation import translate_reader_segments
from .reader_translation.image import explain_reader_image
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


def native_kakao_user_id(request: Request) -> int:
    payload = JMT.check_jwt(request, "mainauth")
    data = payload.get("data") or {}
    email = str(data.get("email") or "").strip().lower()
    if email != native_kakao.OWNER_EMAIL:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "native_kakao_owner_only",
                "message": "이 기능은 지정된 관리자 계정에서만 사용할 수 있습니다.",
            },
        )
    return int(data["id"])


def require_native_kakao_origin(request: Request) -> None:
    origin = request.headers.get("origin", "").rstrip("/").lower()
    allowed = {
        "http://localhost:5173",
        "http://localhost:9000",
        "https://chobab.app",
        "https://aura.chobab.app",
        "https://netaq.chobab.app",
    }
    if origin not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "native_kakao_origin_rejected",
                "message": "허용된 sushisite 화면에서만 카카오 전송을 실행할 수 있습니다.",
            },
        )


def raise_native_kakao(error: native_kakao.NativeKakaoError):
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message,
                "targetRoom": error.target_room, "selectedRoom": error.selected_room,
                "fallbackReason": error.fallback_reason,
                "deliveryStatus": error.delivery_status},
    ) from error


@router.post("/reader/translate")
async def reader_translate(
    request: Request,
    response: Response,
    user_id: int = Depends(current_user_id),
):
    response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return await translate_reader_segments(request, user_id)


@router.post("/reader/explain-image")
async def reader_explain_image(request: Request, response: Response, user_id: int = Depends(current_user_id)):
    response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return await explain_reader_image(request, user_id)


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
    return workspace.list_events(user_id, start, end, event_type, status)


@router.post("/calendar/events", status_code=201)
def create_event(data: EventCreate, user_id: int = Depends(current_user_id)):
    return workspace.create_event(user_id, data)


@router.post("/calendar/events/series", status_code=201)
def create_event_series(
    data: EventSeriesCreate, user_id: int = Depends(current_user_id)
):
    return workspace.create_series(user_id, data)


@router.get("/calendar/events/{event_id}")
def event(event_id: int, user_id: int = Depends(current_user_id)):
    return workspace.get_event(user_id, event_id)


@router.patch("/calendar/events/{event_id}")
def update_event(event_id: int, data: EventUpdate, user_id: int = Depends(current_user_id)):
    return workspace.update_event(user_id, event_id, data)


@router.patch("/calendar/events/{event_id}/scope")
def update_event_scope(
    event_id: int,
    data: EventScopeUpdate,
    user_id: int = Depends(current_user_id),
):
    return workspace.update_event(user_id, event_id, data)


@router.delete("/calendar/events/{event_id}", status_code=204)
def delete_event(event_id: int, user_id: int = Depends(current_user_id)):
    workspace.delete_event(user_id, event_id)
    return Response(status_code=204)


@router.delete("/calendar/events/{event_id}/scope", status_code=204)
def delete_event_scope(
    event_id: int,
    scope: str = "this",
    user_id: int = Depends(current_user_id),
):
    workspace.delete_event(user_id, event_id, scope)
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
def settlements(
    year: int,
    month: int,
    response: Response,
    user_id: int = Depends(current_user_id),
):
    response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
    return repository.school_settlements(user_id, year, month)


class SettlementRegenerationApproval(BaseModel):
    snapshotDigest: str
    newTotal: int
    proposedDigest: str


@router.post("/aura/settlements/generate")
def generate_settlements(year: int, month: int, approval: SettlementRegenerationApproval | None = None,
                         user_id: int = Depends(current_user_id)):
    return repository.generate_school_settlements(user_id, year, month,
        approval=approval.model_dump() if approval else None)


@router.get("/aura/settlements/export.xlsx")
def export_settlements(
    year: int,
    month: int,
    assistant_name: str = Query(default="김지후"),
    user_id: int = Depends(current_user_id),
):
    data = repository.school_settlements(user_id, year, month)
    name = assistant_name.strip() or "김지후"
    assistant_label = name if name.endswith("조교") else f"{name}조교"
    filename = f"{assistant_label} {month}월 클리닉 정산.xlsx"
    return StreamingResponse(
        BytesIO(settlement_workbook(data, assistant_name=assistant_name)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/aura/schools")
def schools(user_id: int = Depends(current_user_id)):
    return repository.list_schools(user_id)


@router.post("/aura/schools", status_code=201)
def create_school(data: SchoolCreate, user_id: int = Depends(current_user_id)):
    return repository.create_school(user_id, data)


@router.post("/aura/schools/advance-stage")
def advance_school_stages(user_id: int = Depends(current_user_id)):
    return repository.advance_school_stages(user_id)


class SchoolOrder(BaseModel):
    school_ids: list[int]


@router.put("/aura/schools/reorder")
def reorder_schools(data: SchoolOrder, user_id: int = Depends(current_user_id)):
    return repository.reorder_schools(user_id, data.school_ids)


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


@router.get("/aura/rounds/{round_id}/modality-preview")
def preview_clinic_round_modality(
    round_id: int,
    scope: Literal["this", "following", "all"] = "this",
    user_id: int = Depends(current_user_id),
):
    return repository.preview_clinic_round_modality(user_id, round_id, scope)


@router.patch("/aura/rounds/{round_id}")
def update_clinic_round(
    round_id: int,
    data: ClinicRoundUpdate,
    user_id: int = Depends(current_user_id),
):
    return repository.update_clinic_round(user_id, round_id, data)


@router.delete("/aura/rounds/{round_id}", status_code=204)
def delete_clinic_round(round_id: int, scope: Literal["this", "following", "all"] = "this", user_id: int = Depends(current_user_id)):
    repository.delete_clinic_round(user_id, round_id, scope)
    return Response(status_code=204)


@router.post("/aura/rounds/{round_id}/targets", status_code=201)
def add_round_target(
    round_id: int, data: RoundTargetCreate, user_id: int = Depends(current_user_id)
):
    return repository.add_round_target(user_id, round_id, data)


@router.delete("/aura/targets/{target_id}", status_code=204)
def delete_round_target(target_id: int, confirm: bool = False,
                        approved_old_amount: int | None = None, approved_new_amount: int | None = None,
                        user_id: int = Depends(current_user_id)):
    approval = (approved_old_amount, approved_new_amount) if approved_old_amount is not None and approved_new_amount is not None else None
    repository.delete_round_target(user_id, target_id, confirm=confirm, approved_price_change=approval)
    return Response(status_code=204)


@router.get("/aura/targets/{target_id}/report")
def target_report(target_id: int, user_id: int = Depends(current_user_id)):
    return repository.get_or_create_target_report(user_id, target_id)


@router.get("/aura/targets/{target_id}/attachments")
def target_report_attachments(target_id: int, user_id: int = Depends(current_user_id)):
    return repository.list_target_report_attachments(user_id, target_id)


def _target_report_pdf(user_id: int, target_id: int) -> bytes:
    report = repository.get_or_create_target_report(user_id, target_id)
    attachments = []
    for item in repository.list_target_report_attachments(user_id, target_id):
        try:
            path, _mime_type, _name = repository.read_target_report_attachment(user_id, item["id"])
            attachments.append({**item, "path": str(path)})
        except HTTPException as error:
            if error.status_code != 404:
                raise
    return report_pdf.render_pdf(report, attachments)


@router.get("/aura/targets/{target_id}/report.pdf")
def download_target_report_pdf(target_id: int, user_id: int = Depends(current_user_id)):
    pdf = _target_report_pdf(user_id, target_id)
    return StreamingResponse(BytesIO(pdf), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="clinic-report-{target_id}.pdf"',
        "Cache-Control": "private, no-store",
    })


def _complete_verified_clinic_delivery(result: dict, user_id: int, report_id: int) -> dict:
    if result.get("sent") is not True or result.get("deliveryStatus") != "verified":
        raise HTTPException(status_code=409, detail="전송 성공이 확인되지 않아 작성 완료로 변경하지 않았습니다.")
    try:
        repository.update_target_report(user_id, report_id, None, submit=True)
    except Exception as error:
        raise HTTPException(status_code=500, detail="카카오 전송은 확인됐지만 작성 완료 저장 또는 첨부 정리를 확인하지 못했습니다. 재전송하지 말고 리포트 상태를 확인해주세요.") from error
    return result


@router.post("/aura/targets/{target_id}/kakao-clinic/send-report")
def send_server_generated_clinic_report(
    target_id: int,
    request: Request,
    user_id: int = Depends(native_kakao_user_id),
):
    require_native_kakao_origin(request)
    report = repository.get_or_create_target_report(user_id, target_id)
    return _execute_immediate_clinic(request, user_id, target_id, report,
        lambda: _send_immediate_clinic_report(user_id, target_id, report))


def _send_immediate_clinic_report(user_id, target_id, report):
    job_id = None
    try:
        try:
            job = native_kakao.create_clinic_job(user_id, target_id, report)
            job_id = job["jobId"]
            if job.get("deliveryFormat") != "text":
                pdf = _target_report_pdf(user_id, target_id)
                pages = report_pdf.render_pages(pdf, max_pages=native_kakao.MAX_PAGES)
                for number, image in enumerate(pages, start=1):
                    native_kakao.store_page(
                        job_id, user_id, target_id, number, "image/jpeg", image
                    )
        except native_kakao.NativeKakaoError:
            raise
        except ValueError as error:
            raise native_kakao.NativeKakaoError(413, str(error), 'report_render_failed') from error
        except Exception as error:
            raise native_kakao.NativeKakaoError(500, '서버에서 리포트 PDF를 만들지 못했습니다.', 'report_render_failed') from error
        return _send_clinic_job_conservatively(job_id, user_id, target_id)
    finally:
        if job_id is not None:
            native_kakao.discard_clinic_job(job_id, user_id, target_id)


def _send_clinic_job_conservatively(job_id, user_id, target_id):
    try:
        return native_kakao.send_clinic_job(job_id, user_id, target_id)
    except native_kakao.NativeKakaoError as error:
        if error.code not in ('send_in_progress', 'recipient_timeout', 'recipient_unverified', 'invalid_clinic_job') and error.delivery_status == 'not_started':
            error.delivery_status = 'unknown'
        raise


def _delivery_request_id(raw):
    import uuid
    if raw is None:
        return uuid.uuid4().hex
    try:
        return uuid.UUID(raw).hex
    except (ValueError, AttributeError):
        raise HTTPException(422, '올바른 전송 요청 번호가 필요합니다.')


def _execute_immediate_clinic(request, user_id, target_id, report, sender):
    from . import clinic_scheduled_delivery as delivery
    request_id = _delivery_request_id(request.headers.get('X-Delivery-Request-Id'))
    job_id, prior = delivery.reserve_immediate(user_id, target_id, request_id)
    if prior is not None:
        if prior['state'] == 'sent':
            return prior
        raise HTTPException(409, detail={'code': prior['errorCode'] or 'request_in_progress', 'message': '기존 전송 요청의 결과를 확인해주세요.', **prior})
    try:
        result = sender()
        if result.get('sent') is not True or result.get('deliveryStatus') != 'verified':
            state = 'partial' if result.get('deliveryStatus') == 'partial' else 'unknown'
            delivery.finish_immediate(job_id, state, 'delivery_unverified', result)
            raise HTTPException(409, {'code': 'delivery_unverified', **delivery.lookup_immediate(user_id, target_id, request_id)})
        delivery.finish_immediate(job_id, 'sent', 'completion_pending', result)
        try:
            _complete_verified_clinic_delivery(result, user_id, report['id'])
        except HTTPException as error:
            raise HTTPException(error.status_code, {'code': 'completion_pending', 'message': str(error.detail), **delivery.lookup_immediate(user_id, target_id, request_id)}) from error
        delivery.finish_completion(job_id)
        return delivery.lookup_immediate(user_id, target_id, request_id)
    except native_kakao.NativeKakaoError as error:
        status = error.delivery_status
        state = status if status in ('partial', 'unknown') else 'failed'
        delivery.finish_immediate(job_id, state, error.code, error.delivery_result)
        raise HTTPException(error.status_code, detail={'code': error.code, 'message': error.message, **delivery.lookup_immediate(user_id, target_id, request_id)}) from error
    except HTTPException:
        raise
    except Exception:
        delivery.finish_immediate(job_id, 'unknown', 'send_exception')
        raise HTTPException(500, {'code': 'send_exception', 'message': '전송 결과를 확인할 수 없습니다. 재전송하지 말고 확인해주세요.', **delivery.lookup_immediate(user_id, target_id, request_id)})


@router.get('/aura/targets/{target_id}/kakao-clinic/delivery-requests/{request_id}')
def get_immediate_clinic_request(target_id: int, request_id: str, user_id: int = Depends(current_user_id)):
    from . import clinic_scheduled_delivery as delivery
    repository.get_or_create_target_report(user_id, target_id)
    return delivery.lookup_immediate(user_id, target_id, _delivery_request_id(request_id))


@router.post("/aura/targets/{target_id}/attachments", status_code=201)
async def upload_target_report_attachment(
    target_id: int,
    request: Request,
    kind: str = Query(...),
    filename: str = Query("image"),
    user_id: int = Depends(current_user_id),
):
    payload = await request.body()
    return await run_in_threadpool(repository.save_target_report_attachment,
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


@router.get("/aura/kakao-self/status")
def native_kakao_status(user_id: int = Depends(native_kakao_user_id)):
    return native_kakao.status()


@router.post("/aura/targets/{target_id}/kakao-self/jobs", status_code=201)
def create_native_kakao_job(
    target_id: int,
    request: Request,
    user_id: int = Depends(native_kakao_user_id),
):
    require_native_kakao_origin(request)
    repository.get_or_create_target_report(user_id, target_id)
    try:
        native_kakao.preflight()
        return native_kakao.create_job(user_id, target_id)
    except native_kakao.NativeKakaoError as error:
        raise_native_kakao(error)


@router.put("/aura/targets/{target_id}/kakao-self/jobs/{job_id}/pages/{page_number}")
async def upload_native_kakao_page(
    target_id: int,
    job_id: str,
    page_number: int,
    request: Request,
    user_id: int = Depends(native_kakao_user_id),
):
    require_native_kakao_origin(request)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > native_kakao.MAX_PAGE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "page_too_large",
                        "message": "리포트 이미지 한 장은 8MB 이하여야 합니다.",
                    },
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Content-Length가 올바르지 않습니다.") from exc
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > native_kakao.MAX_PAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"code": "page_too_large", "message": "리포트 이미지 한 장은 8MB 이하여야 합니다."},
            )
    try:
        return await run_in_threadpool(native_kakao.store_page,
            job_id,
            user_id,
            target_id,
            page_number,
            request.headers.get("content-type", ""),
            bytes(payload),
        )
    except native_kakao.NativeKakaoError as error:
        raise_native_kakao(error)


@router.post("/aura/targets/{target_id}/kakao-self/jobs/{job_id}/send")
def send_native_kakao_job(
    target_id: int,
    job_id: str,
    request: Request,
    user_id: int = Depends(native_kakao_user_id),
):
    require_native_kakao_origin(request)
    try:
        return native_kakao.send_job(job_id, user_id, target_id)
    except native_kakao.NativeKakaoError as error:
        raise_native_kakao(error)


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
        highlight_semantics=data.highlight_semantics,
        include_question_checks=data.include_question_checks,
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


@router.post('/aura/targets/{target_id}/kakao-clinic/jobs',status_code=201)
def create_clinic_kakao_job(target_id:int,request:Request,user_id:int=Depends(native_kakao_user_id)):
    require_native_kakao_origin(request)
    report=repository.get_or_create_target_report(user_id,target_id)
    try:return native_kakao.create_clinic_job(user_id,target_id,report)
    except native_kakao.NativeKakaoError as error:raise_native_kakao(error)

@router.post('/aura/targets/{target_id}/kakao-clinic/jobs/{job_id}/send')
def send_clinic_kakao_job(target_id:int,job_id:str,request:Request,user_id:int=Depends(native_kakao_user_id)):
    require_native_kakao_origin(request)
    report = repository.get_or_create_target_report(user_id,target_id)
    return _execute_immediate_clinic(request, user_id, target_id, report,
        lambda: _send_clinic_job_conservatively(job_id,user_id,target_id))

@router.get('/aura/targets/{target_id}/template')
def target_template(target_id:int,user_id:int=Depends(current_user_id)):
    with repository.connection() as db:
        target=repository._target_owner(db,target_id,user_id)
        _,templates,document=repository._combined_round_template(db,user_id,target)
        if len(templates)==1 and templates[0]:
            import json
            document=json.loads(templates[0]['content_json'])
        return {'document':document}


# Reuse the owner/origin boundary of the existing native Kakao routes.
def settlement_request_owner(request: Request) -> int:
    require_native_kakao_origin(request)
    return native_kakao_user_id(request)


from .settlement_delivery import bind_settlement_router
router.include_router(bind_settlement_router(settlement_request_owner, native_kakao_user_id))

from .classroom_delivery import build_router as build_classroom_router
router.include_router(build_classroom_router(settlement_request_owner, native_kakao_user_id))

from .clinic_scheduled_delivery import build_router as build_clinic_delivery_router
router.include_router(build_clinic_delivery_router(settlement_request_owner, native_kakao_user_id))
