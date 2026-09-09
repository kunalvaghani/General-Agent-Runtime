# Engineering reports: Stages 5–17

Historical backend reports. Authorization was subsequently extended through Stage 20;
see final-stage-reports.md for integration and final acceptance results.

STAGE:
5 — Executor

INTENDED:
Implement executor.

IMPLEMENTED:
Model decisions, strict schemas, exact-call approvals, persisted action budget.

FILES CREATED:
src/gar/core/executor.py; src/gar/core/runtime.py; src/gar/cli/execution.py; tests/integration/test_executor.py

FILES MODIFIED:
Relevant runtime/CLI contracts, run-gar.bat; see source changes and README.

ARCHITECTURE NOTES:
Shared backend services; untrusted model data does not control permissions or state.

TESTS ADDED:
Focused unit/integration cases for this stage.

COMMANDS EXECUTED:
pytest (focused stage suites); ruff check . --fix; ruff format .

TEST RESULTS:
20 focused tests passed; malformed decisions, approvals and action limits covered.

BUGS DISCOVERED:
Formatting diagnostics during implementation; no unresolved failure in the stage checks.

BUGS FIXED:
Formatting diagnostics corrected before proceeding.

SECURITY FINDINGS:
No completion claim from execution alone.

KNOWN LIMITATIONS:
No completion claim from execution alone.

ACCEPTANCE CRITERIA:
[x] Scope implemented
[x] Focused checks passed
[x] Launcher reviewed and updated

STATUS:
READY FOR REVIEW

NEXT STAGE IF APPROVED:
Stage 6 (already authorized).

---

STAGE:
6 — Verifier and recovery

INTENDED:
Implement verifier and recovery.

IMPLEMENTED:
Evidence verification, two explicit retries and two replans; completion requires successful tests after mutations.

FILES CREATED:
src/gar/core/verifier.py; src/gar/core/orchestrator.py; tests/integration/test_verifier.py

FILES MODIFIED:
Relevant runtime/CLI contracts, run-gar.bat; see source changes and README.

ARCHITECTURE NOTES:
Shared backend services; untrusted model data does not control permissions or state.

TESTS ADDED:
Focused unit/integration cases for this stage.

COMMANDS EXECUTED:
pytest (focused stage suites); ruff check . --fix; ruff format .

TEST RESULTS:
15 focused tests passed; model-only claims rejected and retry limit enforced.

BUGS DISCOVERED:
Formatting diagnostics during implementation; no unresolved failure in the stage checks.

BUGS FIXED:
Formatting diagnostics corrected before proceeding.

SECURITY FINDINGS:
Verification targets bounded software goals; explicit retry/replan, no unlimited recovery.

KNOWN LIMITATIONS:
Verification targets bounded software goals; explicit retry/replan, no unlimited recovery.

ACCEPTANCE CRITERIA:
[x] Scope implemented
[x] Focused checks passed
[x] Launcher reviewed and updated

STATUS:
READY FOR REVIEW

NEXT STAGE IF APPROVED:
Stage 7 (already authorized).

---

STAGE:
7 — Memory

INTENDED:
Implement memory.

IMPLEMENTED:
Attributed SQLite memory with four categories, expiry, threshold, search and deletion.

FILES CREATED:
src/gar/memory/manager.py; tests/unit/test_memory.py

FILES MODIFIED:
Relevant runtime/CLI contracts, run-gar.bat; see source changes and README.

ARCHITECTURE NOTES:
Shared backend services; untrusted model data does not control permissions or state.

TESTS ADDED:
Focused unit/integration cases for this stage.

COMMANDS EXECUTED:
pytest (focused stage suites); ruff check . --fix; ruff format .

TEST RESULTS:
Memory and verifier tests passed (3 cases).

BUGS DISCOVERED:
Formatting diagnostics during implementation; no unresolved failure in the stage checks.

BUGS FIXED:
Formatting diagnostics corrected before proceeding.

SECURITY FINDINGS:
Substring retrieval; no embeddings; procedures are not automatically applied.

KNOWN LIMITATIONS:
Substring retrieval; no embeddings; procedures are not automatically applied.

ACCEPTANCE CRITERIA:
[x] Scope implemented
[x] Focused checks passed
[x] Launcher reviewed and updated

STATUS:
READY FOR REVIEW

NEXT STAGE IF APPROVED:
Stage 8 (already authorized).

---

STAGE:
8 — Reflection

INTENDED:
Implement reflection.

IMPLEMENTED:
Trace-derived experiences and unreviewed procedural candidates.

FILES CREATED:
src/gar/learning/reflection.py; tests/unit/test_reflection.py

FILES MODIFIED:
Relevant runtime/CLI contracts, run-gar.bat; see source changes and README.

ARCHITECTURE NOTES:
Shared backend services; untrusted model data does not control permissions or state.

TESTS ADDED:
Focused unit/integration cases for this stage.

COMMANDS EXECUTED:
pytest (focused stage suites); ruff check . --fix; ruff format .

TEST RESULTS:
Reflection and memory tests passed (2 cases).

BUGS DISCOVERED:
Formatting diagnostics during implementation; no unresolved failure in the stage checks.

BUGS FIXED:
Formatting diagnostics corrected before proceeding.

SECURITY FINDINGS:
Deterministic extraction, no autonomous training or candidate execution.

KNOWN LIMITATIONS:
Deterministic extraction, no autonomous training or candidate execution.

ACCEPTANCE CRITERIA:
[x] Scope implemented
[x] Focused checks passed
[x] Launcher reviewed and updated

STATUS:
READY FOR REVIEW

NEXT STAGE IF APPROVED:
Stage 9 (already authorized).

---

STAGE:
9 — Router

INTENDED:
Implement router.

IMPLEMENTED:
Deterministic privacy, capability, context and cost filtering.

FILES CREATED:
src/gar/models/router.py; tests/unit/test_router.py

FILES MODIFIED:
Relevant runtime/CLI contracts, run-gar.bat; see source changes and README.

ARCHITECTURE NOTES:
Shared backend services; untrusted model data does not control permissions or state.

TESTS ADDED:
Focused unit/integration cases for this stage.

COMMANDS EXECUTED:
pytest (focused stage suites); ruff check . --fix; ruff format .

TEST RESULTS:
32 router/model regression cases passed.

BUGS DISCOVERED:
Formatting diagnostics during implementation; no unresolved failure in the stage checks.

BUGS FIXED:
Formatting diagnostics corrected before proceeding.

SECURITY FINDINGS:
Unknown capabilities remain unknown; use explicit profiles for advanced routing.

KNOWN LIMITATIONS:
Unknown capabilities remain unknown; use explicit profiles for advanced routing.

ACCEPTANCE CRITERIA:
[x] Scope implemented
[x] Focused checks passed
[x] Launcher reviewed and updated

STATUS:
READY FOR REVIEW

NEXT STAGE IF APPROVED:
Stage 10 (already authorized).

---

STAGE:
10 — API

INTENDED:
Implement api.

IMPLEMENTED:
Task CRUD operations, exact-ID approval, cancellation, SSE replay, memory deletion and settings.

FILES CREATED:
src/gar/api/service.py; src/gar/api/routes/runtime.py; tests/integration/test_runtime_api.py

FILES MODIFIED:
Relevant runtime/CLI contracts, run-gar.bat; see source changes and README.

ARCHITECTURE NOTES:
Shared backend services; untrusted model data does not control permissions or state.

TESTS ADDED:
Focused unit/integration cases for this stage.

COMMANDS EXECUTED:
pytest (focused stage suites); ruff check . --fix; ruff format .

TEST RESULTS:
API/executor checks passed (7 cases); subsequent focused API regression passed.

BUGS DISCOVERED:
Formatting diagnostics during implementation; no unresolved failure in the stage checks.

BUGS FIXED:
Formatting diagnostics corrected before proceeding.

SECURITY FINDINGS:
Loopback single-user service; one active runtime; no remote authentication.

KNOWN LIMITATIONS:
Loopback single-user service; one active runtime; no remote authentication.

ACCEPTANCE CRITERIA:
[x] Scope implemented
[x] Focused checks passed
[x] Launcher reviewed and updated

STATUS:
READY FOR REVIEW

NEXT STAGE IF APPROVED:
Stage 11 (already authorized).

---

STAGE:
11 — CLI

INTENDED:
Implement cli.

IMPLEMENTED:
Run, resume, approve, replan, doctor, memory and configuration commands with live events.

FILES CREATED:
src/gar/cli/runtime.py; tests/e2e/test_runtime_flow.py

FILES MODIFIED:
Relevant runtime/CLI contracts, run-gar.bat; see source changes and README.

ARCHITECTURE NOTES:
Shared backend services; untrusted model data does not control permissions or state.

TESTS ADDED:
Focused unit/integration cases for this stage.

COMMANDS EXECUTED:
pytest (focused stage suites); ruff check . --fix; ruff format .

TEST RESULTS:
6 focused workflow/CLI/API cases passed; full backend suite recorded below.

BUGS DISCOVERED:
Formatting diagnostics during implementation; no unresolved failure in the stage checks.

BUGS FIXED:
Formatting diagnostics corrected before proceeding.

SECURITY FINDINGS:
Models remain probabilistic; deterministic model fixtures test orchestration.

KNOWN LIMITATIONS:
Models remain probabilistic; deterministic model fixtures test orchestration.

ACCEPTANCE CRITERIA:
[x] Scope implemented
[x] Focused checks passed
[x] Launcher reviewed and updated

STATUS:
READY FOR REVIEW

NEXT STAGE IF APPROVED:
Stage 12 (already authorized).

---

