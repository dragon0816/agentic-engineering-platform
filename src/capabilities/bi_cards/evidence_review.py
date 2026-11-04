"""Evidence review: a person's judgement of one reference, on a card or a relation.

Design: `docs/phases/BI_CARD_MODEL.md` §5.4, proposal §6.1 B and E. A review is a note
on the correction path (`correction.py`): a small Markdown source read with no model,
going source → preview → confirm → commit. It never writes a field: a value that turns
out wrong is a correction note of its own. Levels are words, with no numeric weight.

The judgement lands on the evidence row (a card) or the `relation_evidence` unit (a
relation) as `assessment`: `{"system": {"reason"}, "current": {...}, "history": [...]}`.
`history` keeps the reviewer, time, reason and values before and after of every review,
so the first `before` is what the model said.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from capabilities.bi_cards import card_model, correction, vault
from capabilities.bi_cards.page_import import Page, parse_page
from capabilities.bi_cards.schema import parse_date
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore, BiStoreError, now
from knowledge.repo import repository as repo_engine

BAD_NOTE = frozenset(
    {
        "review_vault_only",
        "review_invalid",
        "reason_required",
        "base_version_missing",
        "reference_unknown",
        "relation_unknown",
    }
)
MAX_SCOPE = 300
#: A relation reviewed with no reference at all links to this, so its reviews gather.
NO_REFERENCE_SOURCE = "relation-review"
VERDICT_STATUS = {"accepted": "confirmed", "pending": "pending", "rejected": "rejected"}
STATUS_VERDICT = {"confirmed": "accepted", "rejected": "rejected"}
ALLOWED = {
    "stance": card_model.STANCES,
    "directness": card_model.DIRECTNESS,
    "same_source": card_model.SAME_SOURCE,
    "verdict": card_model.VERDICTS,
}
JUDGED = ("stance", "directness", "scope", "date", "same_source", "verdict")


@dataclass(frozen=True)
class Review:
    target: str
    card_id: str
    field: str
    relation: str
    reference_id: str
    #: Only what the note says; the rest stays as it was.
    said: dict[str, str]
    reason: str
    author: str
    page: Page


def _judged(
    item: dict[str, Any], stance: Any, date: Any, verdict: str | None = None
) -> dict[str, Any]:
    """A reference's judgement now, from its row or unit. Nothing judged yet is
    `unknown`, and a verdict nobody gave is `pending`."""
    current = (item.get("assessment") or {}).get("current") or {}
    return {
        "stance": stance or card_model.SUPPORTS,
        "directness": current.get("directness") or card_model.UNKNOWN,
        "scope": current.get("scope") or "",
        "date": date or "",
        "same_source": current.get("same_source") or card_model.UNKNOWN,
        "verdict": verdict or current.get("verdict") or "pending",
    }


def render(given: dict[str, Any], reason: str, author: str, at: str) -> str:
    """The note `read` reads back."""
    target = str(given.get("target") or "")
    lines = ["---", correction._line("review", target)]
    for key in ("card", "field", "relation", "reference_id"):
        if given.get(key):
            lines.append(correction._line(key, str(given[key])))
    for key in JUDGED:
        if given.get(key) not in (None, ""):
            lines.append(correction._line(key, str(given[key])))
    lines += [
        correction._line("reason", reason),
        correction._line("author", author),
        correction._line("at", at),
        "---",
        "",
        "# 證據覆核",
        "",
        *reason.splitlines(),
        "",
    ]
    return "\n".join(lines)


def read(text: Any) -> Review:
    page = parse_page("review.md", text if isinstance(text, str) else "")
    if page.problems:
        raise BiStoreError("review_invalid", page.problems[0]["message"])

    def said(key: str) -> str:
        return str(correction._given(page, key) or "").strip()

    target = said("review")
    if target not in ("card", "relation"):
        raise BiStoreError("review_invalid", "覆核單要說明是卡片或關係的證據")
    if not said("card") or (target == "card" and not (said("field") and said("reference_id"))):
        raise BiStoreError("review_invalid", "卡片的覆核單要有 card、field 和 reference_id")
    if target == "relation" and not said("relation"):
        raise BiStoreError("review_invalid", "關係的覆核單要有 relation")
    judged = {key: said(key) for key in JUDGED if said(key)}
    for key, allowed in ALLOWED.items():
        if key in judged and judged[key] not in allowed:
            raise BiStoreError("review_invalid", f"{key} 只能是 {'、'.join(allowed)}")
    if "verdict" not in judged:
        raise BiStoreError("review_invalid", "要選採信、待確認或不採信")
    if len(judged.get("scope", "")) > MAX_SCOPE:
        raise BiStoreError("review_invalid", f"適用範圍最多 {MAX_SCOPE} 字")
    if "date" in judged:
        date = parse_date(judged["date"])
        if date is None:
            raise BiStoreError("review_invalid", f"看不懂日期「{judged['date']}」")
        judged["date"] = date
    reason = said("reason")
    if not reason:
        raise BiStoreError("reason_required", "覆核必須寫理由")
    return Review(
        target=target,
        card_id=said("card"),
        field=said("field"),
        relation=said("relation"),
        reference_id=said("reference_id"),
        said=judged,
        reason=reason,
        author=said("author"),
        page=page,
    )


def _row(store: BiStore, review: Review) -> dict[str, Any]:
    for item in store.evidence(review.card_id):
        if item["field"] == review.field and item["reference_id"] == review.reference_id:
            return item
    raise BiStoreError("reference_unknown", "這張卡片的這個欄位沒有這筆出處")


def _relation_link(
    store: BiStore, review: Review
) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
    """The relation, the reference, the card it rests on, and its link unit (or {})."""
    relation = store.relation_row(review.relation)
    if relation is None:
        raise BiStoreError("relation_unknown", "找不到這條關係")
    reference = review.reference_id or card_model.reference_id(
        NO_REFERENCE_SOURCE, {"relation": review.relation}
    )
    basis = review.card_id
    assert store.vault_id is not None
    link = card_model.evidence_link_id(review.relation, basis, reference)
    units = vault.Vault(store.workspace, store.vault_id).repo.working_units()
    return (
        relation,
        reference,
        basis,
        units.get(f"{card_model.RELATION_EVIDENCE_PREFIX}{link}") or {},
    )


def _before(store: BiStore, review: Review) -> tuple[str, dict[str, Any]]:
    """What the review is on, in words, and its judgement now."""
    if review.target == "card":
        item = _row(store, review)
        dated = None if item["reference_time_basis"] else item["reference_at"]
        return f"{review.field}：{item['excerpt']}", _judged(item, item["stance"], dated)
    relation, reference, _, unit = _relation_link(store, review)
    stance = unit.get("stance")
    if stance is None:
        stance = next(
            (r["stance"] for r in store.relation_references(review.relation)
             if r["reference_id"] == reference),
            None,
        )  # fmt: skip
    verdict = STATUS_VERDICT.get(str(relation["status"]), "pending")
    date = ((unit.get("assessment") or {}).get("current") or {}).get("date")
    statement = (
        f"{relation['relation_type']}（{relation['from_card_id']} → {relation['to_card_id']}）"
    )
    return statement, _judged(unit, stance, date, verdict)


def _usable(store: BiStore, review: Review) -> None:
    if store.card(review.card_id) is None:
        raise BiStoreError("card_unknown", "找不到這張卡片")


def preview(store: BiStore, given: dict[str, Any], *, actor: str) -> dict[str, Any]:
    """What this review would change; writes nothing."""
    store.refuse_write()
    if store.vault_id is None:
        raise BiStoreError("review_vault_only", "只有知識庫的卡片可以覆核證據")
    text = render(
        given,
        str(given.get("reason") or "").strip(),
        str(given.get("author") or "").strip() or actor,
        now(),
    )
    review = read(text)
    _usable(store, review)
    base = given.get("base_version")
    if review.target == "card":
        if not isinstance(base, int):
            raise BiStoreError("base_version_missing", "需要 base_version")
        store.refuse_moved(review.card_id, review.field, base)
    statement, before = _before(store, review)
    after = {**before, **review.said}
    return {
        "target": review.target,
        "statement": statement,
        "before": before,
        "after": after,
        "unchanged": before == after,
        "reason": review.reason,
        "author": review.author,
        "folder": correction.note_folder(store, review.card_id),
        "base_version": base,
        "text": text,
    }


def _assessment(
    old: dict[str, Any] | None,
    before: dict[str, Any],
    after: dict[str, Any],
    review: Review,
    *,
    actor: str,
    at: str,
    source: str,
    system_reason: str = "",
) -> dict[str, Any]:
    """The assessment after this review. What the model said and every earlier review stay."""
    old = old or {}
    system = old.get("system") or ({"reason": system_reason} if system_reason else None)
    found: dict[str, Any] = {
        "current": {k: after[k] for k in ("directness", "scope", "date", "same_source", "verdict")},
        "history": [
            *(old.get("history") or []),
            {
                "by": actor,
                "author": review.author,
                "at": at,
                "reason": review.reason,
                "source": source,
                "before": before,
                "after": after,
            },
        ],
    }
    return {**found, "system": system} if system else found


def apply(store: BiStore, given: dict[str, Any], *, actor: str) -> dict[str, Any]:
    """The person confirmed the review: keep the note as a source and write it, in one
    commit with its reason as the purpose."""
    store.refuse_write()
    if store.vault_id is None:
        raise BiStoreError("review_vault_only", "只有知識庫的卡片可以覆核證據")
    review = read(given.get("text"))
    _usable(store, review)
    base = given.get("base_version")
    if review.target == "card":
        if not isinstance(base, int):
            raise BiStoreError("base_version_missing", "需要 base_version")
        store.refuse_moved(review.card_id, review.field, base)
    statement, before = _before(store, review)
    after = {**before, **review.said}
    if before == after:
        return {"unchanged": True}
    at = now()
    stamp = at.replace(":", "").replace("-", "")
    source = Staging(store.workspace, store.dataset).add_source(
        f"review-{review.card_id}-{stamp}.md",
        text=given["text"],
        folder=correction.note_folder(store, review.card_id),
        media_type="text/markdown",
        actor=actor,
    )
    if review.target == "card":
        row = _row(store, review)
        store.review_evidence(
            review.card_id,
            review.field,
            review.reference_id,
            stance=str(after["stance"]),
            date=str(after["date"]) if after["date"] != before["date"] else None,
            assessment=_assessment(
                row.get("assessment"),
                before,
                after,
                review,
                actor=actor,
                at=at,
                source=source["id"],
            ),
        )
    else:
        relation, reference, basis, unit = _relation_link(store, review)
        vault.decide_relation(
            store.workspace,
            store.vault_id,
            {
                "from": relation["from_card_id"],
                "type": relation["relation_type"],
                "to": relation["to_card_id"],
                # A derived relation stays derived: `decide_relation` keeps its origin.
                "origin": (
                    "registered"
                    if relation["origin"] == card_model.SCHEMA_FIELD
                    else relation["origin"]
                ),
                "status": VERDICT_STATUS[str(after["verdict"])],
                "scope": after["scope"] or None,
                "note": review.reason,
                "evidence": [
                    {
                        "reference_id": reference,
                        "basis_card": basis,
                        "stance": after["stance"],
                        "assessment": _assessment(
                            unit.get("assessment"), before, after, review, actor=actor, at=at,
                            source=source["id"], system_reason=str(relation["note"] or ""),
                        ),
                    }
                ],
            },
            actor,
        )  # fmt: skip
    purpose = f"覆核 {statement}：{review.reason}"
    vault.commit(store.workspace, store.vault_id, {"purpose": purpose[: repo_engine.MAX_PURPOSE]})
    return {"source": source["id"], "after": after}
