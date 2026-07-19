from fastapi import APIRouter

from odi.EVC.router import router as evc_router
from odi.db.router import router as db_router
from odi.files.router import router as files_router


router = APIRouter(
    prefix="/odi",
    tags=["odi"],
)

router.include_router(evc_router)
router.include_router(db_router)
router.include_router(files_router)

'''
configs = {}
results = {}


class Config(BaseModel):
    topic: str
    presenterName: str
    durationMin: int
    difficulty: str
    status: str = "started"


class Result(BaseModel):
    text: str
    configJson: str | None = None


@router.put("/api/sessions/{session_id}/config")
def save_config(session_id: str, config: Config):
    configs[session_id] = config.model_dump()
    return {
        "ok": True,
        "sessionId": session_id,
        "config": configs[session_id],
    }


@router.get("/api/sessions/{session_id}/config")
def get_config(session_id: str):
    if session_id not in configs:
        raise HTTPException(
            status_code=404,
            detail="Config not found",
        )

    return configs[session_id]


@router.post("/api/sessions/{session_id}/result")
def save_result(session_id: str, result: Result):
    results[session_id] = result.model_dump()
    return {
        "ok": True,
        "sessionId": session_id,
        "result": results[session_id],
    }


@router.get("/api/sessions/{session_id}/result")
def get_result(session_id: str):
    if session_id not in results:
        raise HTTPException(
            status_code=404,
            detail="Result not found",
        )

    return results[session_id]
    '''