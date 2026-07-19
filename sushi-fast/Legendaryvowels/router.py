import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .schemas import ProductMode, VoiceEvaluationResponse
from .services.pronunciation.base import EvaluationResult
from .services.pronunciation.feature import FeatureExtractionError
from .services.pronunciation.lpc_evaluator import ReferenceNotFoundError
from .services.sentence.legacy import analyze_sentence_pronunciation
from .services.sentence.service import analyze_voice
from .word_service import create_word_pronunciation_service


router = APIRouter(
    prefix="/pronunciation",
    tags=["pronunciation"],
)


def save_upload_file(
    upload: UploadFile,
    directory: str,
    prefix: str,
) -> str:
    suffix = Path(upload.filename or "").suffix or ".wav"
    destination = Path(directory) / f"{prefix}{suffix}"

    with destination.open("wb") as output:
        shutil.copyfileobj(upload.file, output)

    return str(destination)


@router.get("/health")
def health_check():
    return {"status": "ok", "apiVersion": "v1"}

@router.post(
    "/api/v1/analyze",
    response_model=VoiceEvaluationResponse,
    response_model_by_alias=True,
)
@router.post(
    "/analyze",
    response_model=VoiceEvaluationResponse,
    response_model_by_alias=True,
)
def analyze_voice_api(
    audio: UploadFile = File(...),
    mode: ProductMode = Form(...),
    session_id: str = Form(...),
    attempt_id: str = Form(...),
    target_text: str | None = Form(None),
    topic: str | None = Form(None),
    client_version: str | None = Form(None),
):
    del topic, client_version
    if mode == ProductMode.EDUCATION and not (target_text or "").strip():
        raise HTTPException(
            status_code=422,
            detail="education 모드에서는 target_text가 필요합니다.",
        )

    with tempfile.TemporaryDirectory() as directory:
        audio_path = save_upload_file(
            upload=audio,
            directory=directory,
            prefix="voice",
        )
        try:
            return analyze_voice(
                audio_path=audio_path,
                mode=mode,
                session_id=session_id,
                attempt_id=attempt_id,
                target_text=target_text,
            )
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

@router.post("/api/pronunciation/sentence")
@router.post("/sentence")
def analyze_sentence_api(
    target_text: str = Form(...),
    audio: UploadFile = File(...),
):
    with tempfile.TemporaryDirectory() as directory:
        audio_path = save_upload_file(
            upload=audio,
            directory=directory,
            prefix="sentence",
        )

        return analyze_sentence_pronunciation(
            audio_path=audio_path,
            target_text=target_text,
        )


@router.post(
    "/api/v1/pronunciation/word",
    response_model=EvaluationResult,
)
@router.post(
    "/word",
    response_model=EvaluationResult,
)
def analyze_word_api(
    vowel: str = Form(...),
    audio: UploadFile = File(...),
):
    with tempfile.TemporaryDirectory() as directory:
        audio_path = save_upload_file(
            upload=audio,
            directory=directory,
            prefix="word",
        )
        try:
            result = create_word_pronunciation_service().analyze(
                audio_path,
                vowel.strip(),
            )
            return result.evaluation
        except (FeatureExtractionError, ReferenceNotFoundError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
