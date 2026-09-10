# Azure speech and adaptive Q&A

The existing EVC question provider (`question_generation.py`, default model
`gpt-4.1-mini`) is reused. No second LLM gateway is needed.

## Flow

1. Existing `/questions/generate` establishes the requested total (Unity supplies the web session setting).
2. POST `/sessions/{id}/questions/{zero-based-index}/speech` synthesizes the current question.
   Existing `X-EVC-Session-Token` authentication is required, plus `X-Speech-Voice`
   and an authorized `X-Audience-Id` (audience_01..06).
3. Unity plays QS, waits for baseline, then plays WAV through the audience's AudioSource/LipSync.
4. Only between Start Answer and Finish Answer does Unity record the microphone.
5. POST `/sessions/{id}/questions/{index}/answer` accepts mono PCM16 WAV, max ten minutes/20 MB,
   with `X-Request-Id` UUID and `X-Next-Audience-Id` when another question remains.
   Responses normalize UUIDs to hyphenated form; clients should send canonical UUIDs
   or compare parsed UUID values instead of raw strings.
6. Azure STT text is retained before calling the existing question provider. The LLM receives
   presentation evidence, actual Q&A history and the next speaker's profile/evaluation state.
   It may ask a follow-up or another relevant question. The next slot is replaced; total is unchanged.
7. Response: `question_index`, `request_id`, `saved`, `transcript`, `total`, `next_question`
   (`id`, 1-based `order`, `question`, `intent`, `source_steps`), null after the last answer.
8. Unity validates the returned order/total before advancing and discards the superseded next audio.
   The last answer skips further question generation and continues to the existing report flow.

Silence returns saved=false and permits re-recording. Duplicate requests with the same
audio/ID return the same result; changed data or out-of-order answers return 409.
An LLM failure retains recognized text so retrying does not charge STT again.
Q&A history lives in the existing in-memory session until the final report persists it
as `qa_history`. A server restart/TTL expiry before report completion still loses the
in-progress session, just as the existing SessionStore does. This is not restart recovery.

## Server setup

Install updated `sushi-fast/requirements.txt`. On Debian/Ubuntu the Speech SDK also
requires `libasound2` (or distribution equivalent), OpenSSL and CA certificates.
Set these in the **server secret environment**, never Unity/Resources/APK/Git:

```dotenv
AZURE_SPEECH_KEY=<server secret>
AZURE_SPEECH_REGION=koreacentral
AZURE_STT_MODE=continuous
EVC_STT_PROVIDER=azure
EVC_STT_TIMEOUT_S=120
OPENAI_API_KEY=<existing server secret, unchanged>
```

Continuous recognition works with the PSA F0 resource; Fast transcription does not.
EVC_STT_PROVIDER changes presentation-segment recognition (including word timing);
without it the existing Deepgram default is preserved. Q&A uses Azure.
Run a single EVC worker, consistent with its in-memory SessionStore and the F0 STT
concurrency limit. Configure the reverse proxy answer-request timeout to at least
720 seconds and upload limit to 20 MB. This code does not modify the subscription/tier.

After deploying and verifying the routes, set Unity AzureSpeechConfig.bridgeBaseUrl to
`https://rehear.chobab.app/odi/xreal_rehear/evc`. Do not point it at the earlier standalone gateway.
The six Korean voices are selected by each Unity audience prefab's AudienceVoiceProfile;
the server accepts InJoon, BongJin, GookMin, SunHi, JiMin, SeoHyeon and SoonBok Neural voices.
The beige-suit audience (Aud_W_02) now uses SoonBok; JiMin remains accepted for older clients.
No Azure native SDK is bundled in the APK; Unity uploads WAV over HTTPS and plays the
returned WAV through its existing AudioSource/LipSync path.

## Validation

From sushi-fast with dev dependencies installed:

```sh
python -m pytest odi/EVC/tests/test_answer_service.py odi/EVC/tests/test_question_generation.py odi/EVC/tests/test_report_generation.py odi/EVC/tests/test_inputs_stt.py odi/EVC/tests/test_command_pipeline_api.py odi/EVC/tests/test_report_followup.py -q
python -m odi.EVC.tests.manual_azure_qa_check
```

The second command uses Azure quota for synthetic audio, never the user's microphone.
It uses a mock LLM and therefore is not a live LLM quality test. Deployment, real LLM,
Unity microphone and Quest APK end-to-end tests remain required.

On 2026-09-08 the targeted regression command above passed all 29 tests. PC Unity
tests exercised two Q&A turns with real Azure and a mock LLM. Quest verified all six
original voice profiles driving OVR blendshapes and microphone capture; its test
harness subsequently failed a raw UUID-format comparison on answer submission.
The diagnostic client has been corrected to send canonical UUIDs, but the corrected
Quest answer round trip has not yet been rerun. SoonBok was separately synthesized
successfully against Azure. These checks do not validate production deployment or
real-LLM question quality.
