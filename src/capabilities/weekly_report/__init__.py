"""Workflow 7: the GTM weekly report, from Jira into the team's workbook.

Ported from the pinned `rs_workflow_system` job `jira_weekly_report` and its
pure rules module (`docs/PHASE_7_MIGRATION.md`, "Workflow 7"). The rules
stay pure; the fetch is a capability over the platform's transport; the plan
is a contract that is also the dry-run preview and the evidence.
"""
