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


#: Mail and web hosts many companies share: never a company's alias.
PUBLIC_DOMAINS = frozenset(
    {
        "gmail",
        "googlemail",
        "yahoo",
        "hotmail",
        "outlook",
        "live",
        "msn",
        "icloud",
        "me",
        "aol",
        "proton",
        "protonmail",
        "qq",
        "163",
        "126",
        "hinet",
        "seed",
        "pchome",
        "linkedin",
        "facebook",
    }
)
#: Labels at the end of a host name that say nothing about the company.
_DOMAIN_SUFFIXES = frozenset(
    {
        "com",
        "net",
        "org",
        "co",
        "edu",
        "gov",
        "biz",
        "info",
        "io",
        "ai",
        "tw",
        "cn",
        "hk",
        "jp",
        "kr",
        "sg",
        "us",
        "uk",
        "de",
        "fr",
        "in",
        "idv",
        "www",
        "mail",
        "email",
    }
)


def domain_alias(address: str) -> str:
    """The company's name in an email address or website: `wnc` for
    `ze.wang@wnc.com.tw` or `https://www.wnc.com.tw/`; nothing for a public
    mail service."""
    text = address.strip().casefold()
    host = text.rsplit("@", 1)[1] if "@" in text else re.sub(r"^[a-z]+://", "", text)
    host = host.split("/", 1)[0].split(":", 1)[0]
    labels = [label for label in host.split(".") if label and label not in _DOMAIN_SUFFIXES]
    if not labels:
        return ""
    alias = labels[-1]
    return "" if alias in PUBLIC_DOMAINS or len(alias) < 2 else alias


_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")


def mail_domain(address: str) -> str:
    """The mail domain a company's email or website names, for reading its
    mail: `wnc.com.tw` for `ze.wang@wnc.com.tw` or `https://www.wnc.com.tw/`;
    nothing for a public mail service (`domain_alias` decides) or a value
    that is no host name."""
    if not domain_alias(address):
        return ""
    text = address.strip().casefold()
    host = text.rsplit("@", 1)[1] if "@" in text else re.sub(r"^[a-z]+://", "", text)
    host = host.split("/", 1)[0].split(":", 1)[0].strip(".")
    if "@" not in text and host.startswith("www."):
        host = host[4:]
    return host if _HOST.fullmatch(host) and "." in host else ""


def short_names(company: str) -> frozenset[str]:
    """Romanised short names in a company name: words printed in capitals,
    2-6 letters ("WNC" in "WNC 啟碁科技"), legal suffixes left out. A common
    word ("Technology") is no alias: two companies would share it."""
    words = re.findall(r"[A-Za-z0-9]+", unicodedata.normalize("NFKC", company))
    return frozenset(
        word.casefold()
        for word in words
        if 2 <= len(word) <= 6 and word.isupper() and word.casefold() not in _SUFFIXES
    )


def search_text(*parts: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", part).casefold() for part in parts if part)


_EXTENSION = re.compile(r"(?:ext\.?|extension|分機|轉|#|x)\s*(\d+)\s*$")
_PHONE_TEXT = re.compile(r"^[\d\s\-.()+/]*$")


def phone_key(number: str) -> str:
    """A phone, fax or mobile number as digits and extension, ignoring spaces,
    hyphens, dots and parentheses, with +886 read as a leading 0 (third live
    test 2026-10-20: "(03) 666 7799" is "(03) 666-7799"). "" when the text is
    not a number, so it is compared as written."""
    text = number.casefold().strip()
    extension = ""
    found = _EXTENSION.search(text)
    if found:
        extension, text = found.group(1), text[: found.start()]
    if not _PHONE_TEXT.match(text):
        return ""
    digits = re.sub(r"[\s\-.()/]", "", text)
    if digits.startswith("+886"):
        rest = digits[4:]
        digits = "0" + (rest[1:] if rest.startswith("0") else rest)
    if not digits.lstrip("+"):
        return ""
    return digits + (f"#{extension}" if extension else "")
