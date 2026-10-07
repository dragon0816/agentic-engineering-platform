from pathlib import Path
import csv, json
from datetime import datetime, date
from openpyxl import load_workbook

ws = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-006\X01\workspace')
output_dir = ws / 'output'
print('Workspace:', ws)
print('Output files:')
for p in sorted(output_dir.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(ws), p.stat().st_size)

required = [
    output_dir/'downloads'/'sap_orders.csv',
    output_dir/'downloads'/'sap_invoices.csv',
    output_dir/'expense_approved.csv',
    output_dir/'quotes_accepted.json',
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

def normalize_json_quotes(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ('quotes','data','items','rows','results'):
            if key in obj and isinstance(obj[key], list):
                print('Quote JSON list key:', key)
                return obj[key]
        # If values are quote records, use them.
        vals = list(obj.values())
        if vals and all(isinstance(v, dict) for v in vals):
            print('Quote JSON normalized from mapping values')
            return vals
    raise SystemExit(f'Unsupported quote JSON structure: {type(obj).__name__} keys={list(obj.keys()) if isinstance(obj, dict) else None}')

orders = read_csv(output_dir/'downloads'/'sap_orders.csv')
invoices = read_csv(output_dir/'downloads'/'sap_invoices.csv')
expenses = read_csv(output_dir/'expense_approved.csv')
summary_csv = read_csv(output_dir/'project_summary_sep2026.csv')
with (output_dir/'quotes_accepted_sep2026.json').open(encoding='utf-8') as f:
    quotes_obj = json.load(f)
quotes = normalize_json_quotes(quotes_obj)
print(f'JSON output/quotes_accepted_sep2026.json records={len(quotes)}')
if quotes:
    print(' sample:', quotes[0])

start = date(2026,9,1); end = date(2026,9,30)
def parse_date(s):
    return datetime.strptime(str(s)[:10], '%Y-%m-%d').date()

def check_date_rows(rows, col, name):
    bad = [r for r in rows if not (start <= parse_date(r[col]) <= end)]
    if bad:
        raise SystemExit(f'{name}: {len(bad)} rows outside Sep 2026')
    print(f'OK {name}: all {len(rows)} rows in 2026-09-01..2026-09-30 by {col}')

check_date_rows(orders, 'OrderDate', 'orders')
check_date_rows(invoices, 'InvoiceDate', 'invoices')
check_date_rows(expenses, 'ExpenseDate', 'expenses')
check_date_rows(quotes, 'QuoteDate', 'quotes')

if any(r.get('Status') == 'Cancelled' for r in orders):
    raise SystemExit('orders include Cancelled rows')
print('OK orders: no Cancelled rows')

if any(r.get('Status') != 'Approved' for r in expenses):
    raise SystemExit('expenses include non-Approved rows')
print('OK expenses: all Approved')

if any(r.get('Status') != 'Accepted' for r in quotes):
    raise SystemExit('quotes include non-Accepted rows')
print('OK quotes: all Accepted')

for name, rows, idcols in [
    ('orders', orders, ['OrderID','CustomerID','ProjectID']),
    ('invoices', invoices, ['InvoiceID','OrderID','CustomerID','ProjectID']),
    ('expenses', expenses, ['ExpenseID','ProjectID']),
    ('quotes', quotes, ['QuoteID','ProjectID']),
]:
    for col in idcols:
        for r in rows:
            if col in r and r[col] is not None and not isinstance(r[col], str):
                raise SystemExit(f'{name}.{col} has non-text value {r[col]!r}')
    print(f'OK {name}: ID columns are text values where present')

wb_path = output_dir/'project_integration_report.xlsx'
wb = load_workbook(wb_path, data_only=False)
print('Workbook sheets:', wb.sheetnames)
expected_sheets = ['Summary', 'Orders', 'Invoices', 'Expenses', 'Quotes', 'Exceptions']
for s in expected_sheets:
    if s not in wb.sheetnames:
        raise SystemExit('Workbook missing sheet: ' + s)

for sheet in expected_sheets:
    sh = wb[sheet]
    headers = [c.value for c in sh[1]]
    rows = [row for row in sh.iter_rows(min_row=2, values_only=True) if any(v is not None for v in row)]
    print(f'Sheet {sheet}: data_rows={len(rows)} headers={headers}')

# Summary sheet column validation. Accept existing template names but ensure the four requested metrics are separate.
summary_sheet = wb['Summary']
headers = [c.value for c in summary_sheet[1]]
print('Summary headers:', headers)
metric_aliases = {
    'orders': {'OrderAmount_TWD','OrderTWD','Orders_TWD','Order Amount TWD'},
    'invoice_balance': {'InvoiceBalance_TWD','InvoiceBalanceTWD','Invoice Balance TWD'},
    'approved_expense': {'ApprovedExpense_TWD','ApprovedExpenseTWD','Approved Expense TWD'},
    'accepted_quote': {'AcceptedQuote_TWD','AcceptedQuoteTWD','Accepted Quote TWD'},
}
if 'ProjectID' not in headers:
    raise SystemExit('Summary missing ProjectID')
for metric, aliases in metric_aliases.items():
    found = [h for h in headers if h in aliases]
    if not found:
        raise SystemExit(f'Summary missing separate metric for {metric}; headers={headers}')
    print(f'OK Summary metric {metric}: column {found[0]}')

summary_rows = []
for row in summary_sheet.iter_rows(min_row=2, values_only=True):
    if any(v is not None for v in row):
        summary_rows.append(dict(zip(headers, row)))
print('Summary project rows:', len(summary_rows), 'ProjectIDs:', [r.get('ProjectID') for r in summary_rows])
for r in summary_rows:
    if not isinstance(r.get('ProjectID'), str):
        raise SystemExit('Summary ProjectID is not text: ' + repr(r.get('ProjectID')))
    for h in headers:
        if h != 'ProjectID' and any(h in aliases for aliases in metric_aliases.values()):
            if not isinstance(r.get(h), (int, float)):
                raise SystemExit(f'Summary {r.get("ProjectID")} {h} is not numeric: {r.get(h)!r}')
print('OK Summary: ProjectID text and amount columns numeric')

bad_summary_headers = [str(h) for h in headers if h and ('revenue' in str(h).lower() or '營收' in str(h))]
if bad_summary_headers:
    raise SystemExit('Possible combined revenue column in Summary: ' + ', '.join(bad_summary_headers))
print('OK Summary: no revenue column; orders and quotes remain separate')

# Cross-check workbook detail counts against source extracts.
expected_counts = {
    'Orders': len(orders),
    'Invoices': len(invoices),
    'Expenses': len(expenses),
    'Quotes': len(quotes),
}
for sheet, expected in expected_counts.items():
    actual = sum(1 for row in wb[sheet].iter_rows(min_row=2, values_only=True) if any(v is not None for v in row))
    if actual != expected:
        raise SystemExit(f'{sheet} row count mismatch workbook={actual} source={expected}')
    print(f'OK {sheet}: workbook row count matches source ({actual})')

# Validate summary CSV and workbook summary agree by ProjectID and metric values.
summary_csv_by_project = {r['ProjectID']: r for r in summary_csv}
for r in summary_rows:
    pid = r['ProjectID']
    if pid not in summary_csv_by_project:
        raise SystemExit(f'Summary workbook project {pid} missing in CSV')
print('OK Summary CSV includes all workbook project IDs')

exc_count = sum(1 for row in wb['Exceptions'].iter_rows(min_row=2, values_only=True) if any(v is not None for v in row))
print('Exceptions rows:', exc_count)
print('VALIDATION PASSED')