import hashlib
import asyncio
import io
import json
import wave
from uuid import UUID
from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel, Field
from odi.db import odidb as db
from odi.db.router import get_user_id_from_jwt
from odi.files.service import path_from_storage_path, STORAGE_ROOT, load_pdf_backend
from .service import AVAILABLE, CATALOG, check_script, analyze_attempt, progress

router = APIRouter(prefix="/coaching", tags=["coaching"])


class ScriptSection(BaseModel):
    slide: int | None = Field(default=None, ge=1)
    text: str


class ScriptRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    version: int = 0
    slide_path: str | None = None
    sections: list[ScriptSection] | None = None


@router.post("/script/check")
async def script_check(payload: ScriptRequest, request: Request):
    user = str(get_user_id_from_jwt(request))
    pages = []
    if not payload.text.strip():
        raise HTTPException(422, "스크립트를 입력해 주세요.")
    sections = (
        [s.model_dump() for s in payload.sections]
        if payload.sections is not None
        else None
    )
    if sections is not None and "".join(s["text"] for s in sections) != payload.text:
        raise HTTPException(422, "슬라이드별 텍스트가 전체 원문과 일치하지 않습니다.")
    if payload.slide_path:
        path = path_from_storage_path(payload.slide_path)
        if (STORAGE_ROOT / "users" / user).resolve() not in path.parents:
            raise HTTPException(403, "현재 사용자의 자료만 분석할 수 있습니다.")
        if path.is_file():
            try:
                with load_pdf_backend().open(path) as doc:
                    pages = [p.get_text()[:5000] for p in doc][:100]
            except Exception:
                pages = []
    result = await asyncio.to_thread(check_script, payload.text, pages, sections)
    return {
        **result,
        "version": payload.version,
        "page_count": len(pages),
        "mapping_available": any(pages),
    }


@router.get("/practice")
def practice_list(request: Request):
    user = str(get_user_id_from_jwt(request))
    db.ensure_report_schema()
    with db.get_conn() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM practice_attempts WHERE user_id=? ORDER BY created_at DESC",
                (user,),
            )
        ]
    for row in rows:
        row["feedback"] = json.loads(row["feedback"]) if row["feedback"] else None
    return {
        "catalog": [
            {
                "id": i,
                "title": title,
                "group": group,
                "task": task,
                "available": i in AVAILABLE,
            }
            for i, title, group, task in CATALOG
        ],
        "attempts": rows,
        "progress": progress(rows),
    }


@router.post("/practice/attempts")
async def practice_attempt(
    request: Request,
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    attempt_id: UUID = Form(...),
    metric_id: str = Form(...),
    target_seconds: int = Form(60),
):
    user = str(get_user_id_from_jwt(request))
    db.ensure_report_schema()
    if metric_id not in AVAILABLE or target_seconds not in (30, 60, 120, 180):
        raise HTTPException(422, "지원하지 않는 훈련입니다.")
    data = await audio.read(18_000_001)
    await audio.close()
    if len(data) > 18_000_000:
        raise HTTPException(413, "녹음 파일이 너무 큽니다.")
    try:
        with wave.open(io.BytesIO(data)) as wav:
            duration = wav.getnframes() / wav.getframerate()
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or not 8000 <= wav.getframerate() <= 48000
                or not 1 <= duration <= 181
            ):
                raise ValueError()
            if len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2:
                raise ValueError()
    except Exception:
        raise HTTPException(422, "1초 이상 3분 이내의 모노 WAV 녹음을 보내 주세요.")
    key = str(attempt_id)
    request_hash = hashlib.sha256(data).hexdigest()
    with db.get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        prior = conn.execute(
            "SELECT * FROM practice_attempts WHERE attempt_id=?", (key,)
        ).fetchone()
        if prior:
            if prior["user_id"] != user:
                raise HTTPException(404, "훈련 기록을 찾을 수 없습니다.")
            if (
                prior["metric_id"] != metric_id
                or prior["target_seconds"] != target_seconds
                or (prior["request_hash"] and prior["request_hash"] != request_hash)
            ):
                raise HTTPException(409, "훈련 요청이 변경되었습니다.")
            if prior["state"] != "failed":
                return {"attempt_id": key, "state": prior["state"]}
            conn.execute(
                "UPDATE practice_attempts SET state='queued',error=NULL,duration_seconds=? WHERE attempt_id=?",
                (duration, key),
            )
        else:
            conn.execute(
                "INSERT INTO practice_attempts(attempt_id,user_id,metric_id,duration_seconds,target_seconds,created_at,request_hash) VALUES(?,?,?,?,?,?,?)",
                (
                    key,
                    user,
                    metric_id,
                    duration,
                    target_seconds,
                    db.utc_now(),
                    request_hash,
                ),
            )
    background_tasks.add_task(
        analyze_attempt, key, data, metric_id, duration, target_seconds
    )
    return {"attempt_id": key, "state": "queued"}
