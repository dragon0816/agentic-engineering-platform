"""Build the LLM Wiki feature plugin package from its source in this checkout.

The package is what an AEP owner installs on the Plugins page to update the
LLM Wiki maintenance without updating AEP (Plugin API 1.2, in-process; the Host
loads it at its next start). Inputs are `feature_plugins/llm_wiki/plugin.json`
and every file below its `python/` (Python caches excluded). Line endings are
normalized to LF, so the same source gives the same bytes whatever the Git
checkout settings. This installs nothing and touches no AEP venv or workspace.

    python scripts/build_llm_wiki_plugin.py [--output PATH] [--check]

`--check` fails when PATH is not exactly the package this source builds.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "feature_plugins" / "llm_wiki"
MANIFEST = SOURCE / "plugin.json"
OUTPUT = PROJECT_ROOT / "dist" / "llm-wiki.aep-plugin.json"


def _source(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _shipped(path: Path) -> bool:
    return path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"


def package_bytes() -> bytes:
    """The package envelope built from this checkout's source."""
    from common.plugins import PluginManifest, PluginPackage

    manifest = PluginManifest.model_validate_json(_source(MANIFEST))
    if manifest.in_process is None:
        raise SystemExit("plugin.json does not declare an in-process feature")
    files = {
        path.relative_to(SOURCE).as_posix(): _source(path)
        for path in sorted((SOURCE / "python").rglob("*"))
        if _shipped(path)
    }
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
