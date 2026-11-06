# BI SOP completed — bi-sop

Base: `73f9145c`; branch: `bi-sop`. No push. The next action is for the BI orchestrator to review and merge this documentation commit, then package the release with its existing BI_SOP copy step.

## Delivered

- `docs/guides/BI_SOP.zh-TW.md`: 98 numbered Traditional Chinese steps, exactly one screenshot per step, concrete controls, observed results and failure actions; flow index and fictional practice source text.
- `docs/guides/images/bi-sop/`: 98 newly captured PNGs (1366 x 1000; 13,736,162 bytes). Every image was opened and visually read before copying into the public repository. Only fictional actors/companies/contacts, example email addresses and artificial phone numbers appear; no credential or token in images/address bars. No old screenshot reused, no UI image edited.
- Real isolated headless agent-browser sessions against two independent temporary Agent Web processes on this base; gateway `127.0.0.1:4000`, model `gpt-5.5`, credential supplied only through environment. Two probes returned in 2.0 and 1.5 seconds; no gateway hang observed. Installer workspace assets were installed and `local_owner_grants` retained its default true. No runtime, contract or feed-golden change.
- Covered new vault/domain/folders, two-file conversion and Markdown revision, schema suggestion and AI additive upgrade, Skill AI with five card types and manual v2, batch ingest and source-linked review/check marks, writes, commit via status line, manual/AI benchmark questions, AI dashboard creation/change and ordering, real benchmark, one-step share/date tag `2026-11-07`, second-PC join/cards/dashboard/questions, and chat citing that published version.
- Business-card photo attach/save for two people; same-email update without duplicate; interactive chart/tree/group/file viewer; explicit department/title/manager updates with evidenced line; F5 and actual same-tab reload work; new conversation reads two persisted contacts and their final values.
- Required guidance is explicit: AI 1–4 minutes, tool approval means reading/trusting code and guard is not a sandbox, same-tab F5/new-tab desktop shortcut, Telegram or file photo attachment with no page camera, everyone on same release.

## Actual failures and limits retained in the SOP

- CSV Signal candidate lacked required `so_what` (「所以呢」); rejected it through the GUI. Do not invent source evidence to fill a required field.
- AI first proposed a benchmark forbidding the source's actual six-month calibration period. Pointing to the original text made it correct its latest proposal; only the corrected pair was added.
- Benchmark `bibench-20261106T160502-2c89`: working 2/3, pre-publication shared version 0/3. Calibration question missed six months because the answer read SupplyLink and missed CustomerProduct body. Kept the correct must-include, real failed answer and screenshots; did not weaken the test or change runtime. Reported this to the orchestrator. The entirely fictional tutorial vault was shared with this known limitation explicitly in its purpose; SOP says resolve failed questions before formal sharing.
- Skill AI used its three-trial budget despite a one-trial request, then provided a usable rule; its limits are visible. Human review remains necessary.
- Two PCs are independent workspaces on one machine sharing a fictional local directory. This verifies joining/replay/content/version propagation, not actual OneDrive/SharePoint cloud transport. No Telegram phone interaction, fresh Windows installer execution or Atlas deployment tested. No full repository pytest suite rerun for this documentation-only change.

## Verification

Python: `C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/.venv/Scripts/python`; `PYTHONPATH=src` for tests.

- `python -m pytest tests/test_release_windows.py -q --basetemp C:/Temp/bi-sop-release-tests-73`: 8 passed; after final manuscript/images, rerun with `C:/Temp/bi-sop-release-final-73`: 8 passed in 1.22s.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: 1389 files already formatted.
- `python -m mypy`: no issues in 1047 source files.
- Also `ruff check src tests`, `ruff format --check src tests` (1093 files), `mypy src tests`: passed.
- `python -m build`: wheel and sdist built successfully.
- `python -m pip check`: no broken requirements.
- `git diff --check`: passed (only normal LF/CRLF working-copy notices).
- Documentation audit: 98 consecutive steps; 98 unique links match all public PNG filenames; every image 1366 x 1000 and byte-identical to its fresh reviewed capture; no unfinished text, credential patterns or actual gateway secret. Documentation-only final architecture review: no boundary/policy/runtime change.

## Cleanup and safety

Own servers were loopback ports 65031 and 65052 only. Before stopping, authenticated `/api/activity` on each reported idle with zero items. Both named browsers (`bi-sop-73-pc1`, `bi-sop-73-pc2`) closed. Both temporary server processes shut down normally (exit 0); ports no longer listening and private endpoint files removed. The owner's Agent Web and real vault were never used or restarted.

Private temporary fictional workspaces/captures remain outside the commit for audit. `.scratch` contains local-only automation/verification logs and is ignored; never publish its private bootstrap logs. New work should use a new temporary runtime, not restart or attach to the owner's server. No unfinished implementation remains in this branch.
