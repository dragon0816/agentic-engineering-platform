"""Expected answers for every lab task, computed only from `data/source.json`.

Nothing here looks at an Agent's output. `expected(task, variant)` returns
the IDs, per-row values and totals a correct result must contain; the
checker compares a produced workbook with it.
"""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "data" / "source.json"
RATES = {"TWD": Decimal(1), "USD": Decimal(32), "EUR": Decimal(35)}
CENT = Decimal("0.01")
PROJECTS = ["P001", "P002", "P003", "P004", "P005"]
AS_OF = "2026-09-30"


def source() -> dict[str, Any]:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def twd(amount: str | Decimal, currency: str) -> Decimal:
    return (Decimal(amount) * RATES[currency]).quantize(CENT, rounding=ROUND_HALF_UP)


def between(value: str, start: str, end: str) -> bool:
    return start <= value <= end


def money_by(rows: list[dict[str, Any]], keys: tuple[str, ...], amount: str) -> dict[str, dict[str, str]]:
    """{"key1|key2|currency": {"amount", "twd", "count"}} for a grouped summary."""
    out: dict[str, dict[str, Any]] = defaultdict(lambda: {"amount": Decimal(0), "twd": Decimal(0), "count": 0})
    for row in rows:
        key = "|".join([*(str(row[k]) for k in keys), row["Currency"]])
        out[key]["amount"] += Decimal(row[amount])
        out[key]["twd"] += twd(row[amount], row["Currency"])
        out[key]["count"] += 1
    return {k: {"amount": str(v["amount"]), "twd": str(v["twd"]), "count": v["count"]} for k, v in out.items()}


def total_twd(rows: list[dict[str, Any]], amount: str) -> str:
    return str(sum((twd(r[amount], r["Currency"]) for r in rows), Decimal(0)))


def orders(status: str | None, start: str, end: str, customer: str | None = None,
           exclude_cancelled: bool = False) -> list[dict[str, Any]]:
    return sorted((o for o in source()["sales_orders"]
                   if between(o["OrderDate"], start, end)
                   and (status is None or o["Status"] == status)
                   and (customer is None or o["CustomerID"] == customer)
                   and not (exclude_cancelled and o["Status"] == "Cancelled")),
                  key=lambda o: o["OrderID"])


def sales_expectation(rows: list[dict[str, Any]], with_detail: bool) -> dict[str, Any]:
    out = {
        "sheet": "Details", "id_column": "OrderID",
        "ids": [o["OrderID"] for o in rows],
        "values": {o["OrderID"]: {"CustomerID": o["CustomerID"], "Currency": o["Currency"],
                                  "NetAmount": o["NetAmount"], "NetAmountTWD": str(twd(o["NetAmount"], o["Currency"])),
                                  "OrderDate": o["OrderDate"], "Status": o["Status"],
                                  "ProjectID": o["ProjectID"]}
                   for o in rows},
        "summary_by_currency": money_by(rows, (), "NetAmount"),
        "total_twd": total_twd(rows, "NetAmount"),
        "summary_total_cell": ("Summary", "B2", "Details", "I"),
    }
    if with_detail:
        for o in rows:
            out["values"][o["OrderID"]]["CustomerContact"] = o["CustomerContact"]
            out["values"][o["OrderID"]]["PaymentTerms"] = o["PaymentTerms"]
        out["missing_detail"] = sorted(f"{o['OrderID']}:{f}" for o in rows
                                       for f in ("CustomerContact", "PaymentTerms") if not o[f])
    return out


def expenses(start: str, end: str, employee: str | None = None, statuses: tuple[str, ...] | None = None,
             projects: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    return sorted((e for e in source()["expenses"]
                   if between(e["ExpenseDate"], start, end)
                   and (employee is None or e["EmployeeID"] == employee)
                   and (statuses is None or e["Status"] in statuses)
                   and (projects is None or e["ProjectID"] in projects)),
                  key=lambda e: e["ExpenseID"])


def expense_expectation(rows: list[dict[str, Any]], group: tuple[str, ...]) -> dict[str, Any]:
    return {
        "sheet": "Details", "id_column": "ExpenseID",
        "ids": [e["ExpenseID"] for e in rows],
        "values": {e["ExpenseID"]: {"EmployeeID": e["EmployeeID"], "Currency": e["Currency"], "Amount": e["Amount"],
                                    "AmountTWD": str(twd(e["Amount"], e["Currency"])), "Status": e["Status"],
                                    "ReceiptID": e["ReceiptID"], "Description": e["Description"],
                                    "MissingReceipt": e["MissingReceipt"], "ExpenseDate": e["ExpenseDate"],
                                    "Category": e["Category"], "ProjectID": e["ProjectID"]}
                   for e in rows},
        "summary_group": list(group),
        "summary": money_by(rows, group, "Amount"),
        "total_twd": total_twd(rows, "Amount"),
        "summary_total_cell": ("Summary", "B2", "Details", "I"),
    }


def quotes(start: str, end: str, customer: str | None = None, status: str | None = None,
           projects: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    return sorted((q for q in source()["quotes"]
                   if between(q["QuoteDate"], start, end)
                   and (customer is None or q["CustomerID"] == customer)
                   and (status is None or q["Status"] == status)
                   and (projects is None or q["ProjectID"] in projects)),
                  key=lambda q: q["QuoteID"])


def quote_expectation(rows: list[dict[str, Any]], group: tuple[str, ...]) -> dict[str, Any]:
    return {
        "sheet": "Quotes", "id_column": "QuoteID",
        "ids": [q["QuoteID"] for q in rows],
        "values": {q["QuoteID"]: {"CustomerID": q["CustomerID"], "Currency": q["Currency"],
                                  "Subtotal": q["Subtotal"], "DiscountPercent": q["DiscountPercent"],
                                  "NetAmount": q["NetAmount"], "NetAmountTWD": str(twd(q["NetAmount"], q["Currency"])),
                                  "Status": q["Status"], "ProjectID": q["ProjectID"], "ValidUntil": q["ValidUntil"]}
                   for q in rows},
        "lines": sorted(f"{q['QuoteID']}|{line['ProductID']}|{line['Quantity']}|{line['LineAmount']}"
                        for q in rows for line in q["Lines"]),
        "summary_group": list(group),
        "summary": money_by(rows, group, "NetAmount"),
        "total_twd": total_twd(rows, "NetAmount"),
        "summary_total_cell": ("Summary", "B2", "Quotes", "K"),
    }


def project_expectation(start: str, end: str, projects: list[str], *, include: set[str],
                        customer: str | None = None, expense_projects: tuple[str, ...] | None = None,
                        quote_status: str | None = "Accepted") -> dict[str, Any]:
    data = source()
    keep = set(projects)
    sheets: dict[str, dict[str, Any]] = {}
    sums: dict[str, dict[str, Decimal]] = {p: defaultdict(Decimal) for p in projects}
    if "Orders" in include:
        rows = [o for o in orders(None, start, end, customer, exclude_cancelled=True)
                if customer is not None or o["ProjectID"] in keep]
        sheets["Orders"] = {"id_column": "OrderID", "ids": [o["OrderID"] for o in rows],
                            "twd_column": "AmountTWD",
                            "twd": {o["OrderID"]: str(twd(o["NetAmount"], o["Currency"])) for o in rows}}
        for o in rows:
            if o["ProjectID"] in sums:
                sums[o["ProjectID"]]["OrderTWD"] += twd(o["NetAmount"], o["Currency"])
    if "Invoices" in include:
        rows = sorted((i for i in data["invoices"] if between(i["InvoiceDate"], start, end)
                       and (customer is None or i["CustomerID"] == customer)
                       and (customer is not None or i["ProjectID"] in keep)),
                      key=lambda i: i["InvoiceID"])
        sheets["Invoices"] = {"id_column": "InvoiceID", "ids": [i["InvoiceID"] for i in rows],
                              "twd_column": "BalanceTWD",
                              "twd": {i["InvoiceID"]: str(twd(i["Balance"], i["Currency"])) for i in rows}}
        for i in rows:
            if i["ProjectID"] in sums:
                sums[i["ProjectID"]]["InvoiceBalanceTWD"] += twd(i["Balance"], i["Currency"])
    if "Expenses" in include:
        rows = [e for e in expenses(start, end, statuses=("Approved",), projects=expense_projects or tuple(keep))]
        sheets["Expenses"] = {"id_column": "ExpenseID", "ids": [e["ExpenseID"] for e in rows],
                              "twd_column": "AmountTWD",
                              "twd": {e["ExpenseID"]: str(twd(e["Amount"], e["Currency"])) for e in rows}}
        for e in rows:
            if e["ProjectID"] in sums:
                sums[e["ProjectID"]]["ApprovedExpenseTWD"] += twd(e["Amount"], e["Currency"])
    if "Quotes" in include:
        rows = [q for q in quotes(start, end, customer, quote_status)
                if customer is not None or q["ProjectID"] in keep]
        sheets["Quotes"] = {"id_column": "QuoteID", "ids": [q["QuoteID"] for q in rows],
                            "twd_column": "AmountTWD",
                            "twd": {q["QuoteID"]: str(twd(q["NetAmount"], q["Currency"])) for q in rows}}
        for q in rows:
            if q["ProjectID"] in sums and q["Status"] == "Accepted":
                sums[q["ProjectID"]]["AcceptedQuoteTWD"] += twd(q["NetAmount"], q["Currency"])
    columns = ["OrderTWD", "InvoiceBalanceTWD", "ApprovedExpenseTWD", "AcceptedQuoteTWD"]
    return {
        "sheets": sheets,
        "summary_projects": {p: {c: str(sums[p][c]) for c in columns} for p in projects},
        "summary_columns": [c for c, s in zip(columns, ["Orders", "Invoices", "Expenses", "Quotes"], strict=True)
                            if s in include],
        "empty_sheets": sorted({"Orders", "Invoices", "Expenses", "Quotes"} - include),
    }


def overdue_invoices(start: str, end: str, customer: str | None = None) -> list[str]:
    return sorted(i["InvoiceID"] for i in source()["invoices"]
                  if between(i["InvoiceDate"], start, end) and (customer is None or i["CustomerID"] == customer)
                  and Decimal(i["Balance"]) > 0 and i["DueDate"] < AS_OF)


def expected(task: str, variant: str = "main") -> dict[str, Any]:
    sept = ("2026-09-01", "2026-09-30")
    aug = ("2026-08-01", "2026-08-31")
    if task in {"W01", "W04"}:
        start, end, status = (*aug, "Closed") if variant == "rerun" else (*sept, "Open")
        return sales_expectation(orders(status, start, end), with_detail=task == "W04")
    if task == "W02":
        return sales_expectation(orders(None, "2026-08-01", "2026-10-31", "C001"), with_detail=True)
    if task == "W03":
        rows = sorted((i for i in source()["invoices"] if between(i["InvoiceDate"], *sept)),
                      key=lambda i: i["InvoiceID"])
        by_project: dict[str, Decimal] = defaultdict(Decimal)
        for i in rows:
            by_project[i["ProjectID"]] += twd(i["Balance"], i["Currency"])
        return {
            "sheets": {"Invoices": {"id_column": "InvoiceID", "ids": [i["InvoiceID"] for i in rows],
                                    "twd_column": "BalanceTWD",
                                    "twd": {i["InvoiceID"]: str(twd(i["Balance"], i["Currency"])) for i in rows},
                                    "balance": {i["InvoiceID"]: i["Balance"] for i in rows}}},
            "summary_projects": {p: {"InvoiceBalanceTWD": str(by_project.get(p, Decimal(0)))} for p in PROJECTS},
            "unassigned_balance_twd": str(by_project.get("", Decimal(0))),
            "summary_columns": ["InvoiceBalanceTWD"],
            "overdue": overdue_invoices(*sept),
            "empty_sheets": ["Expenses", "Orders", "Quotes"],
        }
    if task == "D01":
        employee, (start, end) = ("E002", aug) if variant == "rerun" else ("E001", sept)
        return expense_expectation(expenses(start, end, employee), ("Status",))
    if task == "D02":
        out = expense_expectation(expenses(*sept, statuses=("Submitted", "Approved")), ())
        out["exceptions"] = sorted(e for e, v in out["values"].items() if v["MissingReceipt"])
        return out
    if task == "D03":
        out = expense_expectation(expenses(*sept, statuses=("Approved",)), ("EmployeeID", "Category"))
        out["needs_review"] = sorted(e for e, v in out["values"].items() if Decimal(v["AmountTWD"]) > 5000)
        return out
    if task == "D04":
        return expense_expectation(expenses("2026-01-01", "2026-01-31", "E006"), ("Status",))
    if task == "C01":
        customer, (start, end) = ("C002", ("2026-08-01", "2026-10-31")) if variant == "rerun" else ("C001", sept)
        return quote_expectation(quotes(start, end, customer), ("Status",))
    if task == "C02":
        out = quote_expectation(quotes(*sept), ())
        out["expired_not_accepted"] = sorted(q for q, v in out["values"].items()
                                             if v["ValidUntil"] < AS_OF and v["Status"] != "Accepted")
        out["inconsistent"] = []
        return out
    if task == "C03":
        out = quote_expectation(quotes(*sept, status="Accepted", projects=tuple(PROJECTS)), ("ProjectID",))
        by_project = {p: Decimal(0) for p in PROJECTS}
        for v in out["values"].values():
            by_project[v["ProjectID"]] += Decimal(v["NetAmountTWD"])
        out["by_project_twd"] = {p: str(v) for p, v in by_project.items()}
        return out
    if task == "C04":
        if variant == "force_exit2":
            return {"expect_no_report": True}
        return quote_expectation(quotes(*sept, status="Sent"), ("Status",))
    if task == "X01":
        start, end = aug if variant == "rerun" else sept
        return project_expectation(start, end, PROJECTS, include={"Orders", "Invoices", "Expenses", "Quotes"})
    if task == "X02":
        out = project_expectation(*sept, ["P001", "P003"], include={"Orders", "Expenses", "Quotes"},
                                  customer="C001", expense_projects=("P001", "P003"), quote_status=None)
        quote_rows = quotes(*sept, customer="C001")
        out["attention"] = sorted(
            [f"Invoices:{i}" for i in overdue_invoices("2026-01-01", AS_OF, "C001")]
            + [f"Expenses:{e['ExpenseID']}" for e in expenses(*sept, statuses=("Approved",),
                                                              projects=("P001", "P003")) if e["MissingReceipt"]]
            + [f"Quotes:{q['QuoteID']}" for q in quote_rows if q["ValidUntil"] < AS_OF and q["Status"] != "Accepted"])
        # Invoices are read for the attention rule; filling their sheet is optional.
        out["empty_sheets"] = []
        return out
    if task == "X03":
        return project_expectation("2026-10-01", "2026-10-31", ["P003"],
                                   include={"Orders", "Invoices", "Expenses", "Quotes"})
    raise KeyError(task)


TASKS = ["W01", "W02", "W03", "W04", "D01", "D02", "D03", "D04", "C01", "C02", "C03", "C04", "X01", "X02", "X03"]
VARIANTS = {"W01": ["main", "rerun"], "D01": ["main", "rerun"], "C01": ["main", "rerun"],
            "X01": ["main", "rerun"], "C04": ["main", "force_exit2"]}


def all_expected() -> dict[str, Any]:
    return {f"{t}:{v}": expected(t, v) for t in TASKS for v in VARIANTS.get(t, ["main"])}


if __name__ == "__main__":
    print(json.dumps(all_expected(), ensure_ascii=False, indent=1)[:6000])
