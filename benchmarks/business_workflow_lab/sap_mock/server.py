"""SAP-like enterprise query site (synthetic; not a copy of any SAP interface).

Server-rendered HTML only: login, Customers, Sales Orders and Invoices list
pages with filters, sorting and 10-row pages, document detail pages and a CSV
export of the whole filtered result. There is no JSON API.

The fault mode is read from `operator/state/sap_fault.json` on every request
so the operator can set it before a task without restarting:
  normal               nothing injected
  expire_session_once  after the first successful query, the next protected
                       request finds the session expired (once)
  delay_once           the first list query takes 4 seconds (once)

Events go to `operator/state/sap_events.jsonl`; they are the operator's
evidence and are not shown to the Agent.

Run:  python sap_mock/server.py [--port 8810] [--host 127.0.0.1]
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import secrets
import threading
import time
import urllib.parse
from datetime import datetime
from decimal import Decimal
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

LAB = Path(__file__).resolve().parents[1]
DATA = LAB / "operator" / "data" / "source.json"
STATE = LAB / "operator" / "state"
FAULT = STATE / "sap_fault.json"
EVENTS = STATE / "sap_events.jsonl"
USERNAME = "lab.analyst"  # the simulated signed-in Windows user
PAGE_SIZE = 10
LOCK = threading.Lock()

ORDER_COLUMNS = [
    "OrderID",
    "CustomerID",
    "CustomerName",
    "ProjectID",
    "OrderDate",
    "Status",
    "Currency",
    "NetAmount",
]
INVOICE_COLUMNS = [
    "InvoiceID",
    "OrderID",
    "CustomerID",
    "ProjectID",
    "InvoiceDate",
    "DueDate",
    "Currency",
    "Amount",
    "PaidAmount",
    "Balance",
]
CUSTOMER_COLUMNS = ["CustomerID", "CustomerName", "Country"]
LISTS = {
    "orders": {
        "title": "Sales Orders",
        "key": "sales_orders",
        "columns": ORDER_COLUMNS,
        "date": "OrderDate",
        "statuses": ["Open", "Closed", "Cancelled"],
        "id": "OrderID",
    },
    "invoices": {
        "title": "Invoices",
        "key": "invoices",
        "columns": INVOICE_COLUMNS,
        "date": "InvoiceDate",
        "statuses": [],
        "id": "InvoiceID",
    },
    "customers": {
        "title": "Customers",
        "key": "customers",
        "columns": CUSTOMER_COLUMNS,
        "date": None,
        "statuses": [],
        "id": "CustomerID",
    },
}


def load() -> dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def fault() -> dict[str, Any]:
    try:
        return json.loads(FAULT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"mode": "normal"}


def save_fault(state: dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    FAULT.write_text(json.dumps(state), encoding="utf-8")


def event(kind: str, **detail: Any) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    line = {"at": datetime.now().isoformat(timespec="milliseconds"), "event": kind, **detail}
    with LOCK, EVENTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")


SESSIONS: dict[str, tuple[str, object]] = {}

STYLE = """
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1d2731}
header{background:#0a3d62;color:#fff;padding:8px 16px;display:flex;gap:16px;align-items:center}
header a{color:#fff;text-decoration:none} header .grow{flex:1}
main{padding:16px} table{border-collapse:collapse;background:#fff;width:100%}
th,td{border:1px solid #c9d2db;padding:4px 8px;font-size:14px;text-align:left}
th{background:#e3e9ef} td.num{text-align:right}
form.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin-bottom:12px}
form.filters label{display:flex;flex-direction:column;font-size:12px}
.msg{padding:8px;margin:8px 0;border-radius:4px} .error{background:#fde2e1;color:#8a1c14}
.info{background:#e6f1fb} #loading{display:none;color:#0a3d62}
.pager{margin-top:8px;display:flex;gap:8px;align-items:center}
"""


def page(title: str, body: str, user: str | None = None) -> str:
    nav = ""
    if user:
        nav = (
            "<a href='/customers'>Customers</a><a href='/orders'>Sales Orders</a>"
            "<a href='/invoices'>Invoices</a><span class='grow'></span>"
            f"<span id='current-user'>{html.escape(user)}</span>"
            "<form method='post' action='/logout' style='margin:0'>"
            "<button type='submit' id='logout'>Log out</button></form>"
        )
    return (
        f"<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)} - Lab ERP</title><style>{STYLE}</style></head>"
        f"<body><header><strong>Lab ERP (synthetic)</strong>{nav}</header>"
        f"<main><h1>{html.escape(title)}</h1>{body}</main>"
        "<script>document.querySelectorAll('form.filters').forEach(f=>f.addEventListener("
        "'submit',()=>{document.getElementById('loading').style.display='block'}))</script>"
        "</body></html>"
    )


def matches(row: dict[str, Any], spec: dict[str, Any], query: dict[str, str]) -> bool:
    customer = query.get("customer", "").strip()
    project = query.get("project", "").strip()
    status = query.get("status", "").strip()
    start, end = query.get("from", "").strip(), query.get("to", "").strip()
    if customer and row.get("CustomerID") != customer:
        return False
    if project and row.get("ProjectID") != project:
        return False
    if status and row.get("Status") != status:
        return False
    if spec["date"]:
        when = row[spec["date"]]
        if start and when < start:
            return False
        if end and when > end:
            return False
    return True


def filtered(name: str, query: dict[str, str]) -> list[dict[str, Any]]:
    spec = LISTS[name]
    rows = [r for r in load()[spec["key"]] if matches(r, spec, query)]
    sort = query.get("sort") or spec["id"]
    if sort not in spec["columns"]:
        sort = spec["id"]
    numeric = sort in {"NetAmount", "Amount", "PaidAmount", "Balance"}
    rows.sort(
        key=lambda r: (Decimal(r[sort]) if numeric else str(r.get(sort, "")), r[spec["id"]]),
        reverse=query.get("dir") == "desc",
    )
    return rows


class Handler(BaseHTTPRequestHandler):
    server_version = "LabERP/1.0"

    def _client(self) -> str:
        return self.headers.get("User-Agent", "")[:160]

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib name
        pass

    # -- plumbing -----------------------------------------------------------
    def _send(
        self,
        status: int,
        body: str,
        content_type: str = "text/html; charset=utf-8",
        headers: dict[str, str] | None = None,
    ) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _session(self) -> tuple[str | None, str | None]:
        """The signed-in user, if the session was made since the operator's
        last reset: every task starts signed out, as a fresh day would."""
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie["labsid"].value if "labsid" in cookie else None
        held = SESSIONS.get(token or "")
        if held is None or held[1] != fault().get("epoch"):
            return token, None
        return token, held[0]

    def _form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}

    def _guard(self, path: str) -> str | None:
        """The signed-in user, or None after redirecting to the login page."""
        token, user = self._session()
        if user is None:
            event("unauthenticated", path=path, ua=self._client())
            self._redirect("/login?next=" + urllib.parse.quote(path))
            return None
        state = fault()
        if (
            state.get("mode") == "expire_session_once"
            and state.get("armed")
            and not state.get("fired")
        ):
            SESSIONS.pop(token or "", None)
            state["fired"] = True
            save_fault(state)
            event("session_expired_injected", path=path, ua=self._client())
            self._redirect("/login?expired=1&next=" + urllib.parse.quote(path))
            return None
        return user

    def _query_done(self) -> None:
        state = fault()
        if state.get("mode") == "expire_session_once" and not state.get("armed"):
            state["armed"] = True
            save_fault(state)

    # -- routes -------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        url = urllib.parse.urlsplit(self.path)
        query = {
            k: v[0] for k, v in urllib.parse.parse_qs(url.query, keep_blank_values=True).items()
        }
        path = url.path.rstrip("/") or "/"
        if path == "/login":
            return self._login_page(query)
        if path == "/":
            return self._redirect("/orders")
        full = self.path
        user = self._guard(full)
        if user is None:
            return
        parts = path.strip("/").split("/")
        if parts[0] in LISTS and len(parts) == 1:
            return self._list(parts[0], query, user)
        if parts[0] in LISTS and len(parts) == 2 and parts[1] == "export.csv":
            return self._export(parts[0], query)
        if parts[0] in LISTS and len(parts) == 2:
            return self._detail(parts[0], urllib.parse.unquote(parts[1]), user)
        if parts[0] == "projects" and len(parts) == 2:
            return self._project(parts[1], user)
        self._send(404, page("找不到頁面", "<p class='msg error'>找不到這個頁面 (404)。</p>", user))

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        path = urllib.parse.urlsplit(self.path).path
        if path == "/login":
            form = self._form()
            target = form.get("next") or "/orders"
            if not target.startswith("/") or target.startswith("//"):
                target = "/orders"
            # Company single sign-on, simulated (owner, 2026-10-06): the
            # signed-in Windows user continues with one click, no password.
            if form.get("sso") == "company":
                token = secrets.token_hex(16)
                SESSIONS[token] = (USERNAME, fault().get("epoch"))
                event("login", ok=True, ua=self._client())
                return self._redirect(target, f"labsid={token}; HttpOnly; Path=/; SameSite=Lax")
            event("login", ok=False, ua=self._client())
            return self._login_page({"failed": "1", "next": target})
        if path == "/logout":
            token, _ = self._session()
            SESSIONS.pop(token or "", None)
            event("logout")
            return self._redirect("/login", "labsid=; Max-Age=0; Path=/")
        self._send(404, page("找不到頁面", "<p class='msg error'>找不到這個頁面 (404)。</p>"))

    def _login_page(self, query: dict[str, str]) -> None:
        notes = ""
        if query.get("expired"):
            notes += (
                "<p class='msg error' id='session-expired'>工作階段已逾時，請重新登入。 (Session "
                "expired)</p>"
            )
        if query.get("failed"):
            notes += (
                "<p class='msg error' id='login-error'>登入失敗，請再試一次。 (Sign-in failed)</p>"
            )
        body = (
            f"{notes}<p>此系統使用公司帳號自動登入。 This site uses your company account.</p>"
            "<form method='post' action='/login' id='login-form'>"
            f"<input type='hidden' name='next' value='{html.escape(query.get('next', '/orders'))}'>"
            "<input type='hidden' name='sso' value='company'>"
            "<button type='submit' id='login-submit'>使用公司帳號登入 Continue with company account"
            "</button></form>"
        )
        self._send(200, page("Sign in", body))

    def _list(self, name: str, query: dict[str, str], user: str) -> None:
        spec = LISTS[name]
        state = fault()
        if state.get("mode") == "delay_once" and not state.get("fired"):
            state["fired"] = True
            save_fault(state)
            event("delay_injected", list=name)
            time.sleep(4)
        rows = filtered(name, query)
        total = len(rows)
        pages = max(1, -(-total // PAGE_SIZE))
        try:
            number = min(max(1, int(query.get("page", "1"))), pages)
        except ValueError:
            number = 1
        shown = rows[(number - 1) * PAGE_SIZE : number * PAGE_SIZE]
        event(
            "query",
            list=name,
            filters={k: v for k, v in query.items() if k != "page"},
            page=number,
            total=total,
            ua=self._client(),
        )
        self._query_done()
        keep = {k: v for k, v in query.items() if k != "page" and v}

        def link(n: int) -> str:
            return f"/{name}?" + urllib.parse.urlencode({**keep, "page": n})

        status_select = ""
        if spec["statuses"]:
            options = "".join(
                f"<option value='{s}'{' selected' if query.get('status') == s else ''}>{s}</option>"
                for s in spec["statuses"]
            )
            status_select = (
                f"<label for='f-status'>Status<select id='f-status' name='status'>"
                f"<option value=''>(all)</option>{options}</select></label>"
            )
        date_inputs = ""
        if spec["date"]:
            date_inputs = (
                f"<label for='f-from'>Date from (YYYY-MM-DD)<input id='f-from' name='from' "
                f"value='{html.escape(query.get('from', ''))}'></label>"
                f"<label for='f-to'>Date to (YYYY-MM-DD)<input id='f-to' name='to' "
                f"value='{html.escape(query.get('to', ''))}'></label>"
            )
        sort_options = "".join(
            f"<option value='{c}'{' selected' if query.get('sort') == c else ''}>{c}</option>"
            for c in spec["columns"]
        )
        project_input = ""
        if name != "customers":
            project_input = (
                f"<label for='f-project'>Project<input id='f-project' name='project' "
                f"value='{html.escape(query.get('project', ''))}'></label>"
            )
        filters = (
            f"<form class='filters' method='get' action='/{name}' id='filter-form'>"
            f"<label for='f-customer'>Customer ID<input id='f-customer' name='customer' "
            f"value='{html.escape(query.get('customer', ''))}'></label>"
            f"{project_input}{date_inputs}{status_select}"
            f"<label for='f-sort'>Sort by<select id='f-sort' "
            f"name='sort'>{sort_options}</select></label>"
            f"<label for='f-dir'>Order<select id='f-dir' name='dir'><option "
            f"value='asc'>asc</option>"
            f"<option value='desc'{' selected' if query.get('dir') == 'desc' else ''}>"
            "desc</option></select></label>"
            "<button type='submit' id='search'>Search</button></form>"
            "<div id='loading'>Loading… 查詢中</div>"
        )
        export = ""
        if name != "customers":
            export = (
                f"<p><a id='export-csv' href='/{name}/export.csv?{urllib.parse.urlencode(keep)}'>"
                "Export CSV (all filtered rows)</a></p>"
            )
        count = (
            f"<p id='result-count'>Total: <strong>{total}</strong> rows · Page {number} of "
            f"{pages}</p>"
        )
        if not rows:
            table = (
                "<p class='msg info' id='empty-result'>查無資料（0 筆）。 No rows match the "
                "filters.</p>"
            )
        else:
            head = "".join(f"<th data-field='{c}'>{c}</th>" for c in spec["columns"])
            body_rows = []
            for row in shown:
                cells = []
                for column in spec["columns"]:
                    value = html.escape(str(row.get(column, "")))
                    if column == spec["id"] and name != "customers":
                        value = f"<a href='/{name}/{value}' class='doc-link'>{value}</a>"
                    css = (
                        " class='num'"
                        if column in {"NetAmount", "Amount", "PaidAmount", "Balance"}
                        else ""
                    )
                    cells.append(f"<td data-field='{column}'{css}>{value}</td>")
                body_rows.append("<tr>" + "".join(cells) + "</tr>")
            table = (
                f"<table id='results'><thead><tr>{head}</tr></thead>"
                f"<tbody>{''.join(body_rows)}</tbody></table>"
            )
        pager = "<div class='pager' id='pager'>"
        if number > 1:
            pager += f"<a id='prev-page' href='{link(number - 1)}'>‹ Previous</a>"
        pager += f"<span>Page {number} / {pages}</span>"
        if number < pages:
            pager += f"<a id='next-page' href='{link(number + 1)}'>Next ›</a>"
        pager += "</div>"
        self._send(200, page(spec["title"], filters + export + count + table + pager, user))

    def _export(self, name: str, query: dict[str, str]) -> None:
        spec = LISTS[name]
        rows = filtered(name, query)
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(spec["columns"])
        for row in rows:
            writer.writerow([row.get(c, "") for c in spec["columns"]])
        event("export", list=name, filters=query, rows=len(rows), ua=self._client())
        self._query_done()
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self._send(
            200,
            "﻿" + buffer.getvalue(),
            "text/csv; charset=utf-8",
            {"Content-Disposition": f"attachment; filename={name}_{stamp}.csv"},
        )

    def _detail(self, name: str, ident: str, user: str) -> None:
        data = load()
        spec = LISTS[name]
        row = next((r for r in data[spec["key"]] if r[spec["id"]] == ident), None)
        if row is None:
            event("detail", list=name, id=ident, found=False)
            return self._send(
                404,
                page(
                    "找不到文件",
                    f"<p class='msg error' id='not-found'>找不到文件 {html.escape(ident)}。</p>",
                    user,
                ),
            )
        event("detail", list=name, id=ident, found=True, ua=self._client())
        self._query_done()
        fields = list(spec["columns"])
        if name == "orders":
            fields += ["CustomerContact", "PaymentTerms", "SalesRep"]
        items = []
        for field in fields:
            value = html.escape(str(row.get(field, "")))
            if field == "CustomerID":
                value = f"<a href='/customers?customer={value}' id='customer-link'>{value}</a>"
            if field == "ProjectID" and value:
                value = f"<a href='/projects/{value}' id='project-link'>{value}</a>"
            if field == "OrderID" and name == "invoices":
                value = f"<a href='/orders/{value}' id='order-link'>{value}</a>"
            items.append(
                f"<tr><th scope='row'>{field}</th><td data-field='{field}'>{value}</td></tr>"
            )
        body = f"<h2>Header</h2><table id='header'>{''.join(items)}</table>"
        if name == "orders":
            line_cols = ["LineNo", "ProductID", "Quantity", "UnitPrice", "LineAmount"]
            head = "".join(f"<th>{c}</th>" for c in line_cols)
            lines = "".join(
                "<tr>"
                + "".join(
                    f"<td data-field='{c}'>{html.escape(str(line.get(c, '')))}</td>"
                    for c in line_cols
                )
                + "</tr>"
                for line in row["Lines"]
            )
            body += (
                f"<h2>Line items</h2><table "
                f"id='line-items'><thead><tr>{head}</tr></thead><tbody>{lines}</tbody></table>"
            )
        body += f"<p><a href='/{name}'>← Back to {spec['title']}</a></p>"
        self._send(200, page(f"{spec['title'][:-1]} {ident}", body, user))

    def _project(self, ident: str, user: str) -> None:
        project = next((p for p in load()["projects"] if p["ProjectID"] == ident), None)
        if project is None:
            return self._send(
                404, page("找不到專案", "<p class='msg error'>找不到專案。</p>", user)
            )
        rows = "".join(
            f"<tr><th scope='row'>{k}</th><td data-field='{k}'>{html.escape(str(v))}</td></tr>"
            for k, v in project.items()
        )
        self._send(200, page(f"Project {ident}", f"<table id='header'>{rows}</table>", user))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8810)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Lab ERP listening on http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
