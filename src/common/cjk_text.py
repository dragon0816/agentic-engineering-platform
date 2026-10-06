"""Fold look-alike CJK code points that PDF text extraction produces.

A PDF printed by Edge or Word often maps some glyphs to Kangxi radicals or
compatibility ideographs: pypdf then returns `客⼾` (U+2F3E) for `客戶`, which
reads the same and matches nothing. Only those blocks are normalized (NFKC per
character); full-width punctuation and everything else is left as written.
"""

import unicodedata

_FOLDED_BLOCKS = (
    (0x2E80, 0x2EFF),  # CJK Radicals Supplement
    (0x2F00, 0x2FDF),  # Kangxi Radicals
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
)


def _folded(character: str) -> str:
    point = ord(character)
    if any(low <= point <= high for low, high in _FOLDED_BLOCKS):
        return unicodedata.normalize("NFKC", character)
    return character


def fold_cjk_lookalikes(text: str) -> str:
    return "".join(_folded(character) for character in text)
