import re
from dataclasses import dataclass

from ...schemas import (
    AlignmentStatus,
    ErrorLocation,
    Observation,
    PracticeGuidance,
    SpeechWord,
    SyllableResult,
    WordResult,
)
from ..rules import PRACTICE_RESOURCES
from .articulation import get_articulation_tip


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")


@dataclass(frozen=True)
class TextToken:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class AlignmentSummary:
    word_results: list[WordResult]
    matched_syllable_count: int
    total_target_syllable_count: int


def normalize_text(text: str) -> str:
    return "".join(TOKEN_PATTERN.findall(text)).lower()


def tokenize_with_positions(text: str) -> list[TextToken]:
    return [
        TextToken(match.group(), match.start(), match.end())
        for match in TOKEN_PATTERN.finditer(text)
    ]


def _align_sequences(
    expected: list[str],
    recognized: list[str],
) -> list[tuple[AlignmentStatus, int | None, int | None]]:
    rows = len(expected) + 1
    columns = len(recognized) + 1
    costs = [[0] * columns for _ in range(rows)]

    for row in range(1, rows):
        costs[row][0] = row
    for column in range(1, columns):
        costs[0][column] = column

    for row in range(1, rows):
        for column in range(1, columns):
            substitution = costs[row - 1][column - 1] + (
                0 if expected[row - 1] == recognized[column - 1] else 1
            )
            costs[row][column] = min(
                substitution,
                costs[row - 1][column] + 1,
                costs[row][column - 1] + 1,
            )

    aligned: list[tuple[AlignmentStatus, int | None, int | None]] = []
    row = len(expected)
    column = len(recognized)

    while row or column:
        if row and column:
            status = (
                AlignmentStatus.CORRECT
                if expected[row - 1] == recognized[column - 1]
                else AlignmentStatus.SUBSTITUTION
            )
            diagonal_cost = costs[row - 1][column - 1] + (
                0 if status == AlignmentStatus.CORRECT else 1
            )
            if costs[row][column] == diagonal_cost:
                aligned.append((status, row - 1, column - 1))
                row -= 1
                column -= 1
                continue

        if row and costs[row][column] == costs[row - 1][column] + 1:
            aligned.append((AlignmentStatus.DELETION, row - 1, None))
            row -= 1
        else:
            aligned.append((AlignmentStatus.INSERTION, None, column - 1))
            column -= 1

    aligned.reverse()
    return aligned


def align_syllables(expected: str, recognized: str) -> list[SyllableResult]:
    expected_units = list(normalize_text(expected))
    recognized_units = list(normalize_text(recognized))
    return [
        SyllableResult(
            target_index=target_index,
            transcript_index=transcript_index,
            expected=(
                expected_units[target_index]
                if target_index is not None
                else None
            ),
            recognized=(
                recognized_units[transcript_index]
                if transcript_index is not None
                else None
            ),
            status=status,
        )
        for status, target_index, transcript_index in _align_sequences(
            expected_units,
            recognized_units,
        )
    ]


def _first_focus_syllable(
    status: AlignmentStatus,
    expected: str | None,
    recognized: str | None,
    syllable_results: list[SyllableResult],
) -> tuple[int | None, str | None, str | None]:
    if status == AlignmentStatus.SUBSTITUTION:
        for result in syllable_results:
            if result.status != AlignmentStatus.CORRECT:
                return result.target_index, result.expected, result.recognized
    if status == AlignmentStatus.DELETION:
        return 0, expected, None
    if status == AlignmentStatus.INSERTION:
        return None, None, recognized
    return None, expected, recognized


def _display_label(
    *,
    display_position: int | None,
    expected: str | None,
    recognized: str | None,
    status: AlignmentStatus,
) -> str | None:
    if display_position is None:
        if status == AlignmentStatus.INSERTION and recognized:
            return f"추가 인식: {recognized}"
        return None
    if status == AlignmentStatus.DELETION:
        return f"{display_position}번째 글자: {expected} 누락"
    if status == AlignmentStatus.INSERTION:
        return f"{display_position}번째 글자 주변: +{recognized}"
    return f"{display_position}번째 글자: {expected} -> {recognized}"


def _observation_message(
    *,
    display_position: int | None,
    expected: str | None,
    recognized: str | None,
    status: AlignmentStatus,
) -> str:
    prefix = f"{display_position}번째 글자 " if display_position is not None else ""
    if status == AlignmentStatus.SUBSTITUTION:
        return (
            f"{prefix}'{expected}'가 STT에서 "
            f"'{recognized}'로 다르게 인식되었습니다."
        )
    if status == AlignmentStatus.DELETION:
        return f"{prefix}'{expected}'가 STT 전사에서 관측되지 않았습니다."
    if status == AlignmentStatus.INSERTION:
        return f"목표 문장에 없는 '{recognized}'가 STT에서 관측되었습니다."
    return f"{prefix}'{expected}'의 STT 근거가 불확실합니다."


def _build_result_context(
    *,
    status: AlignmentStatus,
    target_index: int | None,
    target_token: TextToken | None,
    recognized_word: str | None,
    syllable_results: list[SyllableResult],
) -> tuple[ErrorLocation | None, Observation, PracticeGuidance | None]:
    focus_syllable_index, expected, recognized = _first_focus_syllable(
        status,
        target_token.text if target_token else None,
        recognized_word,
        syllable_results,
    )
    focus_start = None
    focus_end = None
    display_position = None
    if target_token is not None:
        focus_start = target_token.start
        focus_end = target_token.end
        if focus_syllable_index is not None:
            focus_start = target_token.start + focus_syllable_index
            focus_end = focus_start + 1
        display_position = focus_start + 1

    location = ErrorLocation(
        target_start_char_index=focus_start,
        target_end_char_index_exclusive=focus_end,
        display_char_position=display_position,
        target_word_index=target_index,
        target_syllable_index=focus_syllable_index,
        display_label=_display_label(
            display_position=display_position,
            expected=expected,
            recognized=recognized,
            status=status,
        ),
    )
    observation = Observation(
        expected=expected,
        recognized=recognized,
        status=status,
        message=_observation_message(
            display_position=display_position,
            expected=expected,
            recognized=recognized,
            status=status,
        ),
    )
    tip = get_articulation_tip(expected)
    practice = None
    if tip or expected:
        practice = PracticeGuidance(
            tip=(tip.tip if tip else None),
            articulation_tip_id=(tip.articulation_tip_id if tip else None),
            practice_resource_id=(
                tip.practice_resource_id
                if tip and tip.practice_resource_id
                else PRACTICE_RESOURCES.get(expected or "")
            ),
        )
    return location, observation, practice


def align_text(
    target_text: str,
    transcript: str,
    stt_words: list[SpeechWord],
) -> AlignmentSummary:
    target_tokens = tokenize_with_positions(target_text)
    target_values = [normalize_text(token.text) for token in target_tokens]

    if stt_words:
        recognized_words = [word.word for word in stt_words]
        confidence_by_index = {
            index: word.confidence for index, word in enumerate(stt_words)
        }
    else:
        recognized_words = [
            token.text for token in tokenize_with_positions(transcript)
        ]
        confidence_by_index = {}

    transcript_values = [normalize_text(word) for word in recognized_words]

    word_results: list[WordResult] = []
    matched_count = 0
    total_count = sum(len(value) for value in target_values)

    for status, target_index, transcript_index in _align_sequences(
        target_values,
        transcript_values,
    ):
        target_token = (
            target_tokens[target_index] if target_index is not None else None
        )
        recognized_word = (
            recognized_words[transcript_index]
            if transcript_index is not None
            else None
        )

        if status == AlignmentStatus.CORRECT:
            matched_count += len(target_values[target_index])
            continue

        syllable_results: list[SyllableResult] = []
        if status == AlignmentStatus.SUBSTITUTION:
            syllable_results = align_syllables(
                target_token.text,
                recognized_word,
            )
            matched_count += sum(
                item.status == AlignmentStatus.CORRECT
                for item in syllable_results
            )

        location, observation, practice = _build_result_context(
            status=status,
            target_index=target_index,
            target_token=target_token,
            recognized_word=recognized_word,
            syllable_results=syllable_results,
        )
        word_results.append(
            WordResult(
                target_index=target_index,
                transcript_index=transcript_index,
                expected=target_token.text if target_token else None,
                recognized=recognized_word,
                status=status,
                target_start_char_index=(target_token.start if target_token else None),
                target_end_char_index_exclusive=(
                    target_token.end if target_token else None
                ),
                evidence_source="PRIMARY_STT",
                recognized_word_confidence=(
                    confidence_by_index.get(transcript_index)
                    if transcript_index is not None
                    else None
                ),
                syllable_results=syllable_results,
                location=location,
                observation=observation,
                practice=practice,
            )
        )

    return AlignmentSummary(
        word_results=word_results,
        matched_syllable_count=matched_count,
        total_target_syllable_count=total_count,
    )
