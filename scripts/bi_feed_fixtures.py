"""Build the BI feed fixture vault and the feed's golden answers.

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §6.1. A fictional vault
(`tests/fixtures/bi_feed/vault/`: a few dozen cards, three published analyses
with one parameter `domain`, and an unpublished change after the published
tag) and the answers of `aep.bi.analysis_feed/v1` on it
(`tests/fixtures/bi_feed/golden/*.json`, the requests that give them in
`golden/requests.json`). Atlas vendors the golden files; AEP's contract tests
assert the live routes give exactly them.

    python scripts/bi_feed_fixtures.py           # rebuild the vault and the golden files
    python scripts/bi_feed_fixtures.py --check   # fail when either differs from a rebuild

The build is reproducible: the clock and the random ids are fixed while the
vault is made, and `computed_at` is fixed while the answers are computed.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import random
import shutil
import sys
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src"):  # run as a script: neither is importable then
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from capabilities.bi_cards import analyses, feed, vault, vault_skills  # noqa: E402
from capabilities.bi_cards import store as bi_store  # noqa: E402
from capabilities.bi_cards.store import BiStore, PlannedRow  # noqa: E402
from knowledge.repo import repository as repo_engine  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "bi_feed"
VAULT_DIR = FIXTURE / "vault"
GOLDEN_DIR = FIXTURE / "golden"
VAULT_ID = "feed-fixture"
MADE_AT = "2026-11-01T09:00:00+08:00"
COMPUTED_AT = "2026-11-01T09:30:00+08:00"
SEED = 20261101

# -- the cards (all fictional) -----------------------------------------------------------

ACCOUNTS = [
    ("Alder Robotics", ["robotics"], "TW"),
    ("Birch Automation", ["robotics"], "TW"),
    ("Cedar Motion", ["robotics"], "JP"),
    ("Dogwood Arms", ["robotics", "AIDC"], "US"),
    ("Elm Servo", ["robotics"], "DE"),
    ("Fir Wireless", ["wireless"], "TW"),
    ("Gum Telecom", ["wireless"], "US"),
    ("Hazel Radio", ["wireless", "robotics"], "TW"),
    ("Ivy Modules", ["wireless"], "CN"),
    ("Juniper Compute", ["AIDC"], "US"),
    ("Kapok Power", ["AIDC"], "TW"),
    ("Larch Cooling", ["AIDC"], "TW"),
]
NODES = [
    ("Servo Drive", ["robotics"], "L2"),
    ("Robot Controller", ["robotics"], "L3"),
    ("AMR Platform", ["robotics"], "L4"),
    ("Vision Module", ["robotics"], "L2"),
    ("RF Front End", ["wireless"], "L1"),
    ("Baseband Modem", ["wireless"], "L2"),
    ("GPU Server", ["AIDC"], "L3"),
    ("Power Shelf", ["AIDC"], "L2"),
]
SOLUTIONS = [
    ("Servo Test Bench", ["robotics"], ["Servo Drive", "Robot Controller"]),
    ("Controller EMC Suite", ["robotics"], ["Robot Controller"]),
    ("Fleet Radio Check", ["robotics", "wireless"], ["AMR Platform", "RF Front End"]),
    ("Modem Conformance", ["wireless"], ["Baseband Modem", "RF Front End"]),
    ("Rack Power Analyzer", ["AIDC"], ["Power Shelf"]),
]
TECHNOLOGIES = [
    ("EtherCAT G", ["robotics"], "growth", "2026-06-12"),
    ("TSN Profiles", ["robotics", "wireless"], "growth", "2026-07-03"),
    ("Safety PLd", ["robotics"], "mature", "2026-07-21"),
    ("5G RedCap", ["wireless", "robotics"], "growth", "2026-08-08"),
    ("Wi-Fi 7", ["wireless"], "growth", "2026-08-30"),
    ("UWB Ranging", ["robotics"], "emerging", "2026-09-14"),
    ("48V Busbar", ["AIDC"], "growth", "2026-09-02"),
    ("Liquid Cooling", ["AIDC"], "emerging", "2026-10-05"),
    ("NTN Satellite", ["wireless"], "emerging", "2026-10-19"),
]
LATE_ACCOUNT = ("Maple Grippers", ["robotics"], "EU")  # pushed after the published tag

# -- the analyses ---------------------------------------------------------------------------

DOMAIN = {"domain": {"type": "enum", "values_from": "Account.domain", "default": "robotics"}}
IN_DOMAIN = (
    "EXISTS (SELECT 1 FROM card_values d, json_each(d.value) j "
    "WHERE d.card_id = {card} AND d.field = 'domain' AND j.value = {value})"
)
ANALYSES: list[dict[str, Any]] = [
    {
        "slug": "accounts-by-region",
        "title": "各地區的客戶數",
        "question": "這個領域的客戶分布在哪些地區？",
        "kind": "sql",
        "code": (
            "SELECT r.value AS region, count(*) AS accounts\n"
            "FROM card_values r\n"
            "WHERE r.entity_type = 'Account' AND r.field = 'region'\n"
            f"  AND {IN_DOMAIN.format(card='r.card_id', value=':domain')}\n"
            "GROUP BY r.value\n"
            "ORDER BY accounts DESC, region"
        ),
        "chart": {"type": "bar", "x": "region", "y": "accounts"},
        "params": DOMAIN,
        "requires": {"types": ["Account"], "fields": ["Account.region", "Account.domain"]},
    },
    {
        "slug": "node-coverage",
        "title": "節點的測試方案覆蓋",
        "question": "這個領域的哪些節點還沒有或只有一個測試方案？",
        "kind": "sql",
        "code": (
            "WITH nodes AS (\n"
            "  SELECT n.card_id, n.card AS node FROM card_values n\n"
            "  WHERE n.entity_type = 'Node' AND n.field = 'name'\n"
            f"    AND {IN_DOMAIN.format(card='n.card_id', value=':domain')}\n"
            "), counted AS (\n"
            "  SELECT nodes.node, (\n"
            "    SELECT count(*) FROM card_values s, json_each(s.value) j\n"
            "    WHERE s.entity_type = 'TestSolution' AND s.field = 'nodes'\n"
            "      AND j.value = nodes.node\n"
            "  ) AS solutions FROM nodes\n"
            ")\n"
            "SELECT node, solutions,\n"
            "  CASE solutions WHEN 0 THEN 'gap' WHEN 1 THEN 'warning' END AS level\n"
            "FROM counted\n"
            "ORDER BY solutions, node"
        ),
        "chart": {"type": "table"},
        "params": DOMAIN,
        "requires": {"types": ["Node", "TestSolution"], "fields": ["TestSolution.nodes"]},
    },
    {
        "slug": "tech-updates",
        "title": "每月更新的技術數",
        "question": "這個領域每個月有幾項技術更新？",
        "kind": "python",
        "code": (
            "rows = query(\n"
            '    "SELECT t.value AS updated FROM card_values t "\n'
            "    \"WHERE t.entity_type = 'Technology' AND t.field = 'updated' AND \"\n"
            f'    "{IN_DOMAIN.format(card="t.card_id", value="?")}",\n'
            '    (PARAMS["domain"],),\n'
            ")\n"
            "counts = {}\n"
            "for row in rows:\n"
            '    month = str(row["updated"])[:7]\n'
            "    counts[month] = counts.get(month, 0) + 1\n"
            'result = {"columns": ["month", "technologies"],\n'
            '          "rows": [[m, n] for m, n in sorted(counts.items())]}\n'
        ),
        "chart": {"type": "line", "x": "month", "y": "technologies"},
        "params": DOMAIN,
        "requires": {"types": ["Technology"]},
    },
]
LATE_ANALYSIS = {  # pushed after the published tag: the feed never shows it
    "slug": "draft-only",
    "title": "尚未發佈的分析",
    "kind": "sql",
    "code": "SELECT count(*) AS cards FROM cards",
    "chart": {"type": "table"},
}
LAYOUT = {"order": ["node-coverage", "accounts-by-region", "tech-updates"], "hidden": []}

# -- the requests whose answers are golden --------------------------------------------------

BASE = f"vaults/{VAULT_ID}"
REQUESTS: list[dict[str, Any]] = [
    {"file": "health.json", "path": "health"},
    {"file": "vaults.json", "path": "vaults"},
    {"file": "analyses.json", "path": f"{BASE}/analyses"},
    {"file": "result-node-coverage.json", "path": f"{BASE}/analyses/node-coverage/result"},
    {
        "file": "result-node-coverage-domain-wireless.json",
        "path": f"{BASE}/analyses/node-coverage/result",
        "query": {"domain": "wireless"},
    },
    {
        "file": "result-accounts-by-region.json",
        "path": f"{BASE}/analyses/accounts-by-region/result",
    },
    {
        "file": "result-accounts-by-region-domain-AIDC.json",
        "path": f"{BASE}/analyses/accounts-by-region/result",
        "query": {"domain": "AIDC"},
    },
    {"file": "result-tech-updates.json", "path": f"{BASE}/analyses/tech-updates/result"},
    {
        "file": "error-result_not_ready.json",
        "path": f"{BASE}/analyses/tech-updates/result",
        "query": {"domain": "wireless"},
    },
    {
        "file": "result-tech-updates-domain-wireless.json",
        "path": f"{BASE}/analyses/tech-updates/result",
        "query": {"domain": "wireless"},
        "after_queue": True,
    },
    {
        "file": "error-param_invalid.json",
        "path": f"{BASE}/analyses/accounts-by-region/result",
        "query": {"domain": "space"},
    },
    {
        "file": "error-param_unknown.json",
        "path": f"{BASE}/analyses/accounts-by-region/result",
        "query": {"region": "TW"},
    },
    {"file": "error-analysis_unknown.json", "path": f"{BASE}/analyses/draft-only/result"},
    {"file": "error-vault_unknown.json", "path": "vaults/no-such-vault/analyses"},
    {"file": "error-route_unknown.json", "path": "nothing-here"},
    {"file": "error-origin_refused.json", "path": "vaults", "origin": "https://example.com"},
]


@contextmanager
def frozen() -> Iterator[None]:
    """A fixed clock and seeded ids while the vault is made."""
    rng = random.Random(SEED)
    saved_uuid4 = uuid.uuid4
    saved_now = bi_store.now
    saved_repo_now = repo_engine._now
    bound = [m for m in list(sys.modules.values()) if getattr(m, "now", None) is saved_now]
    uuid.uuid4 = lambda: uuid.UUID(int=rng.getrandbits(128), version=4)
    utc = "2026-11-01T01:00:00+00:00"
    for module in bound:
        module.now = lambda: utc  # type: ignore[attr-defined]
    repo_engine._now = lambda: MADE_AT
    try:
        yield
    finally:
        uuid.uuid4 = saved_uuid4
        for module in bound:
            module.now = saved_now  # type: ignore[attr-defined]
        repo_engine._now = saved_repo_now


def _rows(entity_type: str, items: list[dict[str, Any]]) -> list[PlannedRow]:
    return [
        PlannedRow(
            row=number,
            entity_type=entity_type,
            canonical_key=vault._slug(item["name"], 60),
            name=item["name"],
            values=item,
            synthetic=False,
        )
        for number, item in enumerate(items, start=1)
    ]


def _import(store: BiStore, entity_type: str, items: list[dict[str, Any]]) -> None:
    store.apply(
        _rows(entity_type, items),
        filename=f"{entity_type.lower()}.csv",
        entity_type=entity_type,
        actor="fixture",
    )


def _ok(answer: dict[str, Any]) -> dict[str, Any]:
    if answer.get("push") not in (None, "pushed") and answer.get("status") != "pushed":
        raise SystemExit(f"fixture build failed: {answer}")
    return answer


@contextmanager
def old_layout() -> Iterator[None]:
    """The fixture stays a vault from before the homes (`BI_CARD_MODEL.md` §4), so it
    also proves an old vault still loads: today's code makes the commits it made."""
    saved_body, saved_lists = vault_skills.classify_body, vault._home_lists
    vault.BI_TYPE.layout = repo_engine.DEFAULT_LAYOUT  # type: ignore[assignment]

    def old_body(reg: Any, segments: list[dict[str, str]], library: list[str]) -> str:
        return vault_skills._old_classify_body(reg, segments)

    def old_lists(segments: list[dict[str, str]], library: list[str]) -> dict[str, str]:
        return {vault_skills.SEGMENTS_UNIT: vault._segments_meta(segments)}

    vault_skills.classify_body = old_body
    vault._home_lists = old_lists
    try:
        yield
    finally:
        del vault.BI_TYPE.layout
        vault_skills.classify_body = saved_body
        vault._home_lists = saved_lists


def build_vault(workspace: Path, parent: Path) -> Path:
    """Make the fixture vault under `parent`; returns its folder."""
    with frozen(), old_layout():
        segments = [{"folder": f, "label": label} for f, label in vault.MARKET_SEGMENTS]
        made = vault.create(
            workspace,
            {
                "id": VAULT_ID,
                "path": str(parent),
                "title": "Feed Fixture Market (fictional)",
                "purpose": "虛構資料：BI analysis feed 的契約測試",
                "schema": "bi.schema/v1.1@2.0.0",  # frozen: the golden answers name it
                "author": "fixture",
                "default_pack": False,  # the fixture holds its own three analyses
                "segments": segments,
            },
            "fixture",
        )
        store = BiStore(workspace, made["vault"]["dataset"])
        _import(store, "Account", [{"name": n, "domain": d, "region": r} for n, d, r in ACCOUNTS])
        _import(store, "Node", [{"name": n, "domain": d, "layer": la} for n, d, la in NODES])
        _import(
            store,
            "TestSolution",
            [{"name": n, "domain": d, "nodes": nodes} for n, d, nodes in SOLUTIONS],
        )
        _import(
            store,
            "Technology",
            [{"name": n, "domain": d, "maturity": m, "updated": u} for n, d, m, u in TECHNOLOGIES],
        )
        for given in ANALYSES:
            analyses.save(workspace, VAULT_ID, given)
        target = vault.Vault(workspace, VAULT_ID)
        with target.lock:
            target.repo.stage(feed.DASHBOARD_UNIT, json.dumps(LAYOUT, ensure_ascii=False))
        vault.commit(workspace, VAULT_ID, {"purpose": "加上三個分析與 Dashboard 順序"})
        _ok(vault.push(workspace, VAULT_ID))
        vault.tag(workspace, VAULT_ID, {"name": "v1", "purpose": "第一個發佈版"})
        vault.publish(workspace, VAULT_ID, {"tag": "v1", "confirm": True})
        name, domains, region = LATE_ACCOUNT
        _import(store, "Account", [{"name": name, "domain": domains, "region": region}])
        analyses.save(workspace, VAULT_ID, LATE_ANALYSIS)
        vault.commit(workspace, VAULT_ID, {"purpose": "發佈之後的修改（不在 feed 裡）"})
        _ok(vault.push(workspace, VAULT_ID))
    return parent / VAULT_ID


def join(workspace: Path, folder: Path) -> None:
    """Use the fixture vault folder on a fresh PC (as the contract tests do)."""
    vault.join(workspace, {"path": str(folder), "author": "reader"}, "reader")


def url(request: dict[str, Any]) -> str:
    query = request.get("query") or {}
    return feed.PREFIX + str(request["path"]) + (f"?{urlencode(query)}" if query else "")


def answers(workspace: Path) -> list[tuple[dict[str, Any], int, dict[str, Any]]]:
    """Each golden request's (request, status, body) on a workspace that joined
    the fixture, in order: the defaults computed first (as on publish)."""
    saved = feed.clock
    feed.clock = lambda: COMPUTED_AT
    try:
        feed.compute_defaults(workspace, VAULT_ID)
        found = []
        for request in REQUESTS:
            if request.get("after_queue"):
                feed.drain()
            path, _, query = url(request).partition("?")
            status, body = feed.answer(workspace, "GET", path, query, request.get("origin"))
            found.append((request, status, body))
        return found
    finally:
        feed.clock = saved


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def write_golden(target: Path, found: list[tuple[dict[str, Any], int, dict[str, Any]]]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    manifest = []
    for request, status, body in found:
        (target / request["file"]).write_text(_dump(body), encoding="utf-8", newline="\n")
        manifest.append(
            {
                "file": request["file"],
                "method": "GET",
                "url": url(request),
                "origin": request.get("origin"),
                "status": status,
                "after_queue": bool(request.get("after_queue")),
            }
        )
    document = {
        "format": feed.FORMAT,
        "vault": VAULT_ID,
        "computed_at": COMPUTED_AT,
        "note": (
            "Requests in order on a fresh PC that joined tests/fixtures/bi_feed/vault; "
            "default results are computed first (as on publish); after_queue: the queued "
            "results were computed before this request. Built by scripts/bi_feed_fixtures.py."
        ),
        "requests": manifest,
    }
    (target / "requests.json").write_text(_dump(document), encoding="utf-8", newline="\n")


def build(out_vault: Path, out_golden: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="aep-bi-feed-") as scratch:
        root = Path(scratch)
        (root / "maker").mkdir()
        (root / "shared").mkdir()
        folder = build_vault(root / "maker", root / "shared")
        if out_vault.exists():
            shutil.rmtree(out_vault)
        shutil.copytree(folder, out_vault)
        golden_from(out_vault, out_golden, root / "reader")


def golden_from(vault_folder: Path, out_golden: Path, workspace: Path) -> None:
    """The golden answers of a copy of `vault_folder` joined on `workspace`."""
    copy = workspace.parent / f"{workspace.name}-vault"
    shutil.copytree(vault_folder, copy)
    workspace.mkdir(parents=True, exist_ok=True)
    join(workspace, copy)
    if out_golden.exists():
        shutil.rmtree(out_golden)
    write_golden(out_golden, answers(workspace))


def _holds_files(path: Path) -> bool:
    return not path.is_dir() or any(p.is_file() for p in path.rglob("*"))


def _differences(left: Path, right: Path) -> list[str]:
    """Paths that differ; an empty folder on one side is not a difference, since git
    cannot keep one and a fresh checkout never has it."""
    found: list[str] = []

    def walk(compare: filecmp.dircmp[str], prefix: str) -> None:
        found.extend(prefix + n for n in compare.left_only if _holds_files(Path(compare.left, n)))
        found.extend(prefix + n for n in compare.right_only if _holds_files(Path(compare.right, n)))
        found.extend(prefix + n for n in compare.diff_files + compare.funny_files)
        for name, sub in compare.subdirs.items():
            walk(sub, f"{prefix}{name}/")

    filecmp.clear_cache()
    walk(filecmp.dircmp(left, right, ignore=[]), "")
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with a rebuild")
    args = parser.parse_args(argv)
    if not args.check:
        build(VAULT_DIR, GOLDEN_DIR)
        print(f"wrote {VAULT_DIR.relative_to(REPO)} and {GOLDEN_DIR.relative_to(REPO)}")
        return 0
    with tempfile.TemporaryDirectory(prefix="aep-bi-feed-check-") as scratch:
        root = Path(scratch)
        build(root / "vault", root / "golden")
        problems = [f"vault/{p}" for p in _differences(VAULT_DIR, root / "vault")]
        problems += [f"golden/{p}" for p in _differences(GOLDEN_DIR, root / "golden")]
    for problem in problems:
        print(f"differs: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
