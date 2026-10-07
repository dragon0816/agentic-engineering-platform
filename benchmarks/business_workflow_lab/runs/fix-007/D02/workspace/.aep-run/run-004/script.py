from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Alignment, Protection
from openpyxl.cell import MergedCell
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
import csv, datetime, re

ws_dir = Path.cwd()
input_dir = ws_dir / 'input'
output_dir = ws_dir / 'output'
output_dir.mkdir(exist_ok=True)

print('Inputs present:')
for p in sorted(input_dir.iterdir()):
    print('-', p.name)
print('Exports present:')
for p in sorted(output_dir.glob('*2026_09.csv')):
    print('-', p.name, p.stat().st_size)

# Read rates; notes include commas, only first two columns needed.
rates = {}
with open(input_dir/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('FX header:', header)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('FX rates:', rates)

# Read exports created via the Expense Viewer desktop application.
all_rows = []
for filename in ['submitted_2026_09.csv', 'approved_2026_09.csv']:
    path = output_dir / filename
    if not path.exists():
        raise FileNotFoundError(path)
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        print(filename, 'columns:', reader.fieldnames)
        for row in reader:
            all_rows.append(row)

# Validate source filters before writing.
allowed_status = {'Submitted', 'Approved'}
for row in all_rows:
    if row['Status'] not in allowed_status:
        raise ValueError(f"Unexpected status {row['Status']} in {row['ExpenseID']}")
    if not ('2026-09-01' <= row['ExpenseDate'] <= '2026-09-30'):
        raise ValueError(f"Out-of-period date {row['ExpenseDate']} in {row['ExpenseID']}")
    if row['Currency'] not in rates:
        raise ValueError(f"Missing FX rate for {row['Currency']}")

# Stable date/ID ordering across the combined statuses.
all_rows.sort(key=lambda r: (r['ExpenseDate'], r['ExpenseID']))
print('Combined row count:', len(all_rows))
print('Missing receipt IDs:', [r['ExpenseID'] for r in all_rows if r['MissingReceipt'].strip().lower() == 'true'])

# Helper copying template row styles/formats.
def copy_row_format(sh, src_row, dst_row, max_col):
    sh.row_dimensions[dst_row].height = sh.row_dimensions[src_row].height
    for col in range(1, max_col + 1):
        src = sh.cell(src_row, col)
        dst = sh.cell(dst_row, col)
        if src.has_style:
            dst._style = copy(src._style)
        if src.number_format:
            dst.number_format = src.number_format
        if src.alignment:
            dst.alignment = copy(src.alignment)
        if src.font:
            dst.font = copy(src.font)
        if src.fill:
            dst.fill = copy(src.fill)
        if src.border:
            dst.border = copy(src.border)
        if src.protection:
            dst.protection = copy(src.protection)

def clear_data_rows(sh, start_row, max_col):
    # clear existing data rows without touching header/merged header rows
    if sh.max_row >= start_row:
        for row in range(start_row, sh.max_row + 1):
            for col in range(1, max_col + 1):
                cell = sh.cell(row, col)
                if not isinstance(cell, MergedCell):
                    cell.value = None

wb = load_workbook(input_dir/'expense_template.xlsx')

# Report sheet metadata.
report = wb['Report']
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'ExpenseDate 2026-09-01 to 2026-09-30; Status in Submitted, Approved'
report['B5'] = '2026-10-06T00:00:00+08:00'
report['B7'] = 'Expense Viewer (synthetic lab); fx_rates.csv'
report['D7'] = '2026-10-06T00:00:00+08:00'
missing_ids = [r['ExpenseID'] for r in all_rows if r['MissingReceipt'].strip().lower() == 'true']
report['B9'] = f"Missing receipts listed in Exceptions: {', '.join(missing_ids)}" if missing_ids else 'No missing receipts.'

# Details sheet.
details = wb['Details']
headers = [details.cell(4, c).value for c in range(1, 15)]
print('Details headers:', headers)
clear_data_rows(details, 5, 14)
for idx, row in enumerate(all_rows, start=5):
    copy_row_format(details, 5, idx, 14)
    amount = Decimal(row['Amount'])
    amount_twd = (amount * rates[row['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    missing = row['MissingReceipt'].strip().lower() == 'true'
    values = [
        row['ExpenseID'], row['EmployeeID'], row['EmployeeName'], row['ProjectID'],
        row['ExpenseDate'], row['Category'], row['Currency'], float(amount), float(amount_twd),
        row['Status'], row['ReceiptID'] or None, row['Description'], str(missing).lower(), str(missing).lower()
    ]
    for col, val in enumerate(values, start=1):
        cell = details.cell(idx, col, val)
        if col in [1,2,4,10,11,12,13,14]:
            cell.number_format = '@'
        elif col in [8,9]:
            cell.number_format = '0.00'
        elif col == 5:
            cell.number_format = 'yyyy-mm-dd'

# Update autofilter if present.
if details.auto_filter and details.auto_filter.ref:
    details.auto_filter.ref = f"A4:N{4+len(all_rows)}"

# Summary by Status and Currency.
summary = wb['Summary']
clear_data_rows(summary, 5, 6)
summary['B2'] = f"=SUM(Details!I5:I{4+len(all_rows) if all_rows else 5})"
from collections import defaultdict
summ = defaultdict(lambda: {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
for row in all_rows:
    amount = Decimal(row['Amount'])
    twd = (amount * rates[row['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    key = (row['Status'], '', row['Currency'])
    summ[key]['amount'] += amount
    summ[key]['twd'] += twd
    summ[key]['count'] += 1
summary_rows = sorted(summ.items(), key=lambda kv: (kv[0][0], kv[0][2]))
for idx, ((group, subgroup, currency), vals) in enumerate(summary_rows, start=5):
    copy_row_format(summary, 5, idx, 6)
    out = [group, subgroup or None, currency, float(vals['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), float(vals['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), vals['count']]
    for col, val in enumerate(out, start=1):
        cell = summary.cell(idx, col, val)
        if col in [4,5]:
            cell.number_format = '0.00'

# Exceptions for missing receipt, preserving original ExpenseID and retaining in Details.
exceptions = wb['Exceptions']
clear_data_rows(exceptions, 5, 4)
exc_rows = [r for r in all_rows if r['MissingReceipt'].strip().lower() == 'true']
for idx, row in enumerate(exc_rows, start=5):
    copy_row_format(exceptions, 5, idx, 4)
    vals = [row['ExpenseID'], row['EmployeeID'], row['ExpenseDate'], 'Missing receipt']
    for col, val in enumerate(vals, start=1):
        cell = exceptions.cell(idx, col, val)
        if col in [1,2,4]:
            cell.number_format = '@'
        elif col == 3:
            cell.number_format = 'yyyy-mm-dd'
if exceptions.auto_filter and exceptions.auto_filter.ref:
    exceptions.auto_filter.ref = f"A4:D{4+len(exc_rows)}"

out_path = output_dir / 'expense_report_2026_09_submitted_approved.xlsx'
wb.save(out_path)
print('Wrote', out_path)

# Re-open and verify all stated requirements and template rules.
check = load_workbook(out_path, data_only=False)
errors=[]
# Sheet names unchanged
if check.sheetnames != load_workbook(input_dir/'expense_template.xlsx', read_only=True).sheetnames:
    errors.append('Sheet names changed')
# Header names
det = check['Details']
if [det.cell(4,c).value for c in range(1,15)] != headers:
    errors.append('Details headers changed')
# Details row count and values.
data_rows=[]
for r in range(5, 5+len(all_rows)):
    vals=[det.cell(r,c).value for c in range(1,15)]
    data_rows.append(vals)
if len(data_rows) != 22:
    errors.append(f'Details expected 22 rows, got {len(data_rows)}')
ids=[v[0] for v in data_rows]
if set(ids) != {r['ExpenseID'] for r in all_rows}:
    errors.append('Details ExpenseID set mismatch')
for v in data_rows:
    if v[9] not in allowed_status:
        errors.append(f'Bad status {v[9]}')
    if not ('2026-09-01' <= v[4] <= '2026-09-30'):
        errors.append(f'Bad date {v[4]}')
    if not isinstance(v[7], (int,float)) or not isinstance(v[8], (int,float)):
        errors.append(f'Amounts not numeric for {v[0]}')
    if v[12] not in ('true','false') or v[13] not in ('true','false'):
        errors.append(f'Boolean text bad for {v[0]}')
# Receipt details present from export (blank retained for missing)
for source in all_rows:
    rownum = ids.index(source['ExpenseID']) + 5
    if det.cell(rownum,11).value != (source['ReceiptID'] or None):
        errors.append(f'ReceiptID mismatch {source["ExpenseID"]}')
    if det.cell(rownum,12).value != source['Description']:
        errors.append(f'Description mismatch {source["ExpenseID"]}')
# Exceptions
exc = check['Exceptions']
exc_ids=[]
for r in range(5, 5+len(exc_rows)):
    exc_ids.append(exc.cell(r,1).value)
if exc_ids != missing_ids:
    errors.append(f'Exception IDs mismatch {exc_ids} vs {missing_ids}')
for mid in missing_ids:
    if mid not in ids:
        errors.append(f'Missing receipt expense removed from Details: {mid}')
# Summary formula and rows
sumsh = check['Summary']
expected_formula = '=SUM(Details!I5:I26)'
if sumsh['B2'].value != expected_formula:
    errors.append(f'Summary formula {sumsh["B2"].value} != {expected_formula}')
# Total TWD check with workbook values.
det_total = sum(Decimal(str(det.cell(r,9).value)) for r in range(5,27))
calc_total = sum((Decimal(r['Amount']) * rates[r['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for r in all_rows)
if det_total != calc_total:
    errors.append(f'Total TWD mismatch {det_total} vs {calc_total}')

print('Verification:')
print('- output file exists:', out_path.exists(), out_path.stat().st_size, 'bytes')
print('- Details rows:', len(data_rows))
print('- Details ExpenseIDs:', ids)
print('- Exception ExpenseIDs:', exc_ids)
print('- Summary rows:', len(summary_rows), 'formula:', sumsh['B2'].value, 'total TWD:', det_total)
print('- ReceiptID/Description/MissingReceipt columns verified from exported detail columns')
print('- Missing receipt rows retained in Details:', all(mid in ids for mid in missing_ids))
if errors:
    print('ERRORS:')
    for e in errors: print(' -', e)
    raise SystemExit(1)
print('All checks passed.')