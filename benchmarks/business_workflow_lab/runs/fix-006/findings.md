# fix-006: findings

Setup: AEP `f69ee2c`, with coding 1.6.0 (fill the given template) and the retry of a reply cut at the output limit. Grader 1.2. coding_v1 passed 20/20 on the same build (fix-run-007).

Result: **13 PASS of 16 runs**:
- **W01 to W04** in Edge. W01's rerun with 2026-08/Closed used the same Workflow digest. W04 met the injected session expiry and signed in again.
- **D01 to D04** on the WinForms app through UI Automation. D01's rerun with E002/2026-08 used the same Workflow. D04 met the injected export failure, retried, and produced an empty report.
- **C01 to C04** with real CLI subprocesses, including C01's rerun with C002 and C04's transient exit 4.
- **C04-force_exit2:** the error was reported, with no fake report.

| Task | Status | Cause | Follow-up |
|---|---|---|---|
| X01 | FAIL | The first result was correct, through Edge, the desktop app and the CLI. The rerun failed twice: the Workflow saved the desktop export under a fixed name that the first run had left (`desktop_path_exists`), and the Agent revised the Workflow (1.0.0 to 1.0.1) between the first result and the rerun, so the rerun ran different code. | `save_as` gains `replace: true`. The draft guide says to put run values in output file names (`12c684f`). |
| X02 | FAIL | It used all three interfaces, but did not ask about the open rules (expense scope, attention rules). It assumed them: other projects' expenses, the cancelled order, and a different attention set. | coding 1.5.0/1.6.0's "ask first" has not changed this in three runs. It needs the owner's decision on a shared system-prompt rule. |
| X03 | BLOCKED | Depends on X01. | |

Bypass: X01's scripts read the old Tk app's source again. This is noted; no data file was read.
