# Hermes skill pack: sources and licenses

These skills are ported from the Hermes agent's skills folder
(`<category>/<name>/SKILL.md` and supporting files) by
`scripts/port_hermes_skills.py`. Each keeps its original license and
authors, listed below; the license text a skill ships with (`LICENSE` in
its folder) is kept with it. The MIT License grants permission to use, copy,
modify and distribute the software provided the copyright notice and
permission notice are included; the frontmatter `author` and `license`
fields of every `SKILL.md` are kept unchanged for that reason.

`business-cards` is an internal skill of this platform's owner, shared
with colleagues after the scrub recorded in `pack.json` (no owner name,
data path or delivery command); it is for use inside the company only.

Every skill installs switched off. Changes made in the port are listed
per skill in `pack.json` (`adaptations`).

| Skill | Hermes source | Version | License | Authors |
|---|---|---|---|---|
| hermes-claude-code | autonomous-ai-agents/claude-code | 2.2.1 | MIT | Hermes Agent + Teknium |
| hermes-codex | autonomous-ai-agents/codex | 1.0.1 | MIT | Hermes Agent |
| hermes-computer-use | autonomous-ai-agents/computer-use | 2.1.0 | MIT | Francesco Bonacci (f-trycua), Hermes Agent |
| hermes-opencode | autonomous-ai-agents/opencode | 1.2.0 | MIT | Hermes Agent |
| hermes-architecture-diagram | creative/architecture-diagram | 1.0.0 | MIT | Cocoon AI (hello@cocoon-ai.com), ported by Hermes Agent |
| hermes-ascii-video | creative/ascii-video | 1.0.0 | MIT | SHL0MS, Hermes Agent |
| hermes-baoyu-infographic | creative/baoyu-infographic | 1.56.1 | MIT | 宝玉 (JimLiu) |
| hermes-claude-design | creative/claude-design | 1.1.0 | MIT | BadTechBandit |
| hermes-design-md | creative/design-md | 1.1.0 | MIT | Hermes Agent |
| hermes-humanizer | creative/humanizer | 2.5.1 | MIT | Siqi Chen (@blader, https://github.com/blader/humanizer), ported by Hermes Agent |
| hermes-manim-video | creative/manim-video | 1.0.0 | MIT | SHL0MS, Hermes Agent |
| hermes-p5js | creative/p5js | 1.0.0 | MIT | SHL0MS, Hermes Agent |
| hermes-popular-web-designs | creative/popular-web-designs | 1.0.0 | MIT | Hermes Agent + Teknium (design systems sourced from VoltAgent/awesome-design-md) |
| hermes-songwriting-and-ai-music | creative/songwriting-and-ai-music | 1.0.0 | MIT | Teknium (teknium1), Hermes Agent |
| hermes-sdlc-review | devops/sdlc-review | 1.1.0 | MIT | Jakub Wolniewicz (@frizikk) + Hermes Agent |
| hermes-email-inbox-triage | email/email-inbox-triage | 0.2.0 | MIT | Ben Barclay (benbarclay), Hermes Agent |
| hermes-himalaya | email/himalaya | 1.1.0 | MIT | community |
| hermes-gif-search | media/gif-search | 1.1.0 | MIT | Hermes Agent |
| hermes-songsee | media/songsee | 1.0.0 | MIT | community |
| hermes-youtube-content | media/youtube-content | 1.0.0 | MIT | Teknium (teknium1), Hermes Agent |
| hermes-obsidian | note-taking/obsidian | 1.0.0 | MIT | Teknium (teknium1), Hermes Agent |
| hermes-airtable | productivity/airtable | 1.1.0 | MIT | community |
| hermes-box | productivity/box | 1.0.0 | MIT | Chris Kim (iskysun96), Hermes Agent |
| hermes-business-cards | productivity/business-cards | 1.0.0 | Internal use | AEP (from an internal Hermes skill) |
| hermes-document-to-action-items | productivity/document-to-action-items | 0.1.0 | MIT | Ben Barclay (benbarclay), Hermes Agent |
| hermes-docx | productivity/docx | 1.1.0 | MIT | Nous Research |
| hermes-google-workspace | productivity/google-workspace | 1.2.0 | MIT | Nous Research |
| hermes-maps | productivity/maps | 1.2.0 | MIT | Mibayy |
| hermes-meeting-action-items | productivity/meeting-action-items | 0.1.0 | MIT | Ben Barclay (benbarclay), Hermes Agent |
| hermes-notion | productivity/notion | 2.0.0 | MIT | community |
| hermes-pdf | productivity/pdf | 1.1.0 | MIT | Nous Research |
| hermes-powerpoint | productivity/powerpoint | 1.1.0 | MIT | Nous Research |
| hermes-product-price-monitor | productivity/product-price-monitor | 0.1.0 | MIT | Ben Barclay (benbarclay), Hermes Agent |
| hermes-teams-meeting-pipeline | productivity/teams-meeting-pipeline | 1.1.0 | MIT | Hermes Agent + Teknium |
| hermes-weekly-review-planning | productivity/weekly-review-planning | 0.1.0 | MIT | Ben Barclay (benbarclay), Hermes Agent |
| hermes-xlsx | productivity/xlsx | 1.1.0 | MIT | Nous Research |
| hermes-arxiv | research/arxiv | 1.0.0 | MIT | Hermes Agent |
| hermes-competitor-news-monitor | research/competitor-news-monitor | 0.1.0 | MIT | Ben Barclay (benbarclay), Hermes Agent |
| hermes-grounded-citations | research/grounded-citations | 1.2.0 | MIT | Hermes Agent + Teknium |
| hermes-llm-wiki | research/llm-wiki | 2.1.0 | MIT | Hermes Agent |
| hermes-codebase-inspection | software-development/codebase-inspection | 1.0.0 | MIT | Hermes Agent |
| hermes-dogfood | software-development/dogfood | 1.0.0 | MIT | Teknium (teknium1), Hermes Agent |
| hermes-github | software-development/github | 2.0.0 | MIT | Ben Barclay (benbarclay), Hermes Agent |
| hermes-node-inspect-debugger | software-development/node-inspect-debugger | 1.0.0 | MIT | Hermes Agent |
| hermes-requesting-code-review | software-development/requesting-code-review | 2.1.0 | MIT | Hermes Agent (adapted from obra/superpowers + MorAlekss) |
| hermes-simplify-code | software-development/simplify-code | 1.1.0 | MIT | Hermes Agent (inspired by Claude Code /simplify) |
| hermes-spike | software-development/spike | 1.0.0 | MIT | Hermes Agent (adapted from gsd-build/get-shit-done) |
| hermes-systematic-debugging | software-development/systematic-debugging | 1.1.0 | MIT | Hermes Agent (adapted from obra/superpowers) |
| hermes-test-driven-development | software-development/test-driven-development | 1.1.0 | MIT | Hermes Agent (adapted from obra/superpowers) |
| hermes-ui-ux-pro-max | ui-ux-pro-max | 1.0.0 | MIT | nextlevelbuilder (https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) |
| hermes-blocked-page-recovery | web/blocked-page-recovery | 1.0.0 | MIT | Hermes Agent |
