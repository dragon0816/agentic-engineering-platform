"""Offline characterization of the pinned source read_file tool; no platform imports."""

import hashlib
from pathlib import Path
from types import ModuleType

FIXTURES = Path(__file__).parent / "fixtures"


def source_tools() -> ModuleType:
    source = (FIXTURES / "source_file_tools.txt").read_text(encoding="utf-8")
    assert hashlib.sha256(source.encode()).hexdigest() == (
        "75bc3346d85961d68e700266842f54b80776c811d8e9616df260aba6586aa154"
    )
    module = ModuleType("pinned_source_file_tools")
    exec(compile(source, "source_file_tools.txt", "exec"), module.__dict__)
    return module


def test_source_requires_a_path() -> None:
    assert source_tools().read_file() == "❌ 請提供檔案路徑"


def test_source_guesses_a_path_from_natural_language(tmp_path: Path) -> None:
    """The adaptation intentionally drops this guessing; pin what is being dropped."""
    target = tmp_path / "notes.txt"
    target.write_text("guessed", encoding="utf-8")
    result = source_tools().read_file(task=f"請讀取 {target}")
    assert "<pre>guessed</pre>" in result


def test_source_missing_path_and_non_file_are_informative_results(tmp_path: Path) -> None:
    module = source_tools()
    missing = tmp_path / "absent.txt"
    assert module.read_file(path=str(missing)) == f"檔案不存在：{missing}"
    assert module.read_file(path=str(tmp_path)) == f"這不是一個檔案：{tmp_path}"


def test_source_extension_gate_precedes_size_cap(tmp_path: Path) -> None:
    binary = tmp_path / "firmware.bin"
    binary.write_bytes(b"\x00" * 600_000)
    result = source_tools().read_file(path=str(binary))
    assert "無法讀取二進位檔案" in result
    assert "檔案太大" not in result


def test_source_size_cap_is_500k(tmp_path: Path) -> None:
    module = source_tools()
    big = tmp_path / "big.txt"
    big.write_bytes(b"a" * 500_001)
    assert "檔案太大" in module.read_file(path=str(big))
    exact = tmp_path / "exact.txt"
    exact.write_bytes(b"a" * 500_000)
    assert "<pre>" in module.read_file(path=str(exact))


def test_source_encoding_fallback_reaches_big5_and_latin1(tmp_path: Path) -> None:
    module = source_tools()
    chinese = tmp_path / "big5.txt"
    chinese.write_bytes("中文".encode("big5"))
    assert "<pre>中文</pre>" in module.read_file(path=str(chinese))
    arbitrary = tmp_path / "bytes.txt"
    arbitrary.write_bytes(b"\xff\xfe\x00\x01")
    result = module.read_file(path=str(arbitrary))
    assert "無法解碼" not in result
    assert "<pre>" in result


def test_source_keeps_a_utf8_bom_in_the_content(tmp_path: Path) -> None:
    """utf-8 precedes utf-8-sig in the fallback list, so the BOM is never stripped."""
    target = tmp_path / "bom.txt"
    target.write_bytes("﻿data".encode())
    assert "<pre>﻿data</pre>" in source_tools().read_file(path=str(target))


def test_source_truncates_to_max_lines(tmp_path: Path) -> None:
    target = tmp_path / "long.log"
    target.write_text("\n".join(f"line-{n}" for n in range(1, 151)), encoding="utf-8")
    result = source_tools().read_file(path=str(target), max_lines=100)
    assert "僅顯示前 100 行" in result
    assert "檔案共 150 行" in result
    assert "line-100" in result
    assert "line-101" not in result
