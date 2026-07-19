from fastapi import APIRouter
from . import service
from . import JMT
from pydantic import BaseModel
from fastapi import Response
from fastapi.responses import JSONResponse

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


class EditUserRequest(BaseModel):
    id: int
    password: str | None = None
    email: str | None = None
    new_password: str | None = None
    name: str | None = None




@router.post("/login")
def login(data: LoginRequest):
    success, result = service.login_with_password(
        data.email,
        data.password
    )

    response = JSONResponse({
        "success": success
    })

    if success:
        token = JMT.make_jwt(result["id"], result, ["name", "email", "id"], )

        response.set_cookie(
            key="mainauth",
            value=token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=60 * 60
        )

    return response

@router.get("/isjwt")
def isjwt(request : Request, key : str):
    payload = JMT.check_jwt(request, key)
    
    return payload

        

@router.post("/logout")
def logout():
    response = JSONResponse({
        "success": True
    })

    response.delete_cookie(
        key="mainauth",
        path="/",
        secure=True,
        samesite="none"
    )

    return response


@router.post("/register/send")
def register_send(data: RegisterRequest):
    success = service.send_verification_email(
        data.email,
        data.password,
        data.name
    )

    return {
        "success": success
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