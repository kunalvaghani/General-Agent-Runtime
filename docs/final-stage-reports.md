# Stages 18–20

## STAGE 18 — Models / Memory / Settings

INTENDED: Model library, attributed memory management, runtime configuration.
IMPLEMENTED: Provider discovery with retry; searchable/filterable memory with explicit
individual deletion; persisted default model and timeout with validation/error recovery.
FILES CREATED: web/components/management.tsx; web/app/{models,memory,settings}/page.tsx;
web/tests/management.test.tsx.
FILES MODIFIED: web/app/layout.tsx, globals.css, run-gar.bat, DEVELOPMENT.md, AGENTS.md.
ARCHITECTURE NOTES: Management screens use the existing typed HTTP boundary; task
screens remain separate until Stage 19. Existing configuration and data preserved.
TESTS ADDED: Discovery retry, invalid timeout, save failure preserving inputs, memory deletion.
COMMANDS EXECUTED: run-gar.bat --no-setup web-check.
TEST RESULTS: 20 frontend tests, TypeScript, Next production build passed.
BUGS DISCOVERED: No failing stage checks.
BUGS FIXED: Not applicable.
SECURITY FINDINGS: Individual deletion requires explicit UI confirmation; settings
expose only the backend's allowed fields; memory renders escaped text.
KNOWN LIMITATIONS: Ollama must be available for discovery; full task wiring follows.
ACCEPTANCE CRITERIA:
- [x] Model, memory, settings screens implemented
- [x] Error handling and input preservation tested
- [x] Launcher updated and verified
STATUS: READY FOR REVIEW.
NEXT STAGE IF APPROVED: Stage 19 (already authorized).

## STAGE 19 — Integration

INTENDED: Connect all screens to FastAPI; verify the entire execution path.
IMPLEMENTED: Real task/model/settings/memory APIs; consistent transactional snapshots;
live SSE with stable replay cursors; real once-only approvals, cancellation and resume;
same-origin Next proxy to a loopback backend; combined API/UI startup command.
FILES CREATED: src/gar/launcher.py; tests/integration/test_snapshot.py;
tests/support/{scripted_provider,integration_server}.py; web/tests/browser/integration.spec.ts.
FILES MODIFIED: API, config, task state, persistence, filesystem tool; frontend client,
task screens, event feed, approval, Next config, tests and run-gar.bat. Preview data
moved out of production code into unit-test fixtures; existing browser data preserved.
ARCHITECTURE NOTES: Test host substitutes only model responses and uses temporary data.
Browser requests traverse real Next/FastAPI/SQLite/SSE/tools/Docker/verification/memory.
TESTS ADDED: Snapshot consistency, exact payload persistence, LF file roundtrip;
desktop/mobile full execution and saved management settings.
COMMANDS EXECUTED: web-check; web-e2e via run-gar.bat; targeted pytest regression; Ruff.
TEST RESULTS: 20 frontend tests, TypeScript/build passed; 4 live browser integration
checks passed (28 seconds); 26 state/snapshot/verifier tests plus file roundtrip passed.
BUGS DISCOVERED: Snapshot normalization trimmed nested tool payloads; Windows file
writes translated LF to CRLF, causing valid artifacts to fail exact verification.
BUGS FIXED: Normalize labels only; preserve JSON payloads and supplied file newlines.
SECURITY FINDINGS: Approval request IDs remain backend-authoritative; no preview tool
execution path remains; proxy target and UI origin constrained to loopback HTTP.
KNOWN LIMITATIONS: Previously stripped historical metadata cannot be reconstructed
automatically; create a new task if old evidence was affected. Model fixtures establish
runtime correctness, not arbitrary model reliability. Docker blocker is resolved:
all five previously affected tests passed against the restored engine.
ACCEPTANCE CRITERIA:
- [x] Every screen uses real backend data
- [x] Create → plan → events → tools → verify → complete → memory
- [x] Desktop/mobile live flow and management persistence
- [x] Launcher updated and verified
STATUS: READY FOR REVIEW.
NEXT STAGE IF APPROVED: Stage 20 (already authorized).

## STAGE 20 — End-to-End Validation

INTENDED: Validate all five required V1 scenarios using the integrated application.
IMPLEMENTED: Automated desktop and mobile acceptance for module/test creation,
broken-project repair with a real failed test and bounded resume, dangerous action
approval/rejection, malformed planner and executor output, and active Docker cancellation.
Combined launcher now supports configured frontend ports; acceptance is one batch command.
FILES CREATED: web/tests/browser/acceptance.spec.ts; tests/e2e/test_combined_launcher.py.
FILES MODIFIED: tests/support/scripted_provider.py; web/tests/browser/integration.spec.ts;
src/gar/core/executor.py; tests/integration/test_executor.py; src/gar/launcher.py;
run-gar.bat; README.md; checkpoint and stage reports.
ARCHITECTURE NOTES: Temporary backend data, test-only deterministic model provider,
real SQLite/API/SSE/tools/Docker/verifier/memory. No mock task data in the application.
TESTS ADDED: Five required scenarios (malformed output covered at both stages),
exact/stale approval enforcement, actual container-start detection and removal after
cancel, current retry-attempt prompt state, combined launcher custom ports/data preservation.
COMMANDS EXECUTED: run-gar.bat --no-setup acceptance; targeted executor/launcher pytest;
targeted repair browser retry; final desktop task screenshot inspected.
TEST RESULTS: Final acceptance exit code 0. 172 backend tests passed in 59.03 seconds;
20 frontend tests passed; TypeScript and Next production build passed; Ruff/lint and
formatting passed for 79 Python files; 14 desktop/mobile browser checks passed in 1.1 minutes.
BUGS DISCOVERED: Executor sent a step snapshot from before its RUNNING transition,
so the model received stale attempt counts during recovery.
BUGS FIXED: Reload the persisted active step before constructing the model prompt;
regression asserts attempts 1 then 2 on bounded retry. Stage 19 payload/newline fixes
were also exercised by the complete acceptance gate.
SECURITY FINDINGS: Wrong/stale approval IDs return 409; rejection prevents the process
action; cancellation removes the actual started container and prevents its final write.
Malformed model output cannot produce successful verification or tool side effects.
KNOWN LIMITATIONS: These results establish V1 runtime behavior with deterministic model
responses, not success for arbitrary goals/models. The runtime is single-user/loopback;
remote authentication, additional tools/providers and broader verification remain future
work. Historical metadata already trimmed by older builds is preserved, not guessed back.
ACCEPTANCE CRITERIA:
- [x] Create a Python module and passing unit tests
- [x] Inspect and repair an intentionally broken project after a failed test
- [x] Require exact approval for dangerous action; enforce rejection
- [x] Malformed structured output fails safely
- [x] Cancel an active task and remove its running container
- [x] Integrated UI, API, SSE, verification, memory and persistence verified
- [x] Updated launcher passes full acceptance and combined startup checks
STATUS: READY FOR REVIEW — V1 runtime acceptance passed.
NEXT STAGE IF APPROVED: None scheduled. Stop after Stage 20 as authorized.
