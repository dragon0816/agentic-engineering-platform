"""Smoke-check the three mocks and the templates before any Agent task.

  python operator/smoke.py [--browser]

Checks the SAP-like site over HTTP (and, with --browser, in a real Edge
window through Playwright), the quote CLI through real subprocesses, the Tk
Expense desktop app through its own Tk widgets and, unless --no-window, the
WinForms Expense app (expense_desktop_mock/bin/ExpenseApp.exe) driven only
through Windows UI Automation from Windows PowerShell 5.1. Every expected
count comes from `expected.py`, not from the mocks.
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


WINFORMS = LAB / "expense_desktop_mock"
WINFORMS_EXE = WINFORMS / "bin" / "ExpenseApp.exe"

# Drives ExpenseApp.exe through System.Windows.Automation only and prints one
# JSON object per observation ({"step", "value", "ms"}); smoke_winforms() judges
# them against expected.py. The UI Automation quirks it works around are
# commented inline.
UIA_SCRIPT = r'''param([int]$AppPid, [string]$CsvPath, [string]$Employee, [string]$DateFrom, [string]$DateTo)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
# Quirk: System.Windows.Automation loads its Win32/WinForms client-side proxies on
# first use by walking the call stack for the calling assembly. A PowerShell
# script frame is a DynamicMethod with no ReflectedType, so that walk throws a
# swallowed NullReferenceException and every control degrades to a nameless
# "Pane" without patterns. Making the first call from compiled code fixes it.
Add-Type -ReferencedAssemblies UIAutomationClient, UIAutomationTypes -TypeDefinition @'
using System;
using System.Collections.Concurrent;
using System.Threading;
using System.Windows.Automation;
public static class UiaBoot {
    public static readonly ConcurrentQueue<string> Errors = new ConcurrentQueue<string>();
    // InvokePattern.Invoke on a WinForms button blocks until its Click handler
    // returns, i.e. while a modal message box or dialog it opened is up. Fire it
    // on a worker thread instead and let the script carry on.
    public static void InvokeAsync(AutomationElement element) {
        ThreadPool.QueueUserWorkItem(delegate {
            try { ((InvokePattern)element.GetCurrentPattern(InvokePattern.Pattern)).Invoke(); }
            catch (Exception e) { Errors.Enqueue(element.Current.AutomationId + ": " + e.Message); }
        });
    }
    public static AutomationElement Root() {
        AutomationElement root = AutomationElement.RootElement;
        root.FindAll(TreeScope.Children, Condition.TrueCondition);
        return root;
    }
}
'@
$Root = [UiaBoot]::Root()
$AE = [System.Windows.Automation.AutomationElement]
$CT = [System.Windows.Automation.ControlType]
$TS = [System.Windows.Automation.TreeScope]

$Clock = [Diagnostics.Stopwatch]::StartNew()
function Emit($step, $value) {
    [Console]::Out.WriteLine((@{ step = $step; value = $value; ms = $Clock.ElapsedMilliseconds } | ConvertTo-Json -Compress -Depth 4))
}

function Cond($property, $value) { New-Object System.Windows.Automation.PropertyCondition($property, $value) }
function AndCond($a, $b) { New-Object System.Windows.Automation.AndCondition($a, $b) }

function Wait-Until([scriptblock]$probe, [string]$what, [int]$seconds = 15) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        $found = & $probe
        if ($found) { return $found }
        Start-Sleep -Milliseconds 150
    }
    throw "timed out waiting for $what"
}

function Find-ById($parent, [string]$id, [int]$seconds = 10) {
    # WinForms: AutomationId is the control's Name (via WM_GETCONTROLNAME).
    Wait-Until { $parent.FindFirst($TS::Descendants, (Cond $AE::AutomationIdProperty $id)) } "element $id" $seconds
}

# Windows of the app with this exact title. Owned windows (message boxes, the
# modal detail form, the Save As dialog) show up in the UIA tree as children of
# their owner window rather than of the desktop, so look one level below each
# top-level window of the process as well. A full Descendants search works but
# costs seconds per probe through the MSAA bridge.
function Find-WindowNow([string]$title) {
    $c = AndCond (Cond $AE::ProcessIdProperty $AppPid) (Cond $AE::ControlTypeProperty $CT::Window)
    foreach ($w in $Root.FindAll($TS::Children, $c)) {
        if ($w.Current.Name -eq $title) { return $w }
        foreach ($inner in $w.FindAll($TS::Children, (Cond $AE::ControlTypeProperty $CT::Window))) {
            if ($inner.Current.Name -eq $title) { return $inner }
            foreach ($deeper in $inner.FindAll($TS::Children, (Cond $AE::ControlTypeProperty $CT::Window))) {
                if ($deeper.Current.Name -eq $title) { return $deeper }
            }
        }
    }
    return $null
}

function Find-Window([string]$title, [int]$seconds = 15) {
    Wait-Until { Find-WindowNow $title } "window '$title'" $seconds
}

function Pattern($element, $pattern) { $element.GetCurrentPattern($pattern) }

function Invoke-Async($element) {
    Wait-Until { $element.Current.IsEnabled } "$($element.Current.AutomationId) to be enabled" 10 | Out-Null
    [UiaBoot]::InvokeAsync($element)
}

function Message-Text($dialog) {
    $texts = $dialog.FindAll($TS::Descendants, (Cond $AE::ControlTypeProperty $CT::Text))
    ($texts | ForEach-Object { $_.Current.Name }) -join ' '
}

function Wait-Closed([string]$title) {
    Wait-Until { -not (Find-WindowNow $title) } "'$title' to close" 10 | Out-Null
}

# Dismiss a message box by its first button (OK). Button names are localized by
# the OS UI language, so do not search for "OK".
function Dismiss($dialog, [string]$buttonName = '') {
    $title = $dialog.Current.Name
    $buttons = $dialog.FindAll($TS::Descendants, (Cond $AE::ControlTypeProperty $CT::Button))
    $target = $buttons[0]
    if ($buttonName) { foreach ($b in $buttons) { if ($b.Current.Name -eq $buttonName) { $target = $b } } }
    Invoke-Async $target
    # The owner stays disabled (IsEnabled false) until the box is really gone;
    # invoking a disabled button raises ElementNotEnabledException, whose message
    # on this machine reads "Hot key is already registered".
    Wait-Closed $title
}

function Select-ComboItem($combo, [string]$item) {
    # A DropDownList combobox has no ValuePattern. Its ListItems are already in
    # the UIA tree while collapsed, and SelectionItemPattern.Select() on one sets
    # the selection without expanding (Expand/Collapse work too but cost seconds).
    $li = Wait-Until { $combo.FindFirst($TS::Descendants,
        (AndCond (Cond $AE::ControlTypeProperty $CT::ListItem) (Cond $AE::NameProperty $item))) } "list item $item"
    (Pattern $li ([System.Windows.Automation.SelectionItemPattern]::Pattern)).Select()
    $sel = (Pattern $combo ([System.Windows.Automation.SelectionPattern]::Pattern)).Current.GetSelection()
    ($sel | ForEach-Object { $_.Current.Name }) -join ','
}

function Set-Text($element, [string]$text) {
    (Pattern $element ([System.Windows.Automation.ValuePattern]::Pattern)).SetValue($text)
    (Pattern $element ([System.Windows.Automation.ValuePattern]::Pattern)).Current.Value
}

function Value($element) {
    # A multi-line Win32 edit exposes TextPattern but no ValuePattern.
    $vp = $null
    if ($element.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$vp)) { return $vp.Current.Value }
    (Pattern $element ([System.Windows.Automation.TextPattern]::Pattern)).DocumentRange.GetText(-1)
}

function Rows($list) {
    # A Details-view ListView is a DataGrid whose rows are DataItem (not ListItem).
    $list.FindAll($TS::Children, (Cond $AE::ControlTypeProperty $CT::DataItem))
}

try {
    $main = Find-Window 'Expense Viewer (synthetic lab)' 20
    Emit 'window' $main.Current.Name
    $names = @('EmployeeFilter', 'ProjectFilter', 'DateFrom', 'DateTo', 'StatusFilter', 'QueryButton', 'ResultsList',
               'PreviousButton', 'NextButton', 'CountLabel', 'DetailsButton', 'ExportCsvButton', 'ExportExcelButton')
    # One Descendants walk, then reuse the elements: every UIA round trip through
    # the MSAA bridge costs tens of milliseconds, a FindFirst over the window ~1 s.
    $ctl = @{}
    foreach ($e in $main.FindAll($TS::Descendants, [System.Windows.Automation.Condition]::TrueCondition)) {
        $id = $e.Current.AutomationId
        if ($id -and -not $ctl.ContainsKey($id)) { $ctl[$id] = $e }
    }
    $seen = @{}
    foreach ($n in $names) {
        $e = $ctl[$n]
        $seen[$n] = if ($e) { "$($e.Current.ControlType.ProgrammaticName)|$($e.Current.Name)" } else { $null }
    }
    Emit 'controls' $seen

    Emit 'employee' (Select-ComboItem $ctl['EmployeeFilter'] $Employee)
    Emit 'date_from' (Set-Text $ctl['DateFrom'] $DateFrom)
    Emit 'date_to' (Set-Text $ctl['DateTo'] $DateTo)

    Invoke-Async $ctl['QueryButton']
    $box = Find-Window '查詢完成 Query complete'
    Emit 'query_message' (Message-Text $box)
    Dismiss $box
    $count = $ctl['CountLabel']
    Emit 'count_page1' (Wait-Until { $v = Value $count; if ($v -like 'Total * Page 1 /*') { $v } } 'page 1 count')
    $list = $ctl['ResultsList']
    Emit 'rows_page1' (Rows $list).Count

    Invoke-Async $ctl['NextButton']
    Emit 'count_page2' (Wait-Until { $v = Value $count; if ($v -like '* Page 2 /*') { $v } } 'page 2 count')
    $rows = Rows $list
    Emit 'rows_page2' $rows.Count

    $first = $rows[0]
    (Pattern $first ([System.Windows.Automation.SelectionItemPattern]::Pattern)).Select()
    Emit 'selected' $first.Current.Name
    Invoke-Async $ctl['DetailsButton']
    $detail = Find-Window "Expense detail $($first.Current.Name)"
    Emit 'detail_title' $detail.Current.Name
    Emit 'detail_receipt' (Value (Find-ById $detail 'DetailReceiptID'))
    Emit 'detail_description' (Value (Find-ById $detail 'DetailDescription'))
    Invoke-Async (Find-ById $detail 'CloseButton')
    Wait-Closed "Expense detail $($first.Current.Name)"
    Emit 'detail_closed' $true

    Invoke-Async $ctl['ExportCsvButton']
    $save = Find-Window 'Save As 另存新檔'
    # Common item dialog: the file name box is the Edit with AutomationId 1001
    # inside the "File name" combobox; the Save button has AutomationId 1.
    $fileName = Find-ById $save '1001'
    Emit 'save_default_name' (Value $fileName)
    Emit 'save_name' (Set-Text $fileName $CsvPath)
    $saveCond = AndCond (Cond $AE::AutomationIdProperty '1') (Cond $AE::ControlTypeProperty $CT::Button)
    Invoke-Async ($save.FindFirst($TS::Children, $saveCond))
    $done = Find-Window '匯出完成 Export complete'
    Emit 'export_message' (Message-Text $done)
    Dismiss $done
    Emit 'finished' $true
}
catch {
    Emit 'error' ($_.Exception.Message + ' @ ' + $_.InvocationInfo.PositionMessage)
    exit 1
}
finally {
    $err = $null
    while ([UiaBoot]::Errors.TryDequeue([ref]$err)) { Emit 'invoke_error' $err }
}
exit 0
'''


def build_winforms() -> bool:
    """Build ExpenseApp.exe with build.cmd when it is missing or older than its source."""
    source = WINFORMS / "ExpenseApp.cs"
    if WINFORMS_EXE.exists() and WINFORMS_EXE.stat().st_mtime >= source.stat().st_mtime:
        return True
    run = subprocess.run(["cmd", "/c", str(WINFORMS / "build.cmd")], capture_output=True, text=True, timeout=120)
    record("Expense WinForms: build.cmd compiles ExpenseApp.exe", run.returncode == 0 and WINFORMS_EXE.exists(),
           (run.stdout + run.stderr).strip()[-160:])
    return WINFORMS_EXE.exists()


def smoke_winforms() -> None:
    """Operate the WinForms Expense app only through Windows UI Automation."""
    if not build_winforms():
        return
    want = expected("D01")
    ids = want["ids"]
    pages = -(-len(ids) // 8)
    offsets = reset(label="smoke-winforms")
    proc = subprocess.Popen([str(WINFORMS_EXE)])
    steps: dict[str, Any] = {}
    try:
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "drive_expense.ps1"
            script.write_text(UIA_SCRIPT, encoding="utf-8-sig")  # PowerShell 5.1 needs the BOM for non-ASCII
            target = Path(folder) / "with space" / "expenses uia.csv"
            target.parent.mkdir()
            run = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script),
                 "-AppPid", str(proc.pid), "-CsvPath", str(target), "-Employee", "E001",
                 "-DateFrom", "2026-09-01", "-DateTo", "2026-09-30"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            for line in run.stdout.splitlines():
                if line.startswith("{"):
                    item = json.loads(line)
                    steps[item["step"]] = item["value"]
            record("Expense WinForms: UI Automation script ran to the end", run.returncode == 0 and "finished" in steps,
                   steps.get("error") or steps.get("invoke_error") or run.stderr.strip()[-160:])
            record("Expense WinForms: window title", steps.get("window") == "Expense Viewer (synthetic lab)",
                   steps.get("window"))
            controls = steps.get("controls") or {}
            missing = [n for n, v in controls.items() if not v or v.split("|")[1] != n]
            record("Expense WinForms: every control has its stable UIA name", len(controls) == 13 and not missing,
                   missing or controls.get("ResultsList"))
            record("Expense WinForms: EmployeeFilter set to E001 (SelectionItem)", steps.get("employee") == "E001",
                   steps.get("employee"))
            record("Expense WinForms: DateFrom / DateTo set (ValuePattern)",
                   (steps.get("date_from"), steps.get("date_to")) == ("2026-09-01", "2026-09-30"),
                   (steps.get("date_from"), steps.get("date_to")))
            record("Expense WinForms: Query message box reports the expected count",
                   steps.get("query_message") == f"查詢完成，共 {len(ids)} 筆。", steps.get("query_message"))
            record("Expense WinForms: CountLabel shows the expected total",
                   steps.get("count_page1") == f"Total {len(ids)} rows · Page 1 / {pages}", steps.get("count_page1"))
            record("Expense WinForms: page 1 shows 8 rows", steps.get("rows_page1") == min(8, len(ids)),
                   steps.get("rows_page1"))
            record("Expense WinForms: Next shows page 2 with the rest",
                   steps.get("count_page2") == f"Total {len(ids)} rows · Page 2 / {pages}"
                   and steps.get("rows_page2") == len(ids) - 8, (steps.get("count_page2"), steps.get("rows_page2")))
            chosen = steps.get("selected", "")
            values = want["values"].get(chosen, {})
            record("Expense WinForms: Details opens the selected expense",
                   chosen in ids and steps.get("detail_title") == f"Expense detail {chosen}", steps.get("detail_title"))
            record("Expense WinForms: DetailReceiptID matches the source",
                   bool(values) and steps.get("detail_receipt") == values["ReceiptID"], steps.get("detail_receipt"))
            record("Expense WinForms: DetailDescription keeps the line break",
                   bool(values) and steps.get("detail_description") == values["Description"].replace("\n", "\r\n"),
                   steps.get("detail_description"))
            record("Expense WinForms: Save As offers expenses_export.csv",
                   steps.get("save_default_name") == "expenses_export.csv", steps.get("save_default_name"))
            record("Expense WinForms: export message reports every filtered row",
                   steps.get("export_message") == f"已匯出 {len(ids)} 筆至\n{target}", steps.get("export_message"))
            with open(target, encoding="utf-8-sig", newline="") if target.exists() else io.StringIO() as handle:
                rows = list(csv.DictReader(handle))
            record("Expense WinForms: CSV export has every filtered row",
                   sorted(r["ExpenseID"] for r in rows) == sorted(ids), len(rows))
            # Byte for byte what the Tk edition writes: utf-8-sig, csv.writer, CRLF records
            # (a newline inside a quoted Description stays a bare LF, as with Python's csv).
            source = json.loads((HERE / "data" / "source.json").read_text(encoding="utf-8"))["expenses"]
            chosen_rows = sorted((e for e in source if e["ExpenseID"] in ids),
                                 key=lambda e: (e["ExpenseDate"], e["ExpenseID"]))
            columns = ("ExpenseID", "EmployeeID", "EmployeeName", "ProjectID", "ExpenseDate", "Category", "Currency",
                       "Amount", "Status", "ReceiptID", "Description", "MissingReceipt")
            buffer = io.StringIO(newline="")
            writer = csv.writer(buffer, lineterminator="\r\n")
            writer.writerow(columns)
            writer.writerows([[row[c] for c in columns] for row in chosen_rows])
            raw = target.read_bytes() if target.exists() else b""
            record("Expense WinForms: CSV bytes match the Tk edition (BOM, CRLF, quoting)",
                   raw == buffer.getvalue().encode("utf-8-sig"), raw[:20])
    finally:
        proc.kill()
        proc.wait(10)
    kinds = [e["event"] for e in events("expense", offsets["expense"])]
    record("Expense WinForms: events are logged", {"app_started", "query", "page", "detail", "export"} <= set(kinds),
           kinds)
    reset(label="smoke-winforms-done")


def smoke_templates() -> None:
    for name in ("sales", "expense", "quote", "project"):
        path = LAB / "templates" / f"{name}_template.xlsx"
        failed = [c["name"] for c in template_checks(path, path.name) if c["ok"] is False]
        record(f"Template {name}: checker accepts the pristine template", not failed, failed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true", help="also drive the site in a real Edge window")
    parser.add_argument("--no-window", action="store_true", help="skip opening the real Expense windows (Tk and WinForms)")
    args = parser.parse_args()
    smoke_templates()
    smoke_sap(args.browser)
    smoke_cli()
    smoke_expense()
    if not args.no_window:
        smoke_window()
        smoke_winforms()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} smoke checks passed")
    out = LAB / "operator" / "state" / "smoke.json"
    out.write_text(json.dumps([{"check": n, "ok": ok, "detail": d} for n, ok, d in RESULTS],
                              ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
