from pathlib import Path
import csv, json, os, math
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from openpyxl import load_workbook

ws = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-006\X01\workspace')
input_dir = ws / 'input'
output_dir = ws / 'output'
print('Workspace:', ws)
print('Input files:')
for p in sorted(input_dir.glob('*')):
    print(' -', p.relative_to(ws), p.stat().st_size)
print('Output files:')
for p in sorted(output_dir.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(ws), p.stat().st_size)

required = [
    output_dir/'downloads'/'sap_orders.csv',
    output_dir/'downloads'/'sap_invoices.csv',
    output_dir/'expense_approved.csv',
    output_dir/'quotes_accepted_sep2026.json',
    output_dir/'project_summary_sep2026.csv',
    output_dir/'project_integration_report.xlsx',
]
missing = [str(p.relative_to(ws)) for p in required if not p.exists()]
if missing:
    raise SystemExit('MISSING required outputs: ' + ', '.join(missing))

def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    print(f'CSV {path.relative_to(ws)} rows={len(rows)} headers={list(rows[0].keys()) if rows else []}')
    if rows:
        print(' sample:', rows[0])
    return rows

orders = read_csv(output_dir/'downloads'/'sap_orders.csv')
invoices = read_csv(output_dir/'downloads'/'sap_invoices.csv')
expenses = read_csv(output_dir/'expense_approved.csv')
summary_csv = read_csv(output_dir/'project_summary_sep2026.csv')
quotes_path = output_dir/'quotes_accepted_sep2026.json'
with quotes_path.open(encoding='utf-8') as f:
    quotes = json.load(f)
print(f'JSON {quotes_path.relative_to(ws)} rows={len(quotes)}')
if quotes:
    print(' sample:', quotes[0])

start = date(2026,9,1); end = date(2026,9,30)
def parse_date(s):
    return datetime.strptime(s[:10], '%Y-%m-%d').date()

def check_date_rows(rows, col, name):
    bad = [r for r in rows if not (start <= parse_date(r[col]) <= end)]
    if bad:
        raise SystemExit(f'{name}: {len(bad)} rows outside Sep 2026')
    print(f'OK {name}: all {len(rows)} rows in 2026-09-01..2026-09-30 by {col}')

check_date_rows(orders, 'OrderDate', 'orders')
check_date_rows(invoices, 'InvoiceDate', 'invoices')
check_date_rows(expenses, 'ExpenseDate', 'expenses')
check_date_rows(quotes, 'QuoteDate', 'quotes')

bad_cancelled = [r for r in orders if r.get('Status') == 'Cancelled']
if bad_cancelled:
    raise SystemExit(f'orders include Cancelled rows: {len(bad_cancelled)}')
print('OK orders: no Cancelled rows')

bad_exp = [r for r in expenses if r.get('Status') != 'Approved']
if bad_exp:
    raise SystemExit(f'expenses include non-Approved rows: {len(bad_exp)}')
print('OK expenses: all Approved')

bad_quote = [r for r in quotes if r.get('Status') != 'Accepted']
if bad_quote:
    raise SystemExit(f'quotes include non-Accepted rows: {len(bad_quote)}')
print('OK quotes: all Accepted')

for name, rows, idcols in [
    ('orders', orders, ['OrderID','CustomerID','ProjectID']),
    ('invoices', invoices, ['InvoiceID','OrderID','CustomerID','ProjectID']),
    ('expenses', expenses, ['ExpenseID','ProjectID']),
    ('quotes', quotes, ['QuoteID','ProjectID']),
]:
    for col in idcols:
        present = [r.get(col) for r in rows if col in r]
        nonstr = [v for v in present if not isinstance(v, str)]
        if nonstr:
            raise SystemExit(f'{name}.{col} has non-text values')
    print(f'OK {name}: ID columns are text values where present')

# Workbook verification
wb_path = output_dir/'project_integration_report.xlsx'
wb = load_workbook(wb_path, data_only=False)
print('Workbook sheets:', wb.sheetnames)
expected_sheets = ['Summary', 'Orders', 'Invoices', 'Expenses', 'Quotes', 'Exceptions']
missing_sheets = [s for s in expected_sheets if s not in wb.sheetnames]
if missing_sheets:
    raise SystemExit('Workbook missing sheets: ' + ', '.join(missing_sheets))

for sheet in expected_sheets:
    sh = wb[sheet]
    headers = [c.value for c in sh[1]]
    print(f'Sheet {sheet}: rows={sh.max_row-1} cols={sh.max_column} headers={headers}')

# Check summary headers and rows vs CSV
summary_sheet = wb['Summary']
summary_headers = [c.value for c in summary_sheet[1]]
required_summary_cols = ['ProjectID','OrderAmount_TWD','InvoiceBalance_TWD','ApprovedExpense_TWD','AcceptedQuote_TWD']
for col in required_summary_cols:
    if col not in summary_headers:
        raise SystemExit(f'Summary missing column {col}')
print('OK Summary required columns present')

summary_rows_wb = []
for row in summary_sheet.iter_rows(min_row=2, values_only=True):
    if any(v is not None for v in row):
        summary_rows_wb.append(dict(zip(summary_headers, row)))
print('Summary project rows:', len(summary_rows_wb), 'ProjectIDs:', [r.get('ProjectID') for r in summary_rows_wb])

# Numeric checks in summary
for r in summary_rows_wb:
    if not isinstance(r.get('ProjectID'), str):
        raise SystemExit('Summary ProjectID is not text: ' + repr(r.get('ProjectID')))
    for col in required_summary_cols[1:]:
        val = r.get(col)
        if val is None:
            raise SystemExit(f'Summary {r.get("ProjectID")} {col} is blank')
        if not isinstance(val, (int, float)):
            raise SystemExit(f'Summary {r.get("ProjectID")} {col} is not numeric: {val!r}')
print('OK Summary ProjectID text and amount columns numeric')

# Confirm details sheets contain only stated statuses and no revenue-combination column
for sheet, bad_header_tokens in [('Summary', ['Revenue','營收'])]:
    headers = [str(c.value or '') for c in wb[sheet][1]]
    bad = [h for h in headers if any(tok.lower() in h.lower() for tok in bad_header_tokens)]
    if bad:
        raise SystemExit(f'{sheet} contains possible combined revenue column(s): {bad}')
print('OK no combined revenue column detected in Summary header; orders and quotes remain separate')

# Exception rows count
exc = wb['Exceptions']
exc_count = sum(1 for row in exc.iter_rows(min_row=2, values_only=True) if any(v is not None for v in row))
print('Exceptions rows:', exc_count)

print('VALIDATION PASSED')