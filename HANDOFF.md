# Handoff

Date: 2026-09-29 (Asia/Taipei)
Branch: `codex/company-agent-prereqs`
Base: `origin/main` at `076af0deba81807536934ed4c20fce3936ce8fd5`
Implementation commit: `91ad837`
Pull request: https://github.com/dragon0816/agentic-engineering-platform/pull/129

## Completed

- Replaced the single-route Personal Proof deployment request with one dynamic,
  artifact-pinned `aep-company-agent-integration-v1` request. Issue numbers
  are created at runtime; none is hardcoded.
- Added typed contracts that restrict profile paths to relative POSIX paths,
  restrict the fixture model to credential-free HTTP loopback, and declare
  exact grant requirements.
- Shipped a hash-verified validation package in the Windows preview:
  controlled SOP PDF, valid draft Workflow response, exact published Knowledge
  manifest and immutable Vault, grounded response, and Personal Proof fixture.
- Kept grants separate and least-privilege:
  `workflow-author/draft@1.0.0`, `knowledge-query/ask@1.0.0`, and
  `company-agent/personal-proof-fixture-read@1.0.0`. No general
  `filesystem/read-file` grant was added.
- Marked the fixture tree byte-stable so Knowledge digests and PDF bytes do not
  change across Windows/GitHub checkouts.
- Updated architecture, deployment documentation, progress and sdist rules.

## In Progress

- PR #129 is open. GitHub Platform verification run 36575228427 passed in 4m36s.
- Hermes does not yet implement the new fixed action/profile below.

## Remaining

1. Hermes must allowlist action `install_and_company_agent_integration`,
   profile `aep-company-agent-integration-v1`, and artifact path
   `validation/company-agent-integration-v1/profile.json`.
2. Hermes must run only the artifact profile in an isolated proof workspace,
   structurally render the Knowledge vault path, own the loopback fixture
   server, install only declared actor grants, run doctor/export-assets, and
   collect all four acceptance records. Issue prose is never executable.
3. After CI passes, the owner may merge PR #129. Successful main CI will create
   a new validation Issue and trusted JSON payload automatically.
4. A real company model endpoint remains a later, separately credentialed
   check and is not required for this deterministic integration proof.

## Architecture decisions made

- REUSE the existing Agent, Gateway, Bridge, workflow author, Knowledge query,
  OpenAI-compatible adapter and Personal Proof boundaries.
- ADD an artifact-owned fixed profile instead of a second runtime.
- Use credential-free loopback to prove wiring without API cost; it is not
  evidence of a production model endpoint.
- Keep publication, local grants and technical policy separate.
- Preserve #128's fixture-rooted reader and never broaden it.

## Verification

Supported target: Windows, Python 3.12. Browser tests were excluded by owner
instruction.

```text
pytest --ignore=tests/test_browser.py
1330 passed, 4 skipped

focused profile/workflow/bundle suite
25 passed

ruff check . / ruff format --check .
passed; 288 files formatted

mypy
Success: no issues found in 224 source files

pip check
No broken requirements found

python -m build
Successfully built sdist and wheel

sdist inspection
profile.json, model-responses.json, personal-proof-sop.pdf,
personal_proof.txt: all present

workflow YAML
parsed successfully

GitHub Platform verification run 36575228427
passed; Windows preview built, installed and uploaded
```

## Known issues

- No production company model credential or endpoint was tested.
- Until Hermes adds its allowlisted runner, the new request must block at
  preflight and must not report a functional FAIL.
- Human approval remains the merge gate.

## Next Recommended Action

Give Hermes the fixed-runner prompt. CI is green; merge PR #129 after Hermes
confirms the action/profile are allowlisted.
The next successful main artifact should create one dynamic validation Issue
and begin the three-route proof automatically.
