from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from zoneinfo import ZoneInfo
import csv, shutil, json, os

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)

TEMPLATE = INPUT / 'expense_template.xlsx'
FX = INPUT / 'fx_rates.csv'
EXPORT = OUTPUT / 'expense_E006_2026-01.csv'
REPORT = OUTPUT / 'expense_report_E006_2026-01.xlsx'
EMPLOYEE = 'E006'
DATE_FROM = '2026-01-01'
DATE_TO = '2026-01-31'

print('Inputs being processed:')
print(' template:', TEMPLATE, TEMPLATE.exists(), TEMPLATE.stat().st_size if TEMPLATE.exists() else None)
print(' fx:', FX, FX.exists(), FX.stat().st_size if FX.exists() else None)
print(' export:', EXPORT, EXPORT.exists(), EXPORT.stat().st_size if EXPORT.exists() else None)
if not EXPORT.exists() or EXPORT.stat().st_size == 0:
    raise FileNotFoundError('Export CSV is missing or empty; not treating missing export as success')

# Read fx rates; Note column in this synthetic CSV contains an unquoted comma, so use first two columns only.
rates = {}
with FX.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('fx header:', header)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('rates:', {k: str(v) for k, v in rates.items()})

# Read exported expense rows.
with EXPORT.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    source_headers = reader.fieldnames or []
    rows = list(reader)
print('export headers:', source_headers)
print('export row count:', len(rows))
print('first rows:', rows[:3])

expected_source_headers = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','Status','ReceiptID','Description','MissingReceipt']
if source_headers != expected_source_headers:
    raise AssertionError(f'Unexpected export headers: {source_headers}')

# Validate query constraints and prepare rows for workbook.
prepared = []
exceptions = []
for r in rows:
    if r.get('EmployeeID') != EMPLOYEE:
        raise AssertionError(f"Row outside requested employee: {r}")
    d = r.get('ExpenseDate') or ''
    if not (DATE_FROM <= d <= DATE_TO):
        raise AssertionError(f"Row outside requested date range: {r}")
    cur = r.get('Currency') or ''
    amount_text = r.get('Amount') or ''
    if cur and cur not in rates:
        exceptions.append((r.get('ExpenseID',''), r.get('EmployeeID',''), d, f'Missing FX rate for {cur}'))
        rate = Decimal('0')
    else:
        rate = rates.get(cur, Decimal('0'))
    amount = Decimal(amount_text) if amount_text else Decimal('0')
    amount_twd = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    missing_receipt = (r.get('MissingReceipt') or '').strip().lower()
    needs_review = 'true' if missing_receipt == 'true' else 'false'
    if missing_receipt == 'true':
        exceptions.append((r.get('ExpenseID',''), r.get('EmployeeID',''), d, 'Missing receipt'))
    prepared.append({**r, 'AmountDecimal': amount, 'AmountTWDDecimal': amount_twd, 'NeedsReview': needs_review})

# Build output from template, preserving workbook/sheet names and template formatting as much as practical.
wb = load_workbook(TEMPLATE)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']
exceptions_ws = wb['Exceptions']

now = datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds')
report['B3'] = DATE_FROM
report['D3'] = DATE_TO
report['B4'] = f'EmployeeID={EMPLOYEE}; ExpenseDate={DATE_FROM}..{DATE_TO}; Project=all; Status=all'
report['B5'] = now
report['B7'] = 'Expense Viewer (synthetic lab); fx_rates.csv'
report['D7'] = now
report['B9'] = 'No matching expense rows; exported header-only CSV and generated an empty report.' if not prepared else ''

# Clear old rows below row 4 if template contains any, but leave header row intact.
def clear_data_rows(ws, first_row, max_col):
    if ws.max_row >= first_row:
        for row in ws.iter_rows(min_row=first_row, max_row=ws.max_row, max_col=max_col):
            for cell in row:
                cell.value = None

clear_data_rows(details, 5, 14)
clear_data_rows(summary, 5, 6)
clear_data_rows(exceptions_ws, 5, 4)

# Details rows.
for idx, r in enumerate(prepared, start=5):
    values = [
        r.get('ExpenseID') or None,
        r.get('EmployeeID') or None,
        r.get('EmployeeName') or None,
        r.get('ProjectID') or None,
        r.get('ExpenseDate') or None,
        r.get('Category') or None,
        r.get('Currency') or None,
        float(r['AmountDecimal']),
        float(r['AmountTWDDecimal']),
        r.get('Status') or None,
        r.get('ReceiptID') or None,
        r.get('Description') or None,
        (r.get('MissingReceipt') or '').strip().lower() if r.get('MissingReceipt') != '' else None,
        r['NeedsReview'],
    ]
    for col, value in enumerate(values, start=1):
        cell = details.cell(row=idx, column=col, value=value)
        # IDs and boolean text columns stored as text; dates as YYYY-MM-DD text per template instruction.
        if col in [1,2,4,5,10,11,12,13,14]:
            cell.number_format = '@'
        if col in [8,9]:
            cell.number_format = '0.00'

last_detail_row = 4 + max(len(prepared), 1)  # empty report keeps formula I5:I5.
summary['B2'] = f'=SUM(Details!I5:I{last_detail_row})'

# Summary by Status/Currency when data exists; no rows for an empty report.
from collections import defaultdict
summary_groups = defaultdict(lambda: {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
for r in prepared:
    key = (r.get('Status') or '', r.get('Category') or '', r.get('Currency') or '')
    summary_groups[key]['amount'] += r['AmountDecimal']
    summary_groups[key]['twd'] += r['AmountTWDDecimal']
    summary_groups[key]['count'] += 1
for row_idx, ((status, category, currency), agg) in enumerate(sorted(summary_groups.items()), start=5):
    vals = [status, category, currency, float(agg['amount']), float(agg['twd']), agg['count']]
    for col, value in enumerate(vals, start=1):
        c = summary.cell(row=row_idx, column=col, value=value)
        if col in [4,5]:
            c.number_format = '0.00'

# Exceptions.
for row_idx, exc in enumerate(exceptions, start=5):
    for col, value in enumerate(exc, start=1):
        cell = exceptions_ws.cell(row=row_idx, column=col, value=value or None)
        if col in [1,2,3]:
            cell.number_format = '@'

# Ensure text formats on ID columns even for empty first data row placeholders.
for ws, text_cols in [(details, [1,2,4,5,10,11,12,13,14]), (exceptions_ws, [1,2,3,4])]:
    for col in text_cols:
        ws.cell(row=5, column=col).number_format = '@'
for col in [8,9]:
    details.cell(row=5, column=col).number_format = '0.00'
for col in [4,5]:
    summary.cell(row=5, column=col).number_format = '0.00'

wb.save(REPORT)
print('wrote report:', REPORT, REPORT.stat().st_size)

# Verification: reopen saved workbook and exported CSV.
wb2 = load_workbook(REPORT, data_only=False)
assert wb2.sheetnames == ['Report', 'Details', 'Summary', 'Exceptions', 'Instructions']
rp = wb2['Report']; dt = wb2['Details']; sm = wb2['Summary']; ex = wb2['Exceptions']
checks = {}
checks['report_exists'] = REPORT.exists() and REPORT.stat().st_size > 0
checks['export_exists'] = EXPORT.exists() and EXPORT.stat().st_size > 0
checks['report_dates'] = (rp['B3'].value == DATE_FROM and rp['D3'].value == DATE_TO)
checks['condition_mentions_employee'] = EMPLOYEE in (rp['B4'].value or '')
checks['source_mentions_expense_viewer'] = 'Expense Viewer' in (rp['B7'].value or '')
checks['details_headers'] = [dt.cell(4,c).value for c in range(1,15)]
checks['details_header_match'] = checks['details_headers'] == ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
# Count non-empty detail rows from saved workbook.
detail_nonempty = 0
for row in dt.iter_rows(min_row=5, max_col=14, values_only=True):
    if any(v is not None for v in row):
        detail_nonempty += 1
checks['detail_nonempty_rows'] = detail_nonempty
checks['matches_export_row_count'] = detail_nonempty == len(rows)
checks['summary_formula'] = sm['B2'].value
summary_nonempty = 0
for row in sm.iter_rows(min_row=5, max_col=6, values_only=True):
    if any(v is not None for v in row):
        summary_nonempty += 1
checks['summary_nonempty_rows'] = summary_nonempty
exception_nonempty = 0
for row in ex.iter_rows(min_row=5, max_col=4, values_only=True):
    if any(v is not None for v in row):
        exception_nonempty += 1
checks['exception_nonempty_rows'] = exception_nonempty
checks['empty_report_is_normal'] = (len(rows) == 0 and detail_nonempty == 0 and summary_nonempty == 0 and exception_nonempty == 0 and sm['B2'].value == '=SUM(Details!I5:I5)') or len(rows) > 0

for name, result in checks.items():
    print(name, ':', result)
required_true = ['report_exists','export_exists','report_dates','condition_mentions_employee','source_mentions_expense_viewer','details_header_match','matches_export_row_count','empty_report_is_normal']
for name in required_true:
    if checks[name] is not True:
        raise AssertionError(f'Check failed: {name}={checks[name]}')
print('VERIFICATION PASSED')