# Calendar tasks deployment — 2026-09-27

Added keyboard quick capture (title/date), all/today/overdue/upcoming task views, larger completion checkboxes, immediate status updates, per-item duplicate-request protection, rollback on API failure, and completion undo. Daily planning uses the same pending completion guard. Shared completion stays scoped to the current user; external completion and not-yet-available tasks retain their existing restrictions.

Validation: Svelte check 0 errors/warnings; calendar/Aura browser suite 14 passed initially, two failures corrected and both passed on retest (16 scenarios total). Backend student catalog/workspace tests: 30 passed. Desktop and 390px mobile screenshots reviewed, including save-error recovery. Production Node build succeeded.

Deployment includes the previously prepared student services, note folding, and Android download described in student-services-20260927.md. Production build created separately with BUILD_TARGET=node BUILD_OUT=build-node-next; live build-node replaced only after validation. Frontend and backend LaunchAgents restarted. SQLite online backup verified with quick_check=ok. Backup directory: /Users/sagi/Documents/sushisite-deploy-backups/20260927-todos. Previous frontend also retained at sushi-app/build-node-previous-20260927.

Public entry: https://chobab.app/personal-project/calendar/tasks. Calendar-specific subdomains are not configured in the existing tunnel. Local frontend responds 200; unauthenticated catalog API responds 401 as expected. Public HTTPS HEAD responds 200. Browser smoke uses mocked auth/API to avoid modifying production user data.

Frontend rollback: stop/restart the frontend LaunchAgent around restoring the saved build-node directory. Do not replace the live database merely to roll back frontend code; the backup is recovery-only and would discard newer user changes.

Post-deploy result: both public HTTPS Playwright scenarios passed (mobile/install manifest and quick capture/filter/completion/undo/error rollback). Development server stopped after verification; production services remain running.
