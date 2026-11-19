from fastapi import APIRouter, Depends, HTTPException
from . import service
from . import JMT
from . import sushihash
from pydantic import BaseModel, ConfigDict
from fastapi import Response
from fastapi.responses import JSONResponse
import sqlite3
import json

from fastapi import Request

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    email: str
    code: str
    new_password: str


class EditUserRequest(BaseModel):
    id: int
    password: str | None = None
    email: str | None = None
    new_password: str | None = None
    name: str | None = None

class DeleteUserRequest(BaseModel):
    password: str

class EmailVerificationSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

class EmailVerificationConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str


def current_account_id(request: Request) -> int:
    payload = JMT.check_jwt(request, "mainauth")
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid account session")


def require_own_account(account_id: int, actor_id: int) -> None:
    if account_id != actor_id:
        raise HTTPException(status_code=403, detail="Account access denied")


def public_user(user):
    return {"id": user["id"], "email": user["email"], "name": user["name"], "email_verified": bool(user["email_verified"])}


def set_mainauth_cookie(response, request, user):
    token = JMT.make_jwt(user["id"], public_user(user), ["name", "email", "id", "email_verified"], lifetime_seconds=JMT.MAIN_SESSION_SECONDS)
    secure = _is_secure_request(request)
    response.set_cookie("mainauth", token, httponly=True, secure=secure,
        samesite="none" if secure else "lax", path="/", max_age=JMT.MAIN_SESSION_SECONDS)
    return JMT.jwt.decode(token, JMT.SECRET_KEY, algorithms=[JMT.ALGORITHM])


def _is_secure_request(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded == "https"

    # Cloudflare Tunnel provides the original scheme through Cf-Visitor.  Vite's
    # development proxy may not preserve X-Forwarded-Proto, so recognize both
    # standard headers before falling back to the internal HTTP hop.
    try:
        return json.loads(request.headers.get("cf-visitor", "{}")).get("scheme") == "https" or request.url.scheme == "https"
    except (TypeError, json.JSONDecodeError):
        return request.url.scheme == "https"


@router.post("/login")
def login(data: LoginRequest, request: Request):
    success, result = service.login_with_password(
        data.email.strip().lower(),
        data.password
    )

    response = JSONResponse({
        "success": success,
        "message": None if success else result
    })

    if success:
        set_mainauth_cookie(response, request, result)

    return response

@router.get("/isjwt")
def isjwt(request : Request, key : str, response: Response):
    payload = JMT.check_jwt(request, key)
    response.headers['Cache-Control'] = 'no-store'
    # Renew only a still-valid main session. Never accept an expired signature.
    if key == 'mainauth':
        from datetime import datetime, timezone
        user = service.userdb.get_user(user_id=current_account_id(request))
        if user is None:
            raise HTTPException(status_code=401, detail="Account not found")
        latest = public_user(user)
        if payload.get('data') != latest or payload['exp'] - datetime.now(timezone.utc).timestamp() < 7 * 86400:
            payload = set_mainauth_cookie(response, request, user)
        else:
            payload['data'] = latest
    return payload

        

@router.post("/logout")
def logout(request: Request):
    response = JSONResponse({
        "success": True
    })

    secure_cookie = _is_secure_request(request)
    response.delete_cookie(
        key="mainauth",
        path="/",
        secure=secure_cookie,
        samesite="none" if secure_cookie else "lax"
    )

    return response


@router.post("/register/send")
def register_send(data: RegisterRequest):
    try:
        success = service.send_verification_email(
            data.email,
            data.password,
            data.name
        )
    except sushihash.PasswordTooLongError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=400)

    return {
        "success": success
    }


@router.post("/password-reset/send")
def password_reset_send(data: PasswordResetRequest):
    service.request_password_reset(data.email.strip().lower())
    return {"success": True}


@router.post("/password-reset/confirm")
def password_reset_confirm(data: PasswordResetConfirmRequest):
    success, message = service.reset_password(
        data.email.strip().lower(), data.code.strip(), data.new_password
    )
    return {
        "success": success,
        "message": message
    }


@router.post("/register/verify")
def register_verify(data: VerifyCodeRequest):
    success, result = service.verify_register_code(
        data.email,
        data.code
    )

    return {
        "success": success,
        "data": {k: result[k] for k in ("id", "email", "name")} if success else None,
        "message": None if success else result
    }


@router.post("/login/send")
def login_send(data: VerifyCodeRequest):
    success = service.send_verification_email(
        data.email
    )

    return {
        "success": success
    }


@router.post("/login/verify")
def login_verify(data: VerifyCodeRequest):
    success, result = service.verify_login_code(
        data.email,
        data.code
    )

    return {
        "success": success,
        "data": {k: result[k] for k in ("id", "email", "name")} if success else None,
        "message": None if success else result
    }


@router.put("/user")
def edit_user(data: EditUserRequest, request: Request, response: Response, actor_id: int = Depends(current_account_id)):
    require_own_account(data.id, actor_id)
    current = service.userdb.get_user(user_id=actor_id)
    if current is None:
        raise HTTPException(status_code=401, detail="Account not found")
    if data.email is not None and data.email.strip() and data.email.strip() != current["email"]:
        if not service.verify_account_password(current, data.password):
            raise HTTPException(status_code=403, detail="Current password required")
    try:
        success, result = service.edit_user(
            id=actor_id,
            password=data.password,
            email=data.email,
            new_password=data.new_password,
            name=data.name,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Profile update conflict")

    if success:
        set_mainauth_cookie(response, request, result)
    return {
        "success": success,
        "data": public_user(result) if success else None,
        "message": None if success else result,
        "email_verification_required": not bool(result["email_verified"]) if success else None,
    }


@router.post("/user/email-verification/send")
def send_user_email_verification(data: EmailVerificationSendRequest | None = None, actor_id: int = Depends(current_account_id)):
    result = service.send_account_email_verification(actor_id)
    if result == "missing":
        raise HTTPException(status_code=401, detail="Account not found")
    if result == "cooldown":
        raise HTTPException(status_code=429, detail="Please wait before requesting another email")
    if result == "verified":
        raise HTTPException(status_code=409, detail="Email already verified")
    if result == "changed":
        raise HTTPException(status_code=409, detail="Account email changed; retry")
    if result != "ok":
        raise HTTPException(status_code=503, detail="Email delivery unavailable")
    return {"success": True}


@router.post("/user/email-verification/confirm")
def confirm_user_email_verification(data: EmailVerificationConfirmRequest, request: Request,
                                    response: Response, actor_id: int = Depends(current_account_id)):
    result, user = service.confirm_account_email_verification(actor_id, data.code)
    if result == "missing":
        raise HTTPException(status_code=401, detail="Account not found")
    if result != "ok":
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    set_mainauth_cookie(response, request, user)
    return {"success": True, "data": public_user(user), "email_verification_required": False}


@router.delete("/user/{user_id}")
def delete_user(user_id: int, data: DeleteUserRequest, actor_id: int = Depends(current_account_id)):
    require_own_account(user_id, actor_id)
    current = service.userdb.get_user(user_id=actor_id)
    if current is None or not service.verify_account_password(current, data.password):
        raise HTTPException(status_code=403, detail="Current password required")
    service.delete_user(actor_id)

    return {
        "success": True
    }
