from ...schemas import LpcResult, LpcSyllableSegment, SpeechWord
from ..audio import decode_audio
from ..pronunciation.lpc import calculate_lpc
from ..rules import LPC_RULES
from ..sentence.alignment import normalize_text


def _word_syllables(word: str) -> list[str]:
    korean_syllables = [
        character for character in word if "가" <= character <= "힣"
    ]
    return korean_syllables or list(normalize_text(word))


def analyze_lpc_by_words(
    audio_path: str,
    words: list[SpeechWord],
) -> LpcResult:
    """Experimental sentence-word timestamp LPC slicing.

    This is intentionally outside the formal sentence and letter pipelines.
    It uses recognized word timestamps and equal syllable splitting, so the
    resulting windows are approximate demonstration data.
    """
    signal, sample_rate = decode_audio(audio_path)
    audio_duration = signal.size / sample_rate
    segments: list[LpcSyllableSegment] = []

    for transcript_index, word in enumerate(words):
        syllables = _word_syllables(word.word)
        word_start = max(0.0, min(float(word.start), audio_duration))
        word_end = max(word_start, min(float(word.end), audio_duration))
        if not syllables or word_end <= word_start:
            continue

        syllable_duration = (word_end - word_start) / len(syllables)
        margin_ratio = (1.0 - LPC_RULES.center_window_ratio) / 2.0

        for syllable_index, syllable in enumerate(syllables):
            segment_start = word_start + syllable_index * syllable_duration
            segment_end = segment_start + syllable_duration
            analysis_start = segment_start + syllable_duration * margin_ratio
            analysis_end = segment_end - syllable_duration * margin_ratio
            start_sample = max(0, round(analysis_start * sample_rate))
            end_sample = min(signal.size, round(analysis_end * sample_rate))
            analysis = calculate_lpc(
                signal[start_sample:end_sample],
                sample_rate,
            )
            segments.append(
                LpcSyllableSegment(
                    transcript_index=transcript_index,
                    word=word.word,
                    syllable_index=syllable_index,
                    syllable=syllable,
                    word_start_sec=round(word_start, 4),
                    word_end_sec=round(word_end, 4),
                    segment_start_sec=round(segment_start, 4),
                    segment_end_sec=round(segment_end, 4),
                    analysis_start_sec=round(analysis_start, 4),
                    analysis_end_sec=round(analysis_end, 4),
                    window_strategy="CENTER_WINDOW_APPROXIMATION",
                    analysis=analysis,
                )
            )

    return LpcResult(
        enabled=True,
        segmentation_method="EQUAL_SPLIT_BY_RECOGNIZED_SYLLABLE_COUNT",
        vowel_window_method="CENTER_WINDOW_APPROXIMATION",
        segments=segments,
    )
