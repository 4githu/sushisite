# odi/files/router.py

from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, Form
from fastapi.responses import FileResponse

from auth import JMT
from .service import path_from_storage_path, save_temp_upload


router = APIRouter(
    prefix="/files",
    tags=["odi-files"],
)

JWT_COOKIE_KEY = "odi_token"


def get_user_id_from_jwt(request: Request) -> str:
    payload = JMT.check_jwt(request, JWT_COOKIE_KEY)
    data = payload.get("data", {})
    user_id = data.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="JWT에 user_id가 없습니다.")

    return str(user_id)


@router.post("/upload-temp")
async def upload_temp_file(
    request: Request,
    role: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    user_id = get_user_id_from_jwt(request)
    file_ref = await save_temp_upload(user_id=user_id, role=role, upload=file)

    return {
        "success": True,
        "file": file_ref,
    }


@router.get("/read")
def read_file(
    request: Request,
    path: str,
) -> FileResponse:
    get_user_id_from_jwt(request)

    file_path = path_from_storage_path(path)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    return FileResponse(file_path)