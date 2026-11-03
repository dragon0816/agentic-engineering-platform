"""A profile's field proposal into the schema (`docs/phases/BI_CARD_MODEL.md` §4.3).

A new name is compatible: the reviewer's confirmation merges it into a new schema
version, through the same drafts, diff and upgrade as any schema change, with no
second step. The same name with another definition stops as `schema_conflict` for
a person. Either way the schema's `used_by` records the home, and the profile gets
a new revision saying what became of the proposal. Two PCs merging at once conflict
on the `schema` unit, as any two schema changes do.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards import profile, schema_versions, vault
from capabilities.bi_cards.schema import Registry
from capabilities.bi_cards.store import BiStoreError
from knowledge.repo import skills as repo_skills

#: What may differ between two definitions of one field and still be the same field.
_WORDING = {"name", "label", "used_by"}


def _field_of(document: Mapping[str, Any], type_name: str, name: str) -> dict[str, Any] | None:
    for entity in document.get("types") or []:
        if entity.get("name") == type_name:
            return next((f for f in entity.get("fields") or [] if f.get("name") == name), None)
    return None


def _merged(
    document: dict[str, Any], proposal: Mapping[str, Any], home: str
) -> dict[str, Any] | None:
    """`document` with the proposal's field; None when it already says all of it."""
    existing = _field_of(document, proposal["type"], proposal["field"])
    definition = proposal["definition"]
    if existing is None:
        for entity in document["types"]:
            if entity.get("name") == proposal["type"]:
                entity["fields"].append(
                    {**definition, "name": proposal["field"], "used_by": [home]}
                )
        return document
    differs = sorted(
        key
        for key, value in definition.items()
        if key not in _WORDING and existing.get(key) != value
    )
    if differs:
        raise BiStoreError(
            "schema_conflict",
            f"schema 已經有 {proposal['type']}.{proposal['field']}，定義不同"
            f"（{'、'.join(differs)}）；要由人決定",
            type=proposal["type"],
            field=proposal["field"],
            differs=differs,
        )
    used_by = list(existing.get("used_by") or [])
    if home in used_by:
        return None
    existing["used_by"] = sorted([*used_by, home])
    return document


def _upgrade(
    workspace: Path, target: vault.Vault, current: Registry, document: dict[str, Any], actor: str
) -> Registry:
    """The reviewed document as the vault's next schema version."""
    made = schema_versions.create_draft(workspace, current.ref, "profile 欄位", actor)
    draft_id = made["draft"]["id"]
    document = {**document, "version": made["document"]["version"]}
    saved = schema_versions.save_revision(
        workspace,
        draft_id,
        document=document,
        json_text=None,
        note="合併 profile 提出的欄位",
        source="edit",
        actor=actor,
    )
    ref = schema_versions.publish(workspace, draft_id, saved["revision"], actor)["ref"]
    preview = schema_versions.upgrade_preview(workspace, target.dataset, ref)
    schema_versions.upgrade_apply(workspace, target.dataset, ref, preview["preview_token"], actor)
    return target._registry()


def decide(workspace: Path, vault_id: str, given: Mapping[str, Any], actor: str) -> dict[str, Any]:
    """A person's decision on a proposal: `{home, type, field, decision, confirm}`,
    `decision` being `merge` or `reject`."""
    if given.get("confirm") is not True:
        raise BiStoreError("confirm_required", "合併欄位要由人按確認")
    decision = given.get("decision")
    if decision not in ("merge", "reject"):
        raise BiStoreError("decision_invalid", "decision 必須是 merge 或 reject")
    target = vault._vault(workspace, vault_id)
    home = str(given.get("home") or "")
    with target.lock:
        document = profile.read(target.repo, home, target.repo.working_units())
    proposals = (document or {}).get("proposals") or []
    proposal = next(
        (
            p
            for p in proposals
            if p["type"] == given.get("type")
            and p["field"] == given.get("field")
            and p["status"] == profile.PROPOSED
        ),
        None,
    )
    if document is None or proposal is None:
        raise BiStoreError("proposal_unknown", "這個 profile 沒有這個待審的欄位提議")
    reg = target._registry()
    if decision == "reject":
        proposal["status"] = profile.REJECTED
    else:
        _, base = schema_versions.base_document(workspace, reg.ref)
        changed = _merged(base, proposal, home)
        if changed is not None:
            reg = _upgrade(workspace, target, reg, changed, actor)
        proposal["status"] = profile.MERGED
        view = document.setdefault("types", {}).setdefault(proposal["type"], {"fields": {}})
        view["fields"].setdefault(proposal["field"], {"use": "optional"})
    with target.lock, vault._repo_errors():
        value = profile.stage(target.repo, home, document, reg)
        units = target.repo.working_units()
        waiting = [
            s["name"] for s in repo_skills.current_skills(target.repo, units) if s["needs_update"]
        ]
    return {
        "profile": {"home": home, **value},
        "schema": reg.ref,
        "skills_need_update": waiting,
        "status": target.status(),
    }
