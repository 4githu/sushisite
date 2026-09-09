# Independent audience reactions

Previously an audio update selected all six listeners' motions together. Opt-in
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
3. Continue uploading audio to `/sessions/{session_id}/update`. Its analytical
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

Polling does not call STT/LLM or wait on the audio-analysis lock. It computes at
most one listener decision per request, with at least 0.35s between decisions;
the explicitly paired rear-seat conversation is the exception. Each listener
applies every unseen evidence segment once, in order, then selects once. No new
evidence means no repeated score application or motion reselection.

Individual clocks vary by responsiveness and jitter. Small changes retain the
displayed core; eligible new actions can interrupt rather than wait for a clip
to finish. Selection considers other listeners' current motions, respecting
seat, device and cooldown gates. Both rear actors must qualify for conversation;
the paired commands share timing/group and Unity chooses the seat-specific R/L.

The analytical report state and delayed visible-reaction state are deliberately
separate: ending a presentation before every listener's next tick must not lose
the final segment from evaluation or question generation. Audio capture remains
the existing eight-second segmentation; this change does not remove STT/LLM
latency or create a new per-listener LLM call.

## Validation

`python -m pytest odi/EVC/tests -q --tb=short`: 124 passed.
Coverage includes independent phases/intervals, delayed polls, exact-once ordered
evidence, retry/rollback, state retention, rear pairing, authentication, finish,
nonblocking polling during analysis, and the existing Q&A/report regressions.
Unity companion validation: 57 EditMode + 8 PlayMode tests and pose-continuity
checks on all six audience prefabs passed. Live server/Quest validation follows
deployment; automated tests do not establish subjective animation naturalness.
