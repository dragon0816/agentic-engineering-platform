"""Reading and writing the files a company host keeps in its workspace.

Shared by the host assembly and the platform client, which cannot import
each other: the assembly builds the client, and the client writes what the
assembly later reads.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path


def documents(path: Path) -> Iterator[object]:
    """Every JSON document in a file, which may hold one or a list of them."""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    yield from payload if isinstance(payload, list) else [payload]


def write_atomically(path: Path, content: bytes) -> None:
    """A file appears whole or not at all, so a host that is rebuilt halfway
    through a write never reads half a manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(content)
    os.replace(temporary, path)
