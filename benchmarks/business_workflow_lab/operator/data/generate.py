"""Generate the lab's fixed synthetic data (seed 20261006).

One JSON file, `source.json`, is the only source of truth: the SAP-like web
mock, the Expense desktop mock and the quote CLI each read their own part of
it, and `operator/expected.py` computes every task's expected answer from it.
Nothing here depends on today's date.

Run:  python benchmarks/business_workflow_lab/operator/data/generate.py
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SEED = 20261006
HERE = Path(__file__).resolve().parent
CENT = Decimal("0.01")


def money(value: Decimal | str | int) -> str:
    return str(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP))


def d(text: str) -> date:
    return date.fromisoformat(text)


CUSTOMERS = [
    {"CustomerID": "C001", "CustomerName": "Acme Precision Taiwan Ltd.", "Country": "TW"},
    {"CustomerID": "C002", "CustomerName": "台灣精密股份有限公司", "Country": "TW"},
    {"CustomerID": "C003", "CustomerName": "Northwind Components GmbH", "Country": "DE"},
    {"CustomerID": "C004", "CustomerName": "藍海電子有限公司", "Country": "TW"},
    {"CustomerID": "C005", "CustomerName": "Pacific Test Systems Inc.", "Country": "US"},
    {"CustomerID": "C006", "CustomerName": "Helios Optics B.V.", "Country": "NL"},
    # Deliberately close to C001: a name match would mix the two customers.
    {"CustomerID": "C007", "CustomerName": "Acme Precision Taiwan Limited", "Country": "TW"},
    {"CustomerID": "C008", "CustomerName": "新竹量測科技", "Country": "TW"},
]
EMPLOYEES = [
    {"EmployeeID": "E001", "EmployeeName": "陳怡君 (Yi-Chun Chen)"},
    {"EmployeeID": "E002", "EmployeeName": "Daniel Weber"},
    {"EmployeeID": "E003", "EmployeeName": "林志明"},
    {"EmployeeID": "E004", "EmployeeName": "Maria Santos"},
    {"EmployeeID": "E005", "EmployeeName": "王小華"},
    {"EmployeeID": "E006", "EmployeeName": "Kenji Sato"},
]
PROJECTS = [
    {
        "ProjectID": "P001",
        "ProjectName": "5G RF 驗證平台",
        "CustomerID": "C001",
        "OwnerEmployeeID": "E001",
    },
    {
        "ProjectID": "P002",
        "ProjectName": "Wafer Probe Upgrade",
        "CustomerID": "C002",
        "OwnerEmployeeID": "E003",
    },
    {
        "ProjectID": "P003",
        "ProjectName": "Acme 產線自動化",
        "CustomerID": "C001",
        "OwnerEmployeeID": "E002",
    },
    {
        "ProjectID": "P004",
        "ProjectName": "EMC Chamber Retrofit",
        "CustomerID": "C003",
        "OwnerEmployeeID": "E004",
    },
    {
        "ProjectID": "P005",
        "ProjectName": "Acme Limited 校正服務",
        "CustomerID": "C007",
        "OwnerEmployeeID": "E005",
    },
]
PROJECT_OF = {"C001": ["P001", "P003"], "C002": ["P002"], "C003": ["P004"], "C007": ["P005"]}
CONTACTS = {
    "C001": "Grace Lin <grace.lin@acme-precision.example>",
    "C002": "張美玲 <mei@tw-precision.example>",
    "C003": "Jonas Krüger <jk@northwind.example>",
    "C004": "",  # no contact on file: a detail field that must stay blank
    "C005": "Sam Patel <sam@pacifictest.example>",
    "C006": "Eva de Vries <eva@helios.example>",
    "C007": "Peter Ho <peter.ho@acme-limited.example>",
    "C008": "李建宏 <jh.lee@hsinchu-metrology.example>",
}
PRODUCTS = [
    ("MAT-1001", "Signal Analyzer Module", Decimal("1250.00")),
    ("MAT-1002", "RF Cable Set", Decimal("85.50")),
    ("MAT-1003", "校正服務 (Calibration)", Decimal("420.00")),
    ("MAT-1004", "Shielding Box", Decimal("2300.00")),
    ("MAT-1005", "Test Fixture 治具", Decimal("615.25")),
    ("MAT-1006", "Power Sensor", Decimal("980.00")),
    ("MAT-1007", "Software License (1y)", Decimal("1500.00")),
    ("MAT-1008", "現場安裝工時", Decimal("95.00")),
]
CURRENCY_SCALE = {"TWD": Decimal(30), "USD": Decimal(1), "EUR": Decimal("0.9")}


def lines_for(rng: random.Random, currency: str, max_lines: int) -> list[dict[str, str | int]]:
    out = []
    for product_id, name, base in rng.sample(PRODUCTS, rng.randint(1, max_lines)):
        price = (base * CURRENCY_SCALE[currency]).quantize(CENT, rounding=ROUND_HALF_UP)
        qty = rng.randint(1, 6)
        out.append(
            {
                "ProductID": product_id,
                "ProductName": name,
                "Quantity": qty,
                "UnitPrice": money(price),
                "LineAmount": money(price * qty),
            }
        )
    return out


def customer_project(rng: random.Random, customer: str) -> str:
    projects = PROJECT_OF.get(customer)
    return rng.choice(projects) if projects else ""


# Orders: (date, status, customer, currency); 20 in 2026-09 of which 14 Open.
ORDER_PLAN = [
    ("2026-08-03", "Closed", "C001", "TWD"),
    ("2026-08-07", "Closed", "C002", "USD"),
    ("2026-08-12", "Open", "C003", "EUR"),
    ("2026-08-15", "Cancelled", "C004", "TWD"),
    ("2026-08-19", "Closed", "C007", "TWD"),
    ("2026-08-22", "Open", "C005", "USD"),
    ("2026-08-27", "Closed", "C001", "USD"),
    ("2026-08-31", "Open", "C006", "EUR"),
    ("2026-09-01", "Open", "C001", "TWD"),
    ("2026-09-02", "Open", "C002", "TWD"),
    ("2026-09-03", "Closed", "C003", "EUR"),
    ("2026-09-04", "Open", "C007", "USD"),
    ("2026-09-05", "Open", "C004", "TWD"),
    ("2026-09-08", "Cancelled", "C001", "USD"),
    ("2026-09-09", "Open", "C005", "USD"),
    ("2026-09-10", "Open", "C008", "TWD"),
    ("2026-09-11", "Closed", "C002", "TWD"),
    ("2026-09-14", "Open", "C003", "EUR"),
    ("2026-09-15", "Open", "C001", "EUR"),
    ("2026-09-16", "Open", "C006", "EUR"),
    ("2026-09-18", "Closed", "C007", "TWD"),
    ("2026-09-21", "Open", "C002", "USD"),
    ("2026-09-22", "Cancelled", "C005", "USD"),
    ("2026-09-24", "Open", "C004", "TWD"),
    ("2026-09-25", "Closed", "C001", "TWD"),
    ("2026-09-28", "Open", "C008", "USD"),
    ("2026-09-30", "Open", "C007", "EUR"),
    ("2026-09-30", "Open", "C003", "TWD"),
    ("2026-10-01", "Open", "C001", "USD"),
    ("2026-10-02", "Open", "C002", "TWD"),
    ("2026-10-06", "Closed", "C003", "EUR"),
    ("2026-10-09", "Open", "C001", "TWD"),
    ("2026-10-14", "Cancelled", "C006", "USD"),
    ("2026-10-20", "Open", "C007", "TWD"),
    ("2026-10-27", "Closed", "C004", "TWD"),
    ("2026-10-31", "Open", "C001", "EUR"),
]
TERMS = ["NET10", "NET15", "NET20", "NET30", "NET5", "NET0"]

# Invoices: (invoice date, due date, paid share). The 2026-09 rows cover
# overdue, due-today, zero-balance and partial payments.
INVOICE_PLAN = [
    ("2026-08-06", "2026-08-21", "0.5"),
    ("2026-08-10", "2026-09-09", "1"),
    ("2026-08-20", "2026-09-04", "0.5"),
    ("2026-08-25", "2026-09-24", "0"),
    ("2026-08-29", "2026-09-28", "1"),
    ("2026-08-31", "2026-09-30", "0"),
    ("2026-09-01", "2026-09-16", "0"),
    ("2026-09-02", "2026-09-12", "1"),
    ("2026-09-05", "2026-09-20", "0.4"),
    ("2026-09-08", "2026-10-08", "0"),
    ("2026-09-10", "2026-09-30", "0"),
    ("2026-09-12", "2026-09-22", "0"),
    ("2026-09-15", "2026-09-30", "0.25"),
    ("2026-09-16", "2026-10-16", "1"),
    ("2026-09-18", "2026-09-28", "1"),
    ("2026-09-20", "2026-10-20", "0.6"),
    ("2026-09-22", "2026-09-27", "0.5"),
    ("2026-09-25", "2026-10-25", "0"),
    ("2026-09-30", "2026-09-30", "0"),
    ("2026-10-02", "2026-11-01", "0"),
    ("2026-10-07", "2026-10-22", "1"),
    ("2026-10-12", "2026-11-11", "0"),
    ("2026-10-20", "2026-10-30", "0.5"),
    ("2026-10-28", "2026-11-27", "0"),
]


def build_orders(rng: random.Random) -> list[dict[str, object]]:
    orders = []
    for index, (when, status, customer, currency) in enumerate(ORDER_PLAN):
        lines = lines_for(rng, currency, 3)
        for number, line in enumerate(lines, 1):
            line["LineNo"] = number * 10
            line.pop("ProductName")
        orders.append(
            {
                "OrderID": f"00450{index + 101:05d}",
                "CustomerID": customer,
                "CustomerName": next(
                    c["CustomerName"] for c in CUSTOMERS if c["CustomerID"] == customer
                ),
                "ProjectID": customer_project(rng, customer),
                "OrderDate": when,
                "Status": status,
                "Currency": currency,
                "NetAmount": money(sum(Decimal(str(x["LineAmount"])) for x in lines)),
                "CustomerContact": CONTACTS[customer],
                "PaymentTerms": rng.choice(TERMS),
                "SalesRep": rng.choice(EMPLOYEES)["EmployeeID"],
                "Lines": lines,
            }
        )
    # One C001 order has no payment terms recorded yet: a missing detail field.
    next(o for o in orders if o["OrderDate"] == "2026-10-09")["PaymentTerms"] = ""
    return orders


def build_invoices(rng: random.Random, orders: list[dict[str, object]]) -> list[dict[str, object]]:
    used: set[str] = set()
    invoices = []
    for index, (when, due, share) in enumerate(INVOICE_PLAN):
        candidates = [
            o
            for o in orders
            if o["Status"] != "Cancelled"
            and o["OrderID"] not in used
            and d(str(o["OrderDate"])) <= d(when) - timedelta(days=1)
        ]
        order = candidates[-1] if index % 3 else rng.choice(candidates)
        used.add(str(order["OrderID"]))
        if order["PaymentTerms"]:
            order["PaymentTerms"] = f"NET{(d(due) - d(when)).days}"
        amount = Decimal(str(order["NetAmount"]))
        paid = (amount * Decimal(share)).quantize(CENT, rounding=ROUND_HALF_UP)
        invoices.append(
            {
                "InvoiceID": f"00900{index + 201:05d}",
                "OrderID": order["OrderID"],
                "CustomerID": order["CustomerID"],
                "ProjectID": order["ProjectID"],
                "InvoiceDate": when,
                "DueDate": due,
                "Currency": order["Currency"],
                "Amount": money(amount),
                "PaidAmount": money(paid),
                "Balance": money(amount - paid),
            }
        )
    return invoices


# Expenses: (employee, date, category, currency, amount, status, missing receipt)
EXPENSE_PLAN = [
    # E001, 2026-09: 13 rows (two pages of 8), all three currencies approved.
    ("E001", "2026-09-01", "Travel", "TWD", "1280.00", "Approved", False),
    ("E001", "2026-09-02", "Hotel", "USD", "200.00", "Approved", False),
    ("E001", "2026-09-03", "Meals", "TWD", "450.00", "Submitted", False),
    ("E001", "2026-09-05", "Supplies", "EUR", "42.50", "Approved", False),
    ("E001", "2026-09-08", "Travel", "USD", "88.40", "Draft", False),
    ("E001", "2026-09-10", "Meals", "TWD", "620.00", "Approved", True),
    ("E001", "2026-09-12", "Hotel", "EUR", "155.00", "Rejected", False),
    ("E001", "2026-09-15", "Supplies", "TWD", "2399.00", "Submitted", False),
    ("E001", "2026-09-17", "Travel", "TWD", "3150.00", "Approved", False),
    ("E001", "2026-09-19", "Meals", "USD", "35.75", "Draft", False),
    ("E001", "2026-09-23", "Hotel", "TWD", "4200.00", "Submitted", False),
    ("E001", "2026-09-26", "Supplies", "USD", "12.30", "Rejected", False),
    ("E001", "2026-09-30", "Travel", "EUR", "60.00", "Approved", False),
    # Other employees, 2026-09.
    ("E002", "2026-09-04", "Hotel", "EUR", "180.00", "Approved", False),
    ("E002", "2026-09-09", "Meals", "TWD", "380.00", "Submitted", True),
    ("E002", "2026-09-16", "Travel", "USD", "142.00", "Approved", False),
    ("E002", "2026-09-21", "Supplies", "TWD", "999.00", "Draft", False),
    ("E002", "2026-09-29", "Travel", "TWD", "5000.01", "Rejected", False),
    ("E003", "2026-09-06", "Travel", "TWD", "8800.00", "Approved", False),
    ("E003", "2026-09-13", "Meals", "TWD", "760.00", "Submitted", False),
    ("E003", "2026-09-20", "Hotel", "USD", "120.00", "Approved", False),
    ("E003", "2026-09-27", "Supplies", "EUR", "18.20", "Submitted", False),
    ("E004", "2026-09-07", "Hotel", "USD", "156.25", "Approved", False),
    ("E004", "2026-09-18", "Meals", "TWD", "5000.00", "Approved", False),
    ("E004", "2026-09-24", "Travel", "EUR", "143.00", "Approved", False),
    ("E005", "2026-09-11", "Supplies", "TWD", "1880.00", "Approved", False),
    ("E005", "2026-09-22", "Travel", "USD", "64.90", "Submitted", False),
    ("E005", "2026-09-30", "Meals", "TWD", "300.00", "Approved", False),
    # 2026-08.
    ("E002", "2026-08-03", "Travel", "USD", "210.00", "Approved", False),
    ("E002", "2026-08-11", "Hotel", "TWD", "3600.00", "Submitted", False),
    ("E002", "2026-08-20", "Meals", "EUR", "48.00", "Approved", True),
    ("E002", "2026-08-31", "Supplies", "TWD", "455.00", "Draft", False),
    ("E003", "2026-08-14", "Travel", "TWD", "2100.00", "Approved", False),
    ("E003", "2026-08-28", "Meals", "USD", "22.00", "Rejected", False),
    ("E004", "2026-08-01", "Hotel", "EUR", "95.00", "Approved", False),
    # 2026-10.
    ("E001", "2026-10-01", "Travel", "TWD", "1500.00", "Submitted", False),
    ("E001", "2026-10-15", "Hotel", "USD", "175.00", "Approved", False),
    ("E005", "2026-10-08", "Meals", "TWD", "520.00", "Approved", False),
    ("E006", "2026-10-20", "Travel", "EUR", "310.00", "Submitted", False),
    ("E003", "2026-10-31", "Supplies", "TWD", "640.00", "Draft", False),
]
DESCRIPTIONS = {
    "Travel": ["高鐵 台北-新竹 往返", "Taxi to customer site", "機票 TPE-FRA\n含行李費"],
    "Hotel": ["客戶驗收住宿 2 晚", "Hotel near Hsinchu Science Park", "出差住宿\n(含早餐)"],
    "Meals": ["客戶餐敘", "Team dinner after install", "加班餐費"],
    "Supplies": ["治具耗材", "USB-C adapters", "RF 接頭與轉接器\nSMA x4"],
}
EMPLOYEE_PROJECTS = {
    "E001": ["P001", "P003"],
    "E002": ["P003", "P005"],
    "E003": ["P002", "P004"],
    "E004": ["P004", "P001"],
    "E005": ["P005", "P002"],
    "E006": ["P002"],
}


def build_expenses(rng: random.Random) -> list[dict[str, object]]:
    out = []
    for index, (emp, when, category, currency, amount, status, missing) in enumerate(EXPENSE_PLAN):
        out.append(
            {
                "ExpenseID": f"EXP-{index + 1:05d}",
                "EmployeeID": emp,
                "EmployeeName": next(
                    e["EmployeeName"] for e in EMPLOYEES if e["EmployeeID"] == emp
                ),
                "ProjectID": rng.choice(EMPLOYEE_PROJECTS[emp]),
                "ExpenseDate": when,
                "Category": category,
                "Currency": currency,
                "Amount": money(amount),
                "Status": status,
                "ReceiptID": "" if missing else f"RC{rng.randint(100000, 999999)}",
                "Description": rng.choice(DESCRIPTIONS[category]),
                "MissingReceipt": missing,
            }
        )
    out.sort(key=lambda e: (str(e["ExpenseDate"]), str(e["ExpenseID"])))
    return out


# Quotes: (date, valid until, status, customer, currency, discount)
QUOTE_PLAN = [
    ("2026-08-04", "2026-09-03", "Accepted", "C002", "TWD", 0),
    ("2026-08-06", "2026-09-05", "Expired", "C001", "USD", 5),
    ("2026-08-11", "2026-09-10", "Accepted", "C003", "EUR", 10),
    ("2026-08-14", "2026-09-13", "Sent", "C005", "USD", 0),
    ("2026-08-18", "2026-09-17", "Accepted", "C001", "TWD", 5),
    ("2026-08-21", "2026-09-20", "Draft", "C007", "TWD", 0),
    ("2026-08-25", "2026-09-24", "Expired", "C004", "TWD", 10),
    ("2026-08-28", "2026-09-27", "Accepted", "C007", "EUR", 5),
    ("2026-08-31", "2026-09-30", "Sent", "C002", "USD", 0),
    ("2026-09-01", "2026-09-20", "Sent", "C001", "TWD", 5),
    ("2026-09-03", "2026-10-03", "Accepted", "C001", "USD", 10),
    ("2026-09-04", "2026-09-30", "Draft", "C002", "TWD", 0),
    ("2026-09-07", "2026-10-07", "Accepted", "C002", "EUR", 5),
    ("2026-09-09", "2026-09-28", "Expired", "C001", "EUR", 0),
    ("2026-09-11", "2026-09-25", "Accepted", "C003", "TWD", 10),
    ("2026-09-14", "2026-10-14", "Sent", "C005", "USD", 5),
    ("2026-09-17", "2026-09-29", "Sent", "C007", "TWD", 0),
    ("2026-09-21", "2026-10-21", "Draft", "C001", "TWD", 10),
    ("2026-09-24", "2026-10-24", "Sent", "C004", "USD", 0),
    ("2026-09-28", "2026-10-28", "Accepted", "C006", "EUR", 5),
    ("2026-09-30", "2026-10-30", "Draft", "C008", "TWD", 0),
    ("2026-10-01", "2026-10-31", "Accepted", "C001", "TWD", 0),
    ("2026-10-05", "2026-11-04", "Sent", "C003", "EUR", 5),
    ("2026-10-08", "2026-11-07", "Accepted", "C001", "USD", 10),
    ("2026-10-12", "2026-11-11", "Draft", "C002", "TWD", 0),
    ("2026-10-15", "2026-11-14", "Accepted", "C007", "TWD", 5),
    ("2026-10-19", "2026-11-18", "Expired", "C005", "USD", 0),
    ("2026-10-22", "2026-11-21", "Sent", "C004", "TWD", 10),
    ("2026-10-26", "2026-11-25", "Accepted", "C002", "USD", 0),
    ("2026-10-30", "2026-11-29", "Draft", "C006", "EUR", 5),
]


def build_quotes(rng: random.Random) -> list[dict[str, object]]:
    out = []
    for index, (when, valid, status, customer, currency, discount) in enumerate(QUOTE_PLAN):
        lines = lines_for(rng, currency, 4)
        subtotal = sum(Decimal(str(x["LineAmount"])) for x in lines)
        net = (subtotal * (Decimal(100) - discount) / Decimal(100)).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        out.append(
            {
                "QuoteID": f"Q{index + 1:04d}",
                "CustomerID": customer,
                "ProjectID": customer_project(rng, customer),
                "QuoteDate": when,
                "ValidUntil": valid,
                "Status": status,
                "Currency": currency,
                "Subtotal": money(subtotal),
                "DiscountPercent": str(discount),
                "NetAmount": money(net),
                "Lines": lines,
            }
        )
    # P003 needs an accepted quote in October so the October P003 rerun has data.
    october = next(q for q in out if q["QuoteDate"] == "2026-10-01")
    october["ProjectID"] = "P003"
    return out


def main() -> None:
    rng = random.Random(SEED)
    orders = build_orders(rng)
    invoices = build_invoices(rng, orders)
    expenses = build_expenses(rng)
    quotes = build_quotes(rng)
    source = {
        "seed": SEED,
        "period": {"from": "2026-08-01", "to": "2026-10-31"},
        "customers": CUSTOMERS,
        "employees": EMPLOYEES,
        "projects": PROJECTS,
        "sales_orders": orders,
        "invoices": invoices,
        "expenses": expenses,
        "quotes": quotes,
    }
    target = HERE / "source.json"
    target.write_text(json.dumps(source, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        f"wrote {target} ({len(orders)} orders, {len(invoices)} invoices, "
        f"{len(expenses)} expenses, {len(quotes)} quotes)"
    )


if __name__ == "__main__":
    main()
