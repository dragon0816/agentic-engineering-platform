"""Search/replace edits and the author's read-only view (CODING_AT_SCALE S1)."""

from pathlib import Path

import pytest

from harness.edits import BOM, EditRefused, FileText, apply_edits, parse_edits
from harness.repo_reader import MAX_READ_LINES, ReadRefused, RepoReader


def test_a_crlf_file_with_a_bom_is_edited_on_lf_and_written_back_as_it_was() -> None:
    style = FileText.decode("a.py", (BOM + "x = 1\r\ny = 2\r\n").encode("utf-8"))
    assert style.text == "x = 1\ny = 2\n" and style.newline == "\r\n" and style.bom
    (edit,) = parse_edits([{"path": "a.py", "old": "y = 2", "new": "y = 3\nz = 4"}])
    touched = apply_edits({"a.py": style.text}, [edit])
    assert style.encode(touched["a.py"]) == BOM + "x = 1\r\ny = 3\r\nz = 4\r\n"
    plain = FileText.decode("b.py", b"a\nb\n")
    assert plain.encode("a\r\nc\n") == "a\nc\n"


@pytest.mark.parametrize(
    ("raw", "words"),
    [("caf\xe9".encode("latin-1"), "not UTF-8"), (b"a\r\nb\nc\r\n", "mixes CRLF")],
)
def test_a_file_that_cannot_be_kept_as_it_was_is_refused(raw: bytes, words: str) -> None:
    with pytest.raises(EditRefused, match=words):
        FileText.decode("x.py", raw)


def test_an_edit_must_match_exactly_once_and_a_failed_batch_changes_nothing() -> None:
    files: dict[str, str | None] = {"a.py": "x = 1\nx = 1\ny = 2\n", "b.py": None}
    good = {"path": "a.py", "old": "y = 2", "new": "y = 5"}
    cases = [
        ({"path": "a.py", "old": "x = 1", "new": "x = 2"}, "appears 2 times"),
        ({"path": "a.py", "old": "q = 9", "new": "q = 1"}, "was not found"),
        ({"path": "c.py", "old": "", "new": "z"}, "not a file you may write"),
        ({"path": "a.py", "old": "", "new": "z"}, "already exists"),
        ({"path": "b.py", "old": "z", "new": "w"}, "does not exist yet"),
    ]
    for bad, words in cases:
        with pytest.raises(EditRefused, match=words):
            apply_edits(files, parse_edits([good, bad]))
    assert files["a.py"] == "x = 1\nx = 1\ny = 2\n"  # nothing applied
    touched = apply_edits(files, parse_edits([good, {"path": "b.py", "old": "", "new": "n = 0\n"}]))
    assert touched == {"a.py": "x = 1\nx = 1\ny = 5\n", "b.py": "n = 0\n"}
    for raw in ([], "edit", [{"path": "a.py"}], [3]):
        with pytest.raises(EditRefused):
            parse_edits(raw)


def test_later_edits_in_a_batch_see_the_earlier_ones() -> None:
    touched = apply_edits(
        {"a.py": "a\n"},
        parse_edits(
            [{"path": "a.py", "old": "a", "new": "b"}, {"path": "a.py", "old": "b", "new": "c"}]
        ),
    )
    assert touched == {"a.py": "c\n"}


def _repo(tmp_path: Path) -> RepoReader:
    root = tmp_path / "repo"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("secret")
    (root / ".env").write_text("TOKEN=x")
    (root / "src" / "pkg" / "id_rsa").write_text("key")
    body = "".join(f"        v{i} = {i}\n" for i in range(600))
    (root / "src" / "pkg" / "driver.py").write_bytes(
        (
            "TABLE = {\n" + "".join(f"    'k{i}': {i},\n" for i in range(8)) + "}\n\n\n"
            "class Driver:\n    def build(self):\n" + body + "        return 1\n\n"
            "    def send(self):\n        return 'build_op2'\n\n\ndef helper():\n    pass\n"
        )
        .replace("\n", "\r\n")
        .encode("utf-8")
    )
    (root / "README.md").write_text("Driver notes: build_op2 lives in driver.py\n")
    return RepoReader(root)


def test_the_reader_lists_outlines_reads_and_searches_but_never_shows_secrets(
    tmp_path: Path,
) -> None:
    reader = _repo(tmp_path)
    assert reader.listing(".").splitlines() == ["src/", "README.md  (44 bytes)"]
    assert reader.listing("src/pkg").splitlines()[0].startswith("src/pkg/driver.py")
    outline = reader.outline("src/pkg/driver.py")
    assert "TABLE = ...: lines 1-10" in outline
    assert "class Driver: lines 13-" in outline and "  def send: lines 617-618" in outline
    assert "def helper: lines 621-622" in outline
    first = reader.read("src/pkg/driver.py", 617, 618)
    assert (
        first
        == "617:     def send(self):\n618:         return 'build_op2'\n(lines 619-622 not shown)"
    )
    capped = reader.read("src/pkg/driver.py", 1, 10_000).splitlines()
    assert len(capped) == MAX_READ_LINES + 1 and capped[-1].startswith("(lines 401-")
    hits = reader.search("BUILD_OP2", "src/**/*.py")
    assert hits == "src/pkg/driver.py:618: return 'build_op2'"
    assert "README.md:1:" in reader.search("build_op2")
    overlay = {"src/pkg/driver.py": "def build_op2():\n    pass\n"}
    assert (
        reader.search("def build_op2", "**/*.py", overlay)
        == "src/pkg/driver.py:1: def build_op2():"
    )
    assert reader.read("src/pkg/driver.py", 1, 1, overlay).startswith("1: def build_op2")
    for bad in (".env", ".git/config", "src/pkg/id_rsa", "../x", "C:/Windows/win.ini"):
        with pytest.raises(ReadRefused):
            reader.text(bad)
    assert "secret" not in reader.search("secret") and "TOKEN" not in reader.search("TOKEN")
