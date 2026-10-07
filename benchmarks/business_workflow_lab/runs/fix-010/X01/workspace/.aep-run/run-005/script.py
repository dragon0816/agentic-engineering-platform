from pathlib import Path
import csv
from openpyxl import load_workbook

ws = Path.cwd()
out = ws / 'output'
dl = out / 'downloads'
print('Inspecting workspace:', ws)
print('Output files present:')
for p in sorted(out.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(ws), p.stat().st_size, 'bytes')

expected_aug = out / 'project_integration_2026-08.xlsx'
expected_sep = out / 'project_integration_2026-09.xlsx'
print('\nChecking final workbooks exist and are distinct...')
print('Aug exists:', expected_aug.exists(), expected_aug)
print('Sep exists:', expected_sep.exists(), expected_sep)
if expected_aug.exists() and expected_sep.exists():
    print('Same path:', expected_aug.resolve() == expected_sep.resolve())
    print('Aug size:', expected_aug.stat().st_size)
    print('Sep size:', expected_sep.stat().st_size)

if not expected_aug.exists():
    raise SystemExit('Missing expected August workbook')

wb = load_workbook(expected_aug, data_only=False, read_only=False)
print('\nWorkbook sheets:', wb.sheetnames)
for sheet_name in ['Report','Orders','Invoices','Expenses','Quotes','Summary','Exceptions','Instructions']:
    print(f'Sheet {sheet_name} present:', sheet_name in wb.sheetnames)

# Print dimensions and header rows for key sheets.
for sheet_name in ['Report','Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    sh = wb[sheet_name]
    rows = sh.max_row
    cols = sh.max_column
    header = [sh.cell(1, c).value for c in range(1, cols+1)] if rows else []
    print(f'{sheet_name}: rows={rows}, cols={cols}, header={header}')

# Locate period dates anywhere in Report sheet.
report = wb['Report']
report_values = []
for row in report.iter_rows(values_only=True):
    report_values.extend([v for v in row if v is not None])
print('\nReport non-empty values:', report_values)
print('Contains 2026-08-01:', any('2026-08-01' in str(v) for v in report_values))
print('Contains 2026-08-31:', any('2026-08-31' in str(v) for v in report_values))

# Check source/intermediate CSV row counts from the just-run workflow outputs.
print('\nCSV row counts:')
for rel in ['downloads/sap_orders_open.csv','downloads/sap_orders_closed.csv','downloads/sap_invoices.csv','expense_approved.csv']:
    p = out / rel
    if not p.exists():
        print(rel, 'MISSING')
        continue
    with p.open(newline='', encoding='utf-8-sig') as f:
        rdr = list(csv.reader(f))
    print(rel, 'rows_including_header=', len(rdr), 'data_rows=', max(len(rdr)-1,0), 'header=', rdr[0] if rdr else [])

# Basic workbook content checks for August run.
# Orders should include only Open/Closed statuses if Status column exists.
orders = wb['Orders']
orders_header = [orders.cell(1,c).value for c in range(1, orders.max_column+1)]
if 'Status' in orders_header:
    idx = orders_header.index('Status') + 1
    statuses = sorted({orders.cell(r,idx).value for r in range(2, orders.max_row+1) if orders.cell(r,idx).value is not None})
    print('Orders statuses:', statuses)
    if any(s not in ('Open','Closed') for s in statuses):
        raise SystemExit('Unexpected order status found')

# Expenses should be Approved if Status column exists.
expenses = wb['Expenses']
exp_header = [expenses.cell(1,c).value for c in range(1, expenses.max_column+1)]
if 'Status' in exp_header:
    idx = exp_header.index('Status') + 1
    exp_statuses = sorted({expenses.cell(r,idx).value for r in range(2, expenses.max_row+1) if expenses.cell(r,idx).value is not None})
    print('Expense statuses:', exp_statuses)
    if any(s != 'Approved' for s in exp_statuses):
        raise SystemExit('Unexpected expense status found')

summary = wb['Summary']
summary_header = [summary.cell(1,c).value for c in range(1, summary.max_column+1)]
print('Summary header:', summary_header)
for required in ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']:
    print('Summary required column', required, 'present:', required in summary_header)
    if required not in summary_header:
        raise SystemExit(f'Missing summary column {required}')

print('\nCHECK COMPLETE: August output workbook exists, September workbook still exists, and key workbook/CSV requirements were verified.')