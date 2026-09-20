"""Characterize pinned declarative dispatch, without executing n8n/JS/HTTP."""

import hashlib
import json
from pathlib import Path


def test_source_graph_dispatches_once_then_branches_on_terminal_success() -> None:
    text = (Path(__file__).parent / "fixtures/source_n8n_release.json").read_text(encoding="utf-8")
    assert hashlib.sha256(text.encode()).hexdigest() == (
        "4135789e5a71efba67206f1729d73a0a47e44ef3e61f3855925630765d9e27a5"
    )
    source = json.loads(text)
    http, branch = source["nodes"]
    assert http["type"] == "n8n-nodes-base.httpRequest"
    assert http["parameters"]["method"] == "POST"
    assert not http.get("retryOnFail", False)
    body = http["parameters"]["jsonBody"]
    assert "job: 'release_package'" in body and "params: {" in body
    assert "companyName: $json.companyName" in body and "dryRun: $json.dryRun" in body
    rules = branch["parameters"]["conditions"]
    assert rules["combinator"] == "and"
    assert rules["conditions"][0]["leftValue"] == "={{ $json.ok === true }}"
    assert rules["conditions"][1]["rightValue"] == "success"
    graph = source["connections"]
    assert graph[http["name"]]["main"][0][0]["node"] == branch["name"]
    assert len(graph[branch["name"]]["main"]) == 2
