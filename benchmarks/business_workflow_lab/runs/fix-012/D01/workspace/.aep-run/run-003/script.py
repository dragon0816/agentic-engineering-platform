from pathlib import Path
import openpyxl, csv
ws=Path.cwd()
print((ws/'input'/'expense_manual.md').read_text(encoding='utf-8'))
wb=openpyxl.load_workbook(ws/'output'/'expense_export_E001_2026-09.xlsx', data_only=True)
s=wb['Expenses']
headers=[c.value for c in s[1]]
print('headers', headers)
for row in s.iter_rows(min_row=2, values_only=True):
    print(dict(zip(headers,row)))
