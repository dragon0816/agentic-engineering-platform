"""The two personal spaces the Memory Service itself provides (accumulated memory M3).

`personal/preferences` (§5) and `personal/notes` (§3.9) belong to no Skill:
the Host manages them (`host/memory`), so no installed Skill or Workflow can
declare itself their manager. A Skill or Workflow that wants to read the
person's notes declares `{"space": "personal/notes", "role": "reader"}` in
its `memory_spaces` (the business-cards Skill does, for the 「相關筆記」 of a
person card on the org chart). Preferences are read only by the Host, which
injects them into a turn; nobody declares them.

Only the person's press writes either space: a model has no tool that saves
a preference or a note (owner 2026-10-20, §10.3 and §10.8).
"""

from __future__ import annotations

from collections.abc import Sequence

from common.memory import MemorySpaceDeclaration, MergeRules
from memory.registry import AssetKey

#: The Host's own asset key for the spaces it manages.
HOST_MEMORY: AssetKey = ("host", "memory")
PREFERENCES_SPACE = "personal/preferences"
NOTES_SPACE = "personal/notes"

#: Every entry comes from the person (`user`); an Agent's proposal the
#: person saved is still theirs, kept as `user` with the proposal noted.
PREFERENCES_RULES = MergeRules(
    rules_id="personal.preferences.v1", trust={"user": "user_stated", "agent": "inferred"}
)
NOTES_RULES = MergeRules(
    rules_id="personal.notes.v1", trust={"user": "user_stated", "agent": "inferred"}
)

PREFERENCES_DECLARATION = MemorySpaceDeclaration(
    space=PREFERENCES_SPACE,
    role="manager",
    kinds=("preferences",),
    sensitivity="CONFIDENTIAL",
    retention="until_deleted",
    schema_ref="personal.preference.v1",
    merge_rules=PREFERENCES_RULES.rules_id,
)
NOTES_DECLARATION = MemorySpaceDeclaration(
    space=NOTES_SPACE,
    role="manager",
    kinds=("notes",),
    sensitivity="CONFIDENTIAL",
    retention="until_deleted",
    schema_ref="personal.note.v1",
    merge_rules=NOTES_RULES.rules_id,
)
#: What a Skill or Workflow declares to read the person's notes.
NOTES_READ = MemorySpaceDeclaration(space=NOTES_SPACE, role="reader")

RULES: tuple[MergeRules, ...] = (PREFERENCES_RULES, NOTES_RULES)
#: Declared before any manifest, so the Host keeps these spaces.
HOST_DECLARED: tuple[tuple[AssetKey, Sequence[MemorySpaceDeclaration]], ...] = (
    (HOST_MEMORY, (PREFERENCES_DECLARATION, NOTES_DECLARATION)),
)


def reads_notes(declarations: Sequence[MemorySpaceDeclaration]) -> bool:
    """Whether a manifest's `memory_spaces` declare a read of the notes."""
    return any(item.space == NOTES_SPACE for item in declarations)
