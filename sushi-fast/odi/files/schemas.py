# odi/files/schemas.py
from pydantic import BaseModel
from typing import Literal

class FileRef(BaseModel):
    storage_path: str | None = None
    original_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    status: Literal["temp", "committed"]
    uploaded_at: str | None = None
    expires_at: str | None = None
    page_count: int | None = None
    image_manifest_path: str | None = None

class UploadTempResponse(BaseModel):
    success: bool
    file: FileRef