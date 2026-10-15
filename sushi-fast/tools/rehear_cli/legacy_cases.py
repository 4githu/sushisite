"""Explicit text-case import; never treats historical LLM scores as measurements."""
from rehear_ai.evidence import build_evidence_pack
from rehear_ai.validation import digest


def post_presentation_case(case):
    if not isinstance(case, dict) or not isinstance(case.get("segments"), list):
        raise ValueError("legacy case needs an explicit segment list")
    slides = case.get("slides", [])
    if not isinstance(slides, list) or not all(isinstance(slide, dict) for slide in slides):
        raise ValueError("legacy slides must be objects")
    segments = []
    for step, item in enumerate(case["segments"], 1):
        if not isinstance(item, dict):
            raise ValueError("legacy segments must be objects")
        index = item.get("slide_index")
        slide = slides[index] if isinstance(index, int) and 0 <= index < len(slides) else {}
        segments.append({"source_id": f"segment-{step}", "step": step,
            "client_time_s": item["client_time_s"], "transcript": item["text"],
            "slide_index": index, "slide_text": slide.get("text"), "slide_text_truncated": None,
            "missing_inputs": ["legacy_case_not_observed_session", "speech_metrics"]})
    # Legacy qa_answers contain no question IDs/text. Do not invent the pairing.
    return build_evidence_pack({"source_id": case["id"], "segments": segments, "qa_history": None,
        "excluded_inputs": ["unpaired_legacy_qa_answers", "legacy_case_title", "model_report_scores"]},
        source_version="legacy-post-case.v1:" + digest(case))
