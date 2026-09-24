# Handoff — Phase 7 local interfaces and bounded automation

Updated: 2026-09-24 (Asia/Taipei).
Branch: `phase-7/weekly-mail-effort`.
Pull request: #96, open against `main`.

Progress across all phases remains in `docs/TASKS.md`. This file records only
the current stopping point and the evidence needed to continue without chat
history.

## Completed on this branch

- Weekly report mail is deterministic end to end: board effort aggregation,
  pure HTML content, dependency-free PNG chart, Outlook draft creation and the
  `weekly.mail` Workflow. The Outlook adapter has no send operation.
- The Windows preview carries double-click launchers for local chat, weekly
  preview, weekly apply and weekly mail, plus a scheduled preview task.
- `aep-host web` serves the resident Agent and installed asset catalogue on
  loopback only. A fresh per-run token, Host validation and same-origin request
  checks protect the API. It adds no external web dependency.
- The Tk chat remains as a fallback and reaches the same Local Agent, policy
  and Gateway as CLI, Telegram and the web page.
- A company host may configure the existing provider-neutral model catalog and
  OpenAI-compatible company gateway. Deterministic routes still run before the
  model, and model-selected assets must still be installed and authorized.
- A written SOP can be drafted into a typed Workflow candidate and checked for
  contract, dependency, permission and dry-run viability before publication.
- The installed browser can be driven through typed navigation, inspection,
  form and screenshot operations over a dedicated profile. No arbitrary
  JavaScript or shell execution is exposed.

## Architecture and safety boundaries

- Registry/distribution remains the control plane; execution stays on the
  member's Bridge.
- Publication does not grant execution. Every run still uses actor/device
  admission, installed assets, declared capability grants and approval policy.
- The web interface is an ingress only. It contains no workflow-specific page,
  routing rule or capability implementation.
- The Outlook integration creates a draft and cannot send it.
- Model credentials remain `SecretRef` mappings resolved by the host. No secret
  value is stored in an asset or committed configuration.
- SOP authoring produces a reviewable candidate; it does not publish or execute
  the candidate automatically.
- Browser automation drives a browser already installed on the Bridge and does
  not add a downloaded browser/runtime to the offline bundle.

## Verification at `4d7f6d4`

Commands were run from the repository root with Python 3.12:

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.scratch\pytest-codex-20260924
.venv\Scripts\python.exe -m pytest tests\test_browser.py -q -p no:cacheprovider --basetemp=.scratch\pytest-browser-escalated
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m build
git diff --check origin/main...HEAD
```

Results:

- Full suite inside the command sandbox: 1272 passed, 4 skipped, 9 failed only
  because the sandbox closed the installed browser's debugging WebSocket.
- Installed-browser suite outside the sandbox: 20 passed. These include the 9
  cases above, so the combined result is 1281 passed, 4 skipped.
- Ruff lint and format, mypy, pip check and diff check passed.
- Source distribution and wheel built successfully.
- GitHub Actions run 35997347136 passed on Ubuntu and Windows with Python 3.11
  and 3.12 at the same commit.

## Production validation still required

- Run Outlook draft creation on the enrolled company workstation. No live
  Outlook exists on this development machine or in CI.
- Send one request through the configured internal model gateway and confirm
  its real response shape and credential mapping.
- Run the browser adapter against the real target site using a user-created
  browser profile and confirm the site's authentication/session behavior.
- Workflow 11's real workbook must have the lost `2026_38W` sheet restored
  from the pre-run backup before another live write.
- Workflow 10 slices 4b–4d and its real ruleset parity run remain deferred.

## Next recommended action

Merge PR #96 after its pull-request checks pass. Then commit the owner's
product vision as the product-level source of truth and define the next
contract slice before adding more runtime code: Personal Agent profiles and
memory, the Coding Harness acceptance boundary, standardized Improvement
Requests, and Software as a shared capability type. Keep these as small
architecture/contract PRs rather than extending Phase 7 migration code.
