# Manual delivery confirmation API

## Purpose

Record an operator's confirmation that a settlement message was sent when the UI's delivery result was recorded incorrectly or remained uncertain. This is not proof from Kakao and must not be presented as parent-payment completion.

## Read state

`GET /api/personal/aura/settlements/parents?year={year}&month={month}`

Each billable student item includes:

- `manualDeliveryConfirmed`: whether an operator recorded a manual confirmation
- `manualDeliveryConfirmedAt`: `null` or the confirmation timestamp

The existing `status`, `paidAmount`, and `amount` fields retain their parent-payment meaning.

## Record a manual confirmation

`PATCH /api/personal/aura/settlements/parents/delivery`

```json
{
  "year": 2026,
  "month": 9,
  "studentKey": "<current billable student key>"
}
```

The response is the corresponding item from the parent-settlements list, including the two manual-confirmation fields above. Repeating the request is idempotent.

The operation is owner-scoped and only accepts a student in that owner's current month snapshot. It writes a separate confirmation record keyed by owner, month snapshot, and a hash of the student key. It does not send or retry a Kakao message, alter a delivery receipt/outbox, or change parent-payment fields. A replacement snapshot for the month does not inherit the old confirmation.

## Verification

Synthetic backend regression tests cover the HTTP contract, owner scope, snapshot replacement, and the absence of Kakao bridge calls and payment-state changes.

## Local backend reflection (2026-11-10)

- `app.sushisite.backend` was restarted after the focused suite passed. The service owns `127.0.0.1:8000`; `/openapi.json` returned HTTP 200 and exposed `GET/PATCH /api/personal/aura/settlements/parents` plus `PATCH /api/personal/aura/settlements/parents/delivery`.
- The additive `aura_parent_settlement_delivery_confirmations` table was created in the service database and read back with **0 rows**. No manual confirmation or payment record was written.
- Focused backend tests: **28 passed, 1 Starlette/httpx deprecation warning**. `py_compile` and `git diff --check` passed.
- No actual endpoint mutation, Kakao send, parent-payment change, or remote/CI deployment was performed. The UI remains a separate, unshipped change.
