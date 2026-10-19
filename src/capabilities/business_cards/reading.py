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
_ADDRESS = re.compile(r"\S+@\S+")


def _letters(text: str) -> str:
    return "".join(_TOKENS.findall(unicodedata.normalize("NFKC", text).casefold()))


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
