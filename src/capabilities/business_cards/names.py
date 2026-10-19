"""How two cards are recognised as the same person.

Email decides when both have one. Otherwise the name and the company must
both agree: the company after its legal suffixes are dropped, the name either
as written or through its romanised form, so "Hsiao-Ming Wang" on a signature
finds 王小明 whose card noted that spelling. Romanised names are compared
token-wise in either order (family name first or last) and without spaces or
hyphens, which covers "Wang Hsiao-Ming", "Hsiaoming Wang" and "HSIAO MING WANG".
"""

from __future__ import annotations

import re
import unicodedata

_CJK = re.compile(r"[㐀-鿿豈-﫿]")
_SUFFIXES = (
    "股份有限公司",
    "有限公司",
    "公司",
    "corporation",
    "company",
    "limited",
    "corp",
    "inc",
    "ltd",
    "co",
)
_TOKENS = re.compile(r"[a-z0-9]+")


def email_key(email: str) -> str:
    return email.strip().casefold()


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


def company_key(company: str) -> str:
    text = unicodedata.normalize("NFKC", company).casefold()
    words = re.findall(r"[a-z0-9]+|[^\sa-z0-9]", text)
    kept = [w for w in words if w not in _SUFFIXES and re.match(r"[\w㐀-鿿]", w)]
    joined = "".join(kept)
    for suffix in _SUFFIXES:
        if has_cjk(suffix) and joined.endswith(suffix) and len(joined) > len(suffix):
            joined = joined[: -len(suffix)]
    return joined


def same_company(a: str, b: str) -> bool:
    left, right = company_key(a), company_key(b)
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 3 and shorter in longer


def name_keys(name: str) -> frozenset[str]:
    """Every form this name may appear in when another card writes it."""
    text = unicodedata.normalize("NFKC", name).strip()
    if not text:
        return frozenset()
    if has_cjk(text):
        return frozenset({re.sub(r"\s+", "", text)})
    tokens = _TOKENS.findall(text.casefold())
    if not tokens:
        return frozenset()
    keys = {"".join(tokens)}
    if len(tokens) > 1:
        keys.add("".join(tokens[-1:] + tokens[:-1]))
        keys.add("".join(tokens[1:] + tokens[:1]))
    return frozenset(keys)


def same_name(a: str, b: str) -> bool:
    return bool(name_keys(a) & name_keys(b))


def search_text(*parts: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", part).casefold() for part in parts if part)
