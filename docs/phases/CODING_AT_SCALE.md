# Coding at scale: large files, several files, declared checks

Owner request 2026-10-29: team members must be able to develop chipset-control
programs (the Qualcomm WMT driver, a 125 KB file) through AEP. A colleague's
inventory showed `coding/change@1.0.0` cannot: the author sees the first
20,000 characters of each file and must return the whole file within 8,000
output tokens, one file per run, and only pytest judges. The owner chose
option B: make `coding/change` itself able to do this work.

Builds on `docs/phases/CODING_ON_BRIDGE.md`; every isolation limit there
stays (low integrity, firewall block, Job object, scrubbed environment,
detached worktree, never committed, golden tests never writable).

## Decisions (2026-10-29)

1. **Author stays the internal Gateway model.** The data rule gives external
   agents (Claude Code, Codex) PUBLIC context only; chipset driver code is not
   PUBLIC, so C8 (native Claude Code author) does not apply. The Gateway
   author becomes an explore-then-edit loop instead.
2. **Edits, not whole files.** The model reads what it needs and answers with
   search/replace edits; AEP applies them. Output size no longer depends on
   file size. A whole-file `content` answer is still accepted for the primary
   file (small files, new files).
3. **The model chooses what to read, the host bounds it.** Read-only actions
   over the run's worktree: list a folder, outline a Python file (classes and
   functions with line numbers), read a line range, search text. `.git` and
   credential-shaped files (`.env`, keys, certificates) are never readable.
   Every answer and the whole transcript are capped; the oldest outputs are
   elided first, and the model is told it can read again.
4. **Several files per run, all declared.** The request names the primary file
   and up to 9 more; each must match the repository's `writable` patterns and
   none may be a test. Scope still comes from the request, never the model.
5. **Host-declared checks.** A repository may declare checks run as
   `python -m <module> <args>` by the restricted runner in the worktree (for
   example pylint, mypy, ruff). `{files}` in the arguments becomes the changed
   files. Still no general shell: the host names the module.
6. **Limits in `host.json`.** `author_max_turns`, `author_max_output_tokens`,
   and `change_max_processes` (default 1; raising it lets tests start child
   processes, which inherit low integrity and the Job object but not the
   firewall rule unless they are the runner interpreter: a residual risk the
   host owner accepts by raising it).
7. **Line endings and encoding are kept.** A CRLF file stays CRLF and a BOM
   stays; edits are matched on LF text. A file that is not UTF-8 or mixes
   line endings is refused for editing with a typed message to the model.

## Shape

| Piece | Where |
|---|---|
| Edit application, newline/BOM keeping | `src/harness/edits.py` |
| Read-only worktree view for the author | `src/harness/repo_reader.py` |
| Explore-then-edit author (JSON actions) | `src/harness/model_author.py` |
| Several candidates per change | `src/harness/runtime.py` (`ChangeAuthor` may return a tuple) |
| Declared module checks | `src/harness/check_commands.py` |
| Request `more_files`, binding limits and `checks` | `src/capabilities/coding_change/contracts.py` |
| Workflow 1.1.0 (`more_files`), Skill 1.9.0 | `src/capabilities/coding_change/manifest.py` |

Author actions (one JSON object per turn):

```
{"action": "list", "path": "src/wmt"}
{"action": "outline", "path": "src/wmt/qualcomm_wlan_driver.py"}
{"action": "read", "path": "...", "start": 1200, "end": 1400}
{"action": "search", "text": "build_op2", "glob": "src/**/*.py"}
{"action": "edit", "edits": [{"path": "...", "old": "exact text", "new": "replacement"}]}
{"action": "done"}
```

An edit's `old` must occur exactly once in the file's current text; an empty
`old` creates a declared file that does not exist. A failed batch changes
nothing and the reason goes back to the model. `done` hands the changed files
to the harness, which validates in order: `pytest-new`, the declared checks,
then `pytest-suite`. A repair starts a new exploration with the failure and
the diff so far.

## Known limits (owner)

- The shared credential rule refuses a change whose text matches the secret
  pattern (`password: str` matches). A driver with such lines cannot be
  changed until the owner decides how the harness should treat code that
  names credentials without containing them.
- Uncommitted and git-ignored files are not in the worktree; commit what the
  tests need (locally) first.
- No live run yet: C7 on the practice repository comes first.

## Slices

| Id | Slice | Verification |
|---|---|---|
| S1 | Edits module, repo reader (**done 2026-10-29**) | unit tests |
| S2 | Explore-then-edit author; harness accepts several candidates (**done 2026-10-29**) | scripted-model tests |
| S3 | Request `more_files`, binding limits, declared checks, handler wiring, Workflow 1.1.0 / Skill 1.9.0 (**done 2026-10-29**) | Windows capability tests on a temporary repository (CRLF large file, two files, a module check) |
| S4 | Docs: decisions, contracts, guide `docs/guides/CODING_LARGE_REPO.zh-TW.md` (**done 2026-10-29**) | docs |
| S5 | Live run on a real repository (owner) | owner |
