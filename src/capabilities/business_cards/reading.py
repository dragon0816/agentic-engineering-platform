"""Host checks on what a model read from a card or a signature.

The model reads; the Host keeps it to what is printed. A romanised name is
kept only when the reading says where it is printed (for a card, the line as
printed; for a signature, the block itself); one derived from the email or
from the local-language name is dropped, and an email whose local part looks
made to match a dropped name is marked uncertain (live test 2026-10-20: a
card without an English name came back as "Yanji Fan" with the email bent
to `Yanji.fan@...`).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence

from capabilities.business_cards import names
from capabilities.business_cards.contracts import DroppedField, FieldName

_TOKENS = re.compile(r"[a-z0-9]+")
#: Academic or honorific titles that belong in `honorific`, never in `title`.
#: 博士後 (postdoc) is a job title and stays.
_HONORIFIC = re.compile(r"博士(?!後)|\bDr\.?(?=\s|$|,)|\bPh\.?\s?D\.?", re.IGNORECASE)
_SEPARATORS = " ,，、/|;；"
#: The unified business number (統一編號), 8 digits in Taiwan.
_TAX_ID = re.compile(
    r"(?:統一編號|統一编号|統編|UBN|Tax\s*ID|VAT\s*(?:No\.?|Number)?)\s*[:：#]?\s*(\d{8})",
    re.IGNORECASE,
)
_ADDRESS = re.compile(r"\S+@\S+")


def _letters(text: str) -> str:
    return "".join(_TOKENS.findall(unicodedata.normalize("NFKC", text).casefold()))


def _trim(text: str) -> str:
    return re.sub(r"\s{2,}", " ", text).strip(_SEPARATORS)


def tidy(values: Mapping[str, str]) -> dict[str, str]:
    """A reading with each value in its own field: a degree or honorific in
    the title moves to `honorific`; a unified business number in the notes
    moves to `company_tax_id`. Division and department text is kept exactly
    as read (研展處 I stays 研展處 I)."""
    out = dict(values)
    title = out.get("title", "")
    found = [match.group(0).strip() for match in _HONORIFIC.finditer(title)]
    if found:
        out["title"] = _trim(_HONORIFIC.sub(" ", title))
        known = [part for part in re.split(r"[、,，/ ]+", out.get("honorific", "")) if part]
        merged = list(dict.fromkeys(known + [item.rstrip(",") for item in found]))
        out["honorific"] = " ".join(merged)
    notes = out.get("notes", "")
    match = _TAX_ID.search(notes)
    if match and out.get("company_tax_id", "") in ("", match.group(1)):
        out["company_tax_id"] = match.group(1)
        out["notes"] = _trim(notes[: match.start()] + " " + notes[match.end() :])
    return out


def printed(romanised: str, evidence: str) -> bool:
    """Whether the romanised name appears in the printed text (in either
    name order, spaces and hyphens ignored). An email is no evidence."""
    if not romanised.strip() or not evidence.strip():
        return False
    # An email address is no evidence of a printed name.
    shown = unicodedata.normalize("NFKC", _ADDRESS.sub(" ", evidence)).casefold()
    words = set(_TOKENS.findall(shown))
    wanted = _TOKENS.findall(unicodedata.normalize("NFKC", romanised).casefold())
    if wanted and all(word in words for word in wanted):
        return True  # "Ryan Fan" in "Ryan R.J. Fan"
    text = "".join(_TOKENS.findall(shown))
    return any(key and key in text for key in names.name_keys(romanised))


def check_romanised(
    values: Mapping[str, str], uncertain: Sequence[FieldName], evidence: str
) -> tuple[dict[str, str], tuple[FieldName, ...], tuple[DroppedField, ...]]:
    """The reading with an unprinted romanised name dropped, and the email
    marked uncertain when its local part repeats the dropped name."""
    out = dict(values)
    romanised = out.get("romanised_name", "").strip()
    if not romanised or printed(romanised, evidence):
        return out, tuple(uncertain), ()
    out["romanised_name"] = ""
    unsure = [name for name in uncertain if name != "romanised_name"]
    local = _letters(out.get("email", "").split("@", 1)[0])
    tokens = [token for token in _TOKENS.findall(romanised.casefold()) if len(token) >= 2]
    if local and any(token in local for token in tokens) and "email" not in unsure:
        unsure.append("email")
    dropped = DroppedField(field="romanised_name", value=romanised, reason="not_on_card")
    return out, tuple(unsure), (dropped,)
