# GAR checkpoint — Stage 20 complete

Stages 0–20 in the detailed master-prompt sequence are complete. The shorter
roadmap in the specification uses different numbers; the detailed sequence was
followed. Each stage was tested and reported before proceeding.

## Implemented

- Backend: model adapters, persisted tasks/plans/events, bounded execution,
  restricted Docker tools, approvals, verification/recovery, memory/reflection,
  routing, API and CLI.
- Frontend: dashboard, creation, task details, live SSE, approvals, models,
  memory and settings, all connected to the real backend.
- Launcher: setup, API, combined API/UI startup, frontend setup/checks, and a
  complete acceptance command. Existing configuration, tasks and workspaces preserved.

## Final verified results

The final command `run-gar.bat --no-setup acceptance` returned exit code 0:

| Check | Result |
| --- | --- |
| Backend, including real Docker | 172 passed |
| Frontend unit/component tests | 20 passed |
| Desktop/mobile Chrome integration | 14 passed |
| TypeScript and production build | Passed |
| Ruff and formatting | Passed; 79 Python files |
| Combined batch startup, custom ports, preserved data | Passed |

All five required Stage 20 scenarios passed: module/test creation; broken-project
repair after a real failed test; dangerous action approval/rejection; malformed
structured output failing safely; cancellation of a running Docker task with
confirmed container removal. The browser suite also verifies persisted settings,
live terminal events, successful verification and attributed memory.

Docker startup issue is resolved. Docker 29.3.0 and gar-tools:stage4 were verified.
All five previously blocked Docker tests passed individually, then passed again in
the full suite. No Docker factory reset or data deletion was performed by GAR.

## Run and verify

```bat
run-gar.bat --no-setup dev
run-gar.bat --no-setup acceptance
```

Use the actual UI address printed/opened by the launcher (preferred port 4317,
automatically advanced when occupied). Use `run-gar.bat setup` and `web-setup` on a fresh
installation. Docker must be running with the sandbox image and Ollama must have
an installed model for normal task execution. Acceptance substitutes only model
responses, using isolated temporary data and real services/tools.

Post-acceptance launcher correction: double-clicking run-gar.bat now starts both
services and opens the frontend after its page and proxied API are ready. Startup
errors remain visible. `serve` retains API-only operation; `GAR_OPEN_BROWSER=0`
disables browser opening. The focused launcher/API regression suite passed six tests,
including real default startup, custom ports, preserved data and browser fallback.

## Scope and remaining work

Approved desktop follow-up: implemented test-then-approve Linux Python/Tk desktops
in Docker because Windows Sandbox is unsupported on this machine's Home edition.
Completed task verification is required; a frozen workspace copy is retested with
pytest in the pinned desktop image. Single-use, 15-minute approvals bind the entry
file, full file hashes and image ID. Changed files invalidate launch. The desktop
has no network, no host shell, a read-only root and exactly one read-only snapshot
mount. App changes remain temporary inside /tmp/workspace. GUI images/click/text/key
controls are exposed through the task page and an explicit CLI prepare/approve/stop
workflow. API shutdown and stop-gar.bat clean up owned desktop containers, including
standalone CLI sessions. Frozen copies and audit records remain for review.

Validation checkpoint: 197 backend tests passed with Docker, including the desktop
test/approval/frame/input/stop flow; subsequent stricter desktop checks also passed
with a visible Tkinter window and a button click writing only inside the temporary
copy. Browser review confirmed approval and a counter increment from 0 to 1.
Review caught and fixed duplicate React sibling keys and a window-manager startup
stall; the final display uses Xvfb without that window-manager dependency at runtime.
TypeScript and all 28 frontend tests passed, including the refresh regression.
The desktop image was built and desktop-setup was verified through run-gar.bat.
stop-gar.bat returned success against the isolated review launch and cleared its
launch records; both review server ports closed.
No user task was modified or resumed: the browser check used isolated review data
and a scripted model with real Docker tests and file verification.

2026-09-10 approval/recovery correction: terminal allowlist validation now precedes
approval, including model-requested approval actions. Recoverable tool failures
(unsupported command, failed command, invalid arguments, unknown tool, timeout)
automatically feed observations into bounded retries, then replanning. Existing
global decision counts, two retries and two replans are preserved. A failed replan
consumes its attempt and returns to BLOCKED; cancellation is checked while waiting.
Permission boundary and sandbox/cleanup failures remain outside automatic recovery.
Approval does not transfer to the next proposed dangerous action. Planner/executor
prompts now disclose headless/offline/ephemeral container capabilities. Recovery
telemetry is journaled and displayed in the bottom panel. CLI/API share this logic.

Validation: 192 backend tests passed with `--docker` across unit/integration tests
and the end-to-end runtime flow; 24 frontend tests, TypeScript and changed-file Ruff
checks passed. Seven new recovery regressions cover alternatives, false approval
prevention, fresh approval, boundary rejection, replan success/failure, persistent
budgets and recovery following an approved command failure. A stale CLI assertion
was updated for the previously added five-second graceful shutdown timeout.
The batch startup instructions were updated; no new dependency was introduced.
No existing task was automatically resumed or modified during this fix.

Live activity follow-up: task pages now include a collapsible fixed bottom panel
showing readable event summaries, elapsed wait, recent updates, snapshot freshness
and stream connectivity. Terminal/paused states override an old model-request event;
stale polling reports uncertainty rather than claiming the task is still working.
Event logs merge refreshed snapshots so stream interruptions do not hide updates.
TypeScript validation and all 24 frontend component/unit tests passed. Live browser
inspection could not connect to port 4317 after the running service stopped; visual
verification of this panel remains pending. No backend or task data was modified.
The batch file was updated to document the panel; no extra startup dependency is needed.

Browser-origin correction: screenshots showed Open WebUI assets requesting
`/api/config` and `/_app/version.json` from GAR on port 3000. A subsequent read-only
HTTP check confirmed Open WebUI HTML on that origin and no GAR backend on 8001.
The batch launcher now maps legacy UI port 3000 to 4317, avoiding that previously
shared browser origin without deleting browser data. Custom ports are preserved.
All 22 focused launcher/lifecycle tests passed, including this mapping; live restart verification
remains pending under the approval-review blocker described below.

Post-acceptance shutdown update: `stop-gar.bat` now requests shutdown of tracked
batch launches and cleans up owned process trees and containers labeled with their
launch ID. API-only and frontend-only batch modes also use tracking. PID creation
times guard against reuse; failed cleanup retains records for retry. Existing
configuration/data and shared apps are preserved. Pre-tracking launches require
manual closure once.

Validation of this update: 19 focused lifecycle/launcher unit checks passed,
including mocked startup/stop for all three launch modes and cleanup failures.
Ruff checks passed for all changed Python files.
The prior port-conflict/identity change passed eight launcher/API checks before
shutdown tracking was added. New live batch start/stop and Docker regressions are
**pending**: automatic approval review rejected the process/Docker test run because
its usage limit was reached. This is an execution blocker, not a passing test result;
the Stage 20 counts above describe the earlier acceptance checkpoint.

Pending command: `.venv\Scripts\python.exe -m pytest tests/e2e/test_combined_launcher.py
tests/e2e/test_server.py tests/integration/test_api.py tests/integration/test_docker_tools.py`.

No authorized stages remain. Stop at Stage 20. The application no longer loads
preview tasks or browser drafts; old browser data was left untouched.

Acceptance demonstrates deterministic runtime behavior, not guaranteed success
for arbitrary goals or installed models. Verification targets bounded software
tasks. Retry/replan limits remain enforced. The single-user loopback design has
no remote authentication. Previously stripped historical payloads cannot be
reconstructed automatically; new tasks preserve exact content and line endings.

Reports: final-stage-reports.md (18–20), frontend-stage-reports.md (12–17),
stage-reports.md (backend stages). Historical reports retain their original
checkpoints with explicit continuation/resolution notes.

### Post-stage path and desktop attachment repair — 2026-09-10

The reported task supplied `/workspace/calculator.py` to filesystem.write.
Filesystem resolution now accepts the exact Docker `/workspace` alias within the
task root, applying the same traversal, secret, link and overwrite approval checks.
Executor instructions explicitly request relative file paths. Missing desktop
sessions now give actionable guidance instead of exposing request.json paths;
the UI rejects attaching the current task ID as a desktop session ID.

Validated 57 backend/integration checks including real Docker desktop interaction
and both Windows batch launcher start/stop cases; 8 frontend checks and TypeScript
validation passed. Changed Python files passed Ruff. Docker was initially stopped;
the same Docker and launcher checks passed after its engine became ready.
No stages beyond Stage 20 were introduced. Existing task data and settings remain.

The live retry also exposed an ignored executor `replan` decision: recovery examined
an older tool error instead. Executor replan requests are now persisted and consumed
by bounded orchestration, preserving the two-replan limit and total decision budget.
All 14 executor/recovery tests passed after this fix, including a requested replan
leading to a new plan and an explicit command approval. Ollama was also stopped
and was restarted to restore the installed local model service.

### Post-stage core reliability audit — 2026-09-10

The sequential audit and observed real-model failures are recorded in
`docs/CORE_AUDIT.md` (28 findings, not new implementation stages). Repairs cover
typed decisions, safe file operations, Docker Tk tests, evidence identity,
per-step retries, bounded replanning, partial actions, useful failure feedback,
mandatory independent goal review and retryable model timeouts.
Later real-model failures also led to write-specific completion evidence and
workspace-aware Git tool availability. The user explicitly approved increasing
the saved model timeout to 600 seconds; other settings and task data were preserved.

The latest consolidated checkpoint passed 247 backend, Docker and Windows
launcher tests. Final review-schema/recovery checks passed 26 focused tests;
Ruff check and format validation passed. Earlier frontend validation passed
29 tests and TypeScript. Real Qwen calculator acceptance has not yet passed:
generated syntax errors, incomplete source and model timeouts remain recorded
as failed runs, not replaced with manually authored successful examples.

`run-gar.bat --no-setup live-check` runs a disposable real-model acceptance;
its approval message now accurately covers the eight scoped workspace/Docker
tools. Normal task approval policy, user configuration and saved work are preserved.
