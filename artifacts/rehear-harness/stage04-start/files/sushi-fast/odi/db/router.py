# odi/db/router.py

from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
# odi/db/router.py 상단 import 근처에 추가

from odi.files.service import (
    commit_template_files,
    save_session_video_upload,
    session_media_path_from_storage_path,
)

from auth import JMT
from odi.db import odidb
from odi.db.schema import (
    ConfigUpdateRequest,
    LoginRequest,
    PreSessionFinishRequest,
    PreSessionStartRequest,
    PreSessionStateUpdateRequest,
    RecentTemplateUpdateRequest,
    SessionCreateRequest,
    SessionFinishRequest,
    SessionMediaUpdateRequest,
    TemplateCreateRequest,
    TemplateUpdateRequest,
    UserCreateRequest,
)
from odi.EVC.report_schema import ReportFinishResponse, ReportRecoveryRequest
from odi.EVC.report_service import recover_pre_session_report


router = APIRouter(
    prefix="/db",
    tags=["odi-db"],
)


JWT_COOKIE_KEY = "odi_token"
DEMO_REPORT_TEMPLATE_ID = "template_demo_algorithm_choice"


def validate_presentation_template_for_start(template: dict[str, Any]) -> None:
    """Reject incomplete presentation drafts before a PIN/pre-session can be created."""
    if template.get("type") != "presentation":
        return

    files = template.get("files") or {}
    slide = files.get("slide") or {}
    slide_path = slide.get("storage_path") if isinstance(slide, dict) else None
    # Keep old recent-template records usable while requiring an actual PDF path.
    slide_path = slide_path or files.get("slide_path")
    if not isinstance(slide_path, str) or not slide_path.strip():
        raise ValueError("발표 자료 PDF를 업로드한 뒤 세션을 시작해주세요.")


def raise_404(message: str) -> None:
    raise HTTPException(status_code=404, detail=message)


def raise_400(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def make_user_token(user: dict[str, Any]) -> str:
    return JMT.make_jwt(
        sub=user["user_id"],
        data=user,
        index=["user_id", "auth_id"],
    )


def set_token_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=JWT_COOKIE_KEY,
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=60 * 60
    )


def get_user_id_from_jwt(request: Request) -> str:
    payload = JMT.check_jwt(request, JWT_COOKIE_KEY)
    data = payload.get("data", {})
    user_id = data.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="JWT에 user_id가 없습니다.")

    return user_id


def require_pre_session_owner(pin_code: str, user_id: str) -> dict[str, Any]:
    pre_session = odidb.get_pre_session_by_pin(pin_code)

    if pre_session is None:
        raise_404(f"존재하지 않는 pin_code입니다: {pin_code}")

    template = odidb.get_template(pre_session["template_id"])
    if template is None:
        raise_404("pre_session의 템플릿을 찾을 수 없습니다.")

    if str(template["owner_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="다른 사용자의 준비 세션에는 접근할 수 없습니다.")

    return pre_session


@router.get("/health")
def db_health() -> dict[str, str]:
    return {
        "status": "ok",
        "db": "odi.db",
    }


@router.post("/init")
def init_db() -> dict[str, str]:
    try:
        odidb.init_db()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "db_initialized",
    }


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
) -> dict[str, Any]:
    # Service login must derive authority from the verified primary session.
    identity = JMT.check_jwt(request, 'mainauth')
    if str(payload.auth_id) != str(identity['sub']):
        raise HTTPException(status_code=403, detail='로그인 계정이 일치하지 않습니다.')
    user = odidb.get_user_by_auth_id(payload.auth_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="ODI 서비스에 가입되지 않은 유저입니다.",
        )

    token = make_user_token(user)
    set_token_cookie(response, token)

    return {
        "message": "odi_login_success",
        "user": user,
    }

@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(
        key=JWT_COOKIE_KEY,
        path="/",
        httponly=True,
        secure=True,
        samesite="none",
    )


    return {
        "message": "odi_logout_success",
    }

@router.post("/join")
def join_odi(
    payload: UserCreateRequest,
    response: Response,
    request: Request,
) -> dict[str, Any]:
    identity = JMT.check_jwt(request, 'mainauth')
    if str(payload.auth_id) != str(identity['sub']) or str(payload.user_id) != str(identity['sub']):
        raise HTTPException(status_code=403, detail='로그인 계정이 일치하지 않습니다.')
    try:
        odidb.create_user(
            user_id=payload.user_id,
            auth_id=payload.auth_id,
            config=payload.config,
            recent_template=payload.recent_template,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = odidb.get_user(payload.user_id)

    if user is None:
        raise HTTPException(status_code=400, detail="유저 생성 후 조회에 실패했습니다.")

    token = make_user_token(user)
    set_token_cookie(response, token)

    return {
        "message": "odi_join_success",
        "user": user,
    }

@router.get("/me")
def get_me(request: Request) -> dict[str, Any]:
    user_id = get_user_id_from_jwt(request)
    user = odidb.get_user(user_id)

    if user is None:
        raise_404(f"존재하지 않는 user_id입니다: {user_id}")

    return {
        "user": user,
    }


@router.post("/users")
def create_user(payload: UserCreateRequest) -> dict[str, Any]:
    try:
        odidb.create_user(
            user_id=payload.user_id,
            auth_id=payload.auth_id,
            config=payload.config,
            recent_template=payload.recent_template,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = odidb.get_user(payload.user_id)

    return {
        "message": "user_created",
        "user": user,
    }


@router.get("/users/{user_id}")
def get_user(user_id: str) -> dict[str, Any]:
    user = odidb.get_user(user_id)

    if user is None:
        raise_404(f"존재하지 않는 user_id입니다: {user_id}")

    return {
        "user": user,
    }


@router.get("/users/by-auth/{auth_id}")
def get_user_by_auth_id(auth_id: str) -> dict[str, Any]:
    user = odidb.get_user_by_auth_id(auth_id)

    if user is None:
        raise_404(f"등록되지 않은 auth_id입니다: {auth_id}")

    return {
        "user": user,
    }


@router.put("/users/{user_id}/config")
def update_user_config(
    user_id: str,
    payload: ConfigUpdateRequest,
) -> dict[str, Any]:
    try:
        odidb.update_user_config(
            user_id=user_id,
            config=payload.config,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = odidb.get_user(user_id)

    return {
        "message": "config_updated",
        "user": user,
    }


@router.put("/users/{user_id}/recent-template")
def update_recent_template(
    user_id: str,
    payload: RecentTemplateUpdateRequest,
) -> dict[str, Any]:
    try:
        odidb.update_recent_template(
            user_id=user_id,
            template=payload.template,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = odidb.get_user(user_id)

    return {
        "message": "recent_template_updated",
        "user": user,
    }


def owned_template(template_id: str, request: Request):
    row = odidb.get_template(template_id)
    if not row or str(row["owner_id"]) != str(get_user_id_from_jwt(request)):
        raise HTTPException(404, "템플릿을 찾을 수 없습니다.")
    return row


@router.post("/templates")
def create_template(payload: TemplateCreateRequest, request: Request):
    from odi.db.template_service import save_baseline
    user_id = str(get_user_id_from_jwt(request))
    if str(payload.owner_id) != user_id:
        raise HTTPException(403, "다른 사용자의 환경을 저장할 수 없습니다.")
    return {"template": save_baseline(user_id, payload.template, None, None, payload.template_id)}


@router.get("/templates/{template_id}")
def get_template(template_id: str, request: Request):
    return {"template": owned_template(template_id, request)}


@router.get("/users/{user_id}/templates")
def list_user_templates(user_id: str, request: Request):
    if str(user_id) != str(get_user_id_from_jwt(request)):
        raise HTTPException(403, "다른 사용자의 환경에는 접근할 수 없습니다.")
    return {"templates": odidb.list_templates_by_owner(user_id)}


@router.put("/templates/{template_id}")
def update_template(template_id: str, payload: TemplateUpdateRequest, request: Request):
    from odi.db.template_service import save_baseline
    row = owned_template(template_id, request)
    return {"template": save_baseline(str(row["owner_id"]), payload.template, template_id, payload.expected_version)}


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, request: Request) -> dict[str, str]:
    owned_template(template_id, request)
    try:
        odidb.delete_template(template_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "template_deleted",
    }


@router.post("/pre-sessions/start")
@router.post("/pre-sessions/start-from-recent")
def start_pre_session_from_recent(payload: PreSessionStartRequest, request: Request):
    from odi.db.template_service import prepare
    user_id = str(get_user_id_from_jwt(request))
    if str(payload.user_id) != user_id:
        raise HTTPException(403, "다른 사용자의 세션을 시작할 수 없습니다.")
    draft = payload.template
    if draft is None:
        draft = (odidb.get_user(user_id) or {}).get("recent_template")
    if draft is None:
        raise HTTPException(422, "시작할 환경이 없습니다.")
    try:
        validate_presentation_template_for_start(draft)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return prepare(user_id, draft, payload.template_id or draft.get("id"), payload.request_id, payload.expires_minutes)


@router.get("/pre-sessions/{pin_code}")
def get_pre_session(pin_code: str, request: Request) -> dict[str, Any]:
    pre_session = require_pre_session_owner(pin_code, get_user_id_from_jwt(request))

    return {
        "pre_session": pre_session,
    }


@router.put("/pre-sessions/{pin_code}/state")
def update_pre_session_state(
    pin_code: str,
    payload: PreSessionStateUpdateRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        require_pre_session_owner(pin_code, get_user_id_from_jwt(request))
        odidb.update_pre_session_state(
            pin_code=pin_code,
            state=payload.state,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    pre_session = odidb.get_pre_session_by_pin(pin_code)

    return {
        "message": "pre_session_state_updated",
        "pre_session": pre_session,
    }


@router.post("/pre-sessions/{pin_code}/finish")
def finish_pre_session(
    pin_code: str,
    payload: PreSessionFinishRequest,
    request: Request,
) -> dict[str, Any]:
    user_id = get_user_id_from_jwt(request)
    if str(payload.user_id) != str(user_id):
        raise HTTPException(status_code=403, detail="다른 사용자의 세션을 완료할 수 없습니다.")

    pre_session = require_pre_session_owner(pin_code, user_id)

    try:
        session_id = odidb.finish_linked_pre_session(
            pin_code=pin_code, user_id=str(user_id), template_id=pre_session["template_id"],
            feedback=payload.feedback,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    updated_pre_session = odidb.get_pre_session_by_pin(pin_code)
    session = odidb.get_session(session_id)

    return {
        "message": "pre_session_finished",
        "pre_session": updated_pre_session,
        "session": session,
    }


@router.delete("/pre-sessions/expired")
def delete_expired_pre_sessions() -> dict[str, Any]:
    deleted_count = odidb.delete_expired_pre_sessions()

    return {
        "message": "expired_pre_sessions_deleted",
        "deleted_count": deleted_count,
    }


@router.post(
    "/pre-sessions/{pin_code}/report/retry",
    response_model=ReportFinishResponse,
)
async def retry_pre_session_report(
    pin_code: str,
    payload: ReportRecoveryRequest,
    request: Request,
):
    user_id = get_user_id_from_jwt(request)
    require_pre_session_owner(pin_code, user_id)
    try:
        return await recover_pre_session_report(
            pin_code=pin_code,
            owner_user_id=user_id,
            request_id=payload.request_id,
            planned_seconds=payload.planned_seconds,
            qa_seconds=payload.qa_seconds,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/sessions")
def create_session(payload: SessionCreateRequest) -> dict[str, Any]:
    try:
        session_id = odidb.create_session_with_snapshot(
            user_id=payload.user_id,
            template_id=payload.template_id,
            template=payload.template,
            feedback=payload.feedback,
            state=payload.state,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = odidb.get_session(session_id)

    return {
        "message": "session_created",
        "session": session,
    }


@router.post("/sessions/start/{template_id}")
def start_session_from_template(
    template_id: str,
    user_id: str,
) -> dict[str, Any]:
    user = odidb.get_user(user_id)

    if user is None:
        raise_404(f"존재하지 않는 user_id입니다: {user_id}")

    try:
        session_id = odidb.start_session_from_template(
            user_id=user_id,
            template_id=template_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = odidb.get_session(session_id)

    return {
        "message": "session_started",
        "session": session,
    }


@router.put("/sessions/{session_id}/finish")
def finish_session(
    session_id: str,
    payload: SessionFinishRequest,
) -> dict[str, Any]:
    try:
        odidb.finish_session(
            session_id=session_id,
            feedback=payload.feedback,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = odidb.get_session(session_id)

    return {
        "message": "session_finished",
        "session": session,
    }


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request) -> dict[str, Any]:
    session = odidb.get_session(session_id)

    if session is None:
        raise_404(f"존재하지 않는 session_id입니다: {session_id}")
    if str(session["user_id"]) != str(get_user_id_from_jwt(request)):
        raise HTTPException(status_code=403, detail="다른 사용자의 세션에는 접근할 수 없습니다.")

    return {
        "session": session,
        "comparison": odidb.get_user_report_comparison(
            str(session["user_id"]),
            current_session_id=session_id,
        ),
    }


@router.put("/sessions/{session_id}/media")
def update_session_media(
    session_id: str,
    payload: SessionMediaUpdateRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        odidb.update_session_media(
            session_id=session_id,
            user_id=get_user_id_from_jwt(request),
            media=payload.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return {
        "message": "session_media_updated",
        "session": odidb.get_session(session_id),
    }


@router.post("/sessions/{session_id}/media/upload")
async def upload_session_media(
    session_id: str,
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    user_id = get_user_id_from_jwt(request)
    session = odidb.get_session(session_id)
    if session is None or str(session["user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="영상 연결 대상 세션이 없거나 접근 권한이 없습니다.")

    file_ref = await save_session_video_upload(user_id, session_id, file)
    odidb.update_session_media(
        session_id=session_id,
        user_id=user_id,
        media={
            "video_url": f"/odi/db/sessions/{session_id}/media/file",
            "title": file_ref["original_name"],
            "source": "upload",
            "storage_path": file_ref["storage_path"],
            "mime_type": file_ref["mime_type"],
            "size_bytes": file_ref["size_bytes"],
        },
    )

    return {
        "message": "session_media_uploaded",
        "session": odidb.get_session(session_id),
    }


@router.get("/sessions/{session_id}/media/file")
def read_session_media(session_id: str, request: Request) -> FileResponse:
    user_id = get_user_id_from_jwt(request)
    session = odidb.get_session(session_id)
    if session is None or str(session["user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="영상에 접근할 권한이 없습니다.")

    feedback = session.get("feedback")
    media = feedback.get("media") if isinstance(feedback, dict) else None
    storage_path = media.get("storage_path") if isinstance(media, dict) else None
    if not isinstance(storage_path, str) or not storage_path:
        raise HTTPException(status_code=404, detail="이 세션에 업로드된 영상이 없습니다.")

    file_path = session_media_path_from_storage_path(user_id, session_id, storage_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="영상 파일을 찾을 수 없습니다.")

    return FileResponse(
        file_path,
        media_type=media.get("mime_type") or "application/octet-stream",
        filename=media.get("title") or file_path.name,
        content_disposition_type="inline",
    )


@router.get("/demo-report")
def get_demo_report() -> dict[str, Any]:
    """Public, account-independent report for the presentation demo button."""
    report = odidb.get_latest_completed_session_by_template_id(DEMO_REPORT_TEMPLATE_ID)
    if report is None:
        raise_404("시연용 리포트가 아직 준비되지 않았습니다.")

    return {"session": report}


@router.get("/users/{user_id}/sessions")
def list_user_sessions(
    user_id: str,
    request: Request,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    if str(user_id) != str(get_user_id_from_jwt(request)):
        raise HTTPException(status_code=403, detail="다른 사용자의 세션에는 접근할 수 없습니다.")
    user = odidb.get_user(user_id)

    if user is None:
        raise_404(f"존재하지 않는 user_id입니다: {user_id}")

    sessions = odidb.list_sessions_by_user(
        user_id=user_id,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )

    return {
        "user_id": user_id,
        "sessions": sessions,
    }


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, request: Request) -> dict[str, str]:
    try:
        odidb.delete_session(session_id, user_id=get_user_id_from_jwt(request))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "session_deleted",
    }


@router.get("/sessions/{session_id}/transcript")
def download_session_transcript(session_id: str, request: Request) -> dict[str, Any]:
    user_id = get_user_id_from_jwt(request)
    try:
        segments = odidb.get_presentation_transcript_for_session(session_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"session_id": session_id, "segments": segments}


@router.delete("/sessions/{session_id}/source-data")
def delete_session_source_data(session_id: str, request: Request) -> dict[str, Any]:
    user_id = get_user_id_from_jwt(request)
    try:
        deleted_count = odidb.delete_presentation_source_data(session_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"message": "presentation_source_data_deleted", "deleted_count": deleted_count}


@router.post("/users/{user_id}/templates/cleanup")
def cleanup_expired_templates(user_id: str) -> dict[str, Any]:
    user = odidb.get_user(user_id)
    if user is None:
        raise_404(f"존재하지 않는 user_id입니다: {user_id}")

    config = user.get("config") or {}
    raw_favorites = config.get("favorite_template_ids", config.get("favorite_templates", []))
    favorite_ids = [str(value) for value in raw_favorites if isinstance(value, str)] if isinstance(raw_favorites, list) else []
    deleted_template_ids = odidb.delete_expired_unlinked_templates(
        owner_id=user_id,
        favorite_template_ids=favorite_ids,
        max_age_minutes=60,
    )
    return {
        "message": "expired_unlinked_templates_deleted",
        "deleted_template_ids": deleted_template_ids,
    }
