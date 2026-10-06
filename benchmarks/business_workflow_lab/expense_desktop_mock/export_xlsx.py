"""Write the Expense app's Excel export with openpyxl.

  python export_xlsx.py <request.json>

The WinForms app (ExpenseApp.exe) writes a temporary JSON request
{"path": ..., "columns": [...], "rows": [[...], ...]} and calls this helper
with the system python. Output matches the Tk edition: one sheet named
"Expenses", a header row, data cells formatted as text ("@").
Exit code 0 on success; any failure prints the reason to stderr and exits 1.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: export_xlsx.py <request.json>", file=sys.stderr)
        return 2
    try:
        from openpyxl import Workbook

        with open(sys.argv[1], encoding="utf-8-sig") as handle:
            request = json.load(handle)
        book = Workbook()
        sheet = book.active
        sheet.title = "Expenses"
        sheet.append(list(request["columns"]))
        for row in request["rows"]:
            sheet.append(row)
            for cell in sheet[sheet.max_row]:
                cell.number_format = "@"
        book.save(request["path"])
    except Exception as error:  # noqa: BLE001 - every failure must reach the app as a message
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
