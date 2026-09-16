from fastapi import APIRouter
from . import service
from . import JMT
from . import sushihash
from pydantic import BaseModel
from fastapi import Response
from fastapi.responses import JSONResponse
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
        token = JMT.make_jwt(result["id"], result, ["name", "email", "id"], )

        secure_cookie = _is_secure_request(request)
        response.set_cookie(
            key="mainauth",
            value=token,
            httponly=True,
            secure=secure_cookie,
            samesite="none" if secure_cookie else "lax",
            path="/",
            max_age=60 * 60
        )

    return response

@router.get("/isjwt")
def isjwt(request : Request, key : str):
    payload = JMT.check_jwt(request, key)
    
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
        "data": result if success else None,
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
        "data": result if success else None,
        "message": None if success else result
    }


@router.put("/user")
def edit_user(data: EditUserRequest):
    success, result = service.edit_user(
        id=data.id,
        password=data.password,
        email=data.email,
        new_password=data.new_password,
        name=data.name,
    )

    return {
        "success": success,
        "data": result if success else None,
        "message": None if success else result
    }


@router.delete("/user/{user_id}")
def delete_user(user_id: int):
    service.delete_user(user_id)

    return {
        "success": True
    }
