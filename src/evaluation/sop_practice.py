"""Practice target for SOP to Workflow (docs/phases/SOP_TO_WORKFLOW.md W1).

A small shipment-lookup site on loopback, a tracking workbook and an SOP PDF
that describes the daily routine across them:

1. open the shipment site and search one customer's orders;
2. upsert the result table into `出貨追蹤.xlsx`, sheet `出貨`, keyed by order;
3. press 「標記已通知」 on the site for every delayed order.

It reads web content, writes Excel and acts on a web page, which are the
three kinds of step a generated Workflow needs, without touching any company
system. Data is fixed so a run is reproducible; notifications live in memory
and reset with the server.

    python -m evaluation.sop_practice prepare --out <folder>
    python -m evaluation.sop_practice serve --port 8765
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HEADERS = ("訂單號", "品項", "數量", "預計出貨日", "狀態")
WORKBOOK_NAME = "出貨追蹤.xlsx"
SHEET_NAME = "出貨"
SOP_NAME = "出貨追蹤SOP.pdf"


@dataclass(frozen=True)
class Order:
    order: str
    customer: str
    item: str
    quantity: int
    ship_date: str
    status: str


ORDERS = (
    Order("SO-1001", "C001", "CMW500 校正套件", 2, "2026-10-08", "準時"),
    Order("SO-1002", "C001", "RF 線材組", 10, "2026-10-03", "延遲"),
    Order("SO-1003", "C001", "測試治具 A", 1, "2026-10-12", "準時"),
    Order("SO-1004", "C001", "電源模組", 4, "2026-10-01", "延遲"),
    Order("SO-2001", "C002", "屏蔽箱", 1, "2026-10-09", "準時"),
    Order("SO-2002", "C002", "天線耦合器", 3, "2026-10-02", "延遲"),
)


def _page(title: str, body: str) -> bytes:
    return (
        "<!doctype html><html lang=zh-Hant><head><meta charset=utf-8>"
        f"<title>{html.escape(title)}</title></head><body><h1>{html.escape(title)}</h1>"
        f"{body}</body></html>"
    ).encode()


class PracticeSite:
    """The shipment-lookup site; `url` is ready once `start` returns."""

    def __init__(self, port: int = 0) -> None:
        self.notified: set[str] = set()
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def _send(self, body: bytes, status: int = 200,
                      content_type: str = "text/html; charset=utf-8") -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802 - http.server's name
                url = urlparse(self.path)
                if url.path == "/":
                    self._send(_page("出貨查詢", (
                        "<form action=/orders method=get>"
                        "<label for=customer>客戶代碼</label> "
                        "<input id=customer name=customer> "
                        "<button type=submit>查詢</button></form>"
                    )))
                elif url.path == "/orders":
                    customer = parse_qs(url.query).get("customer", [""])[0].strip().upper()
                    self._send(_page(f"出貨查詢結果 {customer}", site._table(customer)))
                elif url.path == "/state.json":
                    body = json.dumps({"notified": sorted(site.notified)}).encode("utf-8")
                    self._send(body, content_type="application/json")
                else:
                    self._send(_page("找不到頁面", ""), status=404)

            def do_POST(self) -> None:  # noqa: N802
                if urlparse(self.path).path != "/notify":
                    self._send(_page("找不到頁面", ""), status=404)
                    return
                length = int(self.headers.get("Content-Length") or 0)
                form = parse_qs(self.rfile.read(length).decode("utf-8"))
                order = form.get("order", [""])[0]
                known = {item.order: item for item in ORDERS}
                if order in known:
                    site.notified.add(order)
                self.send_response(303)
                customer = known[order].customer if order in known else ""
                self.send_header("Location", f"/orders?customer={customer}")
                self.end_headers()

        self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> None:
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def _table(self, customer: str) -> str:
        rows = [item for item in ORDERS if item.customer == customer]
        if not rows:
            return "<p>查無訂單。</p>"
        head = "".join(f"<th>{name}</th>" for name in (*HEADERS, "通知"))
        body = []
        for item in rows:
            if item.status != "延遲":
                action = ""
            elif item.order in self.notified:
                action = "已通知"
            else:
                action = (f"<form action=/notify method=post><input type=hidden name=order "
                          f"value={item.order}><button type=submit>標記已通知</button></form>")
            cells = (item.order, item.item, str(item.quantity), item.ship_date, item.status)
            body.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells)
                        + f"<td>{action}</td></tr>")
        return (f"<table id=orders><thead><tr>{head}</tr></thead>"
                f"<tbody>{''.join(body)}</tbody></table>")


def write_workbook(path: Path) -> Path:
    """The tracking workbook as a person keeps it: one order already tracked
    with an old status, and one from another customer that must survive."""
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = SHEET_NAME
    sheet.append([*HEADERS, "備註"])
    sheet.append(["SO-1001", "CMW500 校正套件", 2, "2026-10-08", "備料中", "客戶催過一次"])
    sheet.append(["SO-0999", "舊訂單", 1, "2026-09-20", "已出貨", ""])
    book.save(path)
    return path


SOP_HTML = """<!doctype html><html lang=zh-Hant><head><meta charset=utf-8>
<title>出貨追蹤 SOP</title><style>body{font-family:'Microsoft JhengHei',sans-serif;
margin:40px;line-height:1.7} h1{font-size:22px} li{margin:6px 0}</style></head><body>
<h1>每日出貨追蹤 SOP</h1>
<p>負責人：業務助理。頻率：每個工作日上午。</p>
<ol>
<li>打開出貨查詢網站（網址由 IT 提供），在「客戶代碼」欄位輸入要追蹤的客戶代碼，按「查詢」。</li>
<li>把查詢結果表格中的每一筆訂單，更新到 Excel 檔「出貨追蹤.xlsx」的「出貨」工作表：
以「訂單號」為準，已存在的訂單更新品項、數量、預計出貨日與狀態；不存在的訂單新增一列。
不要刪除其他訂單，也不要改「備註」欄。</li>
<li>狀態為「延遲」且尚未通知的訂單，在網站上按該列的「標記已通知」。</li>
<li>完成後確認 Excel 已存檔。</li>
</ol>
<p>注意：不要修改網站上狀態為「準時」的訂單。</p>
</body></html>"""


#: How long printing the SOP may take before it counts as failed.
PRINT_TIMEOUT_SECONDS = 120.0
#: How long a browser that exited is still given to leave a PDF behind (the
#: process started may be a launcher that handed off and exited at once).
PRINT_AFTER_EXIT_SECONDS = 5.0


def _complete_pdf(path: Path) -> bytes | None:
    """The file's bytes once they form a whole PDF, otherwise None."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF"):
        return data
    return None


def _stop_printer(process: subprocess.Popen[bytes]) -> None:
    """End the browser and its helper processes; the PDF is already read."""
    if process.poll() is None:
        if sys.platform == "win32":
            # While the main process is alive, /T reaches the helpers too.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover - a wedged browser
        process.kill()


def write_sop_pdf(path: Path, browser: str | None = None) -> Path:
    """Print the SOP to PDF with the installed Edge or Chrome, headless.

    The PDF being complete is what is waited for, not the browser exiting.
    Measured on 2026-10-07: headless Edge writes this PDF within about six
    seconds, then often stays alive for tens of seconds more and sometimes
    never exits, so waiting for the process timed out although the PDF was
    long finished. Once the file is a whole PDF and reads the same twice, it
    is taken and the browser is stopped. The PDF is printed into the
    temporary folder and only then written to `path`, so `path` never holds
    a partial file.

    Removing the throwaway profile is best effort, as in
    `Browser.discard_profile`: helper processes can still hold it for a
    moment, and a print that succeeded must not fail over a temporary folder.
    """
    from integrations.browser import browser_path

    executable = browser or browser_path()
    if executable is None:
        raise RuntimeError("no Chromium browser is installed to print the SOP")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        source = Path(folder) / "sop.html"
        source.write_text(SOP_HTML, encoding="utf-8")
        printed = Path(folder) / "sop.pdf"
        process = subprocess.Popen(
            [executable, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={Path(folder) / 'profile'}",
             f"--print-to-pdf={printed}", source.as_uri()],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        data: bytes | None = None
        try:
            deadline = time.monotonic() + PRINT_TIMEOUT_SECONDS
            exited_at: float | None = None
            previous: bytes | None = None
            while time.monotonic() < deadline:
                current = _complete_pdf(printed)
                if current is not None and current == previous:
                    data = current
                    break
                previous = current
                if process.poll() is not None:
                    exited_at = exited_at or time.monotonic()
                    if time.monotonic() - exited_at > PRINT_AFTER_EXIT_SECONDS:
                        break
                time.sleep(0.2)
        finally:
            _stop_printer(process)
    if data is None:
        raise RuntimeError("the browser did not write the SOP PDF")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def prepare(folder: Path) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    return write_workbook(folder / WORKBOOK_NAME), write_sop_pdf(folder / SOP_NAME)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation.sop_practice")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare").add_argument("--out", type=Path, required=True)
    commands.add_parser("serve").add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        workbook, sop = prepare(args.out)
        print(f"wrote {workbook}\nwrote {sop}")
        return 0
    site = PracticeSite(args.port)
    print(f"practice site at {site.url} (Ctrl+C stops it)")
    try:
        site._server.serve_forever()
    except KeyboardInterrupt:
        site.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
