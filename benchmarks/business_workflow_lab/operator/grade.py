"""Grade one task's output folder against the expected answer.

Returns the checks and the separate verdicts the report needs:
`excel_correct` (the workbook alone) is kept apart from interface evidence,
code generation, execution and workflow reuse, so one success flag cannot
hide a gap in another.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from check import (
    check,
    column_total,
    dec,
    detail_checks,
    empty_sheet_check,
    formula_checks,
    grouped_summary_check,
    ids_in,
    project_summary_check,
    table,
    template_checks,
    text,
)
from expected import expected
from openpyxl import load_workbook

TEMPLATE = {"W01": "sales", "W02": "sales", "W04": "sales", "W03": "project",
            "D01": "expense", "D02": "expense", "D03": "expense", "D04": "expense",
            "C01": "quote", "C02": "quote", "C03": "quote", "C04": "quote",
            "X01": "project", "X02": "project", "X03": "project"}
NAMED_OUTPUT = {"W01": "september_open_orders.xlsx", "D01": "E001_september_expenses.xlsx",
                "X03": "october_P003.xlsx"}
SALES_FIELDS = ("CustomerID", "Currency", "NetAmount", "NetAmountTWD", "OrderDate", "Status", "ProjectID")
EXPENSE_FIELDS = ("EmployeeID", "Currency", "Amount", "AmountTWD", "Status", "ExpenseDate", "Category", "ProjectID")
QUOTE_FIELDS = ("CustomerID", "Currency", "Subtotal", "DiscountPercent", "NetAmount", "NetAmountTWD", "Status",
                "ProjectID", "ValidUntil")


def find_workbook(output: Path, task: str, subfolder: str | None = None) -> Path | None:
    folder = output / subfolder if subfolder else output
    if not folder.is_dir():
        return None
    named = NAMED_OUTPUT.get(task)
    if named and not subfolder:
        hits = list(folder.rglob(named))
        if hits:
            return hits[0]
    candidates = [p for p in folder.rglob("*.xlsx") if not p.name.startswith("~$")
                  and (subfolder or "rerun" not in p.relative_to(folder).parts)
                  and "workflow" not in p.relative_to(folder).parts]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def all_text(path: Path) -> str:
    book = load_workbook(path)
    return "\n".join(text(c.value) for s in book for row in s.iter_rows() for c in row if c.value is not None)


def grade_workbook(task: str, variant: str, path: Path | None, reply: str, output: Path) -> list[dict[str, Any]]:
    if task == "C04" and variant == "force_exit2":
        produced = [p for p in output.rglob("*.xlsx") if "workflow" not in p.parts]
        rows = 0
        for p in produced:
            book = load_workbook(p)
            if "Quotes" in book.sheetnames:
                rows += len(table(book["Quotes"])[1])
        return [
            check("exit 2: no report with data rows was produced", rows == 0, f"{len(produced)} files, {rows} rows"),
            check("exit 2: the reply reports the CLI error", bool(re.search(r"exit\s*code\s*2|exit 2|結束代碼\s*2|"
                                                                            r"rejected the request parameters",
                                                                            reply, re.I)), reply[:300]),
        ]
    if path is None:
        return [check("an Excel deliverable exists", False, "no .xlsx in output/")]
    exp = expected(task, variant)
    template = f"{TEMPLATE[task]}_template.xlsx"
    out = [check("an Excel deliverable exists", True, str(path.name))]
    out += template_checks(path, template)
    out += formula_checks(path, exp.get("summary_total_cell"), template)
    kind = TEMPLATE[task]
    if kind == "sales":
        fields = SALES_FIELDS + (("CustomerContact", "PaymentTerms") if task in {"W02", "W04"} else ())
        out += detail_checks(path, exp, "Details", "OrderID", fields)
        out.append(_total(path, "Details", "NetAmountTWD", exp["total_twd"]))
        out.append(grouped_summary_check(path, exp["summary_by_currency"], need_amount=True))
        if task == "W01":
            order = ids_in(path, "Details", "OrderID")
            out.append(check("Details sorted by OrderID", order == sorted(order), order[:5]))
        if task == "W02":
            notes = all_text(path) + "\n" + reply
            missing = [m for m in exp["missing_detail"] if m.split(":")[0] not in notes]
            out.append(check("summary says which detail fields are missing", not missing, exp["missing_detail"]))
    elif kind == "expense":
        out += detail_checks(path, exp, "Details", "ExpenseID", EXPENSE_FIELDS + (
            ("ReceiptID", "Description", "MissingReceipt") if task in {"D02", "D03"} else ()))
        out.append(_total(path, "Details", "AmountTWD", exp["total_twd"]))
        if exp["ids"]:
            out.append(grouped_summary_check(path, exp["summary"], need_amount=task != "D02"))
        else:
            out.append(check("empty report: Details has no rows", not ids_in(path, "Details", "ExpenseID")))
        if task == "D02":
            got = sorted(set(ids_in(path, "Exceptions", "ExpenseID")))
            out.append(check("Exceptions lists exactly the missing-receipt expenses", got == exp["exceptions"],
                             {"got": got, "want": exp["exceptions"]}))
        if task == "D03":
            book = load_workbook(path)
            _, rows, _ = table(book["Details"])
            flagged = sorted(text(r.get("ExpenseID")) for r in rows if str(r.get("NeedsReview")).lower() == "true")
            out.append(check("NeedsReview true exactly when AmountTWD > 5000", flagged == exp["needs_review"],
                             {"got": flagged, "want": exp["needs_review"]}))
    elif kind == "quote":
        out += detail_checks(path, exp, "Quotes", "QuoteID", QUOTE_FIELDS)
        out.append(_total(path, "Quotes", "NetAmountTWD", exp["total_twd"]))
        book = load_workbook(path)
        if "Lines" in book.sheetnames:
            _, rows, _ = table(book["Lines"])
            got = sorted(f"{text(r.get('QuoteID'))}|{text(r.get('ProductID'))}|{int(dec(r.get('Quantity')) or 0)}|"
                         f"{dec(r.get('LineAmount'))}" for r in rows)
            out.append(check("Lines: every quote line joined to its QuoteID", got == exp["lines"],
                             {"missing": sorted(set(exp["lines"]) - set(got))[:5],
                              "extra": sorted(set(got) - set(exp["lines"]))[:5]}))
        if task == "C03":
            rows_by_project = _summary_numbers_by_key(path)
            wrong = [f"{p}: {rows_by_project.get(p)} != {v}" for p, v in exp["by_project_twd"].items()
                     if dec(v) not in rows_by_project.get(p, set())]
            out.append(check("Summary: one row per project P001-P005 with TWD totals (zero kept)", not wrong, wrong))
        elif exp["summary"]:
            out.append(grouped_summary_check(path, exp["summary"], need_amount=True))
        if task == "C02":
            findings = next(iter(output.rglob("findings.md")), None)
            body = findings.read_text(encoding="utf-8", errors="replace") if findings else ""
            out.append(check("findings.md exists", findings is not None))
            missing = [q for q in exp["expired_not_accepted"] if q not in body]
            out.append(check("findings.md names every expired, not-accepted quote", not missing, missing))
            out.append(check("findings.md: boundary quotes need a human look (Q0012 due on 09-30, Q0015 accepted)",
                             None, [line for line in body.splitlines() if "Q0012" in line or "Q0015" in line][:4]))
    else:
        for name, sheet in exp["sheets"].items():
            got = ids_in(path, name, sheet["id_column"])
            missing = sorted(set(sheet["ids"]) - set(got))
            book = load_workbook(path)
            _, rows, _ = table(book[name]) if name in book.sheetnames else ([], [], [])
            outside = sorted(text(r.get(sheet["id_column"])) for r in rows
                             if text(r.get(sheet["id_column"])) not in sheet["ids"] and text(r.get("ProjectID")))
            out.append(check(f"{name}: every expected document, none from other projects",
                             not missing and not outside and len(got) == len(set(got)),
                             {"missing": missing, "other projects": outside,
                              "duplicates": sorted({g for g in got if got.count(g) > 1})}))
            wrong = [f"{text(r.get(sheet['id_column']))}: {text(r.get(sheet['twd_column']))}" for r in rows
                     if text(r.get(sheet["id_column"])) in sheet["twd"]
                     and dec(r.get(sheet["twd_column"])) != dec(sheet["twd"][text(r.get(sheet["id_column"]))])]
            out.append(check(f"{name}: {sheet['twd_column']} values", not wrong, wrong[:8]))
        out.append(project_summary_check(path, exp["summary_projects"], exp["summary_columns"]))
        if exp.get("empty_sheets"):
            out.append(empty_sheet_check(path, exp["empty_sheets"]))
        if task == "W03":
            book = load_workbook(path)
            _, rows, _ = table(book["Exceptions"])
            overdue = sorted(text(r.get("DocumentID")) for r in rows if "overdue" in text(r.get("Reason")).lower())
            out.append(check("Exceptions: Overdue exactly for balance > 0 and due before 2026-09-30",
                             overdue == exp["overdue"], {"got": overdue, "want": exp["overdue"]}))
        if task == "X02":
            got = set(ids_in(path, "Exceptions", "DocumentID"))
            missing = [a for a in exp["attention"] if a.split(":")[1] not in got]
            out.append(check("Exceptions: every attention item by the clarified rules", not missing, missing))
    return out


def _total(path: Path, sheet: str, column: str, want: str) -> dict[str, Any]:
    got = column_total(path, sheet, column)
    return check(f"{sheet}: {column} total (independent of formulas)", got == Decimal(want), f"{got} vs {want}")


def _summary_numbers_by_key(path: Path) -> dict[str, set[Decimal]]:
    book = load_workbook(path)
    if "Summary" not in book.sheetnames:
        return {}
    out: dict[str, set[Decimal]] = {}
    for index in range(5, book["Summary"].max_row + 1):
        cells = [c.value for c in book["Summary"][index]]
        keys = [text(c) for c in cells if c is not None and dec(c) is None]
        numbers = {dec(c) for c in cells if dec(c) is not None}
        if not numbers and any(c in (None, "") for c in cells):
            numbers.add(Decimal("0.00"))
        for key in keys:
            out.setdefault(key, set()).update(numbers)
    return out


def verdict(checks: list[dict[str, Any]]) -> bool | None:
    decided = [c["ok"] for c in checks if c["ok"] is not None]
    return all(decided) if decided else None
