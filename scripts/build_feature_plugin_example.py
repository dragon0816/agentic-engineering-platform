"""Build the synthetic Hello feature package from the integration-test fixture.

Run from a source checkout; this does not install anything or touch AEP's venv.
The worker has one canonical source in tests/fixtures/plugins/worker.py.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def example_bytes() -> bytes:
    from plugin_fixture_helpers import build_package

    from common.plugins import PluginPackage, PluginPage, TextBlock

    package = build_package("demo-hello")
    page = package.manifest.pages[0]
    example_page = PluginPage(
        page_id=page.page_id,
        title="Hello Plugin",
        blocks=(
            TextBlock(kind="text", text="本機測試 plugin；只使用合成資料。"),
            *page.blocks[1:],
        ),
    )
    manifest = package.manifest.model_copy(
        update={
            "title": "Hello Plugin 測試",
            "description": (
                "Generic feature-plugin demo. Synthetic local notes only; no company data."
            ),
            "pages": (example_page,),
        }
    )
    return PluginPackage.build(manifest, {item.path: item.raw for item in package.files}).to_bytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "examples/plugins/hello.aep-plugin.json"
    )
    args = parser.parse_args()
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    sys.path.insert(1, str(PROJECT_ROOT / "tests"))
    payload = example_bytes()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"{args.output}: {len(payload)} bytes, sha256 {hashlib.sha256(payload).hexdigest()}")


if __name__ == "__main__":
    main()
