from pathlib import Path
from openpyxl import load_workbook
import json, csv

workspace = Path.cwd()
print('WORKSPACE', workspace)
print('INPUT FILES')
for p in sorted((workspace/'input').glob('*')):
    print('-', p.name, p.stat().st_size)
print('OUTPUT FILES')
for p in sorted((workspace/'output').glob('*')):
    print('-', p.name, p.stat().st_size)

out = workspace/'output'
report = out/'E001_september_expenses.xlsx'
export = out/'E001_2026-09_expense_export.xlsx'
print('REPORT_EXISTS', report.exists())
print('EXPORT_EXISTS', export.exists())

if report.exists():
    wb = load_workbook(report, data_only=False)
    print('REPORT_SHEETS', wb.sheetnames)
    for s in wb.sheetnames:
        ws = wb[s]
        print('SHEET', s, 'MAX_ROW', ws.max_row, 'MAX_COL', ws.max_column)
    # Dump key sheet contents for verification
    for s in ['Report','Summary','Details','Exceptions']:
        if s in wb.sheetnames:
            ws = wb[s]
            print('\n--', s, '--')
            max_rows = min(ws.max_row, 25)
            for row in ws.iter_rows(min_row=1, max_row=max_rows, values_only=True):
                print(row)
    # Count details rows by nonblank first column from row 5
    if 'Details' in wb.sheetnames:
        ws = wb['Details']
        detail_rows = []
        for r in range(5, ws.max_row+1):
            vals = [ws.cell(r,c).value for c in range(1, ws.max_column+1)]
            if any(v is not None for v in vals):
                detail_rows.append(vals)
        print('DETAIL_ROW_COUNT_FROM_ROW5', len(detail_rows))
        # Check types in expected columns if headers row 4
        headers = [ws.cell(4,c).value for c in range(1, ws.max_column+1)]
        print('DETAIL_HEADERS_ROW4', headers)
        for i, vals in enumerate(detail_rows[:3], start=1):
            print('DETAIL_SAMPLE', i, vals)
    if 'Summary' in wb.sheetnames:
        ws = wb['Summary']
        print('SUMMARY_B2', ws['B2'].value)
        summary_rows = []
        for r in range(5, ws.max_row+1):
            vals = [ws.cell(r,c).value for c in range(1, ws.max_column+1)]
            if any(v is not None for v in vals): summary_rows.append(vals)
        print('SUMMARY_ROW_COUNT_FROM_ROW5', len(summary_rows))
        print('SUMMARY_ROWS', summary_rows)

if export.exists():
    wb = load_workbook(export, data_only=True)
    print('EXPORT_SHEETS', wb.sheetnames)
    ws = wb[wb.sheetnames[0]]
    print('EXPORT_MAX_ROW', ws.max_row, 'EXPORT_MAX_COL', ws.max_column)
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 10), values_only=True):
        print('EXPORT_ROW', row)
