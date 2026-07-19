from dataclasses import dataclass


HANGUL_BASE = 0xAC00
HANGUL_END = 0xD7A3
JUNGSEONG_COUNT = 21
JONGSEONG_COUNT = 28

VOWELS = [
    "ㅏ",
    "ㅐ",
    "ㅑ",
    "ㅒ",
    "ㅓ",
    "ㅔ",
    "ㅕ",
    "ㅖ",
    "ㅗ",
    "ㅘ",
    "ㅙ",
    "ㅚ",
    "ㅛ",
    "ㅜ",
    "ㅝ",
    "ㅞ",
    "ㅟ",
    "ㅠ",
    "ㅡ",
    "ㅢ",
    "ㅣ",
]


@dataclass(frozen=True)
class ArticulationTip:
    tip: str
    articulation_tip_id: str
    practice_resource_id: str | None = None


SYLLABLE_TIPS = {
    "고": ArticulationTip(
        tip=(
            "'고'를 연습할 때는 입술을 둥글게 모으고 앞으로 내밀어 "
            "첫 모음이 분명하게 들리도록 천천히 발음해 보세요."
        ),
        articulation_tip_id="ko_syllable_go_tip_01",
        practice_resource_id="ko_syllable_go_01",
    ),
}

VOWEL_TIPS = {
    "ㅏ": "입을 자연스럽게 열고 밝은 '아' 소리가 나도록 천천히 발음해 보세요.",
    "ㅓ": "입을 너무 옆으로 벌리지 말고 편안하게 열어 '어' 소리를 확인해 보세요.",
    "ㅗ": "입술을 둥글게 모으고 앞으로 살짝 내밀어 '오' 소리를 길게 확인해 보세요.",
    "ㅜ": "입술을 더 작고 둥글게 모아 '우' 소리를 안정적으로 내보세요.",
    "ㅡ": "입술 힘을 빼고 입을 크게 열지 않은 상태에서 '으' 소리를 유지해 보세요.",
    "ㅣ": "입꼬리를 자연스럽게 옆으로 두고 '이' 소리를 또렷하게 내보세요.",
}


def extract_vowel(syllable: str | None) -> str | None:
    if not syllable or len(syllable) != 1:
        return None
    code = ord(syllable)
    if code < HANGUL_BASE or code > HANGUL_END:
        return None
    offset = code - HANGUL_BASE
    vowel_index = (offset // JONGSEONG_COUNT) % JUNGSEONG_COUNT
    return VOWELS[vowel_index]


def get_articulation_tip(syllable: str | None) -> ArticulationTip | None:
    if not syllable:
        return None
    if syllable in SYLLABLE_TIPS:
        return SYLLABLE_TIPS[syllable]

    vowel = extract_vowel(syllable)
    if vowel not in VOWEL_TIPS:
        return None
    return ArticulationTip(
        tip=f"'{syllable}'를 연습할 때는 {VOWEL_TIPS[vowel]}",
        articulation_tip_id=f"ko_vowel_{vowel}_tip_01",
    )
