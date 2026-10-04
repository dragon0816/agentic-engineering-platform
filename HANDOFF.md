# Handoff

Date: 2026-10-04 (Asia/Taipei). Branch: main. Current task: make Agent Web Ask replies readable by rendering Markdown locally; continue the evidence-first product/market Knowledge work after the owner reviews the new UI.

## Latest completed slice

- Ask now renders headings, paragraphs, ordered/unordered lists, blockquotes, inline/fenced code, absolute HTTP(S)/mailto links, and GFM-style tables. Wide tables scroll horizontally. The same renderer is used for a new reply and for previously saved conversation messages.
- The renderer constructs only known DOM elements and text nodes. Model-supplied HTML stays text, javascript/data/file links do not become anchors, and no CDN or new dependency is required. The API and stored conversation messages remain plain text. The decision is recorded in docs/DECISIONS.md.
- Focused tests passed: browser script syntax, Markdown DOM behavior/security, and Ask composer structure (3 passed). Ruff on touched source/tests, mypy on the touched source and git diff --check passed. A synthetic matrix answer was rendered in headless Edge and visually inspected at ignored .scratch/markdown-render-preview.png. Per the owner's latest preference, full test/lint/type/build verification is deferred to the merge checkpoint.
- The already installed project Web was restarted on 127.0.0.1:53582 with the owner's existing User-scope credentials. At verification time the launcher PID was 61632 and listening Python child PID was 50056. A fresh local token URL was opened in the Codex browser pane. Real HTTP checks returned 200, confirmed the new renderer is served, and returned a 25-cell Knowledge matrix with status answered; the temporary test conversation was deleted. Confirm process identity before any later restart.
- The temporary startup output file in ignored .scratch/agent-web-53582-20261004-092559.stdout contains the current local URL and is ACL-restricted to RSINT/CHI_L, SYSTEM and Administrators. It is locked while the Web process runs; remove it after that process stops. The previous startup output was removed when the prior process stopped. Never commit or print local Web tokens.

## Relevant prior state

- The Knowledge matrix capability and Skill were committed as 4ecf4b9. The Vault-wide Raw scan returned 25 cells, 15 nearby lexical mentions and 10 separate-passage leads. These are discovery leads, never verified product/option suitability. A local ignored report is at .scratch/rs-product-market-matrix-2026-10-04.md; it may contain source markings and must not be committed.
- The Host startup diagnostic fix was committed as 301c20d. The owner's intermittent knowledge_invalid refusal was not reproduced once the Vault and published manifest were checked with the real User-scope LiteLLM credential. The stale portable Web process had also been occupying port 53582; it was stopped before the project Web was started.
- The six-layer harness inventory is in docs/HARNESS_6_LAYER_STATUS.md. The immediate Knowledge gap remains explicit evidence sufficiency, bounded re-retrieval and an independent final-claim check for one selected product/market cell.

## Next action

- Ask the owner to inspect the currently running Ask page; no new command, credential reset or second Web process is needed. If the browser shows an old tab, use the newly opened tab because each Web restart issues a new local token.
- After the owner chooses one matrix cell, validate its application, standard, product/option specifications and customer evidence before drafting a strategy recommendation. Full verification of the current UI slice can run at the owner-requested merge checkpoint.
