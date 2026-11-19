# Aura clinic Kakao send failure — sanitized diagnosis

## Finding

The operational log contains a `command=send outcome=error` event at line 34546 with `elapsed_ms=6227`, `uncertain=True`, and a redacted detail field. The event has no recipient/job correlation in the permitted evidence, so it cannot be attributed to the reported clinic send or a specific recipient. The error reason is not recoverable from this log entry.

In the checked shared source, `kakao_bridge.invoke` writes `detail=<redacted>` when `redact_errors=True`. The settlement and classroom delivery wrappers pass that flag; the clinic report calls in `native_kakao.send_clinic_job` do not. However, these caller files are dirty shared-tree files and the log has no runtime build/version marker, so this source-to-log comparison cannot prove which code version produced the event. The event therefore cannot safely be attributed to the clinic flow (or disambiguated between the redacted flows).

The event has `uncertain=True`; in the current bridge implementation this flag reflects `committed`, set immediately before the Accessibility send-button press. That indicates a send-click attempt boundary was reached, **not** proof Kakao accepted or delivered a message. The exact error is intentionally redacted, and actual delivery remains unknown. No clinic-report defect is established, so no source change was made.

## Verification

- Synthetic command: `./.venv/bin/python -m pytest -q personal_project/tests/test_kakao_send_gate.py personal_project/tests/test_kakao_recipient_safety.py personal_project/tests/test_native_kakao.py`
- Result: **50 passed**, 7 existing deprecation warnings, 4.45 seconds.
- The system Python lacked `pytest`; rerunning with the repository virtualenv succeeded.
- No Kakao send, student-record access, production restart, or deployment was performed.
- Existing shared-tree edits to `ops/kakao_bridge.swift`, `sushi-fast/personal_project/native_kakao.py`, `sushi-fast/personal_project/kakao_bridge.py`, and `sushi-fast/personal_project/tests/test_native_kakao.py` were inspected and left untouched.

## Limit

The missing recipient/job correlation and redacted error detail prevent identifying the exact UI failure (or confirming which clinic action produced the event). No live reproduction was attempted because it could send a message.
