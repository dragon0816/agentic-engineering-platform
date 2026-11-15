"""Build the BI overview feature package from its source in this checkout.

Run from a source checkout; this installs nothing and touches no AEP venv,
workspace or BI data. Inputs are `feature_plugins/bi_overview/manifest.json`
and exactly the worker files listed in `WORKER_FILES`. Line endings are
normalized to LF, so the same source gives the same bytes whatever the Git
checkout settings; the output is `examples/plugins/bi-overview.aep-plugin.json`.

    python scripts/build_bi_overview_plugin.py [--output PATH] [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "feature_plugins" / "bi_overview"
MANIFEST = SOURCE / "manifest.json"
WORKER_PACKAGE = "aep_plugin_bi_overview"
#: The worker files packaged, by name; nothing else in the folder is included.
WORKER_FILES = ("__init__.py", "reader.py", "worker.py")
OUTPUT = PROJECT_ROOT / "examples" / "plugins" / "bi-overview.aep-plugin.json"


def _source(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def package_bytes() -> bytes:
    """The package envelope built from this checkout's source."""
    from common.plugins import PluginManifest, PluginPackage

    manifest = PluginManifest.model_validate_json(_source(MANIFEST))
    if manifest.worker_package != WORKER_PACKAGE:
        raise SystemExit(f"the manifest's worker package is not {WORKER_PACKAGE}")
    folder = SOURCE / "worker" / WORKER_PACKAGE
    files = {f"worker/{WORKER_PACKAGE}/{name}": _source(folder / name) for name in WORKER_FILES}
    return PluginPackage.build(manifest, files).to_bytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--check", action="store_true", help="fail if the output differs instead of writing it"
    )
    args = parser.parse_args()
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    payload = package_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if args.check:
        current = args.output.read_bytes() if args.output.is_file() else b""
        if current != payload:
            raise SystemExit(f"{args.output} is not the package built from this source")
        print(f"{args.output}: up to date, sha256 {digest}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"{args.output}: {len(payload)} bytes, sha256 {digest}")


if __name__ == "__main__":
    main()
