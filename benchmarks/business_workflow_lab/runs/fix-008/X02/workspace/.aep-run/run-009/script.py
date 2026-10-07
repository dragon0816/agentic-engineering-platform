from pathlib import Path
from openpyxl import load_workbook
import csv, json
from datetime import datetime, date

ws = Path.cwd()
print('Workspace:', ws)
print('Output files:')
for p in sorted((ws/'output').rglob('*')):
    if p.is_file():
        print(f' - {p.relative_to(ws)} ({p.stat().st_size} bytes)')

report = ws/'output'/'project_report_C001_2026-09_TWD.xlsx'
assert report.exists(), 'Missing workbook output'
wb = load_workbook(report, data_only=False)
print('Workbook sheets:', wb.sheetnames)

# Print relevant template instructions to confirm rules actually required.
inst = wb['Instructions']
print('Instructions rows:')
for r in range(1, inst.max_row + 1):
    vals = [inst.cell(r,c).value for c in range(1, min(inst.max_column,3)+1)]
    if any(v is not None for v in vals):
        print(r, vals)

def sheet_headers(name):
    sh = wb[name]
    return [sh.cell(4,c).value for c in range(1, sh.max_column+1)]

def sheet_rows(name):
    sh = wb[name]
    out = []
    for r in range(5, sh.max_row+1):
        vals = [sh.cell(r,c).value for c in range(1, sh.max_column+1)]
        if any(v is not None for v in vals):
            out.append(vals)
    return out

def d(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return datetime.fromisoformat(str(v)[:10]).date()

start = date(2026, 9, 1)
end = date(2026, 9, 30)
cutoff = date(2026, 9, 30)

# Check CSV outputs exist and their source rows are as expected.
for rel in ['output/downloads/orders_C001_2026-09.csv','output/downloads/invoices_C001_2026-09.csv','output/expenses_P001_Approved_2026-09.csv','output/expenses_P003_Approved_2026-09.csv']:
    p = ws/rel
    assert p.exists(), f'Missing {rel}'
    with p.open(newline='', encoding='utf-8-sig') as f:
        dr = csv.DictReader(f)
        source_rows = list(dr)
        print(rel, 'headers=', dr.fieldnames, 'rows=', len(source_rows))

expected_counts = {'Orders':3, 'Invoices':3, 'Expenses':9, 'Quotes':4, 'Summary':2, 'Exceptions':4}
actual_counts = {s: len(sheet_rows(s)) for s in expected_counts}
print('Workbook data row counts:', actual_counts)
assert actual_counts == expected_counts, f'Unexpected workbook row counts: {actual_counts}'

# Report metadata and condition.
report_sh = wb['Report']
assert d(report_sh['B3'].value) == start
assert d(report_sh['D3'].value) == end
condition = str(report_sh['B4'].value)
for phrase in ['Customer C001','orders exclude Cancelled','expenses Approved','quotes all statuses','FX from input/fx_rates.csv']:
    assert phrase in condition, f'Missing condition note: {phrase}'

# FX rates loaded from attachment only.
fx = {}
with (ws/'input'/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        if row.get('Currency') and row.get('RateToTWD'):
            fx[row['Currency']] = float(row['RateToTWD'])
print('FX rates:', fx)
assert fx == {'TWD': 1.0, 'USD': 32.0, 'EUR': 35.0}

# Validate sheets.
h = sheet_headers('Orders'); rows = sheet_rows('Orders'); idx = {n:i for i,n in enumerate(h) if n}
assert h == ['OrderID', 'ProjectID', 'CustomerID', 'OrderDate', 'Status', 'Currency', 'NetAmount', 'AmountTWD']
for r in rows:
    assert isinstance(r[idx['OrderID']], str)
    assert r[idx['CustomerID']] == 'C001'
    assert r[idx['Status']] != 'Cancelled'
    assert start <= d(r[idx['OrderDate']]) <= end
    assert abs(r[idx['NetAmount']] * fx[r[idx['Currency']]] - r[idx['AmountTWD']]) < 0.01

h = sheet_headers('Invoices'); rows = sheet_rows('Invoices'); idx = {n:i for i,n in enumerate(h) if n}
assert h == ['InvoiceID', 'OrderID', 'ProjectID', 'CustomerID', 'InvoiceDate', 'DueDate', 'Currency', 'Amount', 'PaidAmount', 'Balance', 'BalanceTWD']
for r in rows:
    assert isinstance(r[idx['InvoiceID']], str)
    assert isinstance(r[idx['OrderID']], str)
    assert r[idx['CustomerID']] == 'C001'
    assert start <= d(r[idx['InvoiceDate']]) <= end
    assert abs(r[idx['Balance']] * fx[r[idx['Currency']]] - r[idx['BalanceTWD']]) < 0.01

h = sheet_headers('Expenses'); rows = sheet_rows('Expenses'); idx = {n:i for i,n in enumerate(h) if n}
assert h == ['ExpenseID', 'ProjectID', 'EmployeeID', 'ExpenseDate', 'Status', 'Currency', 'Amount', 'AmountTWD']
for r in rows:
    assert isinstance(r[idx['ExpenseID']], str)
    assert r[idx['ProjectID']] in {'P001','P003'}
    assert r[idx['Status']] == 'Approved'
    assert start <= d(r[idx['ExpenseDate']]) <= end
    assert abs(r[idx['Amount']] * fx[r[idx['Currency']]] - r[idx['AmountTWD']]) < 0.01

h = sheet_headers('Quotes'); rows = sheet_rows('Quotes'); idx = {n:i for i,n in enumerate(h) if n}
assert h == ['QuoteID', 'ProjectID', 'CustomerID', 'QuoteDate', 'ValidUntil', 'Status', 'Currency', 'NetAmount', 'AmountTWD']
for r in rows:
    assert isinstance(r[idx['QuoteID']], str)
    assert r[idx['CustomerID']] == 'C001'
    assert start <= d(r[idx['QuoteDate']]) <= end
    assert abs(r[idx['NetAmount']] * fx[r[idx['Currency']]] - r[idx['AmountTWD']]) < 0.01
assert {r[idx['Status']] for r in rows} == {'Sent','Accepted','Draft','Expired'}

h = sheet_headers('Summary'); rows = sheet_rows('Summary'); idx = {n:i for i,n in enumerate(h) if n}
assert h == ['ProjectID', 'OrderTWD', 'InvoiceBalanceTWD', 'ApprovedExpenseTWD', 'AcceptedQuoteTWD']
assert {r[idx['ProjectID']] for r in rows} == {'P001','P003'}
# Values should be numeric totals by project in TWD; formulas are not required by user or Instructions.
for r in rows:
    assert all(isinstance(r[i], (int,float)) for i in [idx['OrderTWD'], idx['InvoiceBalanceTWD'], idx['ApprovedExpenseTWD'], idx['AcceptedQuoteTWD']])

h = sheet_headers('Exceptions'); rows = sheet_rows('Exceptions'); idx = {n:i for i,n in enumerate(h) if n}
assert h == ['Source', 'DocumentID', 'ProjectID', 'Reason']
actual = {(r[idx['Source']], r[idx['DocumentID']], r[idx['ProjectID']]) for r in rows}
expected = {('Invoices','0090000219','P001'), ('Expenses','EXP-00006','P001'), ('Quotes','Q0010','P001'), ('Quotes','Q0014','P001')}
print('Exceptions actual:', actual)
assert actual == expected, actual
for r in rows:
    reason = str(r[idx['Reason']])
    if r[idx['Source']] == 'Invoices':
        assert 'DueDate <= 2026-09-30' in reason and 'BalanceTWD' in reason
    if r[idx['Source']] == 'Expenses':
        assert 'MissingReceipt=True' in reason
    if r[idx['Source']] == 'Quotes':
        assert 'ValidUntil < 2026-09-30' in reason and 'Status' in reason

print('CHECK PASSED: all stated requirements verified from saved files.')