"""Explicit PUBLIC-only TypeSafe benchmark with no real network traffic."""

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from evaluation.jev_live import PUBLIC_CORPUS, TYPESAFE_SYSTEMONE, run_public_benchmark


class Reply:
    status = 200

    def __init__(self, choice: str) -> None:
        self.choice = choice
        self.closed = False

    def chunks(self) -> Iterator[bytes]:
        yield json.dumps(
            {
                "model": "jev-latest",
                "answers": {
                    "skill_candidate": {
                        "type": "choice",
                        "choice": self.choice,
                        "confidence": 0.96,
                        "probabilities": {"0": 0.02, "1": 0.96, "2": 0.02},
                    }
                },
                "usage": {"input_tokens": 40, "output_tokens": 1},
            }
        ).encode()

    def close(self) -> None:
        self.closed = True


class Transport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], Mapping[str, str], float]] = []
        self.replies: list[Reply] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> Reply:
        payload = json.loads(body)
        self.calls.append((url, payload, headers, timeout_s))
        user = payload["state"]["messages"][-1]["text"]
        reply = Reply("0" if "What installed" in user else "1")
        self.replies.append(reply)
        return reply


def test_live_entry_sends_only_pinned_public_skill_cases_and_scores_abstention() -> None:
    transport = Transport()
    report = run_public_benchmark(
        model="jev-latest", credential=lambda: "synthetic-token", transport=transport
    )
    assert len(transport.calls) == 4
    assert all(
        url == TYPESAFE_SYSTEMONE and timeout == 3.0
        for url, _, _, timeout in transport.calls
    )
    assert all(
        headers["Authorization"] == "Bearer synthetic-token"
        for _, _, headers, _ in transport.calls
    )
    assert all(
        payload["state"]["messages"][0]["text"].startswith("Synthetic PUBLIC")
        for _, payload, _, _ in transport.calls
    )
    assert all(reply.closed for reply in transport.replies)
    measured = report["jev-systemone"]["skill_selection"]
    assert measured["answered"] == 3
    assert measured["abstained"] == 1
    assert measured["coverage"] == 0.75
    assert measured["total_cost_usd"] is None
    assert report["aep-none-baseline"]["skill_selection"]["exact_accuracy"] == 0.25
    assert "synthetic-token" not in json.dumps(report)
    assert "public wiki" not in json.dumps(report)


def test_changed_corpus_is_rejected_before_credential_or_transport(tmp_path: Path) -> None:
    altered = tmp_path / "golden.json"
    altered.write_bytes(PUBLIC_CORPUS.read_bytes() + b" ")
    transport = Transport()

    def forbidden_credential() -> str:
        pytest.fail("credential read before corpus authorization")

    with pytest.raises(ValueError, match="reviewed digest"):
        run_public_benchmark(
            corpus=altered,
            model="jev-latest",
            credential=forbidden_credential,
            transport=transport,
        )
    assert transport.calls == []


def test_missing_credential_fails_before_request() -> None:
    transport = Transport()

    def missing_credential() -> str:
        raise KeyError("missing")

    with pytest.raises(KeyError):
        run_public_benchmark(
            model="jev-latest",
            credential=missing_credential,
            transport=transport,
        )
    assert transport.calls == []


def test_a_tunnelled_self_hosted_endpoint_is_used_and_plain_lan_http_is_refused() -> None:
    """A self-hosted SystemOne service (Laya) is reached through an SSH tunnel
    on loopback; plain HTTP to a LAN address would carry the token in clear,
    so it is refused before the credential is read."""
    transport = Transport()
    tunnel = "http://127.0.0.1:18000/v1/systemone"
    run_public_benchmark(
        model="laya-rl-agent", credential=lambda: "synthetic-token",
        transport=transport, endpoint=tunnel,
    )
    assert transport.calls and all(url == tunnel for url, _, _, _ in transport.calls)

    def forbidden_credential() -> str:
        pytest.fail("credential read for a refused endpoint")

    with pytest.raises(ValueError):
        run_public_benchmark(
            model="laya-rl-agent", credential=forbidden_credential, transport=Transport(),
            endpoint="http://172.25.228.141:8000/v1/systemone",
        )


def test_the_skills_corpus_is_pinned_and_sends_real_descriptions() -> None:
    from evaluation.jev_live import SKILLS_CORPUS

    transport = Transport()
    run_public_benchmark(
        corpus=SKILLS_CORPUS, model="laya-rl-agent", credential=lambda: "synthetic-token",
        transport=transport,
    )
    assert len(transport.calls) == 26
    _, payload, _, _ = transport.calls[0]
    criteria = payload["questions"]["skill_candidate"]["criteria"]
    assert len(criteria) == 9                       # preserve + eight installed commands
    assert any("SDE weekly report" in text for text in criteria.values())
    assert not any(text.startswith("Synthetic installed") for text in criteria.values())
