# Reliability slice 1 — implementation and decision record

2026-11-18. Branch harness/reliability-141, baseline ad532e2db3acd04c11289145665a62353eddcc79.
Implementation/testing was authorized by the user. No deployment, push, PR or merge.

## Implemented

- CodingHarnessHandler reports failed or needs_input outcomes at the Bridge boundary; it retains typed command/validation evidence.
- RunPythonHandler reports nonzero exit, executor timeout and unknown exit as distinct non-retryable failures. A failed process no longer completes a Workflow or dispatches a dependent sentinel.
- A local CapabilityTaskFailed exception carries declared output evidence. Bridge validates it against the installed output model before retaining it in CapabilityResult.data; invalid evidence is invalid_output.
- No CapabilityResult wire/schema change, generic JSON inspection, new framework, retry rule, permission change or BI logic change.
- Window/web-readable and CLI direct capability replies show known Draft refusal/preview, excluding the echoed request. Telegram displays closed refusal/failure codes without the payload.
- Direct capability Bridge timeout says work may still be running.
- MCP explicit tool errors now use mcp_tool_failed, without exposing server error content. Adapter timeout remains discovery-only and Bridge call timeout is unchanged.
- Current baseline already fixed CLI non-success exit status; no extra CLI exit migration was introduced.

## Verification

- Red gate after explicit fixture authorization: 7 failed, 2 passed. Failures confirmed nested coding result loss, exit 1/timeout/unknown becoming Workflow success, hidden Draft refusal, missing timeout warning and MCP invalid_input diagnosis.
- Initial focused group: 101 passed in 4.09 s.
- Restricted-runner/reliability group: 29 passed, 1 skipped in 7.82 s; skipped live installed coding runner is absent on this machine.
- Final new regression file, including a real Windows restricted process that exits 1 with no Excel: 12 passed in 1.23 s. The real Workflow failed with completed_steps=0, original output retained and no workbook produced. This is a synthetic current-baseline regression, not the missing historical SOP incident.
- Ruff lint: passed; format check: 1311 files already formatted.
- Mypy: success, 977 source files. Initial test-typing errors were corrected before this successful check.
- Build: wheel and sdist successfully built.
- pip check: no broken requirements.
- git diff --check: passed.
- First full suite completed: **10 failed, 5298 passed, 35 skipped in 1730.06 s**. All ten failures were BI cases. Seven were reproduced as long-path fixture failures and passed with a short base; three other BI failures reproduced on the unchanged baseline. See baseline-regression-notes.md. This run imported the S1 code before S2; the final S2 full suite is separate. No full-suite pass is claimed.
- Full command: .venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp .scratch/pytest-full-reliability --junitxml=.scratch/pytest-full-reliability.xml
- Full output: .scratch/pytest-full-reliability.log. Unified exec session: 56852. Query/poll only this own test process as needed; it is not a delegated task.
- All package installations were confined to the branch's dedicated .venv. Real BI vaults, original worktrees, production configuration and firewall settings were not changed.

## Tested issue requiring a direction decision

A controlled scratch-only experiment (.scratch/timeout-ownership-repro.py) used the actual Bridge and a thread handler with explicit existing policy grants. Two sequential calls each returned timeout; after the first call's deadline the second started another worker while the first was still active.

Observed: first_failure=timeout; second_failure=timeout; max_concurrent_workers=2; invoked_workers=2; artifact_existed_before_release=false; workers_after_release=0. Both writes occurred only in the dedicated scratch folder after releasing the fixture Event. This proves overlapping worker execution in one Bridge, not duplicate business effects, a live Office failure or cross-host behavior.

Accurate wording does not solve ownership. Broad retry/resume behavior is deliberately unchanged. The next phase needs a supported operation-finality/resource-ownership contract, rather than assuming asyncio cancellation stopped a thread.

The owner selected in-flight operation/resource tracking until acknowledged completion/stop, blocking conflicting retries and reusing existing state. Slice 2 implements this decision for Python and Coding Harness workers; see slice-2-design.md and slice-2-results.md. The generic untracked-thread reproduction remains a baseline experiment, not a claim that every handler is now covered.

## Remaining limits

The current baseline already has native tool loops, restricted Python, model-backed coding, completion-check contracts, telemetry and recovery components. Older review inventories are obsolete where they claimed these missing.
Original SOP/PDF and deployment logs are still absent.
A successful process exit alone is not workbook business validation. First task oracle and binding to current acceptance contracts remain necessary before a generic SOP-to-Excel claim.
No full-system reliability target, 90% repair benchmark, live Office effect, cross-host ownership or historical root cause is claimed.
