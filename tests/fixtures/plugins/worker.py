"""Synthetic feature-plugin worker (stdlib only), speaking the existing
`aep-extension-jsonl/v1` request/reply protocol on standard input/output.

Packaged as `worker/aep_plugin_<namespace>/worker.py`; the same file serves any
namespace because it reads its own manifest from the staged package envelope
named by AEP_PLUGIN_PACKAGE_FILE. Data lives only under AEP_PLUGIN_DATA_ROOT.

Capabilities, by local name:
- `read_summary` (read): `count` notes and `items` rows of `label`/`value`.
- `write_note` (write): appends one line to notes.jsonl and increments
  counter.txt, so the real number of executions is visible on disk.
  The note `FAIL` is refused with code `fixture_failure` and writes nothing.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, cast

PROTOCOL = "aep-extension-jsonl/v1"


def _manifest() -> dict[str, Any]:
    envelope = json.loads(Path(os.environ["AEP_PLUGIN_PACKAGE_FILE"]).read_text(encoding="utf-8"))
    return cast(dict[str, Any], envelope["manifest"])


def _data_root() -> Path:
    root = Path(os.environ["AEP_PLUGIN_DATA_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _notes(root: Path) -> list[str]:
    path = root / "notes.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)["note"] for line in path.read_text(encoding="utf-8").splitlines() if line
    ]


def _counter(root: Path) -> int:
    path = root / "counter.txt"
    return int(path.read_text(encoding="utf-8")) if path.is_file() else 0


def _reply(request_id: str, status: str, **fields: object) -> None:
    sys.stdout.write(
        json.dumps({"protocol": PROTOCOL, "request_id": request_id, "status": status, **fields})
        + "\n"
    )
    sys.stdout.flush()


def main() -> None:
    manifest = _manifest()
    by_name = {item["spec"]["identity"]["name"]: item["spec"] for item in manifest["capabilities"]}
    identities = [spec["identity"] for spec in by_name.values()]
    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        request_id = request["request_id"]
        operation = request["operation"]
        if operation == "health":
            _reply(request_id, "healthy", capabilities=identities)
            continue
        if operation == "shutdown":
            _reply(request_id, "succeeded")
            return
        identity = request.get("capability") or {}
        spec = by_name.get(identity.get("name"))
        if spec is None or identity.get("version") != manifest["identity"]["version"]:
            _reply(request_id, "refused", code="fixture_unknown_capability")
            continue
        local = spec["name"].split(".", 1)[1]
        arguments = request.get("arguments") or {}
        root = _data_root()
        if local == "read_summary":
            notes = _notes(root)
            rows = [
                {"label": f"note-{index}", "value": note} for index, note in enumerate(notes, 1)
            ]
            _reply(request_id, "succeeded", data={"count": len(notes), "items": rows})
        elif local == "write_note":
            note = arguments.get("note")
            if note == "FAIL":
                _reply(request_id, "failed", code="fixture_failure")
                continue
            with (root / "notes.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"note": note}) + "\n")
            counter = _counter(root) + 1
            (root / "counter.txt").write_text(str(counter), encoding="utf-8")
            _reply(request_id, "succeeded", data={"saved": True, "counter": counter})
        else:
            _reply(request_id, "refused", code="fixture_unknown_capability")


if __name__ == "__main__":
    main()
