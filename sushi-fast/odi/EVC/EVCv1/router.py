# xreal_rehair/evc/router.py

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .service import create_mock_session, get_session, update_evc_from_audio


router = APIRouter(
    prefix="/evc",
    tags=["xreal-rehear-evc"],
)


@router.post("/mock-session")
async def create_evc_mock_session():
    session = create_mock_session()

    return {
        "session_id": session.session_id,
        "message": "mock EVC session created",
        "personas": [persona.model_dump() for persona in session.personas],
        "evc_state": session.evc_state.model_dump(),
    }


@router.get("/sessions/{session_id}")
async def read_evc_session(session_id: str):
    try:
        session = get_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return {
        "session_id": session.session_id,
        "summary": session.summary,
        "step": session.step,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "personas": [persona.model_dump() for persona in session.personas],
        "evc_state": session.evc_state.model_dump(),
    }


@router.post("/update")
async def update_evc(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    language: str = Form("ko-KR"),
):
    try:
        return await update_evc_from_audio(
            session_id=session_id,
            audio=audio,
            language=language,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"EVC update failed: {e}") from e