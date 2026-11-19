import hashlib
import asyncio
import io
import json
import wave
from uuid import UUID, uuid4

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


class PracticeRunRequest(BaseModel):
    metric_id: str
    source_session_id: str | None = None
    origin: str = "manual"


class FollowUpRequest(BaseModel):
    session_id: str


STAGES = ("baseline", "guided_practice", "independent_retry", "transfer_challenge")


@router.get("/practice/runs")
def list_practice_runs(request: Request, limit: int = 50, offset: int = 0):
    user = str(get_user_id_from_jwt(request))
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, "페이지 범위가 올바르지 않습니다.")
    db.ensure_report_schema()
    with db.get_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT run_id,metric_id,source_session_id,origin,created_at FROM practice_runs WHERE user_id=? ORDER BY created_at DESC,run_id DESC LIMIT ? OFFSET ?",
            (user, limit, offset),
        )]
    return {"runs": rows}


@router.post("/practice/runs")
def create_practice_run(payload: PracticeRunRequest, request: Request):
    user = str(get_user_id_from_jwt(request))
    db.ensure_report_schema()
    if payload.metric_id not in AVAILABLE:
        raise HTTPException(422, "지원하지 않는 훈련입니다.")
    if payload.origin != "manual":
        raise HTTPException(422, "검증되지 않은 추천 출처입니다.")
    run_id = str(uuid4())
    with db.get_conn() as conn:
        if payload.source_session_id and not conn.execute(
            "SELECT 1 FROM sessions WHERE session_id=? AND user_id=? AND state='completed'",
            (payload.source_session_id, user),
        ).fetchone():
            raise HTTPException(404, "원본 세션을 찾을 수 없습니다.")
        conn.execute(
            "INSERT INTO practice_runs(run_id,user_id,metric_id,source_session_id,origin,created_at) VALUES(?,?,?,?,?,?)",
            (run_id, user, payload.metric_id, payload.source_session_id, payload.origin, db.utc_now()),
        )
    return {"run_id": run_id, "metric_id": payload.metric_id, "source_session_id": payload.source_session_id, "origin": payload.origin}


@router.get("/practice/runs/{run_id}")
def get_practice_run(run_id: UUID, request: Request):
    user = str(get_user_id_from_jwt(request))
    db.ensure_report_schema()
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM practice_runs WHERE run_id=? AND user_id=?", (str(run_id), user)).fetchone()
        if row is None:
            raise HTTPException(404, "연습 흐름을 찾을 수 없습니다.")
        stages = [dict(r) for r in conn.execute(
            "SELECT s.stage,a.attempt_id,a.state,a.score,a.target_seconds,a.duration_seconds,a.completed_at FROM practice_run_stages s JOIN practice_attempts a ON s.attempt_id=a.attempt_id WHERE s.run_id=? AND a.user_id=? ORDER BY CASE s.stage WHEN 'baseline' THEN 1 WHEN 'guided_practice' THEN 2 WHEN 'independent_retry' THEN 3 ELSE 4 END",
            (str(run_id), user),
        )]
        followups = [r[0] for r in conn.execute(
            "SELECT f.session_id FROM practice_run_followups f JOIN sessions s ON s.session_id=f.session_id WHERE f.run_id=? AND s.user_id=? ORDER BY s.created_at,f.session_id",
            (str(run_id), user),
        )]
        failed = [dict(r) for r in conn.execute(
            "SELECT f.stage,f.attempt_id FROM practice_run_failed_attempts f JOIN practice_attempts a ON a.attempt_id=f.attempt_id WHERE f.run_id=? AND a.user_id=? ORDER BY a.created_at,f.attempt_id",
            (str(run_id), user),
        )]
    return {**dict(row), "stages": stages, "failed_stage_attempts": failed, "follow_up_sessions": followups}


@router.post("/practice/runs/{run_id}/followups")
def add_practice_followup(run_id: UUID, payload: FollowUpRequest, request: Request):
    user = str(get_user_id_from_jwt(request))
    db.ensure_report_schema()
    with db.get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute("SELECT source_session_id,created_at FROM practice_runs WHERE run_id=? AND user_id=?", (str(run_id), user)).fetchone()
        if run is None:
            raise HTTPException(404, "연습 흐름을 찾을 수 없습니다.")
        session = conn.execute("SELECT started_at,ended_at FROM sessions WHERE session_id=? AND user_id=? AND state='completed'", (payload.session_id, user)).fetchone()
        if session is None:
            raise HTTPException(404, "후속 세션을 찾을 수 없습니다.")
        if run["source_session_id"] == payload.session_id:
            raise HTTPException(409, "원본 세션은 후속 세션이 아닙니다.")
        completed = conn.execute("SELECT a.completed_at FROM practice_run_stages s JOIN practice_attempts a ON a.attempt_id=s.attempt_id WHERE s.run_id=? AND s.stage='transfer_challenge' AND a.state='completed'", (str(run_id),)).fetchone()
        if completed is None:
            raise HTTPException(409, "전이 과제를 완료해야 후속 세션을 연결할 수 있습니다.")
        if not session["started_at"] or not session["ended_at"] or not completed["completed_at"]:
            raise HTTPException(409, "세션과 연습의 시각을 확인할 수 없습니다.")
        ordered = conn.execute(
            "SELECT julianday(?) > julianday(?) AND julianday(?) > julianday(?) AND julianday(?) >= julianday(?)",
            (session["started_at"], run["created_at"], session["started_at"], completed["completed_at"], session["ended_at"], session["started_at"]),
        ).fetchone()[0]
        if ordered != 1:
            raise HTTPException(409, "연습 완료 이후 시작한 세션만 연결할 수 있습니다.")
        conn.execute("INSERT OR IGNORE INTO practice_run_followups(run_id,session_id) VALUES(?,?)", (str(run_id), payload.session_id))
    return {"run_id": str(run_id), "session_id": payload.session_id}


@router.post("/practice/attempts")
async def practice_attempt(
    request: Request,
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    attempt_id: UUID = Form(...),
    metric_id: str = Form(...),
    target_seconds: int = Form(60),
    run_id: UUID | None = Form(None),
    stage: str | None = Form(None),
    restart_failed: bool = Form(False),
):
    user = str(get_user_id_from_jwt(request))
    db.ensure_report_schema()
    if metric_id not in AVAILABLE or target_seconds not in (30, 60, 120, 180):
        raise HTTPException(422, "지원하지 않는 훈련입니다.")
    if (run_id is None) != (stage is None) or (stage is not None and stage not in STAGES):
        raise HTTPException(422, "연습 흐름과 단계가 올바르지 않습니다.")
    if restart_failed and run_id is None:
        raise HTTPException(422, "실패 단계의 연습 흐름이 필요합니다.")
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
        if run_id is not None:
            run = conn.execute("SELECT metric_id FROM practice_runs WHERE run_id=? AND user_id=?", (str(run_id), user)).fetchone()
            if run is None:
                raise HTTPException(404, "연습 흐름을 찾을 수 없습니다.")
            if run["metric_id"] != metric_id:
                raise HTTPException(409, "연습 흐름의 역량이 다릅니다.")
        prior = conn.execute(
            "SELECT * FROM practice_attempts WHERE attempt_id=?", (key,)
        ).fetchone()
        if prior:
            if prior["user_id"] != user:
                raise HTTPException(404, "훈련 기록을 찾을 수 없습니다.")
            historical = conn.execute(
                "SELECT 1 FROM practice_run_failed_attempts WHERE attempt_id=?", (key,)
            ).fetchone()
            if historical:
                raise HTTPException(409, "교체된 실패 시도는 다시 제출할 수 없습니다.")
            linked = conn.execute("SELECT run_id,stage FROM practice_run_stages WHERE attempt_id=?", (key,)).fetchone()
            if (str(run_id) if run_id else None, stage) != ((linked["run_id"], linked["stage"]) if linked else (None, None)):
                raise HTTPException(409, "기존 훈련의 연습 단계가 다릅니다.")
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
            replaced_attempt_id = None
            if run_id is not None:
                previous = STAGES[STAGES.index(stage) - 1] if stage != "baseline" else None
                if previous and not conn.execute(
                    "SELECT 1 FROM practice_run_stages s JOIN practice_attempts a ON s.attempt_id=a.attempt_id WHERE s.run_id=? AND s.stage=? AND a.state='completed'",
                    (str(run_id), previous),
                ).fetchone():
                    raise HTTPException(409, "이전 연습 단계를 완료해야 합니다.")
                current = conn.execute("SELECT s.attempt_id,a.state FROM practice_run_stages s JOIN practice_attempts a ON a.attempt_id=s.attempt_id WHERE s.run_id=? AND s.stage=?", (str(run_id), stage)).fetchone()
                if current:
                    if not restart_failed or current["state"] != "failed":
                        raise HTTPException(409, "이미 기록된 연습 단계입니다.")
                    replaced_attempt_id = current["attempt_id"]
                elif restart_failed:
                    raise HTTPException(409, "재시작할 실패 단계가 없습니다.")
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
            if run_id is not None:
                if replaced_attempt_id:
                    conn.execute("INSERT INTO practice_run_failed_attempts(run_id,stage,attempt_id) VALUES(?,?,?)", (str(run_id), stage, replaced_attempt_id))
                    conn.execute("UPDATE practice_run_stages SET attempt_id=? WHERE run_id=? AND stage=?", (key, str(run_id), stage))
                else:
                    conn.execute("INSERT INTO practice_run_stages(run_id,stage,attempt_id) VALUES(?,?,?)", (str(run_id), stage, key))
    background_tasks.add_task(
        analyze_attempt, key, data, metric_id, duration, target_seconds
    )
    return {"attempt_id": key, "state": "queued"}
