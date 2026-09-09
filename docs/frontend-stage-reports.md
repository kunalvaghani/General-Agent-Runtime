# Frontend stage reports

Historical Stages 12–17. These preview screens were subsequently integrated with the
real backend in Stage 19; Stage 18–20 results are in final-stage-reports.md. The former
Docker startup blocker is resolved and its five affected tests passed on retry.

The detailed master-prompt sequence is authoritative: 12 bootstrap, 13 dashboard,
14 creation, 15 detail, 16 events, 17 approvals. The shorter roadmap uses different
numbers. Full integration remains Stage 19. Fixtures are explicitly labeled and
do not run agents or manufacture verification evidence.

## Stage 12

INTENDED: Next.js, TypeScript, Tailwind shell, typed client and error boundaries.
IMPLEMENTED: All above; independent preview shell and environment example.
FILES CREATED: web/package.json, package-lock.json, tsconfig.json, next.config.ts,
next-env.d.ts, postcss.config.mjs, vitest.config.ts, app/layout.tsx, app/page.tsx,
app/globals.css, app/error.tsx, app/not-found.tsx, lib/api.ts, lib/types.ts,
tests/setup.ts, tests/api.test.ts, .env.example.
FILES MODIFIED: run-gar.bat, .gitignore.
ARCHITECTURE NOTES: Client contracts separate from backend orchestration.
TESTS ADDED: Backend error propagation.
COMMANDS EXECUTED: run-gar.bat --no-setup web-check.
TEST RESULTS: TypeScript passed; 1 test passed; Next production build passed.
BUGS DISCOVERED: Sandbox blocked Node subprocesses.
BUGS FIXED: Authorized validation outside the subprocess restriction succeeded.
SECURITY FINDINGS: No secrets embedded in client config.
KNOWN LIMITATIONS: Screens are independent until integration Stage 19.
ACCEPTANCE CRITERIA:
- [x] Shell, typed API client, errors and environment config
- [x] Launcher setup/start/check commands and validation
STATUS: READY FOR REVIEW.
NEXT STAGE IF APPROVED: Stage 13, already authorized.

## Stage 13

INTENDED: Task dashboard and runtime health indicators.
IMPLEMENTED: Counts, status filter, task links, empty/loading/retry states; health
explicitly marked disconnected in independent preview mode.
FILES CREATED: lib/preview.ts, components/dashboard.tsx, tests/dashboard.test.tsx.
FILES MODIFIED: app/page.tsx, app/globals.css, vitest.config.ts, run-gar.bat, README.md.
ARCHITECTURE NOTES: Static examples are separate from UI components.
TESTS ADDED: Filtering/navigation, disconnected health, empty/error/retry behavior.
COMMANDS EXECUTED: run-gar.bat --no-setup web-check.
TEST RESULTS: 3 cumulative tests, typecheck and production build passed.
BUGS DISCOVERED: Missing Vitest imports in test TypeScript.
BUGS FIXED: Explicit test imports and automatic JSX compilation.
SECURITY FINDINGS: Stored data is never executed; React escapes task text.
KNOWN LIMITATIONS: Health is not a live service probe before Stage 19.
ACCEPTANCE CRITERIA:
- [x] Dashboard and explicit runtime health state
- [x] Launcher updated and checks passed
STATUS: READY FOR REVIEW.
NEXT STAGE IF APPROVED: Stage 14, already authorized.

## Stage 14

INTENDED: Task creation UI.
IMPLEMENTED: Goal/model/budget form, validation, pending and error states, saved drafts.
FILES CREATED: lib/create-task.ts, components/new-task.tsx, app/tasks/new/page.tsx,
tests/new-task.test.tsx.
FILES MODIFIED: app/layout.tsx, run-gar.bat.
ARCHITECTURE NOTES: Injectable creation function; previews stay pending without agent logic.
TESTS ADDED: Invalid input, persistence, preservation on failure, double submission.
COMMANDS EXECUTED: run-gar.bat --no-setup web-check.
TEST RESULTS: 6 cumulative tests, typecheck and production build passed.
BUGS DISCOVERED: None in stage checks.
BUGS FIXED: Not applicable.
SECURITY FINDINGS: Drafts are local to the browser; no model calls or tool permissions.
KNOWN LIMITATIONS: Real model discovery and task submission belong to Stage 19.
ACCEPTANCE CRITERIA:
- [x] Validated creation form and failure recovery
- [x] Launcher updated and verified
STATUS: READY FOR REVIEW.
NEXT STAGE IF APPROVED: Stage 15, already authorized.

## Stage 15

INTENDED: Goal/status/plan/current step/tool calls/verification/logs.
IMPLEMENTED: Dynamic detail route with all sections and missing/loading/error states.
FILES CREATED: lib/task-detail.ts, components/task-detail.tsx, app/tasks/[id]/page.tsx,
tests/task-detail.test.tsx.
FILES MODIFIED: app/globals.css, run-gar.bat.
ARCHITECTURE NOTES: Awaited Next route params; independent data loader; React text escaping.
TESTS ADDED: Dependencies/evidence, missing task, untrusted output and absent verification.
COMMANDS EXECUTED: run-gar.bat --no-setup web-check.
TEST RESULTS: 9 cumulative tests, typecheck and production build passed.
BUGS DISCOVERED: None in stage checks.
BUGS FIXED: Not applicable.
SECURITY FINDINGS: Tool output is rendered as text, never injected HTML.
KNOWN LIMITATIONS: Example plans and logs are labeled preview fixtures.
ACCEPTANCE CRITERIA:
- [x] All requested detail sections and missing-data states
- [x] Launcher updated and verified
STATUS: READY FOR REVIEW.
NEXT STAGE IF APPROVED: Stage 16, already authorized.

## Stage 16

INTENDED: SSE reconnect, deduplication, completed tasks, disconnects and UI errors.
IMPLEMENTED: Typed EventSource transport with replay cursor/backoff, bounded log,
terminal shutdown, validation, cleanup and retry UI. Preview records stay static.
FILES CREATED: lib/events.ts, components/event-feed.tsx, tests/events.test.ts.
FILES MODIFIED: components/task-detail.tsx, run-gar.bat.
ARCHITECTURE NOTES: Backend URL is injected at integration; no simulated agent loop.
TESTS ADDED: Ordered replay/duplicates, cursor resume, terminal shutdown, cross-task
rejection, cancellation of pending reconnects.
COMMANDS EXECUTED: run-gar.bat --no-setup web-check.
TEST RESULTS: 12 cumulative tests, typecheck and production build passed.
BUGS DISCOVERED: None in stage checks.
BUGS FIXED: Not applicable.
SECURITY FINDINGS: Stream records must match the requested task and journal ID.
KNOWN LIMITATIONS: Full live screen wiring is Stage 19; logs keep latest 500 events.
ACCEPTANCE CRITERIA:
- [x] SSE transport and lifecycle behavior covered by tests
- [x] Connection/error states and bounded event rendering
- [x] Launcher updated and verified
STATUS: READY FOR REVIEW.
NEXT STAGE IF APPROVED: Stage 17, already authorized.

## Stage 17

INTENDED: Permission requests and approve/reject, with backend authority.
IMPLEMENTED: Exact tool/arguments/reason/step/request review; once-only submission;
stale-request refresh, network retry, explicit preview acknowledgement. Production
approval adapter sends only request_id and approve, never rewritten tool arguments.
FILES CREATED: lib/approval.ts, components/approval.tsx, tests/approval.test.tsx,
playwright.config.ts, tests/browser/preview.spec.ts.
FILES MODIFIED: components/task-detail.tsx, app/globals.css, lib/preview.ts,
run-gar.bat, README.md, stage reports.
ARCHITECTURE NOTES: Rendering and authority separated through injected submit handler.
Preview approval cannot call a real tool or change runtime task status.
TESTS ADDED: Exact approve/reject payloads, repeated click protection, stale request,
network retry, HTTP contract, desktop/mobile creation-detail-persistence and approval.
COMMANDS EXECUTED: run-gar.bat --no-setup web-check; run-gar.bat --no-setup web-e2e.
TEST RESULTS: 17 frontend tests, TypeScript and production build passed; 4 desktop/
mobile Chrome tests passed. Mobile approval screenshot inspected for readability.
BUGS DISCOVERED: Browser test matched Next's route announcer as well as form alert;
example terminal arguments used command instead of backend's argv field.
BUGS FIXED: Scoped the alert selector; aligned the example argument name with backend.
SECURITY FINDINGS: No blanket approval; request IDs are immutable UI inputs; 409
disables submission until current request is reviewed; untrusted text stays escaped.
KNOWN LIMITATIONS: Full live approval and SSE screen wiring await Stage 19. Chrome
is required by the browser suite. No claim of final V1 acceptance is made.
ACCEPTANCE CRITERIA:
- [x] Permission review and approve/reject controls
- [x] Exact request, stale state and repeat-click behavior tested
- [x] Launcher updated with browser verification and verified
- [x] Desktop/mobile navigation, storage and review flow verified
STATUS: READY FOR REVIEW.
NEXT STAGE IF APPROVED: Stage 18. This historical stopping point was subsequently
extended through Stage 20; see final-stage-reports.md for the continuation.

## Final regression note

Resolved on continuation: the user restored Docker Desktop. All five previously
blocked Docker-dependent tests passed against Docker 29.3.0 and gar-tools:stage4
(10.25 seconds). Together with the prior 162 passing tests, the earlier regression
is now clear. No Docker reset or deletion was performed by GAR. Stage 19–20 results
and the current checkpoint are recorded in final-stage-reports.md and PROGRESS.md.
