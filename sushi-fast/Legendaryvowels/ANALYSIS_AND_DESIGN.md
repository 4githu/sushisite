# Korean Voice Evaluation Server Analysis

## Current Code Behavior

The current sentence pipeline is in `services/sentence/service.py`.

- `education` mode requires `target_text`.
- Audio is decoded to 16 kHz mono PCM with `ffmpeg`.
- Audio retry checks:
  - minimum duration: `0.4` seconds
  - minimum peak RMS: `0.003`
  - decode timeout: `30` seconds
- Primary STT is Deepgram:
  - env `DEEPGRAM_PRIMARY_MODEL`
  - default model: `nova-3`
- Optional verification STT is enabled when `STT_VERIFICATION_ENABLED=1`,
  `GOOGLE_STT_VERIFICATION_ENABLED=1`, or legacy `DEEPGRAM_VERIFICATION_MODEL`
  exists.
  - default verification provider: `google`
  - verification trigger: average word confidence `< 0.65`
  - or target/transcript similarity `< 0.85`
  - verification disagreement returns `UNDETERMINED`
- Text matching uses normalized text:
  - keeps only Korean, English letters, and numbers
  - removes spaces and punctuation
  - lowercases English
- `textMatchScore = matchedSyllableCount / totalTargetSyllableCount * 100`
- `education.overallScore = textMatchScore`
- `presentation.overallScore`:
  - without `target_text`: `deliveryScore`
  - with `target_text`: `textMatchScore * 0.6 + deliveryScore * 0.4`

For the sample:

- target: `안녕하세요, 고 발표를 시작하겠습니다.`
- transcript: `안녕하세요, 그 발표를 시작하겠습니다.`
- normalized target length: `16`
- matched count: `15`
- text score: `93.75`
- observed issue: original-text position `8`, `고 -> 그`

## Differences From Earlier Explanation

- `pronunciation_score: 85.0` is not a current fixed value and is not LLM-generated.
  Current education score is calculated from text alignment.
- Sentence LPC is not part of the formal sentence pipeline.
  It is isolated in `services/experimental/sentence_lpc.py`.
- Current sentence evidence is STT text alignment, not open phoneme recognition.
- Word timestamps exist when Deepgram returns `words`, but syllable or phoneme timestamps do not exist yet.
- Delivery metrics were previously bundled into one score. They are now exposed as:
  - `timingScore`
  - `pauseScore`
  - `fluencyScore`
  - `deliveryScore`

## Implemented Response Improvements

The response keeps existing fields and adds machine-readable fields.

Location uses original text positions:

- `targetStartCharIndex`: 0-based original string index
- `targetEndCharIndexExclusive`: original string exclusive end index
- `displayCharPosition`: 1-based original string position for humans
- `targetWordIndex`: 0-based token index
- `targetSyllableIndex`: 0-based syllable index inside the target token
- `displayLabel`: human label, for example `8번째 글자: 고 -> 그`

Observation and practice are separated:

- `observation`: STT-observed difference only
- `practice`: deterministic articulation reference

This avoids claiming actual articulation errors from STT.

## Scoring Policy

Configured in `services/rules.py`.

Temporary values are marked as calibration values because they need real Korean
speech data before they can be treated as validated thresholds.

### textMatchScore

- Applies only when `target_text` exists.
- Unit: percent, `0-100`.
- Formula: `matched_syllables / total_target_syllables * 100`.
- Missing target: `null`.

### pauseScore

- Unit: percent, `0-100`.
- Starts at `100`.
- Silence penalty:
  - acceptable silence ratio: `0.35`
  - penalty: `(silenceRatio - 0.35) * 80`
- Long pause:
  - threshold: `0.7` seconds
  - penalty: `5` points each
  - cap: `30`

### fluencyScore

- Unit: percent, `0-100`.
- Starts at `100`.
- Filler words: `어`, `음`, `그`, `저`, `뭐`
- Filler penalty: `2` points each, cap `20`.
- Speaking rate:
  - normal range: `150-420` characters per minute
  - slow penalty: `(150 - cpm) / 7.5`, cap `20`
  - fast penalty: `(cpm - 420) / 10.0`, cap `20`

### timingScore

- Requires at least two STT word timestamps.
- Uses word duration divided by normalized character count.
- Temporary target char duration: `0.18` seconds.
- Outlier ratio: `0.75`.
- Maximum average timing penalty: `25`.
- Also penalizes local duration inconsistency.
- Missing word timing: `null`.

### deliveryScore

When `timingScore` exists:

```text
deliveryScore = timingScore * 0.35 + pauseScore * 0.35 + fluencyScore * 0.30
```

When `timingScore` is missing:

```text
deliveryScore = pauseScore * 0.5 + fluencyScore * 0.5
```

### overallScore

Education:

```text
overallScore = textMatchScore
```

Presentation without script:

```text
overallScore = deliveryScore
```

Presentation with script:

```text
overallScore = textMatchScore * 0.6 + deliveryScore * 0.4
```

## Technology Review

### Deepgram

Current implementation uses Deepgram because it provides Korean STT, word-level
timestamps, and confidence values in one hosted API. It is useful for transcript
and word-time evidence, but it is still STT text evidence and can include
language-model correction.

Current option stance:

- `filler_words=True`: keep, because filler count is a delivery metric.
- `utterances=True`: keep if later utterance timing is needed.
- `smart_format=True`: acceptable for display transcript, but analysis should
  eventually request or preserve a less formatted transcript separately.

### Google Cloud Speech-to-Text

Google Cloud Speech-to-Text is separate from Gemini. A `GEMINI_API_KEY` is not
the same credential as Google Cloud Speech-to-Text authentication.

Expected requirement:

- Google Cloud project
- Speech-to-Text API enabled
- service account or Application Default Credentials
- billing enabled

Use it as an independent secondary STT only if credentials are configured. Do
not choose the result that best matches the script. If Deepgram and Google differ
meaningfully, return `UNDETERMINED` or low-confidence evidence.

Current optional env:

```env
STT_VERIFICATION_ENABLED=1
STT_VERIFICATION_PROVIDER=google
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/google-service-account.json
GOOGLE_STT_LANGUAGE_CODE=ko-KR
GOOGLE_STT_MODEL=latest_long
STT_VERIFICATION_MIN_AVERAGE_CONFIDENCE=0.65
STT_VERIFICATION_MIN_TARGET_SIMILARITY=0.85
```

Required package when Google verification is enabled:

```bash
pip install google-cloud-speech
```

### Azure Pronunciation Assessment

Azure Speech Pronunciation Assessment is the strongest commercial candidate for
pronunciation assessment because it is designed for pronunciation scoring rather
than plain transcription. Before adoption, verify Korean language support and
whether phoneme-level detail is exposed for the required locale and pricing tier.

### Montreal Forced Aligner

MFA is useful for script-to-audio forced alignment when acoustic models and
pronunciation dictionaries are available. It aligns a known transcript to time.
It should not be treated as open phoneme recognition. If a user says a different
phoneme, forced alignment may still force the script phoneme onto the audio.

### WhisperX

WhisperX is useful for word-level alignment over Whisper transcripts. Korean
support depends on the available alignment model. It is not a direct Korean
phoneme pronunciation assessor.

### wav2vec2 / CTC Forced Alignment

A Korean CTC acoustic model could provide emissions for alignment or posterior
comparison. This is the best local-model path for future phoneme posterior or
Goodness-of-Pronunciation style work, but it requires model selection,
calibration, and likely GPU for acceptable latency.

### torchaudio Forced Alignment

torchaudio alignment tooling can demonstrate CTC alignment, but production use
depends on available maintained bundles and Korean model quality. Treat it as a
research path, not the immediate backend implementation.

## Recommendation

Short term:

- Keep Deepgram as primary STT.
- Expose STT evidence limitations clearly.
- Keep deterministic text alignment for sentence education.
- Keep LPC for single-letter/vowel practice.
- Add deterministic articulation tips from a table.
- Use `presentation` without script as delivery-only scoring.

Mid term:

- Add Google Cloud Speech-to-Text as optional independent verification only when
  proper Google Cloud credentials exist.
- Store both raw and display transcripts.
- Do not compute text accuracy when the same generated transcript is used as the
  reference.

Long term:

- Evaluate Azure Pronunciation Assessment for commercial pronunciation scoring.
- Evaluate a Korean CTC model for local phoneme posterior comparison.
- Use forced alignment only for timing against a known script, not as proof of
  observed phoneme correctness.

## Unity Migration Notes

Existing fields still exist:

- `targetText`
- `transcript`
- `score.overallScore`
- `score.textMatchScore`
- `words`
- `wordResults`
- `feedback`

New preferred fields:

- `transcriptInfo.rawTranscript`
- `transcriptInfo.displayTranscript`
- `transcriptInfo.textAccuracyApplicable`
- `alignmentEvidence.evidenceType`
- `alignmentEvidence.limitation`
- `score.timingScore`
- `score.pauseScore`
- `score.fluencyScore`
- `wordResults[].location.displayLabel`
- `wordResults[].observation.message`
- `wordResults[].practice.tip`
- `wordResults[].practice.articulationTipId`
- `feedback.practiceItems[].tip`
