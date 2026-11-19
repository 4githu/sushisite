# Aura AI report provider/error handling — live verification

Date: 2026-11-09 (KST)

## Scope and change handling

The provider-block classification, HTTP 422 guidance, safe diagnostic handling, and related regression coverage were already present in the working tree. The outbox patch was not reapplied, and no source implementation was added or reverted during this verification. Existing unrelated working-tree changes were left untouched.

## Regression and Kakao safety

- Command: `./.venv/bin/python -m pytest -q personal_project/tests`
- Result: exit 0; **299 passed, 12 warnings**.
- Kakao-related test paths found in the suite use mocked bridge/subprocess calls, test doubles, or an explicit disabled-transport gate. No actual Kakao message was sent.

## Backend restart and live HTTP verification

- Restarted `gui/<uid>/app.sushisite.backend` once with `launchctl kickstart -k`.
- PID changed from **60155** to **61885**. PID 61885 owned the `127.0.0.1:8000` listener after restart.
- Local OpenAPI returned **200** and contained the Aura AI report generation route.
- Used the already-authenticated browser session on the Aura site. Same-origin model and saved-history GET requests returned **200**. No credential, cookie, or session value was read or emitted.
- Made exactly one browser HTTP POST to `/api/personal/aura/targets/{target_id}/ai-reports/generate` using the available default model, automatic score mode, and `force=true` to avoid reusing the prior result.
- Generation response: **HTTP 200**, one result, run ID **238**; no diagnostic/error code was returned.
- Read-back verification: saved-history GET returned **200**, count increased from 1 to 2, and run ID 238 was present. Read-only local DB metadata showed generation run 238 `completed` and the associated report record `submitted`.

Request payload contents and report/student contents are intentionally not recorded. The run preceding this verification (run 237) remains unresolved; no root cause is inferred for it. The three previously confirmed provider safety blocks remain `PROHIBITED_CONTENT` as reported by the user.

## Limits

This verifies the restarted `app.sushisite.backend` service and its live browser HTTP path; it is not a separate CI/build-pipeline deployment. No repeated generation, safety-filter bypass, or Kakao send was performed. Ego Lite 0.6.2.7 displayed an update notice; no upgrade was performed without approval.
