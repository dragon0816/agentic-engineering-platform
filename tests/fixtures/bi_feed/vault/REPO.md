# Feed Fixture Market (fictional)

虛構資料：BI analysis feed 的契約測試

- Type: `bi`
- Repository id: `feed-fixture`

This folder is maintained through AEP. Nobody edits or deletes a file here; every file is added once by its author. This page is generated: do not edit it.

## Schema in use

- Version: `bi.schema/v1.1@2.0.0`
- File: `schemas/bi.schema__v1.1@2.0.0.json`
- Readable description: `schemas/bi.schema__v1.1@2.0.0.md`

## Skills in use

| Skill | Revision | Role | Applies to | Schema | State |
|---|---|---|---|---|---|
| `classify` | 1 | classify | every source | `bi.schema/v1.1@2.0.0` | ok |

## Versions

- Published: tag `v1` (by fixture)
- The maintenance head is 2 commit(s) ahead of it.
- Tags: `v1`

| Date | Author | Purpose |
|---|---|---|
| 2026-11-01 | fixture | 發佈之後的修改（不在 feed 裡） |
| 2026-11-01 | fixture | 匯入 account.csv：1 張卡、3 個欄位 |
| 2026-11-01 | fixture | 加上三個分析與 Dashboard 順序 |
| 2026-11-01 | fixture | 匯入 technology.csv：9 張卡、36 個欄位 |
| 2026-11-01 | fixture | 匯入 testsolution.csv：5 張卡、15 個欄位 |

## How to maintain

- **New sources.** Add them under `sources/<folder>/` through AEP.
- **Add a field or a type.** Upgrade the schema with Session A (a new version), then update every skill listed as needing an update.
- **Change a rule.** Edit the skill in AEP; it is saved as a new revision and committed.
- **Share your work.** Commit with its purpose, then push.
- **Release.** Tag the version and publish it (one person confirms); the Agent reads the published version.
- **Undo.** Revert to an earlier tag or commit; history is kept.
