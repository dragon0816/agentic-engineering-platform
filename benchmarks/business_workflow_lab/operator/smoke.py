"""Smoke-check the three mocks and the templates before any Agent task.

  python operator/smoke.py [--browser]

Checks the SAP-like site over HTTP (and, with --browser, in a real Edge
window through Playwright), the quote CLI through real subprocesses, and the
Expense desktop app through its own Tk widgets. Every expected count comes
from `expected.py`, not from the mocks.
"""

from __future__ import annotations

import argparse
import csv
import http.cookiejar
import io
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(HERE))
from check import template_checks  # noqa: E402
from expected import expected  # noqa: E402
from reset import events, reset  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: Any = "") -> None:
    RESULTS.append((name, ok, str(detail)[:200]))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:160]}", flush=True)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Site:
    def __init__(self, base: str) -> None:
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def get(self, path: str) -> tuple[str, str]:
        with self.opener.open(self.base + path, timeout=30) as reply:
            return reply.geturl(), reply.read().decode("utf-8-sig")

    def login(self, password: str = "Lab#2026") -> tuple[str, str]:
        body = urllib.parse.urlencode({"username": "lab.analyst", "password": password, "next": "/orders"})
        with self.opener.open(self.base + "/login", data=body.encode(), timeout=30) as reply:
            return reply.geturl(), reply.read().decode("utf-8")


def total(page: str) -> int:
    found = re.search(r"Total: <strong>(\d+)</strong>", page)
    return int(found.group(1)) if found else -1


def smoke_sap(browser: bool) -> None:
    port = free_port()
    server = subprocess.Popen([sys.executable, str(LAB / "sap_mock" / "server.py"), "--port", str(port)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(base + "/login", timeout=1).read()
                break
            except OSError:
                time.sleep(0.1)
        reset(label="smoke-sap")
        site = Site(base)
        url, _ = site.get("/orders")
        record("SAP: unauthenticated request goes to login", "/login" in url, url)
        url, page = site.login("wrong")
        record("SAP: wrong password is refused", "login-error" in page)
        url, _ = site.login()
        record("SAP: login works", url.endswith("/orders"), url)
        sept = expected("W01")
        query = "/orders?" + urllib.parse.urlencode({"from": "2026-09-01", "to": "2026-09-30", "status": "Open"})
        _, first = site.get(query)
        record("SAP: Sept Open total matches expected", total(first) == len(sept["ids"]), total(first))
        _, second = site.get(query + "&page=2")
        ids = re.findall(r"class='doc-link'>(\d+)<", first) + re.findall(r"class='doc-link'>(\d+)<", second)
        record("SAP: two pages give every ID once", sorted(ids) == sorted(sept["ids"]), len(ids))
        _, page = site.get("/orders/0045000101")
        record("SAP: order detail shows CustomerContact and PaymentTerms",
               "data-field='CustomerContact'" in page and "data-field='PaymentTerms'" in page)
        _, exported = site.get("/orders/export.csv?" + urllib.parse.urlencode(
            {"from": "2026-09-01", "to": "2026-09-30", "status": "Open"}))
        rows = list(csv.DictReader(io.StringIO(exported)))
        record("SAP: CSV export has all filtered rows", sorted(r["OrderID"] for r in rows) == sorted(sept["ids"]),
               len(rows))
        _, invoices = site.get("/invoices?from=2026-09-01&to=2026-09-30")
        record("SAP: Sept invoices span two pages", total(invoices) > 10 and "next-page" in invoices, total(invoices))
        _, empty = site.get("/orders?customer=C999")
        record("SAP: empty query is a normal zero-row page", "empty-result" in empty and total(empty) == 0)
        offsets = reset(sap="expire_session_once", label="smoke-expire")
        site = Site(base)
        site.login()  # lands on /orders: the first successful query
        url, page = site.get(query + "&page=2")
        record("SAP: expire_session_once sends the next request to login", "session-expired" in page, url)
        site.login()
        _, page = site.get(query + "&page=2")
        record("SAP: re-login recovers", total(page) == len(sept["ids"]))
        kinds = [e["event"] for e in events("sap", offsets["sap"])]
        record("SAP: expiry is in the event log", "session_expired_injected" in kinds, kinds)
        reset(sap="delay_once", label="smoke-delay")
        site = Site(base)
        started = time.monotonic()
        site.login()  # the redirect to /orders is the first list
        record("SAP: delay_once delays the first list", time.monotonic() - started >= 3.5,
               round(time.monotonic() - started, 2))
        reset(label="smoke-sap-done")
        if browser:
            smoke_browser(base)
    finally:
        server.terminate()
        server.wait(10)


def smoke_browser(base: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        browser = play.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(accept_downloads=True)
        page.goto(base + "/orders")
        page.fill("#username", "lab.analyst")
        page.fill("#password", "Lab#2026")
        page.click("#login-submit")
        page.fill("#f-from", "2026-09-01")
        page.fill("#f-to", "2026-09-30")
        page.select_option("#f-status", "Open")
        page.click("#search")
        page.wait_for_selector("#result-count")
        record("SAP (Edge): filter shows the expected total",
               f"Total: {len(expected('W01')['ids'])} rows" in page.inner_text("#result-count"))
        page.click("#next-page")
        page.wait_for_selector("#results")
        record("SAP (Edge): next page works", "Page 2 of 2" in page.inner_text("#result-count"))
        page.click("a.doc-link >> nth=0")
        record("SAP (Edge): detail opens", page.is_visible("td[data-field='PaymentTerms']"))
        page.go_back()
        with page.expect_download() as download:
            page.click("#export-csv")
        path = download.value.path()
        rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
        record("SAP (Edge): CSV download has every filtered row", len(rows) == len(expected("W01")["ids"]),
               len(rows))
        browser.close()


def cli(*args: str, env_mode: str | None = None) -> subprocess.CompletedProcess[str]:
    if env_mode:
        reset(quote=env_mode, label="smoke-cli")
    return subprocess.run(["cmd", "/c", str(LAB / "quote_cli_mock" / "quote_cli.cmd"), *args],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


def smoke_cli() -> None:
    reset(label="smoke-cli")
    run = cli("--help")
    record("CLI: --help exits 0", run.returncode == 0 and "Exit codes" in run.stdout)
    run = cli("quotes", "list", "--customer", "C001", "--from", "2026-09-01", "--to", "2026-09-30", "--format", "json")
    items = json.loads(run.stdout)["items"] if run.returncode == 0 else []
    record("CLI: list C001 Sept matches expected", sorted(i["QuoteID"] for i in items) == expected("C01")["ids"],
           [i["QuoteID"] for i in items])
    record("CLI: stderr is clean on success", run.stderr == "", run.stderr)
    run = cli("quotes", "get", "Q0011", "--format", "json")
    body = json.loads(run.stdout)
    record("CLI: get has header and line_items", run.returncode == 0 and body["header"]["QuoteID"] == "Q0011"
           and len(body["line_items"]) >= 1)
    run = cli("quotes", "get", "Q9999", "--format", "json")
    record("CLI: unknown quote exits 3 with stderr only", run.returncode == 3 and run.stdout == "", run.stderr)
    run = cli("quotes", "list", "--status", "Open")
    record("CLI: bad status exits 2", run.returncode == 2, run.stderr.strip()[-80:])
    run = cli("quotes", "list", "--customer", "C999", "--format", "json")
    record("CLI: empty result exits 0 with zero items", run.returncode == 0 and json.loads(run.stdout)["count"] == 0)
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "with space" / "quotes.csv"
        run = cli("quotes", "export", "--from", "2026-09-01", "--to", "2026-09-30", "--output", str(target))
        rows = list(csv.DictReader(open(target, encoding="utf-8-sig"))) if target.exists() else []
        record("CLI: export to a path with spaces", run.returncode == 0 and len(rows) == len(expected("C02")["ids"]),
               len(rows))
    first = cli("quotes", "list", "--status", "Sent", "--format", "json", env_mode="transient_once")
    second = cli("quotes", "list", "--status", "Sent", "--format", "json")
    record("CLI: transient_once exits 4 then 0", first.returncode == 4 and second.returncode == 0,
           (first.returncode, second.returncode))
    run = cli("quotes", "list", "--format", "json", env_mode="force_exit2")
    record("CLI: force_exit2 exits 2 with a stderr reason", run.returncode == 2 and run.stdout == "", run.stderr.strip())
    reset(label="smoke-cli-done")


def smoke_expense() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox

    sys.path.insert(0, str(LAB / "expense_desktop_mock"))
    import expense_app

    shown: list[str] = []
    messagebox.showinfo = lambda title, text, **_k: shown.append(f"{title}: {text}")  # type: ignore[assignment]
    messagebox.showerror = lambda title, text, **_k: shown.append(f"ERROR {title}: {text}")  # type: ignore[assignment]
    messagebox.askyesno = lambda *_a, **_k: True  # type: ignore[assignment]
    offsets = reset(label="smoke-expense")
    root = tk.Tk()
    app = expense_app.ExpenseApp(root)
    root.update()
    app.employee.set("E001")
    app.date_from.insert(0, "2026-09-01")
    app.date_to.insert(0, "2026-09-30")
    app.query()
    want = expected("D01")["ids"]
    record("Expense: E001 Sept total matches expected", len(app.rows) == len(want), app.count_label.cget("text"))
    record("Expense: first page shows 8 rows", len(app.tree.get_children()) == 8)
    app.turn(1)
    record("Expense: page 2 shows the rest", len(app.tree.get_children()) == len(want) - 8,
           app.count_label.cget("text"))
    app.tree.selection_set(app.tree.get_children()[0])
    app.details()
    root.update()
    dialogs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    record("Expense: detail dialog opens", len(dialogs) == 1, dialogs[0].title() if dialogs else "")
    for dialog in dialogs:
        dialog.destroy()
    with tempfile.TemporaryDirectory() as folder:
        targets = iter([str(Path(folder) / "e.csv"), str(Path(folder) / "e.xlsx"), str(Path(folder) / "f.csv"),
                        str(Path(folder) / "g.csv")])
        filedialog.asksaveasfilename = lambda **_k: next(targets)  # type: ignore[assignment]
        app.export("csv")
        rows = list(csv.DictReader(open(Path(folder) / "e.csv", encoding="utf-8-sig")))
        record("Expense: CSV export has every filtered row", sorted(r["ExpenseID"] for r in rows) == sorted(want),
               len(rows))
        app.export("xlsx")
        from openpyxl import load_workbook

        sheet = load_workbook(Path(folder) / "e.xlsx")["Expenses"]
        record("Expense: Excel export has every filtered row", sheet.max_row - 1 == len(want), sheet.max_row - 1)
        reset(expense="export_fail_once", label="smoke-expense-fail")
        app.export("csv")
        record("Expense: export_fail_once writes no file", not (Path(folder) / "f.csv").exists()
               and "暫時無法寫入" in shown[-1], shown[-1])
        app.export("csv")
        record("Expense: the retry writes the file", (Path(folder) / "g.csv").exists())
    app.employee.set("E006")
    app.date_from.delete(0, "end")
    app.date_from.insert(0, "2026-01-01")
    app.date_to.delete(0, "end")
    app.date_to.insert(0, "2026-01-31")
    app.query()
    record("Expense: empty query reports zero rows", app.rows == [] and "0 筆" in shown[-1], shown[-1])
    root.destroy()
    kinds = [e["event"] for e in events("expense", offsets["expense"])]
    record("Expense: events are logged", {"query", "detail", "export", "export_failed_injected"} <= set(kinds))
    reset(label="smoke-expense-done")


def smoke_window() -> None:
    """The real app opens a desktop window a person (or a UI tool) can see."""
    proc = subprocess.Popen([sys.executable, str(LAB / "expense_desktop_mock" / "expense_app.py")])
    try:
        title = ""
        for _ in range(40):
            time.sleep(0.25)
            title = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-Process -Id {proc.pid}).MainWindowTitle"],
                capture_output=True, text=True, timeout=30).stdout.strip()
            if title:
                break
        record("Expense: a real desktop window appears", title == "Expense Viewer (synthetic lab)", title)
    finally:
        proc.terminate()
        proc.wait(10)


def smoke_templates() -> None:
    for name in ("sales", "expense", "quote", "project"):
        path = LAB / "templates" / f"{name}_template.xlsx"
        failed = [c["name"] for c in template_checks(path, path.name) if c["ok"] is False]
        record(f"Template {name}: checker accepts the pristine template", not failed, failed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true", help="also drive the site in a real Edge window")
    parser.add_argument("--no-window", action="store_true", help="skip opening the real Expense window")
    args = parser.parse_args()
    smoke_templates()
    smoke_sap(args.browser)
    smoke_cli()
    smoke_expense()
    if not args.no_window:
        smoke_window()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} smoke checks passed")
    out = LAB / "operator" / "state" / "smoke.json"
    out.write_text(json.dumps([{"check": n, "ok": ok, "detail": d} for n, ok, d in RESULTS],
                              ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
