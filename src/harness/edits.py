"""Search/replace edits for the change author (`docs/phases/CODING_AT_SCALE.md`).

The model never returns a large file: it names an exact passage and its
replacement, and this module applies it. Matching is on LF text; a CRLF file
is written back with CRLF and a BOM is kept, so an edit does not turn into a
whole-file line-ending diff. A batch applies completely or not at all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

BOM = "﻿"


class EditRefused(Exception):
    """An edit that cannot be applied; the message goes back to the model."""


@dataclass(frozen=True)
class FileText:
    """A file's text as the model sees it (LF), and how to write it back."""

    text: str
    newline: str = "\n"
    bom: bool = False

    @classmethod
    def decode(cls, path: str, raw: bytes) -> FileText:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise EditRefused(f"{path} is not UTF-8 text and cannot be edited here") from None
        bom = text.startswith(BOM)
        if bom:
            text = text[1:]
        crlf = text.count("\r\n")
        if crlf and crlf != text.count("\n"):
            raise EditRefused(f"{path} mixes CRLF and LF line endings and cannot be edited here")
        if crlf:
            return cls(text.replace("\r\n", "\n"), "\r\n", bom)
        return cls(text, "\n", bom)

    def encode(self, text: str) -> str:
        """The content to write for `text` (LF), in this file's own style."""
        body = text.replace("\r\n", "\n")
        if self.newline != "\n":
            body = body.replace("\n", self.newline)
        return (BOM if self.bom else "") + body


@dataclass(frozen=True)
class Edit:
    path: str
    old: str
    new: str


def parse_edits(raw: object) -> tuple[Edit, ...]:
    if not isinstance(raw, list) or not raw:
        raise EditRefused('"edits" must be a non-empty list of {"path", "old", "new"}')
    edits: list[Edit] = []
    for item in raw:
        if not isinstance(item, dict):
            raise EditRefused('each edit must be an object {"path", "old", "new"}')
        path, old, new = item.get("path"), item.get("old", ""), item.get("new")
        if not isinstance(path, str) or not isinstance(old, str) or not isinstance(new, str):
            raise EditRefused('each edit needs string "path", "old" and "new"')
        edits.append(Edit(path=path.strip().replace("\\", "/"), old=old, new=new))
    return tuple(edits)


def apply_edits(current: Mapping[str, str | None], edits: Sequence[Edit]) -> dict[str, str]:
    """The new LF text of every file the batch touches.

    `current` maps each file the author may write to its LF text, or None when
    it does not exist yet. Nothing is returned unless every edit applies.
    """
    texts: dict[str, str | None] = dict(current)
    touched: dict[str, str] = {}
    for edit in edits:
        if edit.path not in texts:
            allowed = ", ".join(sorted(texts))
            raise EditRefused(f"{edit.path} is not a file you may write (you may write: {allowed})")
        text = texts[edit.path]
        old = edit.old.replace("\r\n", "\n")
        new = edit.new.replace("\r\n", "\n")
        if not old:
            if text:
                raise EditRefused(
                    f'{edit.path} already exists; an empty "old" only creates a new file'
                )
            updated = new
        else:
            if text is None:
                raise EditRefused(f'{edit.path} does not exist yet; create it with an empty "old"')
            found = text.count(old)
            if found == 0:
                raise EditRefused(
                    f'the "old" text was not found in {edit.path}; read the lines again and '
                    "copy them exactly, including indentation"
                )
            if found > 1:
                raise EditRefused(
                    f'the "old" text appears {found} times in {edit.path}; include more '
                    "surrounding lines so it matches exactly once"
                )
            updated = text.replace(old, new, 1)
        texts[edit.path] = updated
        touched[edit.path] = updated
    return touched
