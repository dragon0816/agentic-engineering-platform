"""Loopback-only fictional SAP UI. Exports come from browser DOM interaction."""

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = (HERE / "mock-sap.html").read_text(encoding="utf-8")


def make_page(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    records = json.loads((HERE / "fixtures/records.json").read_text(encoding="utf-8"))
    page = destination / "index.html"
    page.write_text(HTML.replace("__RECORDS__", json.dumps(records)), encoding="utf-8")
    return page


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    make_page(args.directory)
    handler = partial(SimpleHTTPRequestHandler, directory=str(args.directory.resolve()))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
