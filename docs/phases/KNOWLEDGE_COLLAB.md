# Knowledge collaboration: pull, benchmark, push (design)

Owner design, 2026-10-11. This design addresses the conflicts that come up when several
maintainers develop one knowledge vault together. It builds on K1 (sandboxes), K3.1
(vault-resident rules), K3.2 (section edits and the deletion guard) and K3.3–K3.4
(three-way merge, publish). Plan: `docs/phases/KNOWLEDGE_PIPELINE_RELEASE.zh-TW.md` 4.8.

## 1. The workflow

```
Pull → edit skills → Convert → Ingest → Benchmark → Push
```

A sandbox works like a git branch with a pull request:

| Git idea | Here |
|---|---|
| shared repository | the **project vault**: the shared folder the team maintains (for this project `OneDrive - Rohde & Schwarz/RS_Knowledge`) |
| branch / pull request | a **sandbox**: a private working copy, opened from the project vault at a known point |
| pull a subtree | **Pull** chosen `drop/` folders of the project vault into the sandbox |
| commit | Convert and Ingest inside the sandbox, after editing `CLAUDE.md` / `skills/` there if needed |
| CI | **Benchmark**: the question sets for the pulled scope, sandbox against project vault |
| merge | **Push**: a three-way merge into the project vault, recording who pushed and from which sandbox |

## 2. The project vault is configured, not fixed

- For this project the project vault is `RS_Knowledge`. Another project sets its own
  location; nothing is tied to this folder.
- host.json `knowledge_pipeline.vaults[]` gains per project:
  - `root`: the project vault, e.g. the OneDrive `RS_Knowledge` folder.
  - `drop_root`: where originals are collected. Default `<root>/drop`.
  - `questions_root`: the question sets. Default `<root>/checks/questions`.
  - `maintainers`: who may push (owner decision: co-developers may push). A person is
    identified by the Agent's actor. OneDrive's own sharing still decides who can write
    the folder at all.
- The Agent's query Knowledge stays a published, digest-checked local version (as
  today). After a push, "Refresh from the project vault" stages a new local version of
  it. The project vault itself is never served directly.

## 3. Pull: choose the scope by folder

- When opening a sandbox, the maintainer picks one or more folders under `drop_root` at
  any depth, for example `drop/Market/`, `drop/Market/AI/` or `drop/Productions/CMX500/`.
- The sandbox gets:
  - **The whole project vault's knowledge**: `wiki/`, `raw/`, `index.md`, `log.md`,
    `decisions.md`, `CLAUDE.md`, `skills/`, `checks/`. It also gets a `.base` snapshot for
    the merge. `drop/` is not copied.

    The wiki must be whole: ingest updates shared pages, such as a product or company page
    that a new market source mentions.
  - **Only the pulled originals**, copied to the sandbox's `drop/` with their folder path
    kept (`drop/Market/AI/x.pdf`). Keeping the first folder keeps the category rules
    (`skills/ingest-market` applies to `raw/Market`).

    An original whose content hash is already ingested in the project vault is skipped
    and listed as "already in the vault".
- The pulled folders are the sandbox's **scope**:
  - They are recorded in `sandbox.json` with the list of pulled files.
  - At merge, changes to pages outside the scope are marked proposals. This is the K3
    rule, with the scope taken from the pulled folders instead of a single matrix cell.
- Pull can be repeated in an open sandbox to bring in more folders or new originals.

## 4. Edit skills in the sandbox

- The sandbox's `CLAUDE.md` and `skills/*/SKILL.md` can be edited on the Knowledge page
  (an editor limited to those files) or in Obsidian.
- The next Convert and Ingest use the edited rules.
- Rule changes merge back with the pages at Push (K3, 195eb6c).

### Product lines under a category (owner question, 2026-10-11)

A category may have sub-folders with their own rules, for example the four product
lines under `Productions/`:
- `drop/Productions/VNA/` converts to `raw/Productions/VNA/`.
- `skills/ingest-vna/SKILL.md` declares `applies_to: raw/Productions/VNA`.
- **Rules layer from the general to the specific.** A VNA source gets `CLAUDE.md`,
  then `ingest-productions` (the rules every product line shares, such as never
  inventing an option code), then `ingest-vna` (only what is VNA-specific). Shared rules
  are written once, not copied into four skills.
- A product line's sandbox pulls only its folder. Its question sets are
  `productions/` (shared), `vna/`, and combinations such as `market_vna/`.
- Naming: the product-line folders should match the K2 index's four product
  categories, so index, question sets and ownership line up.
- People: one owner per product line (drop folder, skill, question set), one keeper of
  the shared `ingest-productions` (may be one of them), and a reviewer for shared pages
  (technical concepts, companies), whose changes arrive as proposals.

## 5. Benchmark: question sets by folder and folder combination

- The question format is the owner's existing one in `checks/questions/`:
  - one question per `.md` file;
  - `必須提到:` (must mention) and `不可以說:` (must not say) lists, checked by plain
    string matching;
  - an HTML comment explaining why the question exists.

  Grading is done by the program, not by a model. Missing an answer ("漏講") is the main
  failure it catches.
- Question sets follow the drop folders:
  - `checks/questions/market/` holds questions about Market;
  - `checks/questions/productions/` holds questions about Productions;
  - `checks/questions/market_productions/` holds questions that need both;
  - any combination of folder names joined by `_` is a set. There are as many sets as the
    team creates.
  - Questions directly under `checks/questions/` form the general set.
- Folder names match categories case-insensitively and singular or plural
  (`market` = `Market`, `production` = `Productions`). The order of the parts does not
  matter.
- By default a sandbox runs every set whose categories all fall inside its pulled scope;
  every folder of a pulled path counts (`Productions/VNA` gives `production` and `vna`).
  - Example: a sandbox that pulled Market and Productions runs `market/`,
    `productions/` and `market_productions/`.
  - The maintainer can add or remove sets before running, for example add the general
    set, to adjust the range under test.
- Each question is asked twice through the Knowledge Harness: once against the sandbox
  (loaded in process as a temporary Knowledge version, never written to host.json) and
  once against the project vault's current state.
- The result is a table per question: pass or fail on each side, with the missing
  must-mention terms and any forbidden phrase found.
  - A **regression** is a question that passes on the project vault and fails in the
    sandbox. It is listed first.
- Results are saved in the sandbox and become part of the push record.
- Benchmark runs write telemetry like the other benchmarks (contract v0.3), so Atlas can
  show them.

## 6. Push: merge into the project vault and record it

- **Who.** Any maintainer listed for the project may push; no second approval is needed
  (owner, 2026-10-11).
- **No lock: first push wins (owner, 2026-10-11).** Like git, nobody holds files while
  working. Whoever pushes first is merged. A later push is merged against the vault as
  it is then, and must pass the gate again.
- **Steps.**
  1. **Merge against the vault as it is now.** The K3.3 three-way merge runs with
     `.base` (where the sandbox started), the sandbox, and the project vault at push
     time. The result is a candidate in the sandbox area.
     - Two-sided edits of the same section are conflicts, resolved on the Knowledge page
       side by side.
     - Nothing is written while a conflict is open.
  2. **Benchmark gate on the merged result.** The selected question sets are run on the
     candidate and on the current project vault. The push is allowed only when both hold:
     - no question regresses (passes on the vault, fails on the candidate). A regression
       **blocks** the push (owner);
     - the candidate's score is not lower than the vault's.

     If the vault changed since the last benchmark, both are run again before pushing.
  3. **Compare and write.**
     - Right before writing, the vault's digest is compared with the one the merge used.
       If someone pushed in between, the push goes back to step 1 automatically.
     - The write then copies only the merged files into the vault, in place. The project
       vault is a folder people open in Obsidian, so no versioned copy is made.
     - Every file it overwrites is first copied to `.ingest-backup/<push id>/`. A push
       can be undone from that backup and the push record.
     - No lock is held while people work. The only exclusion is this compare-and-write,
       which takes seconds.
  4. **Check after writing.** Run lint and the sourced-line check: no line linking a
     source, and no ⚠️ line, from either side may be lost. Any finding is reported in the
     push record.
- **The push record.** One file per push in `pushes/<push id>.json`, plus a `log.md`
  entry `## [date] push | <sandbox label>`. It holds:
  - who pushed, the sandbox id and label, when the sandbox was opened and pushed;
  - the pulled folders and files;
  - the skill and schema files changed;
  - the pages added and changed, with any proposals marked;
  - conflicts and how each was resolved;
  - the benchmark sets run, with scores on both sides and regressions;
  - the backup location.
## 7. Why this answers the collaboration conflicts

| Conflict | Handled by |
|---|---|
| two people ingest into one vault at the same time | each works in a sandbox; the first push wins, a later push re-merges and must pass the gate again |
| A rewrites a shared page that B also changed | section-level edits (K3.2) and the per-section three-way merge (K3.3); only the same section edited on both sides conflicts |
| a rule change silently degrades another domain | benchmark sets by folder and combination; regressions shown before push |
| content lost by an over-eager rewrite | the sourced-line guard at ingest and again after the push |
| "who changed this and why?" | the push record and `log.md` entry; backups per push |
| OneDrive sync corrupting history | no git in the shared folder; backups and push records instead |

## 8. Changes from the current build

- Sandbox create: copy from the project vault without `drop/`, plus Pull. K3 copies the
  published local vault and has no pull.
- New: question sets by folder, the sandbox benchmark, the benchmark gate, in-place push with
  backups, push records, maintainers, and the per-project `drop_root` / `questions_root`.
- K3.4's publish of a versioned local copy becomes "Refresh from the project vault"
  for the Agent's query version.
- The Knowledge page follows the workflow (Pull → Skills → Convert → Ingest → Benchmark
  → Push). It includes the page improvements requested on 2026-10-11:
  - category-aware drop;
  - status next to the buttons;
  - Markdown preview of Raw, wiki and skill files, and of each plan's added lines;
  - the skill editor;
  - side-by-side conflicts;
  - layered index under "Advanced".

## 9. Slices

C1 project vault settings and Pull → C2 skill editor and Markdown preview → C3 question
sets and the sandbox benchmark → C4 benchmark gate, in-place compare-and-write push with backups and push
records → C5 Knowledge page in workflow order → C6 live trial with two sandboxes on
`RS_Knowledge` copies (never the real folder until the owner says so).

## 10. Owner decisions (2026-10-11)

1. A regression blocks the push.
2. No lock. The first push wins; a later push re-merges against the current vault and is
   allowed only when its merged result scores no lower than the vault and regresses no
   question. "Not lower" is the reading taken; "strictly higher" would block pushes that
   only add knowledge the questions do not ask about.
3. The first live pushes go to a copy of `RS_Knowledge`, not the real folder.
