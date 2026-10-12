from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border
from openpyxl.utils import get_column_letter
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import csv, re, os, json

ws = Path.cwd()
in_dir = ws/'input'
out_dir = ws/'output'
out_dir.mkdir(exist_ok=True)

TEMPLATE = in_dir/'expense_template.xlsx'
FX = in_dir/'fx_rates.csv'
CSV_FILES = [out_dir/'submitted_2026-09.csv', out_dir/'approved_2026-09.csv']
OUT = out_dir/'expense_report_2026-09_submitted_approved.xlsx'

print('Inputs:')
print(' template', TEMPLATE, TEMPLATE.exists())
print(' fx', FX, FX.exists())
for p in CSV_FILES:
    print(' csv', p.name, p.exists(), p.stat().st_size if p.exists() else None)

# Read FX rates robustly even if notes contain unquoted commas; first two columns are what matters.
rates = {}
with open(FX, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('fx header:', header)
    for row in reader:
        if len(row) >= 2 and row[0].strip():
            rates[row[0].strip()] = Decimal(row[1].strip())
print('rates:', rates)

records = []
for p in CSV_FILES:
    with open(p, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        print(p.name, 'headers:', reader.fieldnames)
        for row in reader:
            row = {k: (v if v is not None else '') for k, v in row.items()}
            records.append(row)

# Validate and filter exactly requested period/status from exported sources.
allowed_status = {'Submitted', 'Approved'}
filtered = []
for r in records:
    d = r['ExpenseDate']
    st = r['Status']
    if '2026-09-01' <= d <= '2026-09-30' and st in allowed_status:
        filtered.append(r)
    else:
        print('excluded unexpected row:', r)

# De-duplicate by ExpenseID if same expense appears twice; keep first.
seen = set(); deduped = []
for r in filtered:
    eid = r['ExpenseID']
    if eid in seen:
        print('duplicate skipped:', eid)
        continue
    seen.add(eid); deduped.append(r)

# Sort stable by ExpenseDate, ExpenseID for repeatable report.
deduped.sort(key=lambda r: (r['ExpenseDate'], r['ExpenseID']))
print('records selected:', len(deduped))
print('first rows:', deduped[:3])

wb = load_workbook(TEMPLATE)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']
exceptions = wb['Exceptions']

# Utility: clear old data rows without disturbing header/format too much.
def clear_from(sheet, start_row, max_col):
    if sheet.max_row >= start_row:
        for row in sheet.iter_rows(min_row=start_row, max_row=sheet.max_row, max_col=max_col):
            for c in row:
                c.value = None

clear_from(details, 5, 14)
clear_from(summary, 5, 6)
clear_from(exceptions, 5, 4)

# Copy row style from template row 5 if present, else row 4.
def copy_row_style(sheet, src_row, dst_row, max_col):
    for col in range(1, max_col+1):
        src = sheet.cell(src_row, col)
        dst = sheet.cell(dst_row, col)
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

# Fill report metadata.
now_iso = datetime.now().astimezone().isoformat(timespec='seconds')
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'ExpenseDate 2026-09-01~2026-09-30; Status in Submitted, Approved'
report['B5'] = now_iso
report['B7'] = 'Expense Viewer export CSV; fx_rates.csv'
report['D7'] = now_iso
report['B9'] = 'Missing receipt expenses are retained in Details and listed in Exceptions.'

headers = [details.cell(4, c).value for c in range(1, 15)]
print('detail headers:', headers)

# Number formats.
for i, r in enumerate(deduped, start=5):
    copy_row_style(details, 5 if details.max_row >= 5 else 4, i, 14)
    currency = r['Currency'].strip()
    amount = Decimal(str(r['Amount']).strip())
    if currency not in rates:
        raise ValueError(f'Missing FX rate for {currency}')
    amount_twd = (amount * rates[currency]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    missing_bool = str(r.get('MissingReceipt','')).strip().lower() == 'true'
    values = [
        r['ExpenseID'], r['EmployeeID'], r['EmployeeName'], r['ProjectID'], r['ExpenseDate'],
        r['Category'], currency, float(amount), float(amount_twd), r['Status'],
        r.get('ReceiptID',''), r.get('Description',''), 'true' if missing_bool else 'false',
        'true' if missing_bool else 'false'
    ]
    for col, val in enumerate(values, start=1):
        cell = details.cell(i, col)
        cell.value = val
        if col in [1,2,4,7,10,11,12,13,14]:
            cell.number_format = '@'
        elif col == 5:
            cell.number_format = 'yyyy-mm-dd'
        elif col in [8,9]:
            cell.number_format = '0.00'

last_detail_row = 4 + len(deduped)
summary['B2'] = f'=SUM(Details!I5:I{last_detail_row if deduped else 5})'

# Summary grouped by Status + Currency.
from collections import defaultdict
sum_map = defaultdict(lambda: {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
for r in deduped:
    key = (r['Status'], r['Currency'])
    amount = Decimal(str(r['Amount']).strip())
    twd = (amount * rates[r['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    sum_map[key]['amount'] += amount
    sum_map[key]['twd'] += twd
    sum_map[key]['count'] += 1
for idx, ((status, currency), agg) in enumerate(sorted(sum_map.items()), start=5):
    copy_row_style(summary, 5 if summary.max_row >= 5 else 4, idx, 6)
    vals = [status, '', currency, float(agg['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), float(agg['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), agg['count']]
    for col, val in enumerate(vals, start=1):
        cell = summary.cell(idx, col)
        cell.value = val
        if col in [1,2,3]: cell.number_format = '@'
        elif col in [4,5]: cell.number_format = '0.00'
        elif col == 6: cell.number_format = '0'

# Exceptions: missing receipts, keep original ExpenseID.
missing = [r for r in deduped if str(r.get('MissingReceipt','')).strip().lower() == 'true']
for idx, r in enumerate(missing, start=5):
    copy_row_style(exceptions, 5 if exceptions.max_row >= 5 else 4, idx, 4)
    vals = [r['ExpenseID'], r['EmployeeID'], r['ExpenseDate'], 'Missing receipt']
    for col, val in enumerate(vals, start=1):
        cell = exceptions.cell(idx, col)
        cell.value = val
        if col in [1,2,4]: cell.number_format = '@'
        elif col == 3: cell.number_format = 'yyyy-mm-dd'

# Keep filters if present or set useful ranges.
details.auto_filter.ref = f'A4:N{last_detail_row if deduped else 5}'
summary.auto_filter.ref = f'A4:F{4 + len(sum_map) if sum_map else 5}'
exceptions.auto_filter.ref = f'A4:D{4 + len(missing) if missing else 5}'

wb.save(OUT)
print('Wrote', OUT, OUT.stat().st_size)
print('selected count', len(deduped), 'missing count', len(missing), 'summary groups', len(sum_map))
print('missing ids', [r['ExpenseID'] for r in missing])
print('output files now:', [p.name for p in sorted(out_dir.glob('*'))])