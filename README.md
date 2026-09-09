# General-Agent-Runtime

GAR adds execution infrastructure around compatible language models. This repository
implements the integrated backend and frontend through **Stage 20**. All required
V1 runtime acceptance scenarios pass; work stops at the authorized Stage 20 boundary.
Ollama discovery and single-prompt generation work through a provider-neutral interface.
Tasks, generated plans, step transitions and events persist in SQLite. Tools can be
invoked through the bounded executor, with approvals, verification, memory, routing,
API and CLI support. Final acceptance passed **172 backend tests**, **20 frontend
tests**, and **14 desktop/mobile browser checks**, including live Docker.

Frontend stage reports are in `docs/frontend-stage-reports.md`; backend reports are
in `docs/stage-reports.md`. Follow the detailed master-prompt stage numbering.

### Run the complete workspace

Requires Node.js 20.9+ (validated with Node 24), Python 3.11+, Ollama with an installed
model, and Docker Desktop with the sandbox image. The UI now uses real backend data.
Existing preview browser drafts are left untouched but are no longer loaded.

```bat
run-gar.bat --no-setup web-setup
run-gar.bat --no-setup dev
run-gar.bat --no-setup web
run-gar.bat --no-setup web-check
run-gar.bat --no-setup web-e2e
run-gar.bat --no-setup acceptance
```

`dev` starts API and UI together and opens the verified GAR page. The preferred UI
port is 4317 and API port is 8000; occupied ports are skipped automatically. Use the
exact address printed by the launcher. Ctrl+C or `stop-gar.bat` stops GAR.
`web-setup` installs the locked npm dependencies;
`web-check` runs TypeScript, frontend tests and a production build. Use `setup`
first if the Python environment has not been installed. Existing browser data,
backend configuration and workspaces are preserved.

`web-e2e` uses desktop/mobile Chrome, an isolated temporary backend on port 8100,
and the frontend on port 3100. Both ports must be free. It substitutes only model
responses; SQLite, APIs, SSE, approvals, filesystem tools and Docker are real.
User tasks, settings, memory and workspaces are not used by these tests.
`acceptance` runs the complete backend, lint, frontend and browser gate. The former
Docker startup blocker is resolved. Acceptance scenarios use deterministic model
responses; arbitrary installed-model performance is not implied by these results.

The Next.js server proxies `/api/v1` to `GAR_BACKEND_URL` (default loopback port 8000).
`dev` derives this target from backend settings. Standalone `web` uses the default
or `web/.env.local`; custom UI origins must match backend `GAR_WEB_ORIGIN`.
See `docs/final-stage-reports.md` for Stages 18–20 and current acceptance results.

## Local setup

On Windows, double-click **run-gar.bat** to install dependencies, initialize the
database, start both API and frontend, and open the UI in your default browser once
ready. The UI normally uses **http://127.0.0.1:4317**. The batch launcher maps the
legacy UI port 3000 to 4317 because Open WebUI can leave cached pages or service
workers on port 3000 even when its server is stopped. Other custom UI ports are
preserved. Occupied ports are skipped and the actual address is printed/opened.
API port conflicts are handled the same way. Keep the launcher window open.
Close the old Open WebUI/error tab and use the newly opened GAR tab after startup.
Task pages include a fixed bottom activity panel with recent runtime events,
time since the last event, server polling freshness and stream connection state.
It explicitly distinguishes waiting for a model, approval pauses, blocked tasks,
failure, cancellation and completion. A reachable server does not prove model
progress; long model calls display the wait without inventing intermediate output.
If startup fails, the window stays open so you can read the error. Use
`run-gar.bat --no-setup serve` for API-only startup. Set `GAR_OPEN_BROWSER=0` to
suppress automatic browser opening. The first setup requires internet access to Python
package indexes. Subsequent setup preserves `.env` and existing data.

```bat
run-gar.bat setup
run-gar.bat --no-setup
run-gar.bat --no-setup models
run-gar.bat --no-setup ask "What is 2 plus 2?" --model qwen3-vl:2b
run-gar.bat --no-setup check
```

Without `--no-setup`, the launcher installs current declared dependencies before
running. `setup` installs and initializes only; `check` runs tests and Ruff. Other
arguments (up to nine) are forwarded to GAR. Run without a command to start both
services and open the frontend. Use `serve` to start only the API.

Double-click **stop-gar.bat** to stop tracked GAR launches from this repository,
including combined, API-only and frontend-only batch startup. It requests shutdown,
then cleans up their child processes and sandbox containers tagged with the launch
ID. Ownership records in `.gar-run` include process start times to prevent stopping
an unrelated process that reuses a PID. Failed cleanup retains records for retry;
Docker must be available to verify container cleanup. The stop window shows the
result; scripts can use `stop-gar.bat --no-pause`.

Your tasks, workspaces, settings, Docker images and volumes are preserved. Shared
Docker Desktop, Ollama, other apps and browser windows remain open. Older GAR
windows started before tracking was added must be closed once manually. Direct
developer commands outside these batch launch modes are not tracked.

The launcher uses the repository directory even when called from another directory,
supports spaces in paths, and returns a nonzero exit code on failure. An existing
Python 3.11+ `.venv` is reused; otherwise it creates one using the Windows Python
launcher or `python`. It never deletes an incompatible environment automatically.
It does not start Ollama; model commands require your Ollama service to be running.

The launcher will be updated and verified each stage; see `DEVELOPMENT.md`.

Use Python **3.11 or newer**. On Windows, use `py -3.11` in place of `python`
when the default interpreter is older.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env
.venv\Scripts\gar --help
.venv\Scripts\gar serve
```

On macOS/Linux, create the environment with `python3.11 -m venv .venv`, then use
`.venv/bin/python` and `.venv/bin/gar` instead.

The API runs at http://127.0.0.1:8000. `GET /api/v1/health` returns
`{"status":"ok","service":"gar","version":"0.1.0"}`. Interactive API documentation
is at `/docs`. Health indicates process liveness, not model or agent readiness.
Stop the server with Ctrl+C.

Other entry points: `gar version`, `python -m gar --help`, or
`python -m uvicorn gar.api.app:create_app --factory --host 127.0.0.1`.
The direct Uvicorn command uses Uvicorn's host/port options; `gar serve` uses GAR settings.

## Configuration

Settings precedence: explicit Python arguments, environment variables, `.env` in the
current working directory, defaults. Configuration is validated before serving.

| Variable | Default | Allowed values |
| --- | --- | --- |
| `GAR_HOST` | `127.0.0.1` | `127.0.0.1`, `localhost`, `::1` |
| `GAR_PORT` | `8000` | 1–65535 |
| `GAR_LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `GAR_WEB_ORIGIN` | `http://127.0.0.1:3000` | Loopback HTTP origin for the UI |

The CLI permits loopback binding only. Tool permissions and local origin checks are
enforced; this is a single-user runtime without remote authentication. `.env` and runtime
data are ignored by Git. GAR logging writes lifecycle messages to stderr without
dumping configuration, and preserves unrelated logging handlers.

## Checks

```powershell
.venv\Scripts\python -m pytest
ruff check .
ruff format --check .
```

The `src/gar` package separates API and CLI from orchestration, tool permissions,
verification, attributed memory and reflection. Procedural memories are unreviewed
candidates and are never automatically executed or used for training.
Dependency ranges are declared in
`pyproject.toml`; a reproducible deployment lock and production hardening are deferred.

## Model layer (Stage 1)

Start your installed Ollama service (`ollama serve`) and ensure a model is already
installed. GAR does not download models automatically. The `ask` command only generates
an answer; task execution uses the bounded executor and validated tool registry.

```powershell
.venv\Scripts\gar models
.venv\Scripts\gar models refresh
.venv\Scripts\gar use qwen3-vl:2b
.venv\Scripts\gar ask "Explain dependency injection"
.venv\Scripts\gar ask "Reply with OK" --model qwen3-vl:2b
```

Use an exact model name from `gar models`. Both listing commands fetch current data.
`gar use` validates the name before atomically saving it in `~/.gar/model.json`.
Selection precedence is `--model`, `GAR_DEFAULT_MODEL`, then saved selection.
Set `GAR_CONFIG_DIR` to change the selection directory. Selection is CLI configuration,
not task persistence. Commands return exit code 1 for provider/selection failures and
2 for invalid configuration.

`GAR_OLLAMA_URL` defaults to `http://127.0.0.1:11434`; `GAR_MODEL_TIMEOUT` defaults
to 120 seconds per request (positive, at most 3600). Remote endpoints are explicit
configuration: prompts are sent to that endpoint. Redirects and environment proxy
inheritance are disabled. URLs containing credentials, queries or fragments are rejected.

`ModelAdapter` defines `discover`, `health`, and `generate`; `ModelRegistry` keeps
provider-qualified model IDs and replaces discovery snapshots only after successful
refresh. Health checks discovery availability, not whether a particular model fits
in memory or supports a requested feature. No capabilities are guessed from names.

The Ollama adapter uses non-streaming `/api/chat` and `/api/tags`, validates response
envelopes, and normalizes HTTP, transport, timeout and malformed-response errors.
Tool definitions and JSON schemas can be supplied to `generate`; returned tool calls
remain proposals. Structured answer content is checked against its JSON schema with
external reference fetching disabled. The executor supplies tool observations as untrusted
context and authorizes all tool calls through the registry. Generation is not retried silently.

Tests use mock HTTP transports and require no model download. Live model checks are
reported separately because installed models and available hardware vary.

## Task state and persistence (Stage 2)

```bat
run-gar.bat --no-setup task-create "Inspect a Python project" qwen3-vl:2b
run-gar.bat --no-setup tasks
run-gar.bat --no-setup task TASK_ID
run-gar.bat --no-setup cancel TASK_ID
```

The CLI `task-create` command records a **PENDING** goal only. Use `gar run` or the UI
to create and execute a task, or `gar plan TASK_ID` to generate a plan explicitly.
The workspace path is allocated logically under
`data/workspaces/<id>`; tool execution creates and enforces this workspace boundary.

`GAR_DATA_DIR` defaults to `./data`. The database is `GAR_DATA_DIR/gar.db`. The launcher
and API startup initialize schema version 1 without removing existing rows. Direct CLI
commands interpret relative data paths from the current directory; the batch launcher
always uses the repository directory. `gar db-init` also initializes the database.

Domain models validate nonempty goals, bounded step counts, dependency IDs and cycles.
Repository writes validate lifecycle rules and update task versions atomically with
their events. Stale writers are rejected. Plans retain prior revisions; step status
changes update the current revision and append events. Only one step may be active,
and dependencies must be complete before starting a dependent step. Tasks cannot enter
VERIFYING until their steps complete, or reach COMPLETED without the evidence verifier.

Persisted events have monotonic IDs and support replay after an ID through the Python
repository and SSE endpoint. Restart preserves state but does not automatically resume
tasks. Task snapshots, controls, models, tools, memory and settings are available under
`/api/v1`; see `/docs`. Failed steps support bounded explicit resume; migration tooling
beyond schema version validation remains outside V1.

## Structured planner (Stage 3)

Start Ollama separately and choose an installed model from `gar models`:

```bat
run-gar.bat --no-setup task-create "Create a calculator module with tests" qwen3-vl:2b
run-gar.bat --no-setup plan TASK_ID
run-gar.bat --no-setup task TASK_ID
run-gar.bat --no-setup plan-help
```

Replace TASK_ID with the ID printed by task creation. `plan` uses the task's saved
model. It checks model availability before claiming the task. The planner passes a
JSON schema to the adapter and independently validates the returned plan, including
unique IDs, acyclic dependencies, step limits, nonempty expected outputs and explicit
completion criteria. The model cannot supply runtime task IDs, revisions, statuses or
attempt counts. JSON embedded in prose and tool proposals are rejected.

Accepted plans remain **PLANNING** with a saved plan. No step or tool executes.
Generation/validation failures after claiming a task leave it **BLOCKED**, with no plan
saved; repeat `plan TASK_ID` to explicitly retry. Discovery failures leave the task
unchanged. Existing plans are not overwritten; `gar replan TASK_ID` creates a bounded
new revision, while `gar resume TASK_ID` can retry failed steps.
Cancellation or a concurrent update prevents a late model response from saving a plan.

Runtime events record the request, validated response and saved plan, without storing
raw model output or prompts in telemetry. A process killed abruptly while planning may
leave a PLANNING task without a plan; crash recovery remains future work. No SQLite
transaction is held open while awaiting the model. Completion criteria survive restart
and old Stage 2 plans remain readable without a database migration.

Validation establishes structural correctness, not that a plan is sufficient to solve
the goal or that a model's proposed criterion is meaningful. Objective evidence checking
is handled by the runtime verifier. The Python planner accepts at most 20,000 characters of
explicit reference context; the CLI sends the goal and limit only, without reading files.
The launcher adds `plan-help` and continues to preserve configuration and database state.

## Tool runtime (Stage 4)

`gar tools` lists strict input schemas and risk classifications. All calls pass through
`ToolRegistry.execute`; unknown tools, extra fields and invalid arguments are rejected.
There is no model-to-tool connection yet. Tool calls do not advance task/step state.

```bat
run-gar.bat --no-setup tools
run-gar.bat --no-setup tools-help
run-gar.bat --no-setup tool TASK_ID filesystem.write write.json
run-gar.bat --no-setup tool TASK_ID filesystem.read read.json
```

Example `write.json`: `{"path":"hello.py","content":"print('hello')"}`.
Example `read.json`: `{"path":"hello.py"}`. Argument-file paths are relative to the
repository when using the batch launcher. Tool paths are relative to the task workspace.
The CLI creates the task workspace on first use. Parent directories of written files
must already exist. The workspace must be a dedicated directory, not a credential store.

Available tools: `filesystem.list`, `filesystem.read`, `filesystem.write`, `terminal.run`,
`python.run`, `git.status`, `git.diff`. The filesystem tools reject traversal, absolute
paths, Windows device/ADS paths, links, reparse points, hardlinks and known secret paths.
Reads are limited to 1 MB; directory results to 1,000 entries. New writes are CAUTION;
overwriting an existing file is DANGEROUS and needs `--approve` for that call.

Python and terminal calls are DANGEROUS because code can modify/delete workspace files.
Their approval comes from the trusted CLI flag, never a JSON argument. Approval is not
saved for future calls. PROHIBITED actions remain denied regardless of approval.

Process tools require **Docker Desktop running with Linux containers** and this image:

```bat
run-gar.bat --no-setup sandbox-setup
run-gar.bat --no-setup sandbox-check
run-gar.bat --no-setup tool TASK_ID python.run code.json --approve
run-gar.bat --no-setup tool TASK_ID terminal.run tests.json --approve
```

Example `code.json`: `{"code":"print(2 + 2)"}`.
Example `tests.json`: `{"argv":["python","-m","pytest","-q"]}`.
Terminal allows only `python -m pytest`, `python -m pytest -q`, and
`python -m unittest discover`; it never invokes a host shell. The image contains Python,
pytest and Git. Image setup downloads build dependencies; tool calls never pull images.

Containers use a non-root user, no network, a read-only root, no added capabilities,
bounded memory/CPU/process counts and a temporary directory. Only the task workspace is
mounted; Git inspection mounts it read-only. Timeout/cancellation triggers container
removal, including descendant processes. Output is capped at 64 KiB. On Linux hosts,
the dedicated workspace must be writable by container UID 65534 for write operations.
There is no unsandboxed fallback when Docker is unavailable.

Before mounting, GAR checks up to 10,000 entries and rejects known secret files and links.
Normal `.git` directories are allowed only for container inspection; external Git directory
files are rejected. Host filesystem checks assume no competing malicious host process
swapping paths during an operation. This is not a hardened multi-user host sandbox.
Containers have no workspace disk quota; approved code may consume workspace disk space.

Calls produce a structured result with ID, status, output, exit code and error code.
`data/tool-audit.db` records requests, approval decisions, starts and results outside the
mounted workspace. Failure to write the initial audit record prevents execution.
Known secret patterns are redacted; this is best-effort and cannot identify every secret.
The audit is local SQLite, not a tamper-proof security log. Existing schema-1 task data
is preserved; no migration is needed for the separate tool audit database.

Normal `check` skips the four Docker end-to-end tests. Run `sandbox-check` after building
the image to verify actual Python/tests/Git execution, timeout cleanup and isolation.
