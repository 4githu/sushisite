"""Explicit research export/storage. No service route calls this by default."""
from rehear_ai.evidence import OBSERVED_METRICS, build_evidence_pack as build_neutral_evidence
from rehear_ai.validation import validate_assessment


def _mapping(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)


def build_evidence_pack(records, *, source_version: str, source_id="backend-export",
                        stt_by_step=None, segment_offsets_s=None, slides=(), qa_history=None,
                        omitted_source_ids=(), truncated=False):
    """Reuse DTO/preprocessor outputs; offsets must be explicitly observed, never guessed.

    ReportSegmentRecord does not persist STT words. A caller with the original
    SpeechTextResult may supply it; otherwise word times remain missing. Existing
    slide DTOs do not prove that extracted text was complete.
    """
    stt_by_step, segment_offsets_s = stt_by_step or {}, segment_offsets_s or {}
    slide_by_index = {_mapping(slide)["index"]: _mapping(slide) for slide in slides}
    segments = []
    for value in records:
        record = _mapping(value)
        step = record["step"]
        context = record.get("context") or {}
        stt = _mapping(stt_by_step[step]) if step in stt_by_step else None
        if stt is not None and stt["transcript"] != record["transcript"]:
            raise ValueError("STT result does not belong to the supplied segment transcript")
        metrics = record.get("speech_metrics") or {}
        slide = slide_by_index.get(record.get("slide_index"))
        segments.append({"source_id": f"segment-{step}", "step": step,
            "client_time_s": record["client_time_s"], "segment_offset_s": segment_offsets_s.get(step),
            "transcript": record["transcript"], "words": stt.get("words") if stt is not None else None,
            "speech_metrics": {key: metrics[key] for key in OBSERVED_METRICS if key in metrics},
            "gaze_scalar": context.get("gaze_delivery_score"), "slide_index": record.get("slide_index"),
            "slide_text": slide.get("text") if slide else None, "slide_text_truncated": None,
            "missing_inputs": list((record.get("evaluation") or {}).get("missing_inputs") or [])})
    qa = None
    if qa_history is not None:
        qa = [{"source_id": f"qa-{index + 1}", "question": _mapping(entry)["question"],
               "answer": _mapping(entry).get("answer", _mapping(entry).get("transcript"))}
              for index, entry in enumerate(qa_history)]
    return build_neutral_evidence({"source_id": source_id, "segments": segments, "qa_history": qa,
        "omitted_source_ids": list(omitted_source_ids), "truncated": truncated,
        "excluded_inputs": ["prior_model_evaluation_scores", "prior_model_evaluation_prose",
                            "evc_state", "ai_reactions", "report_scores"]}, source_version=source_version)


def store_internal_result(records, *, run_id: str, result, evidence, rubric):
    """Opt-in caller-owned storage; no public report projection or implicit DB write."""
    result = validate_assessment(result, evidence, rubric)
    serialized = result.model_dump(mode="json")
    if not run_id.strip():
        raise ValueError("research run ID is required")
    if run_id in records and records[run_id] != serialized:
        raise ValueError("research run ID already contains a different result")
    records[run_id] = serialized
