from difflib import SequenceMatcher

from ...schemas import (
    AlignmentStatus,
    ProductMode,
    SentenceIssue,
    SentencePronunciationResult,
    SpeechWord,
)
from .alignment import normalize_text
from .service import analyze_voice


def calculate_text_accuracy(target_text: str, transcript: str) -> float:
    target = normalize_text(target_text)
    recognized = normalize_text(transcript)
    if not target:
        return 0.0
    return round(SequenceMatcher(None, target, recognized).ratio() * 100.0, 2)


def analyze_sentence_pronunciation(
    audio_path: str,
    target_text: str,
) -> SentencePronunciationResult:
    result = analyze_voice(
        audio_path=audio_path,
        mode=ProductMode.EDUCATION,
        session_id="legacy-session",
        attempt_id="legacy-attempt",
        target_text=target_text,
    )

    issues = []
    for word_result in result.word_results:
        issue_type = {
            AlignmentStatus.SUBSTITUTION: "substitution",
            AlignmentStatus.DELETION: "omission",
            AlignmentStatus.INSERTION: "insertion",
            AlignmentStatus.UNDETERMINED: "unknown",
        }.get(word_result.status)
        if issue_type is None:
            continue

        issues.append(
            SentenceIssue(
                target_text=word_result.expected or "",
                recognized_text=word_result.recognized,
                target_start_index=word_result.target_start_char_index,
                target_end_index=word_result.target_end_char_index_exclusive,
                target_word=word_result.expected,
                target_syllable=(
                    word_result.syllable_results[0].expected
                    if len(word_result.syllable_results) == 1
                    else None
                ),
                issue_type=issue_type,
                severity="medium",
                confidence=word_result.recognized_word_confidence or 0.0,
                comment=(
                    word_result.observation.message
                    if word_result.observation
                    else result.confidence_note
                ),
                practice_instruction=(
                    word_result.practice.tip
                    if word_result.practice and word_result.practice.tip
                    else result.feedback.next_action or "다시 연습해 보세요."
                ),
            )
        )

    return SentencePronunciationResult(
        target_text=target_text.strip(),
        transcript=result.transcript,
        text_accuracy=result.score.text_match_score or 0.0,
        pronunciation_score=result.score.overall_score or 0.0,
        needs_repractice=result.needs_repractice,
        summary_comment=(
            result.feedback.summary
            or "분석 근거가 충분하지 않아 결과를 확정하지 않았습니다."
        ),
        words=[
            SpeechWord(
                word=word.text,
                start=word.start_sec,
                end=word.end_sec,
                confidence=word.stt_confidence,
            )
            for word in result.words
        ],
        issues=issues,
    )
