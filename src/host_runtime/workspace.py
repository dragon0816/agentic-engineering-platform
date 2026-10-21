"""Reading and writing the files a company host keeps in its workspace.

Shared by the host assembly and the platform client, which cannot import
each other: the assembly builds the client, and the client writes what the
assembly later reads.
"""

import json
import os
import time
from collections.abc import Iterator
from pathlib import Path

#: How often a replace is tried when Windows refuses it for a moment (a scanner
#: or indexer holding the file), with a growing pause in between.
REPLACE_ATTEMPTS = 6


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
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            # Windows refuses a replace while another process (a virus
            # scanner, the search indexer) briefly holds either file.
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(0.05 * (attempt + 1))
