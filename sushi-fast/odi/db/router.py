# odi/db/router.py

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
# odi/db/router.py 상단 import 근처에 추가

from odi.files.service import commit_template_files

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
    TemplateCreateRequest,
    TemplateUpdateRequest,
    UserCreateRequest,
)


router = APIRouter(
    prefix="/db",
    tags=["odi-db"],
)


JWT_COOKIE_KEY = "odi_token"
DEMO_REPORT_TEMPLATE_ID = "template_demo_algorithm_choice"


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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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


@router.post("/templates")
def create_template(payload: TemplateCreateRequest) -> dict[str, Any]:
    try:
        template_id = odidb.create_template(
            owner_id=payload.owner_id,
            template=payload.template,
            template_id=payload.template_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    template = odidb.get_template(template_id)

    return {
        "message": "template_created",
        "template": template,
    }


@router.get("/templates/{template_id}")
def get_template(template_id: str) -> dict[str, Any]:
    template = odidb.get_template(template_id)

    if template is None:
        raise_404(f"존재하지 않는 template_id입니다: {template_id}")

    return {
        "template": template,
    }


@router.get("/users/{user_id}/templates")
def list_user_templates(user_id: str) -> dict[str, Any]:
    user = odidb.get_user(user_id)

    if user is None:
        raise_404(f"존재하지 않는 user_id입니다: {user_id}")

    templates = odidb.list_templates_by_owner(user_id)

    return {
        "user_id": user_id,
        "templates": templates,
    }


@router.put("/templates/{template_id}")
def update_template(
    template_id: str,
    payload: TemplateUpdateRequest,
) -> dict[str, Any]:
    try:
        odidb.update_template(
            template_id=template_id,
            template=payload.template,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    template = odidb.get_template(template_id)

    return {
        "message": "template_updated",
        "template": template,
    }


@router.delete("/templates/{template_id}")
def delete_template(template_id: str) -> dict[str, str]:
    try:
        odidb.delete_template(template_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "template_deleted",
    }


# odi/db/router.py 안의 기존 start_pre_session_from_recent 함수를 이걸로 교체

@router.post("/pre-sessions/start-from-recent")
def start_pre_session_from_recent(
    payload: PreSessionStartRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        user_id = get_user_id_from_jwt(request)
        if str(payload.user_id) != str(user_id):
            raise HTTPException(status_code=403, detail="다른 사용자의 세션을 시작할 수 없습니다.")

        user = odidb.get_user(user_id)

        if user is None:
            raise ValueError(f"존재하지 않는 user_id입니다: {payload.user_id}")

        recent_template = user.get("recent_template")

        if recent_template is None:
            raise ValueError("recent_template이 없습니다.")

        committed_template, bundle_info = commit_template_files(
            user_id=user_id,
            template=recent_template,
        )

        template_id = odidb.create_template(
            owner_id=user_id,
            template=committed_template,
        )

        saved_template = odidb.get_template(template_id)

        if saved_template is None:
            raise ValueError("템플릿 저장 후 조회에 실패했습니다.")

        odidb.update_recent_template(
            user_id=user_id,
            template=saved_template["template"],
        )

        pre_session = odidb.create_pre_session(
            template_id=template_id,
            expires_minutes=payload.expires_minutes,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "pre_session_created",
        "pin_code": pre_session["pin_code"],
        "pre_session": pre_session,
        "template": saved_template,
        "file_bundle": bundle_info,
    }

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
        session_id = odidb.start_session_from_template(
            user_id=user_id,
            template_id=pre_session["template_id"],
        )

        odidb.finish_session(
            session_id=session_id,
            feedback=payload.feedback,
        )

        odidb.attach_session_to_pre_session(
            pin_code=pin_code,
            session_id=session_id,
            state="finished",
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
def get_session(session_id: str) -> dict[str, Any]:
    session = odidb.get_session(session_id)

    if session is None:
        raise_404(f"존재하지 않는 session_id입니다: {session_id}")

    return {
        "session": session,
    }


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
    limit: int = 20,
) -> dict[str, Any]:
    user = odidb.get_user(user_id)

    if user is None:
        raise_404(f"존재하지 않는 user_id입니다: {user_id}")

    sessions = odidb.list_sessions_by_user(
        user_id=user_id,
        limit=limit,
    )

    return {
        "user_id": user_id,
        "sessions": sessions,
    }


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user_id: str) -> dict[str, str]:
    try:
        odidb.delete_session(session_id, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "session_deleted",
    }


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
