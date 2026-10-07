from pathlib import Path
import csv
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
import openpyxl

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
print('Workspace:', ws)
print('Output files:', sorted(p.name for p in output_dir.glob('*')))

workbook_path = output_dir / 'E001_september_expenses.xlsx'
export_path = output_dir / 'expense_export_E001_2026-09-01_2026-09-30.csv'
compat_export_path = output_dir / 'E001_september_expenses_export.csv'
for p in [workbook_path, export_path, compat_export_path]:
    assert p.exists(), f'missing {p}'
    print(f'Found {p.name}: {p.stat().st_size} bytes')

# CSV export from desktop app
with export_path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    csv_rows = list(reader)
    csv_headers = reader.fieldnames
print('CSV headers:', csv_headers)
print('CSV row count:', len(csv_rows))
assert csv_headers == ['ExpenseID', 'EmployeeID', 'EmployeeName', 'ProjectID', 'ExpenseDate', 'Category', 'Currency', 'Amount', 'Status', 'ReceiptID', 'Description', 'MissingReceipt']
assert len(csv_rows) == 13
assert all(r['EmployeeID'] == 'E001' for r in csv_rows)
assert all('2026-09-01' <= r['ExpenseDate'] <= '2026-09-30' for r in csv_rows)

# FX rates
with (input_dir / 'fx_rates.csv').open('r', encoding='utf-8-sig', newline='') as f:
    rate_rows = list(csv.DictReader(f))
fx = {r['Currency']: Decimal(r['RateToTWD']) for r in rate_rows}
print('FX rates used:', fx)

expected_summary = defaultdict(lambda: {'Count': 0, 'Amount': Decimal('0'), 'AmountTWD': Decimal('0')})
expected_exceptions = []
for r in csv_rows:
    amount = Decimal(r['Amount'])
    amount_twd = (amount * fx[r['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    key = (r['Status'], r['Currency'])
    expected_summary[key]['Count'] += 1
    expected_summary[key]['Amount'] += amount
    expected_summary[key]['AmountTWD'] += amount_twd
    if r['MissingReceipt'].strip().lower() == 'true':
        expected_exceptions.append(r)
expected_twd_total = sum(v['AmountTWD'] for v in expected_summary.values())
print('Expected summary groups:', dict(expected_summary))
print('Expected TWD total:', expected_twd_total)
print('Expected exceptions:', len(expected_exceptions))

# Workbook
wb = openpyxl.load_workbook(workbook_path, data_only=False)
print('Workbook sheets:', wb.sheetnames)
for sheet in ['Report', 'Details', 'Summary', 'Exceptions', 'Instructions']:
    assert sheet in wb.sheetnames, f'missing sheet {sheet}'

def table(sheet_name):
    sh = wb[sheet_name]
    headers = [sh.cell(4, c).value for c in range(1, sh.max_column + 1)]
    while headers and headers[-1] is None:
        headers.pop()
    rows = []
    for rr in range(5, sh.max_row + 1):
        vals = [sh.cell(rr, c).value for c in range(1, len(headers) + 1)]
        if any(v is not None for v in vals):
            rows.append(dict(zip(headers, vals)))
    return headers, rows

d_headers, d_rows = table('Details')
s_headers, s_rows = table('Summary')
e_headers, e_rows = table('Exceptions')
print('Details headers:', d_headers)
print('Summary headers:', s_headers)
print('Exceptions headers:', e_headers)
print('Details rows:', len(d_rows))
print('Summary rows:', len(s_rows))
print('Exceptions rows:', len(e_rows))
print('Summary B2 formula:', wb['Summary']['B2'].value)

assert d_headers == ['ExpenseID', 'EmployeeID', 'EmployeeName', 'ProjectID', 'ExpenseDate', 'Category', 'Currency', 'Amount', 'AmountTWD', 'Status', 'ReceiptID', 'Description', 'MissingReceipt', 'NeedsReview']
assert s_headers == ['Group', 'SubGroup', 'Currency', 'Amount', 'AmountTWD', 'Count']
assert e_headers == ['ExpenseID', 'EmployeeID', 'ExpenseDate', 'Reason']
assert len(d_rows) == 13
assert len(s_rows) == 7
assert len(e_rows) == 1
assert wb['Summary']['B2'].value == '=SUM(Details!I5:I17)'

# Details check against CSV and types/placeholders.
for r in d_rows:
    assert isinstance(r['ExpenseID'], str)
    assert isinstance(r['EmployeeID'], str)
    assert isinstance(r['Amount'], (int, float))
    assert isinstance(r['AmountTWD'], (int, float))
    assert str(r['MissingReceipt']) in {'true', 'false'}
    assert str(r['NeedsReview']) in {'true', 'false'}
    assert r['EmployeeID'] == 'E001'
    assert '2026-09-01' <= r['ExpenseDate'] <= '2026-09-30'

# Summary check: Group = status, Currency = currency.
for r in s_rows:
    key = (r['Group'], r['Currency'])
    assert key in expected_summary, f'unexpected summary row {r}'
    exp = expected_summary[key]
    assert int(r['Count']) == exp['Count'], f'count mismatch {key}'
    assert Decimal(str(r['Amount'])).quantize(Decimal('0.01')) == exp['Amount'].quantize(Decimal('0.01')), f'amount mismatch {key}'
    assert Decimal(str(r['AmountTWD'])).quantize(Decimal('0.01')) == exp['AmountTWD'].quantize(Decimal('0.01')), f'amountTWD mismatch {key}'
workbook_twd_total = sum(Decimal(str(r['AmountTWD'])).quantize(Decimal('0.01')) for r in s_rows)
assert workbook_twd_total == expected_twd_total == Decimal('31877.90')
print('Workbook TWD total from Summary rows:', workbook_twd_total)

# Exceptions check: one missing receipt from CSV.
assert e_rows[0]['ExpenseID'] == expected_exceptions[0]['ExpenseID'] == 'EXP-00006'
assert e_rows[0]['EmployeeID'] == 'E001'
assert e_rows[0]['ExpenseDate'] == '2026-09-10'
assert e_rows[0]['Reason'] == 'Missing receipt'

print('FINAL CHECK PASSED')
print('Verified: exported CSV, filled template workbook, details/status-currency summary, TWD total 31877.90, and missing-receipt exception.')
