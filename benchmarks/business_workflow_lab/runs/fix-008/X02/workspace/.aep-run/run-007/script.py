from pathlib import Path
from openpyxl import load_workbook
import json, csv, os
from datetime import datetime, date

ws = Path.cwd()
print('Workspace:', ws)
print('Output files present:')
for p in sorted((ws/'output').rglob('*')):
    if p.is_file():
        print(f' - {p.relative_to(ws)} ({p.stat().st_size} bytes)')

report = ws/'output'/'project_report_C001_2026-09_TWD.xlsx'
if not report.exists():
    raise SystemExit('Missing expected workbook')

wb = load_workbook(report, data_only=False)
print('Workbook sheets:', wb.sheetnames)

# Template uses row 4 as headers and row 5+ as data for detail/summary/exception sheets.
def headers(sheet):
    sh = wb[sheet]
    return [sh.cell(4,c).value for c in range(1, sh.max_column+1)]

def rows(sheet):
    sh = wb[sheet]
    out = []
    for r in range(5, sh.max_row+1):
        vals = [sh.cell(r,c).value for c in range(1, sh.max_column+1)]
        if any(v is not None for v in vals):
            out.append(vals)
    return out

expected_counts = {'Orders':3, 'Invoices':3, 'Expenses':9, 'Quotes':4, 'Summary':2, 'Exceptions':4}
actual_counts = {s: len(rows(s)) for s in expected_counts}
print('Data row counts from row 5:', actual_counts)
assert actual_counts == expected_counts, f'Row count mismatch: {actual_counts}'

# Check metadata
report_sh = wb['Report']
print('Report from/to:', report_sh['B3'].value, report_sh['D3'].value)
print('Report condition:', report_sh['B4'].value)
assert str(report_sh['B3'].value) == '2026-09-01'
assert str(report_sh['D3'].value) == '2026-09-30'
assert 'Customer C001' in str(report_sh['B4'].value)
assert 'FX from input/fx_rates.csv' in str(report_sh['B4'].value)

# Orders: exclude Cancelled; C001; date window; amount numeric
h = headers('Orders'); data = rows('Orders')
idx = {name:i for i,name in enumerate(h) if name}
print('Orders headers:', h)
print('Orders data:', data)
assert all(r[idx['CustomerID']] == 'C001' for r in data)
assert all(r[idx['Status']] != 'Cancelled' for r in data)
assert all('2026-09-01' <= str(r[idx['OrderDate']]) <= '2026-09-30' for r in data)
assert all(isinstance(r[idx['AmountTWD']], (int,float)) for r in data)
assert all(isinstance(r[idx['OrderID']], str) for r in data)

# Invoices: C001; check overdue unpaid as-of 2026-09-30 exists only expected invoice exception
h = headers('Invoices'); data = rows('Invoices')
idx = {name:i for i,name in enumerate(h) if name}
print('Invoices data:', data)
assert all(r[idx['CustomerID']] == 'C001' for r in data)
assert all('2026-09-01' <= str(r[idx['InvoiceDate']]) <= '2026-09-30' for r in data)
assert all(isinstance(r[idx['BalanceTWD']], (int,float)) for r in data)
assert all(isinstance(r[idx['InvoiceID']], str) for r in data)

# Expenses: Approved only, P001/P003 only, amounts numeric
h = headers('Expenses'); data = rows('Expenses')
idx = {name:i for i,name in enumerate(h) if name}
print('Expenses data:', data)
assert all(r[idx['ProjectID']] in {'P001','P003'} for r in data)
assert all(r[idx['Status']] == 'Approved' for r in data)
assert all('2026-09-01' <= str(r[idx['ExpenseDate']]) <= '2026-09-30' for r in data)
assert all(isinstance(r[idx['AmountTWD']], (int,float)) for r in data)
assert all(isinstance(r[idx['ExpenseID']], str) for r in data)

# Quotes: all statuses retained; C001; dates in September; amount numeric
h = headers('Quotes'); data = rows('Quotes')
idx = {name:i for i,name in enumerate(h) if name}
print('Quotes data:', data)
assert all(r[idx['CustomerID']] == 'C001' for r in data)
assert all('2026-09-01' <= str(r[idx['QuoteDate']]) <= '2026-09-30' for r in data)
assert {r[idx['Status']] for r in data} == {'Sent','Accepted','Draft','Expired'}
assert all(isinstance(r[idx['AmountTWD']], (int,float)) for r in data)
assert all(isinstance(r[idx['QuoteID']], str) for r in data)

# Exceptions exactly according to stated attention conditions.
h = headers('Exceptions'); data = rows('Exceptions')
idx = {name:i for i,name in enumerate(h) if name}
print('Exceptions data:', json.dumps(data, ensure_ascii=False, default=str))
expected_exceptions = {
    ('Invoices', '0090000219', 'P001'),
    ('Expenses', 'EXP-00006', 'P001'),
    ('Quotes', 'Q0010', 'P001'),
    ('Quotes', 'Q0014', 'P001'),
}
actual_exceptions = {(r[idx['Source']], r[idx['DocumentID']], r[idx['ProjectID']]) for r in data}
assert actual_exceptions == expected_exceptions, actual_exceptions
assert any('overdue' in str(r[idx['Reason']]).lower() or '逾期' in str(r[idx['Reason']]) for r in data if r[idx['Source']] == 'Invoices')
assert any('receipt' in str(r[idx['Reason']]).lower() or '收據' in str(r[idx['Reason']]) for r in data if r[idx['Source']] == 'Expenses')
assert all(('ValidUntil' in str(r[idx['Reason']]) or 'valid' in str(r[idx['Reason']]).lower()) for r in data if r[idx['Source']] == 'Quotes')

# Summary projects and formulas/numeric cells
h = headers('Summary'); data = rows('Summary')
idx = {name:i for i,name in enumerate(h) if name}
print('Summary data:', data)
assert {r[idx['ProjectID']] for r in data} == {'P001','P003'}
for r in range(5, wb['Summary'].max_row+1):
    if wb['Summary'].cell(r,1).value:
        assert wb['Summary'].cell(r,2).data_type == 'f', 'Summary OrderTWD should be formula'
        assert wb['Summary'].cell(r,3).data_type == 'f', 'Summary InvoiceBalanceTWD should be formula'
        assert wb['Summary'].cell(r,4).data_type == 'f', 'Summary ApprovedExpenseTWD should be formula'
        assert wb['Summary'].cell(r,5).data_type == 'f', 'Summary AcceptedQuoteTWD should be formula'

print('CHECK PASSED: workbook contents match the requested filters, FX/source note, row counts, ID text preservation, numeric TWD amounts, exceptions, and summary formulas.')