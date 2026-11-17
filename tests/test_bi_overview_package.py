"""The BI overview feature package: manifest, deterministic build and the real
JSON-lines worker on synthetic BI data (Plugin API 1.1, H1/H4).

The worker runs as a real subprocess with the manager's own bootstrap and the
existing bounded `WorkerSession`. Synthetic data only, built with the real BI
store in temporary folders; no Host, HTTP, model or company data. Installing
through the manager and Agent Web is covered by the integration tests.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from aep_bi.cards import card_model, vault
from aep_bi.cards.store import BiStore
from aep_bi.host.bi_cards_api import route
from common.plugins import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    MAX_TABLE_ROWS,
    PluginManifest,
    PluginPackage,
    capability_models,
    parse_plugin_package,
)
from extensions.runtime import ExtensionRequest
from plugins.process import BOOTSTRAP, WorkerRefusal, WorkerSession, invoke

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "feature_plugins" / "bi_overview"
WORKER_ROOT = SOURCE / "worker"
EXAMPLE = ROOT / "examples" / "plugins" / "bi-overview.aep-plugin.json"
READ_BI = "AEP_PLUGIN_READ_BI"
HOSTILE = "<img src=x onerror=alert(1)>"


def _builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_bi_overview_plugin", ROOT / "scripts" / "build_bi_overview_plugin.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _worker() -> ModuleType:
    if str(WORKER_ROOT) not in sys.path:
        sys.path.insert(0, str(WORKER_ROOT))
    return importlib.import_module("aep_plugin_bi_overview.worker")


def _package() -> PluginPackage:
    return parse_plugin_package(_builder().package_bytes())


def _service(package: PluginPackage) -> Any:
    return package.manifest.capability("bi-overview.read_overview")


def _checked(package: PluginPackage, data: Any) -> dict[str, Any]:
    """The worker's answer as the manager validates it against the declared outputs."""
    output = capability_models(_service(package))[1]
    return dict(output.model_validate_json(json.dumps(data), strict=True).model_dump(mode="json"))


def _tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _call(ws: Path, method: str, path: str, body: Any = None) -> dict[str, Any]:
    status, payload = route(ws, "tester", method, path, {}, body)
    assert status == 200, payload
    return dict(payload)


def _synthetic_bi(tmp_path: Path) -> tuple[Path, str]:
    """A workspace with the fictional demo dataset (104 cards), an empty vault
    and one dataset whose database is not SQLite."""
    ws = tmp_path / "pc"
    _call(ws, "POST", "/api/bi/demo/load", {"dataset": "demo"})
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _call(
        ws,
        "POST",
        "/api/bi/vaults",
        {
            "path": str(shared),
            "title": "Fictional Signals",
            "schema": "bi.schema/v1.1",
            "author": "alice",
            "default_pack": False,
        },
    )
    broken = ws / "bi" / "broken"
    broken.mkdir()
    (broken / "bi.sqlite").write_bytes(b"not a database" * 10)
    return ws / "bi", vault.dataset_name(str(made["vault"]["id"]))


@pytest.fixture
def staged(tmp_path: Path) -> Path:
    """The package's files and envelope as the manager stages them."""
    package = _package()
    root = tmp_path / "staged"
    for item in package.files:
        target = root / item.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item.raw)
    (root / "package.json").write_bytes(package.to_bytes())
    return root


def _start(staged: Path, read_bi: str | None) -> WorkerSession:
    environment = {key: value for key, value in os.environ.items() if key != READ_BI}
    environment["AEP_PLUGIN_PACKAGE_FILE"] = str(staged / "package.json")
    if read_bi is not None:
        environment[READ_BI] = read_bi
    process = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-u",
            "-B",
            "-c",
            BOOTSTRAP,
            str(staged / "worker"),
            "aep_plugin_bi_overview.worker",
        ],
        cwd=staged,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return WorkerSession(process)


@pytest.fixture
def session_for(staged: Path) -> Iterator[Any]:
    started: list[WorkerSession] = []

    def start(read_bi: str | None) -> WorkerSession:
        session = _start(staged, read_bi)
        started.append(session)
        return session

    yield start
    for session in started:
        session.close()


def _read(session: WorkerSession) -> Any:
    package = _package()
    return invoke(session, _service(package).spec.identity, {}, 30)


# -- the manifest and the package ----------------------------------------------------------


def test_the_manifest_is_one_read_only_page_service_and_no_agent_tool() -> None:
    manifest = PluginManifest.model_validate_json((SOURCE / "manifest.json").read_bytes())
    assert manifest.plugin_id == "bi-overview.overview"
    assert manifest.identity.version == "0.1.0"
    assert (manifest.core_api.minimum, manifest.core_api.below) == ("1.1.0", "2.0.0")
    assert manifest.data.reads == ("bi",)
    assert manifest.tool_capabilities == ()
    (service,) = manifest.page_services
    assert service.spec.side_effect == "read" and service.inputs == ()
    assert [(r.route_id, r.capability) for r in manifest.routes] == [
        ("summary", "bi-overview.read_overview")
    ]
    assert manifest.assets == () and manifest.requires == ()
    (page,) = manifest.pages
    assert {block.kind for block in page.blocks} == {"text", "metric", "table"}


def test_the_build_is_deterministic_explicit_and_is_the_committed_example() -> None:
    builder = _builder()
    first, second = builder.package_bytes(), builder.package_bytes()
    assert first == second
    package = parse_plugin_package(first)
    folder = WORKER_ROOT / "aep_plugin_bi_overview"
    assert {item.path: item.raw for item in package.files} == {
        f"worker/aep_plugin_bi_overview/{name}": (folder / name)
        .read_bytes()
        .replace(b"\r\n", b"\n")
        for name in ("__init__.py", "reader.py", "worker.py")
    }
    assert package.content_sha256 == PluginPackage.digest_of(package.manifest, package.files)
    # No path of this checkout, user, token or company data rides in the package.
    text = first.decode("utf-8")
    for leak in (str(ROOT), str(ROOT).replace("\\", "\\\\"), "Users", "token", "@"):
        assert leak not in text, leak
    assert EXAMPLE.read_bytes() == first


def test_the_worker_bounds_match_the_contract() -> None:
    worker = _worker()
    assert worker.MAX_RESPONSE_BYTES == MAX_RESPONSE_BYTES
    assert worker.MAX_REQUEST_LINE > MAX_REQUEST_BYTES
    assert worker.MAX_ROWS == MAX_TABLE_ROWS
    source = (WORKER_ROOT / "aep_plugin_bi_overview" / "worker.py").read_text(encoding="utf-8")
    imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    allowed = (
        "from __future__",
        "import json",
        "import os",
        "import re",
        "import sys",
        "from pathlib",
        "from typing",
        "from aep_plugin_bi_overview.reader",
    )
    assert all(line.startswith(allowed) for line in imports), imports  # stdlib and its reader
    assert "BiStore" not in source and "ensure_current" not in source


# -- the real worker process ---------------------------------------------------------------


def test_health_declares_exactly_the_manifest_capabilities(session_for: Any) -> None:
    session = session_for(None)
    reply = session.exchange(ExtensionRequest(request_id="h", operation="health"), 30)
    assert reply.status == "healthy"
    assert reply.capabilities == tuple(c.spec.identity for c in _package().manifest.capabilities)


def test_the_overview_reads_synthetic_bi_data_and_changes_nothing(
    tmp_path: Path, session_for: Any
) -> None:
    bi_root, vault_dataset = _synthetic_bi(tmp_path)
    before = _tree(bi_root)
    data = _checked(_package(), _read(session_for(str(bi_root))))
    assert _tree(bi_root) == before
    assert data["bi_status"] == "ready"
    assert data["datasets_found"] == 3 and data["datasets_unavailable"] == 1
    assert data["cards_known"] == 104  # the demo's cards plus the empty vault's
    assert data["cards_total"] == "—" and data["truncated"] is False
    assert data["coverage"].startswith("不完整") and "1 個資料集無法讀取" in data["coverage"]
    rows = {row["name"]: row for row in data["datasets"]}
    assert rows["demo"]["cards"] == "104" and rows["demo"]["status"] == "ready"
    assert rows["demo"]["origin"] == "本機資料庫" and rows["demo"]["version"] == "—"
    assert rows["broken"]["status"] == "corrupt" and rows["broken"]["cards"] == "—"
    assert rows["broken"]["reason"] == "not_sqlite"
    assert rows[vault_dataset]["cards"] == "0"
    assert "非已發佈" in rows[vault_dataset]["origin"]
    assert all(isinstance(value, str) for row in data["datasets"] for value in row.values())


def test_a_complete_overview_gives_the_total_and_an_outdated_vault_is_not_rebuilt(
    tmp_path: Path, session_for: Any
) -> None:
    bi_root, vault_dataset = _synthetic_bi(tmp_path)
    (bi_root / "broken" / "bi.sqlite").unlink()
    (bi_root / "broken").rmdir()
    session = session_for(str(bi_root))
    complete = _checked(_package(), _read(session))
    assert complete["coverage"] == "完整" and complete["cards_total"] == "104"

    path = BiStore(bi_root.parent, vault_dataset).path
    with closing(sqlite3.connect(path)) as db:
        db.execute(f"PRAGMA user_version = {card_model.MODEL_VERSION - 1}")
        db.commit()
    before = _tree(bi_root)
    outdated = _checked(_package(), _read(session))
    assert _tree(bi_root) == before
    row = next(item for item in outdated["datasets"] if item["name"] == vault_dataset)
    assert (row["status"], row["reason"], row["cards"]) == (
        "outdated",
        "projection_version",
        "—",
    )
    assert outdated["cards_total"] == "—" and outdated["cards_known"] == 104
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == card_model.MODEL_VERSION - 1


def test_a_missing_bi_folder_is_reported_and_not_created(tmp_path: Path, session_for: Any) -> None:
    absent = tmp_path / "no-workspace" / "bi"
    data = _checked(_package(), _read(session_for(str(absent))))
    assert (data["bi_status"], data["datasets_found"], data["datasets"]) == ("missing", 0, [])
    assert data["cards_total"] == "—" and "還沒有 BI 資料夾" in data["coverage"]
    assert not absent.exists() and not absent.parent.exists()


@pytest.mark.parametrize(
    ("binding", "code"), [(None, "bi_context_missing"), ("", "bi_context_missing"),
                          ("relative/bi", "bi_context_invalid")]
)  # fmt: skip
def test_without_a_usable_bi_binding_the_worker_refuses(
    session_for: Any, binding: str | None, code: str
) -> None:
    session = session_for(binding)
    with pytest.raises(WorkerRefusal) as refused:
        _read(session)
    assert refused.value.code == code
    assert session.alive  # a refusal is an answer, not a crash


# -- requests the worker refuses, and the response bound -------------------------------------


def _manifest() -> dict[str, Any]:
    return dict(json.loads(_package().to_bytes())["manifest"])


def _identity() -> dict[str, Any]:
    return dict(_service(_package()).spec.identity.model_dump(mode="json"))


@pytest.mark.parametrize(
    ("line", "request_id", "code"),
    [
        (b"not json", "unknown", "request_malformed"),
        (b"\xff\xfe", "unknown", "request_malformed"),
        (b"[1, 2]", "unknown", "request_malformed"),
        (b'{"protocol": "aep-extension-jsonl/v1", "operation": "health"}', "unknown",
         "request_malformed"),
        (b'{"protocol": "other/v9", "request_id": "r", "operation": "health"}', "r",
         "protocol_unsupported"),
        (b'{"protocol": "aep-extension-jsonl/v1", "request_id": "r", "operation": "drop"}', "r",
         "operation_unknown"),
    ],
)  # fmt: skip
def test_malformed_requests_are_refused(line: bytes, request_id: str, code: str) -> None:
    reply, stop = _worker().respond(line, _manifest())
    assert (reply["request_id"], reply["status"], reply["code"], stop) == (
        request_id,
        "refused",
        code,
        False,
    )


def test_only_the_declared_service_without_arguments_is_served(tmp_path: Path) -> None:
    worker = _worker()
    base = {"protocol": "aep-extension-jsonl/v1", "request_id": "r", "operation": "invoke"}
    other = {**_identity(), "name": "write-note"}
    for request, code in (
        ({**base, "capability": other, "arguments": {}}, "capability_unknown"),
        ({**base, "capability": {**_identity(), "version": "9.9.9"}}, "capability_unknown"),
        (
            {**base, "capability": _identity(), "arguments": {"dataset": "x"}},
            "arguments_unexpected",
        ),
    ):
        reply, _ = worker.respond(json.dumps(request).encode(), _manifest())
        assert (reply["status"], reply["code"]) == ("refused", code)
    reply, _ = worker.respond(json.dumps({**base, "operation": "health"}).encode(), None)
    assert (reply["status"], reply["code"]) == ("failed", "package_unreadable")


def test_an_oversized_line_is_refused_and_the_worker_keeps_serving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()
    health = json.dumps(
        {"protocol": "aep-extension-jsonl/v1", "request_id": "h", "operation": "health"}
    ).encode()
    source = io.BytesIO(b"x" * (worker.MAX_REQUEST_LINE + 10) + b"\n" + health + b"\n")
    sink = io.BytesIO()
    monkeypatch.delenv("AEP_PLUGIN_PACKAGE_FILE", raising=False)
    worker.serve(source, sink)
    first, second = [json.loads(line) for line in sink.getvalue().splitlines()]
    assert (first["request_id"], first["code"]) == ("unknown", "request_too_large")
    assert second["request_id"] == "h"


def test_many_long_rows_are_cut_to_the_response_bound_and_marked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker = _worker()
    rows = [
        {"name": HOSTILE + "名" * 400 + str(index), "kind": "local", "status": "ready",
         "reason": None, "cards": 1, "updated": "2026-11-15T00:00:00Z" + "更" * 400,
         "schema": "bi.schema/v1.1@1.1.0" + "式" * 400, "dashboard": True,
         "subscribed": False, "read_only": False, "projection": False}
        for index in range(MAX_TABLE_ROWS)
    ]  # fmt: skip
    overview = {"status": "ready", "reason": None, "datasets": rows, "total": 250,
                "truncated": True, "invalid_registrations": 0}  # fmt: skip
    monkeypatch.setattr(worker, "read_overview", lambda root, limit: overview)
    data = worker.summary(tmp_path)
    line = worker._line({"protocol": "p", "request_id": "x" * 128, "status": "s", "data": data})
    assert len(line) <= MAX_RESPONSE_BYTES
    checked = _checked(_package(), data)
    assert checked["truncated"] is True and checked["cards_total"] == "—"
    assert checked["datasets_found"] == 250
    assert 0 < len(checked["datasets"]) < MAX_TABLE_ROWS  # rows were cut to fit
    assert all(
        len(value) <= worker.MAX_CELL for row in checked["datasets"] for value in row.values()
    )
    assert checked["datasets"][0]["name"].startswith(HOSTILE)  # text, shown by the core as text
