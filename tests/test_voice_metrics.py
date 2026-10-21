from typing import Any

from benchmarks.voice_to_knowledge.metrics import score


def test_known_edit_distances() -> None:
    result = score("a b c", "a x c d")
    assert result["raw"]["wer"] == {"edits": 2, "reference_units": 3, "rate": 2 / 3}
    assert score("kitten", "sitting")["raw"]["cer"]["edits"] == 3


def test_mixed_tokens_and_raw_normalized_separation() -> None:
    result = score("測試 Wi-Fi 8。", "測試 wi-fi 8")
    assert result["normalized"]["mer"]["rate"] == 0
    assert result["raw"]["cer"]["edits"] > 0
    assert result["normalized"]["mer"]["reference_units"] == 4


def test_empty_reference_never_hides_insertions() -> None:
    result = score("", "Thank you")
    assert result["normalized"]["wer"]["rate"] is None
    assert result["normalized"]["wer"]["edits"] == 2
    assert result["silence_hallucination"] is True
    assert score("", "")["silence_hallucination"] is False


def test_term_precision_recall_with_false_positives_and_repeats() -> None:
    terms = score("UWB UWB CMP180", "UWB Qualcomm")["terms"]
    assert terms["tp"] == 1 and terms["fp"] == 1 and terms["fn"] == 2
    assert terms["precision"] == 0.5 and terms["recall"] == 1 / 3
    assert score("x", "y")["terms"]["precision"] is None
    assert score("UWB", "UWBextra")["terms"]["tp"] == 0


def test_number_and_negation_diagnostics() -> None:
    result = score("不支援 180 MHz, not 8", "支援 180 MHz 7")
    assert result["diagnostics"]["reference_numbers"] == ["180", "8"]
    assert result["diagnostics"]["hypothesis_numbers"] == ["180", "7"]
    assert result["diagnostics"]["reference_negations"] == ["不", "not"]


def test_micro_summary_keeps_failures_and_undefined_silence_rate() -> None:
    from benchmarks.voice_to_knowledge.metrics import summarize

    common = dict(language="en", kind="human", split="pilot", thermal="warm")
    rows: list[dict[str, Any]] = [
        {
            **common,
            "id": "1",
            "status": "ok",
            "metrics": score("a b", "a"),
            "latency_seconds": 1.0,
            "rtf": 0.5,
        },
        {**common, "id": "2", "status": "failed"},
    ]
    result = summarize(rows)["en/human/pilot/warm"]
    assert result["attempts"] == 2 and result["failed"] == 1
    assert result["normalized"]["wer"]["rate"] == 0.5
    assert result["silence"]["rate"] is None
