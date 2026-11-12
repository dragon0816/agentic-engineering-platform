# Data Skills, Dashboards and Outlook: capability assessment

Date: 2026-11-12. Read-only assessment requested after package delivery. No
runtime/harness/permissions/settings changes, asset installation, real mailbox
reading or production data processing occurred.

## Version and evidence limits

Resident bundle source remains 044bd7b599df43716121720af23b7e1842ef2370;
delivered package runtime source is e69371e62ec2a01d31eead91f67ff9e4404a4254.
The assessed BI cards, BI Skill/analysis agents, mail-read capability, Outlook
reader, agent-mode and agent-mail source paths are identical between these refs
(git diff --quiet). Tests ran on the delivery worktree with its src explicitly
on PYTHONPATH, using the original repository Python environment.

These are existing deterministic fixture tests with scripted model responses;
they establish implemented contracts and tool paths, not arbitrary real-model
prompt success. No fresh novice-prompt/live-model end-to-end acceptance or real
Outlook thread reconciliation was performed. A colleague's own host was not
inspected.

## Data-processing Skills and Dashboards

Knowledge > BI cards has dedicated AI sessions:

- Rule creation/revision: bi_skill__suggest proposes source classification and
  extraction rules. It can inspect fictional/approved sources, trial draft rules
  without staging cards, compare results and evaluate extraction/answer effects.
- Processing programs: bi_skill__draft_tool proposes Python for sources a rule
  cannot read. bi_skill__try_tool refuses unapproved code; the person approves
  exact code before trials and separately saves it. This is distinct from an
  Agent Skill manifest whose commands bind existing capabilities/Workflows.
- Analysis and Dashboard: bi_analysis__sql/python explore working BI data;
  bi_analysis__propose_dashboard validates analyses/chart columns and layout,
  returns previews, and stages analyses/layout only after the person's Apply.
  Dashboard renders saved analyses; tables/bar/line/scatter and parameters exist.
- General Ask can query published BI data and attach charts, and propose a
  saved SQL analysis for approval. The complete multi-analysis Dashboard tool
  is supplied by the dedicated analysis AI session. These entry points are
  not evidence that arbitrary Excel + one general Ask prompt automatically
  creates and validates a reusable Skill and Dashboard without further setup.

Useful novice prompts for a later live acceptance:

- Rule AI: "這份來源的日期與金額請統一格式，缺值保留並標記，整理成可重用規則。"
- Analysis AI: "幫我做每月銷售額、業務排名與部門占比的 Dashboard，缺資料請先問我。"

Prerequisites remain a selected BI knowledge base/schema/data and an eligible
configured model. Only required missing business information should be asked.
Repeated deterministic transformations belong in a Workflow; Skills guide its
selection/procedure. No general-purpose Excel portability claim was verified.

Documentation gap: BI_BUILD.zh-TW.md currently says the AI cannot write a
processing program, while bi_skill_agent.py and its tests implement draft_tool
and approved trials. The guide is stale at this point; no shipped package or
runtime was silently changed as part of this assessment.

## Outlook: implemented versus available to a conversation

1. outlook/draft@1.0.0 is present in the live authoring capability catalog.
   SDE weekly report uses draft creation; it does not prove mailbox search/read
   is registered for the same model conversation.
2. integrations/outlook_mail.py implements read-only search/read via desktop
   Outlook COM/pywin32, enforcing the configured folders/date/exclusion scope.
   Agent mode exposes outlook_search/outlook_read, with conversation approval.
3. Host registration of outlook/search@1.0.0 and outlook/read@1.0.0 is conditional
   on asset usage (host.py). The live catalog does not list them; a direct
   aep_capability lookup returned capability_unknown. Read-only check-skill
   probes binding each returned "capability ... is not installed". Initial
   probe aliases used hyphens and were rejected; corrected underscore aliases
   reached the capability checks. No draft was submitted or installed.
4. Current resident agent-mode settings: Claude Code/Copilot/Codex flags all
   false; mail scope 180 days, one allowed folder, Sent Items not allowed.
   These are this PC's settings, not a diagnosis of the colleague's PC.
5. Agent-mode tools and general Gateway-installed capabilities are separate
   exposure paths. This explains how draft generation can work while a model
   reports it has no read-mail tool. Procedure text alone cannot bind an absent
   capability. Investigate normal asset/setup options first; any routing/tool
   registration harness edit still needs the owner's separately scoped consent.

## Mail thread analysis boundary

Models can summarize multiple retrieved related messages: chronology, decisions,
open questions, owners and actions. The current reader exposes individual
message IDs, not ConversationID/ConversationIndex or a whole-thread retrieval
operation. Search is keyword/sender/snippet based with up to 50 returned results
and a bounded per-folder scan, under the person's date/folder scope. Read bodies
are capped at 20,000 characters. Sent replies, older messages, other folders or
cut results can be missing; subject matching alone cannot prove complete thread
membership. Therefore complete-thread analysis is not yet accepted as reliable.

A later acceptance should use a known fictional conversation split across Inbox
and Sent Items, prove membership/counts/time order and truncation reporting, then
check the summary against the source. Missing scope or missing messages must be
reported, never represented as a complete conversation. No live email was read
to perform this assessment.

## Exact focused checks

- Data/BI: test_bi_skill_agent, test_bi_dashboard_proposal, test_bi_analyses,
  test_bi_board, test_bi_chat_sql, test_bi_chat_charts, test_bi_chat_save:
  47 passed in102.68s.
- Outlook: test_agent_mail, test_outlook_mail_folders, test_outlook_com_threads,
  test_mail_draft_capability:28 passed,2 skipped in23.73s.
  The two live mailbox tests deliberately require AEP_OUTLOOK_TESTS=1;
  this run used0 and AEP_GUI_TESTS=0. No assertion was changed.
- Logs/JUnit: .scratch/data-dashboard-assessment/focused.log/focused.xml and
  outlook.log/outlook.xml. Total75 passed,2 skipped; all subprocesses completed.

No new feature, live-model success, complete-mail-thread guarantee or Knowledge
quality change is claimed. Next work would be a separately scoped novice-flow
acceptance and mail-tool availability repair, using Skills/assets first and
requesting consent before any necessary harness edit.
