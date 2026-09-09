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
