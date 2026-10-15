"""Where an accepted review proposal goes (experience review E3, owner 2026-10-13).

- `rule_edit` naming a vault rule (`skills/<name>/SKILL.md`): a review sandbox scoped
  to that rule's folder, holding the proposal; the Knowledge page opens the rule with
  the proposal added as an unsaved edit, so the owner compares, edits, benchmarks
  and pushes as usual.
- `test_question`: a review sandbox with a draft question in
  `checks/questions/<folder>/`, its must-mention terms left for the expert.
- `knowledge_gap`: the gap list, for the domain owner to add sources.
- `issue`, or a rule that is not a vault rule: an issue note to follow up by hand.

Nothing is written to a project vault here: a sandbox reaches it only by a push.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from host_runtime.experience_proposals import ReviewProposal
from knowledge.schema import front_fields

PROPOSAL_FILE = ".review-proposal.json"
_SKILL_NAME = re.compile(r"(?:skills/)?([A-Za-z0-9][A-Za-z0-9._-]*)(?:/SKILL\.md)?")


class RuleTarget:
    def __init__(self, base: str, path: str, scope: str | None) -> None:
        self.base, self.path, self.scope = base, path, scope


def _folders(root: Path) -> list[str]:
    found: set[str] = set()
    for area in ("drop", "raw"):
        folder = root / area
        if folder.is_dir():
            found.update(
                p.name for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")
            )
    return sorted(found)


def _scope_of(root: Path, rel: str) -> str | None:
    fields = front_fields((root / rel).read_text(encoding="utf-8", errors="ignore"))
    applies = fields.get("applies_to", "").strip().strip("/")
    if applies.startswith("raw/"):
        folder = applies[len("raw/") :]
        # The same folders a sandbox may be scoped to: collected (drop) or converted (raw).
        if (root / "drop" / folder).is_dir() or (root / "raw" / folder).is_dir():
            return folder
    name = (fields.get("name") or rel.split("/")[1]).casefold()
    return next(
        (f for f in _folders(root) if name in (f"ask-{f.casefold()}", f"ingest-{f.casefold()}")),
        None,
    )


def resolve_rule(target: str, bases: dict[str, Path]) -> RuleTarget | None:
    """The vault rule file a proposal's target names, in the first project
    vault that has it."""
    names = [m.group(1) for m in _SKILL_NAME.finditer(target)]
    for base, root in bases.items():
        for name in names:
            rel = f"skills/{name}/SKILL.md"
            if (root / rel).is_file():
                return RuleTarget(base, rel, _scope_of(root, rel))
    return None


def question_folder(target: str, root: Path) -> str | None:
    """The category folder a test question belongs to, if the target names one."""
    lowered = target.casefold()
    return next((f for f in _folders(root) if f.casefold() in lowered), None)


def draft_question(proposal: ReviewProposal) -> str:
    """A question file whose terms an expert fills in; never invented here."""
    question = " ".join(proposal.text.split()) or "(question)"
    return (
        f"---\nname: review-{proposal.proposal_id}\nasked_by: （待指定）\n---\n\n"
        f"# {question}\n\n必須提到:\n  - （請專家填寫）\n\n不可以說:\n\n"
        f"<!--\nFrom experience review {proposal.review_id}: {proposal.diagnosis}\n"
        "The must-mention terms are left for an expert; a question without terms is\n"
        "listed as not graded and does not count in the benchmark until filled in.\n-->\n"
    )


def write_proposal(sandbox_root: Path, proposal: ReviewProposal, path: str) -> None:
    (sandbox_root / PROPOSAL_FILE).write_text(
        json.dumps(
            {
                "proposal_id": proposal.proposal_id,
                "kind": proposal.kind,
                "path": path,
                "text": proposal.text,
                "diagnosis": proposal.diagnosis,
                "confirm": proposal.confirm,
                "cause": proposal.cause,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


def read_proposal(sandbox_root: Path) -> dict[str, Any] | None:
    path = sandbox_root / PROPOSAL_FILE
    if not path.is_file():
        return None
    try:
        loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded
