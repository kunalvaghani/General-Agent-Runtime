# Core reliability audit — 2026-09-10

Scope: model adapter → planner → executor → tools → persistence → verification,
plus API lifecycle and UI visibility. Existing stages stop at 20; this is repair work.

Observed task ef8668d64e4942379b618ca487a828c5 made zero tool calls. It requested
three plans and exhausted the two-replan limit. Increasing retries alone would
repeat the same failure. Passing scripted tests did not demonstrate local-model success.

Repair order (each item requires focused tests before the next):

1. **Model/tool contract:** Decision.arguments is an unconstrained object, despite
   concrete tool schemas. Supply a tool-specific structured response schema and
   preserve independent runtime validation/approval.
2. **Planning context:** executor sees one step without the full plan; prompts
   describe GUI goals as unsupported despite the approved desktop feature. Supply
   the plan, explain capability boundaries consistently, reserve repair budget,
   and require implementation + tests + final test execution.
3. **Failure and recovery:** model/protocol failures lack persisted reasons;
   stale observations can drive recovery; verification failures cannot resume with
   no failed step. Persist current failure details and route verification repair
   through bounded replanning, preserving approvals and total budgets.
4. **Filesystem usability:** writing tests/test_app.py cannot create its parent
   directory. Add safe parent creation using the same path/link checks.
5. **Verification identity:** aliases of the same file are compared separately,
   and reused step IDs across plan revisions can inherit unrelated evidence.
   Canonicalize paths and bind new observations to plan revisions.
6. **Acceptance coverage:** add a reproducible real-Ollama + Docker run, record
   artifacts, test evidence and limitations; do not substitute a scripted model
   or manually authored calculator for the acceptance result.
7. **Docker dependency mismatch:** confirmed `import tkinter` failed with missing
   libtk8.6.so in gar-tools:stage4. Add the Tk runtime library so guarded GUI
   modules can be imported for headless tests; interactive windows still use
   the separately approved desktop image.
8. **Partial tool calls marked steps complete:** a diagnostic file read completed
   a test/repair step. Add explicit step_complete decisions with bounded multiple
   calls per step; retain exact pending-approval resumption. Plans now use up to
   six coherent milestones, each of which may require multiple calls.
9. **Snippet overwrites:** the real model replaced complete Python modules with
   indented method fragments. Clarify replacement semantics in the tool schema
   and reject syntactically invalid Python before changing files, with repair feedback.
10. **Optional file paths:** file reads/writes inherited the directory-list default
    path `.`. A real response omitted path and prompted to overwrite a directory.
    File paths are now required in both decoder schemas and runtime validation;
    non-file targets are rejected before approval.
11. **Missing directory operation:** the real model created a file as a folder.
    Add filesystem.mkdir, explicit folder/file instructions, and recoverable
    path-type errors that preserve existing data.
12. **GUI test environment:** Tk imports alone did not permit widget tests.
    Add a temporary virtual display with explicit readiness and cleanup inside
    the test container. The first xvfb-run wrapper hung before Python started;
    replace it with a trusted entry point patterned after the working desktop.
13. **Launcher test isolation:** a live frontend held the default Next build lock.
    Use validated, unique test build directories; both launcher cases now pass
    without stopping the user's frontend.
14. **Retry feedback:** protocol failures were persisted but cleared before the
    next model prompt, leaving retries without their failure reason. Supply that
    failure explicitly in the next prompt while clearing stale recovery state.
15. **Replanning loses the repair target:** slicing the tail of raw metadata can
    discard prior work and failure context. Real runs repeatedly replanned the
    original implementation. Supply bounded, valid JSON containing the current
    failure, previous step states, written paths and recent results; ask for
    targeted repair and tests while preserving existing work.
16. **Exhausted actions still advertised:** the constrained response schema still
    offered replan after both replans were used. Omit that action when unavailable,
    expose availability in the prompt and retain runtime enforcement.
17. **Stale failure revival:** repair context selected an old rejected write even
    after successful writes/reads. Use the current failure only; clarify that
    rejected content never replaced the current file, and that completion means
    the current step rather than the entire task.
18. **No evidence-backed finish action:** an inspection could only finish by
    repeating a tool or sending an unverified response. Add complete_step with
    successful call IDs from the current step and plan revision. Invented evidence
    is rejected; completing steps still leads to independent final verification.
19. **Repeated inspections:** three identical unchanged reads/lists now produce
    actionable no-progress feedback and bounded recovery instead of silently
    consuming the entire decision budget.
20. **Acceptance fidelity:** use the app's configured model endpoint/timeout,
    record response durations and distinguish approval pauses from failures.
    The disposable harness may approve the existing scoped file and Docker tools;
    production approvals remain unchanged.
21. **Repair-plan dependencies:** a real repair plan referenced completed steps
    from the previous revision and was rejected as an invalid graph. Resolve only
    dependencies known by the repository to be complete; still reject unknown
    dependencies and retain edges to steps reintroduced in the new plan.
22. **Retries exhausted by unrelated steps:** the real run reached its first
    test execution but was denied recovery because earlier writing steps used
    two retries. Enforce three attempts per step instead of two retries across
    the entire task. Keep cumulative retry counts, total decision budget and
    the two-replan limit; no counter is reset to manufacture a passing result.
23. **Unchanged failing tests and premature test completion:** the model reran
    the same failures without edits. Withhold that test action until a successful
    workspace write or Python repair action, and reject premature reruns before
    another approval. Test steps require successful, untruncated test evidence
    after edits, even if a model marks a repair write complete. Keep failure
    details through read-only inspection and describe Tk test setup accurately.

## Repair checkpoints

- 1–2: typed tool/argument schemas (including exact test argv), full plan context,
  remaining budget, actionable plan examples and typed tool hints implemented.
  Planner tests include a mandatory final-test milestone after planned edits.
- 3: current failure reasons, bounded protocol-error retry, and verification-driven
  replanning implemented. Recovery tests preserve separate command approvals.
- 4–5: safe nested creation, canonical write identity and revision-bound evidence
  implemented. Outside paths, secrets and linked files remain rejected.
- 7: rebuilt through `run-gar.bat --no-setup sandbox-setup`; real Docker Tk import
  test passes without opening a window.
- 8–10: multi-call steps, preserved approval continuation, non-destructive Python
  syntax checks, mandatory paths and pre-approval file validation implemented.
- Consolidated checkpoint: 229 backend and real Docker tool tests passed;
  29 frontend tests and TypeScript passed after the planner/path fixes.
- 11–12: directory operations and recoverable file/directory conflicts implemented.
  The rebuilt tool image passes real Tk create/update/destroy testing. Retesting
  the previous generated calculator now returns six ordinary test failures
  (its tests passed None as the GUI root), rather than a display startup timeout.
  This distinguishes a generated-code failure from the repaired environment.
- 13: both launcher start/stop cases passed with unique Next build directories.
- 14–15: retry feedback and structured repair context implemented. Regression
  checks cover prior failure delivery, previous step states and large histories.
- The app was restarted and both API and frontend health checks returned 200.
  Browser verification showed the connected GAR workspace, four preserved user
  tasks and the new-task decision budget of 50.
- 6: `run-gar.bat --no-setup live-check` added. Actual Qwen/Docker runs are retained
  under `.gar-run/live-acceptance-*`. Failed runs are evidence of remaining problems,
  not successes. No manually written calculator is substituted for generated code.
  Run `278506aad3e74b66a37416930cb84098` reached Docker tests but stopped after
  repeated replanning at 14 decisions; its generated tests incorrectly passed
  None as a Tk root. A fresh run tests the subsequent repair-context correction.
  Run `c32911ea7fc340219346da53a6ea81bb` stopped at 10 decisions after revisiting
  a rejected syntax error and requesting a third replan. Items 16–17 address
  those observed failures; 20 focused schema/executor/recovery tests pass.
  Run `42fdbff0f5124283a0b5d25f4ebce621` repeatedly inspected the same file,
  then reached tests and paused for a file-read approval the old harness did not
  grant. That pause was not a runtime failure. The fixture was cancelled for the
  revised harness. Completion/loop regression checks pass (23 focused tests).
  Run `355681623fd84d58a904d22ccfe4a73b` exposed completed-step dependency
  handling and the task-wide retry cap, then repeated tests without a repair.
  Its resumptions retained all files and cumulative counters; it did not pass.
  Items 21–23 passed focused regressions (29 schema/executor/recovery checks).
  A new, unassisted acceptance run uses all corrections together.

24. **Syntax repair lacks the rejected source location:** a fresh run repeatedly
    generated missing string quotes. Rejected source is never saved, so reading
    the file cannot retrieve that error. Return a bounded offending line and caret
    with the syntax diagnostic. Tests cover the real missing-quote failure,
    oversized source lines, and preservation of existing files.

25. **Tests passing was confused with goal satisfaction:** final verification
    checked file integrity and command success but never reviewed the original
    goal. Add a separate, tool-free model review of the actual artifacts and test
    output against the user goal and every completion criterion. Explicit schema
    keys prevent duplicate/omitted criteria. Missing evidence, invalid responses,
    timeouts and oversized review context fail closed. Concrete deficiencies feed
    bounded repair. The installed Ollama rejects a 2000-character reason bound;
    a 500-character bound was verified to compile. Model review is an additional
    check, never a replacement for tests or an authorization to execute code.
26. **Timeouts stopped recovery:** executor classified model timeouts as an
    unavailable provider. Preserve an explicit timeout reason and use the existing
    bounded retry path. The next prompt says no tool executed and requests a
    smaller complete action. A regression verifies one timeout, one successful
    write, unchanged approvals, and cumulative decision/retry accounting.

27. **Reads could certify implementation work:** the model cited a read of a
    placeholder as proof a filesystem.write step was implemented. Write steps
    now require successful write evidence; read actions cannot advance them or
    enable complete_step. Both the schema and runtime enforce this. Tool decisions
    also have short reasons and no unused output body, reducing irrelevant text.
28. **Unavailable Git tools distracted repair:** a fresh task folder has no Git
    repository, but Git tools remained in every decision schema. Omit them from
    the model's tools/schema until the workspace contains a repository, and reject
    stale proposals before launching a container. Direct CLI diagnostics remain
    available. Tool timeouts now explain the execution limit and the separate
    interactive-desktop workflow rather than returning an empty error message.

Continuation checkpoint:
- 236 backend and real Docker checks passed, with output retained in
  `.gar-run/core-tests-latest.log`. The subsequent source-diagnostic change passed
  all 42 tool checks (including Windows subprocess limits).
- Fresh run `bf484fee4bd44358a4102732dbb8338c` blocked at eight decisions after
  repeated invalid Python writes. It did not pass; no generated calculator was
  substituted or budget reset. The diagnostic correction is being tested in a
  new fixture, `7bb66322dfc64d43b98786083fb68ed2`. That run timed out during test
  generation after claiming a placeholder window was implemented. It did not
  pass. Items 25–26 address those newly observed gaps.
- The expanded suite passed 247 tests including real Docker and both Windows
  start/stop launcher cases. The final keyed review schema and timeout recovery
  also passed 26 focused verifier/recovery/runtime checks. Ruff check and format
  validation pass.
- Real Qwen negative review `a0f36b90359449aab85ba4ac3c177b34` correctly rejected
  an intentionally incomplete calculator whose weak test passed in Docker.
  This verifies the new goal-review gate; it is not a successful code-generation
  acceptance. The app restarted and the browser confirmed CONNECTED with all four
  saved user tasks preserved. Launcher checks also passed after adding cleanup of
  only each test's temporary TypeScript include entries.
- With explicit user approval, saved model_timeout was increased from 120 to 600
  seconds; default_model and all other settings were preserved. The 120-second
  fixture `36c95c06e8624724986b56f87cf8b8c7` was cancelled and retained when the
  setting changed. Fresh 600-second fixture `394fd81940b84d59a4b19b934fabb697`
  reached five failing Docker tests, but then claimed read-only inspections were
  implementations, repeatedly used unavailable Git and timed out a Python command.
  It blocked at 18 decisions. Items 27–28 passed 35 focused schema/executor/recovery
  checks and all 42 tool checks before another fresh acceptance run.

Remaining capability boundaries: small models can still generate bad programs;
test execution and model review are evidence, not proof of arbitrary goal satisfaction.
Goal review currently refuses evidence larger than 40000 characters; it does not
silently discard source to claim success. Tools remain
offline and task-folder scoped. GUI launch requires tested snapshot approval.
