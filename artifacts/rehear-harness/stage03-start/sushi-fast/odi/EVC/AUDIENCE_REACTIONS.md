# Independent audience reactions

An audio update can select all configured listeners' motions together. Opt-in
sessions now share one STT/LLM analysis but consume that evidence on independent
listener clocks. Existing clients keep the legacy update/commands contract.

## Deploy and integrate

Deploy this branch through the normal server process; no new package, key, or
environment variable is required for this scheduler. Existing speech/LLM setup
still applies. Restarting the current in-memory session store requires starting
a new presentation session.

1. Send multipart `independent_reactions=true` to
   `POST /odi/xreal_rehear/evc/smart-start`.
2. Only enable polling if the response confirms `independent_reactions: true`.
3. Continue uploading audio to `POST /odi/xreal_rehear/evc/update`. Its analytical
   audience states remain complete for reports/questions, but its commands are
   empty in this mode. Do not apply these analytical states to visible actors.
4. Poll `POST /odi/xreal_rehear/evc/sessions/{session_id}/reactions` every 250ms,
   with the existing `X-EVC-Session-Token` header and JSON:
   `{"request_id":"<UUID>","client_time_s":12.5}`.
5. Apply the returned `audiences` and `commands`. This response has its own
   `sequence`, separate from the audio `step`. Retry uncertain requests with the
   same UUID and captured time; the last 32 responses are cached.
6. Pause polling with the presentation clock. Cancel polling and pending
   backchannel commands at finish/Q&A/scene exit. Keep Q&A speech under its
   existing separate control.

Polling does not call STT/LLM or wait on the audio-analysis lock. Up to six actors
retain one decision per request and the 0.35s dispatch gap. Larger populations
use `min(4, ceil(a/6))` primary decisions per request with the same gap and a hard
24-command budget (including decomposed layers and paired commands). A choice
that exceeds the remaining budget is wholly rolled back and deferred; layers
are never truncated. Oldest deadlines are served first. Each listener
applies every unseen evidence segment once, in order, then selects once. No new
evidence means no repeated score application or motion reselection.

Individual clocks vary by responsiveness and jitter. Small changes retain the
displayed core; eligible new actions can interrupt rather than wait for a clip
to finish. Selection considers other listeners' current motions, respecting
seat, device and cooldown gates. Both rear actors must qualify for conversation;
the paired commands share timing/group and Unity chooses the seat-specific R/L.

The analytical report state and delayed visible-reaction state are deliberately
separate: ending a presentation before every listener's next tick must not lose
the final accepted segment from evaluation or question generation. The earlier
eight-second upload example is not a measurement of the Unity consumer. The
included historical CLI benchmark uses 30-second segments. This change does not
remove collection/STT/LLM latency or create a new per-listener LLM call.

## Clock domains and freshness

`TimingTrace` records pipeline entry, lock acquisition, STT/evaluation completion,
commit and response-ready monotonic observations. Entry is after HTTP multipart
upload handling; response-ready is not wire-send or Unity receive time. The last
32 successful request traces are retained internally and logged as metadata.
Source client times, STT timestamps and report evidence stay unchanged.

Legacy `/update.commands` retains the existing client-time offsets. With no
consumer clock observation, Unity time and evidence age remain unknown. A request
at 30s with 5s of server processing still emits 30.1s commands; adding server
elapsed time would incorrectly assume an advancing presentation clock during
pauses. Independent mode uses the supplied poll clock for command placement;
it is labeled `client_poll_unverified`, not an authoritative Unity clock.

Inject `PlaybackPolicy` when constructing the scheduler to tune these defaults:

| Policy | Default | Basis and behavior |
|---|---:|---|
| slide event TTL | 6s | Rounded headroom above the supplied historical CLI processing max (~5.53s); not a measured Unity tolerance |
| pause / utterance boundary TTL | 2s | Conservative momentary-event window; a prior pause is not proof of a current pause |
| other contextual signal TTL | 6s | Same historical processing allowance as slide signals |
| full playback age limit | 15s | Finite admission window allowing ~6s processing + ~6s synthetic 50-actor dispatch spread plus headroom |
| forward clock slack | 30s | Explicit discontinuity guard in addition to observed server elapsed; not a synchronization estimate |
| pending evidence per listener | 64 | Backpressure bound; accepted deltas are never discarded |

The 2s TTL used for slide events in tests is an injected test policy. Expired
momentary context becomes neutral `during_speech`, with slide reference cleared
and no action candidates, including actions inferred from old metrics. At >15s
the entire playback choice is suppressed (`stale_playback`), while every unseen
delta is still applied exactly once in order. An ahead source timestamp has
unknown age: momentary context is suppressed, while existing state-derived ACT03
may remain eligible. It is not assigned a fabricated age of zero.

Equal poll times do not advance listener state, deadlines or RNG. The existing
0.25s regression tolerance remains; larger regressions and a forward advance
exceeding server elapsed +30s return 409 `playback_clock_discontinuity` without
advancing the accepted clock. Resume the previous presentation clock or start a
new session after a reset. The backend does not invent a new epoch. The first
poll has no previous reference and cannot establish a real clock offset.

Cached request IDs return the original UUIDs, times and sequence even after
finish. New polls after finish return no commands. Consumers must still cancel
queued playback at finish as described above. Metadata logs include per-actor
deadline wait, pending depth, source step, observed event age and drop reason,
without audio, transcript, evaluation prose or tokens.

## Overload

`EVC_MAX_PENDING_UPDATES=3` bounds active plus waiting updates per session
(normally one active and two waiting). An independent scheduler with a full 64-evidence listener
backlog refuses new analysis before STT. These return the existing 429 capacity
error; retry without advancing `expected_step`. Cached completed updates bypass
admission and keep their original result.

`EVC_PROVIDER_WORKERS=4` bounds actual shared STT/segment-evaluation threads per
process, including STT used for answers. There is no unbounded provider work
queue. Async timeout/cancellation does not stop a thread or release its slot;
the slot is released when the call actually completes. Fresh capacity rejection
is 429 `provider_capacity_exceeded`; if a retry is blocked after a provider
timeout/error, the original provider error and its existing 502 mapping survive.
Permanently stalled workers can exhaust capacity; forced thread termination is
not implemented. Multi-process deployments each have their own limits.

## Validation

2026-10-15: offline timing suite 27 tests, existing suite 129 tests and audience
suite 50 tests pass. The six-actor pre-change goldens are unchanged. In the
all-due synthetic 250ms poll case, last primary decision wait is 0 / 2.5 / 2.5 /
6.0 seconds for 1 / 6 / 12 / 50 actors, compared with 0 / 2.5 / 5.5 / 24.5 before.
These are synthetic scheduling measurements, not Unity latency or load results.
See the root `docs/rehear-ai/PROGRESS.md` for commands and remaining limits.

This workspace run did not execute Unity EditMode/PlayMode, Quest, actual actor
mapping, consumer pause behavior or clock synchronization. Earlier Unity test
counts in this document are not evidence for this implementation. Actual
rendering latency and subjective animation naturalness remain unverified.
