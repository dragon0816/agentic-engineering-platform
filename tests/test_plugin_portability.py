"""The installer ownership check also works on the supported Python 3.11 API."""

import sys
from pathlib import Path

import pytest

from plugins.package import PluginStageError, owned_path


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions")
def test_junction_check_does_not_require_python_312_path_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _winapi

    # The redirect remains inside the workspace, so resolved containment alone
    # cannot distinguish this other component's data from the plugin's files.
    target = tmp_path / "other-component"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_bytes(b"synthetic component data")
    alias = tmp_path / "plugin-folder"
    _winapi.CreateJunction(str(target), str(alias))
    monkeypatch.setattr(Path, "is_junction", None, raising=False)
    with pytest.raises(PluginStageError) as refused:
        owned_path(tmp_path, alias / "keep.txt")
    assert refused.value.code == "plugin_path_invalid"
    assert sentinel.read_bytes() == b"synthetic component data"
