# Aura schedule behavior — user decision, 2026-11-06

- Preserve the user's primary workflow: creating, editing and deleting schedules, including recurrence. Do not remove or disable an existing capability as a response to a hypothetical risk.
- Aura intentionally permits overlapping classes. Routine Aura schedule edits must not require overlap approval.
- Latest correction: calculate settlements ONLY when the user explicitly requests monthly calculation. Creating, editing, viewing schedules and editing participants must not call the pricing engine or require pricing approval. Existing calculated amounts and payment acknowledgements remain unchanged until explicit calculation. New schedules are uncalculated, not automatically billed. Preserve report ownership and sent-message history.
- Retain the user-approved 12-hour maximum. An over-limit error must show the actual entered AM/PM times and total duration; do not replace this with a vague error or an approval dialog.
- Repeated classes share an explicit series ID. Never infer recurrence from similar student/school names. Preserve existing series identity through edits. Move each occurrence's start/end by the respective edit deltas so an existing different duration is not silently overwritten.
- This occurrence, this and following, and the entire series must mean the same scope for update and delete. Scope must cross UI, API and owner-scoped transaction boundaries. Never report repeat deletion complete after deleting one occurrence.
- Keep genuine ownership, student report/attachment protection, and exact recipient checks for actual external sends. These are distinct from routine schedule editing.
- The user's latest decision supersedes old Kanban contracts requiring `repricing_approval_required` for schedule edits. Do not restore obsolete acceptance criteria merely to make old tests pass.
- Required regression evidence: `tests/test_schedule_first_contract.py` and UI `tests/aura-series-scope.e2e.ts`; retain tests of actual HTTP state, owner isolation, unchanged student IDs/reports and series identity. Verify the deployed build, not just a stale dev server or a mock response. Candidate tests are not production verification.

- Communication: distinguish user requests from agent-created policies. A code review request is not authorization for new workflow restrictions. Report material product changes separately and briefly: changed behavior, practical impact, and only a necessary user decision. Do not bury these in task IDs, test counts or long status text.
