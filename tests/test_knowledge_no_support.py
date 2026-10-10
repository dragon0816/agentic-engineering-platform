"""A reply that only says nothing supports an answer is not validated (owner 2026-10-10)."""

from pathlib import Path

from test_knowledge_wiki_primary import _ask, _number, _procedure, _Synth, _wiki_vault

from host_runtime.knowledge_observation import KnowledgeBridgeActions, declares_no_support


def test_short_no_support_replies_are_recognised() -> None:
    for text in (
        "No provided RAW passage supports a specific Oscilloscope opportunity in "
        "Aerospace / Defense [67].",
        "No Raw passage supports any specific Automotive opportunity [66].",
        "Raw evidence does not explicitly map the analyzer to an RFIC-validation step [66].",
        "知識庫中沒有段落支持示波器在航太國防的機會 [3]。",
    ):
        assert declares_no_support(text), text


def test_substantive_answers_are_not_flagged() -> None:
    assert not declares_no_support("ZNA-K2 provides time domain TDR analysis [2].")
    long_answer = ("The CMX500 supports Wi-Fi 7 signaling tests [1]. " * 20
                   + "The Vault does not state a Wi-Fi 8 option code [3].")
    assert len(long_answer) > 700 and not declares_no_support(long_answer)
    # A gap named after the facts, not instead of them.
    late = ("CMP180 covers Wi-Fi 7 production RF tests up to 8 GHz [1]. " * 8
            + "No passage supports Wi-Fi 8 production use [2].")
    assert not declares_no_support(late)


def _validate(tmp_path: Path, write: str) -> tuple[dict[str, str], KnowledgeBridgeActions]:
    procedure = _procedure()
    model = _Synth(lambda prompt: write.format(n=_number(prompt, "ZNA-K2 | time domain")))
    record = _ask(_wiki_vault(tmp_path), procedure, model)
    actions = KnowledgeBridgeActions(lambda: {}, required_evidence=("raw_citations",),
                                     procedure=procedure)
    actions.result = {"ok": True, "record": record}
    return {c.check_id: c.status for c in actions.validate()}, actions


def test_a_cited_no_support_reply_fails_validation_so_the_harness_retries(
    tmp_path: Path,
) -> None:
    checks, actions = _validate(
        tmp_path, "No provided passage supports a ZNA option recommendation [{n}].")
    assert checks["answer_nonempty"] == "failed" and actions.no_support
    evidence = [c.evidence_ref for c in actions.validate()]
    assert "no_substantive_answer" in evidence


def test_a_real_cited_answer_still_validates(tmp_path: Path) -> None:
    checks, actions = _validate(tmp_path, "ZNA-K2 provides time domain TDR analysis [{n}].")
    assert checks["answer_nonempty"] == "passed" and not actions.no_support
