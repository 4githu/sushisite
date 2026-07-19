import unittest

from Legendaryvowels.schemas import AudioMetrics, SpeechWord
from Legendaryvowels.services.sentence.alignment import align_text
from Legendaryvowels.services.sentence.scoring import calculate_delivery_score_components


class SentenceAnalysisTest(unittest.TestCase):
    def test_alignment_adds_original_text_location_and_tip(self):
        result = align_text(
            "안녕하세요, 고 발표를 시작하겠습니다.",
            "안녕하세요, 그 발표를 시작하겠습니다.",
            [
                SpeechWord(word="안녕하세요", start=0.64, end=1.6, confidence=0.51),
                SpeechWord(word="그", start=2.0, end=2.64, confidence=0.93),
                SpeechWord(word="발표를", start=3.36, end=4.4, confidence=0.99),
                SpeechWord(word="시작하겠습니다", start=4.48, end=5.6, confidence=0.99),
            ],
        )

        self.assertEqual(result.matched_syllable_count, 15)
        self.assertEqual(result.total_target_syllable_count, 16)
        self.assertEqual(len(result.word_results), 1)

        word_result = result.word_results[0]
        self.assertEqual(word_result.location.display_char_position, 8)
        self.assertEqual(word_result.location.display_label, "8번째 글자: 고 -> 그")
        self.assertEqual(
            word_result.observation.message,
            "8번째 글자 '고'가 STT에서 '그'로 다르게 인식되었습니다.",
        )
        self.assertEqual(
            word_result.practice.articulation_tip_id,
            "ko_syllable_go_tip_01",
        )
        self.assertIn("입술을 둥글게", word_result.practice.tip)

    def test_delivery_score_components_are_split(self):
        metrics = AudioMetrics(
            duration_sec=6.0,
            speech_duration_sec=5.2,
            silence_duration_sec=0.8,
            silence_ratio=0.13,
            long_pause_count=0,
            average_rms=0.02,
            peak_rms=0.08,
            speaking_rate_cpm=184.62,
            filler_count=1,
        )
        words = [
            SpeechWord(word="안녕하세요", start=0.64, end=1.6, confidence=0.51),
            SpeechWord(word="그", start=2.0, end=2.64, confidence=0.93),
            SpeechWord(word="발표를", start=3.36, end=4.4, confidence=0.99),
            SpeechWord(word="시작하겠습니다", start=4.48, end=5.6, confidence=0.99),
        ]

        timing_score, pause_score, fluency_score, delivery_score = (
            calculate_delivery_score_components(metrics, words)
        )

        self.assertIsNotNone(timing_score)
        self.assertEqual(pause_score, 100.0)
        self.assertEqual(fluency_score, 98.0)
        self.assertGreaterEqual(delivery_score, 0.0)
        self.assertLessEqual(delivery_score, 100.0)


if __name__ == "__main__":
    unittest.main()
