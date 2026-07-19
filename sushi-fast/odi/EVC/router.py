# xreal_rehair/evc/router.py

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .schema import UtterancePosition
from .service import create_smart_session, get_session, update_evc_from_audio


router = APIRouter(
    prefix="/xreal_rehear/evc",
    tags=["xreal-rehear-evc"],
)


@router.post("/smart-start")
async def smart_start(
    presentation_title: str = Form(...),
    topic_interest: str = Form("middle"),
    prior_knowledge: str = Form("middle"),
    slide_file: UploadFile | None = File(None),
):
    try:
        session = await create_smart_session(
            presentation_title=presentation_title,
            topic_interest=topic_interest,
            prior_knowledge=prior_knowledge,
            slide_file=slide_file,
        )

        return {
            "session_id": session.session_id,
            "presentation_title": session.presentation_title,
            "initial_evc_state": session.evc_state.model_dump(),
            "topic_interest": session.topic_interest,
            "prior_knowledge": session.prior_knowledge,
            "slide_count": len(session.slides),
            "slides": [slide.model_dump() for slide in session.slides],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"smart-start failed: {e}") from e


@router.get("/sessions/{session_id}")
async def read_session(session_id: str):
    try:
        session = get_session(session_id)

        return {
            "session_id": session.session_id,
            "presentation_title": session.presentation_title,
            "evc_state": session.evc_state.model_dump(),
            "step": session.step,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "topic_interest": session.topic_interest,
            "prior_knowledge": session.prior_knowledge,
            "segment_notes": session.segment_notes,
            "slide_count": len(session.slides),
            "slides": [slide.model_dump() for slide in session.slides],
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/update")
async def update_evc(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    current_slide_index: int = Form(0),
    utterance_position: UtterancePosition = Form("during_speech"),
    language: str = Form("ko-KR"),
    gaze_delivery_score: float | None = Form(None),
):
    try:
        return await update_evc_from_audio(
            session_id=session_id,
            audio=audio,
            current_slide_index=current_slide_index,
            utterance_position=utterance_position,
            language=language,
            gaze_delivery_score=gaze_delivery_score,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"EVC update failed: {e}") from e