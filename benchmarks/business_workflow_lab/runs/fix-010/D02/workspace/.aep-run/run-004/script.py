from pathlib import Path
import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from copy import copy
from openpyxl import load_workbook

workspace = Path.cwd()
in_dir = workspace / 'input'
out_dir = workspace / 'output'
out_dir.mkdir(exist_ok=True)

# Read source files exported from Expense Viewer. These exports are the current filtered full result sets
# and include the detail-window fields ReceiptID, Description, MissingReceipt.
records = []
source_counts = {}
for name in ['submitted_2026-09.csv', 'approved_2026-09.csv']:
    path = out_dir / name
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        print(name, 'headers:', reader.fieldnames)
        rows = list(reader)
        source_counts[name] = len(rows)
        print(name, 'rows:', len(rows), 'sample:', rows[:1])
        records.extend(rows)

# Read FX rates. CSV note text has commas; only first two columns are needed.
rates = {}
with (in_dir / 'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('fx header:', header)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('rates:', {k: str(v) for k, v in rates.items()})

allowed_status = {'Submitted','Approved'}
for r in records:
    assert '2026-09-01' <= r['ExpenseDate'] <= '2026-09-30', r
    assert r['Status'] in allowed_status, r
    assert r['Currency'] in rates, r

records.sort(key=lambda r: (r['ExpenseDate'], r['ExpenseID']))

for r in records:
    amt = Decimal(r['Amount'])
    r['AmountTWD'] = (amt * rates[r['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    missing = str(r.get('MissingReceipt','')).strip().lower() == 'true'
    r['MissingReceiptOut'] = 'true' if missing else 'false'
    r['NeedsReview'] = 'true' if missing else 'false'
    r['ExpenseDateObj'] = date.fromisoformat(r['ExpenseDate'])

wb = load_workbook(in_dir / 'expense_template.xlsx')
ws_report = wb['Report']
ws_details = wb['Details']
ws_summary = wb['Summary']
ws_ex = wb['Exceptions']

def clear_data(ws, start_row=5):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

def copy_row_style(ws, src_row, dst_row, max_col):
    for col in range(1, max_col+1):
        src = ws.cell(src_row, col)
        dst = ws.cell(dst_row, col)
        if src.has_style:
            dst._style = copy(src._style)
        dst.number_format = src.number_format
        dst.alignment = copy(src.alignment)
        dst.font = copy(src.font)
        dst.fill = copy(src.fill)
        dst.border = copy(src.border)

clear_data(ws_details)
clear_data(ws_summary)
clear_data(ws_ex)

now_iso = datetime.now().astimezone().isoformat(timespec='seconds')
ws_report['B3'] = date(2026, 9, 1); ws_report['B3'].number_format = 'yyyy-mm-dd'
ws_report['D3'] = date(2026, 9, 30); ws_report['D3'].number_format = 'yyyy-mm-dd'
ws_report['B4'] = 'Status in Submitted, Approved; ExpenseDate 2026-09-01 through 2026-09-30'
ws_report['B5'] = now_iso
ws_report['B7'] = 'Expense Viewer; fx_rates.csv'
ws_report['D7'] = now_iso

for idx, r in enumerate(records, start=5):
    copy_row_style(ws_details, 4, idx, 14)
    values = [
        r['ExpenseID'], r['EmployeeID'], r['EmployeeName'], r['ProjectID'], r['ExpenseDateObj'],
        r['Category'], r['Currency'], float(Decimal(r['Amount'])), float(r['AmountTWD']), r['Status'],
        r.get('ReceiptID','') or None, r.get('Description','') or None, r['MissingReceiptOut'], r['NeedsReview']
    ]
    for col, val in enumerate(values, start=1):
        c = ws_details.cell(idx, col, val)
        if col in (1,2,3,4,6,7,10,11,12,13,14):
            c.number_format = '@'
        elif col == 5:
            c.number_format = 'yyyy-mm-dd'
        elif col in (8,9):
            c.number_format = '0.00'

last_detail = 4 + len(records) if records else 5
ws_summary['B2'] = f'=SUM(Details!I5:I{last_detail})' if records else '=SUM(Details!I5:I5)'
ws_summary['B2'].number_format = '0.00'

# Summary by Status and Currency, avoiding mixed-currency original amount totals.
summary = {}
for r in records:
    key = (r['Status'], '', r['Currency'])
    summary.setdefault(key, {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
    summary[key]['amount'] += Decimal(r['Amount'])
    summary[key]['twd'] += r['AmountTWD']
    summary[key]['count'] += 1

for idx, (key, vals) in enumerate(sorted(summary.items()), start=5):
    copy_row_style(ws_summary, 4, idx, 6)
    status, sub, cur = key
    rowvals = [status, sub or None, cur, float(vals['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), float(vals['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), vals['count']]
    for col, val in enumerate(rowvals, start=1):
        c = ws_summary.cell(idx, col, val)
        if col in (1,2,3): c.number_format = '@'
        elif col in (4,5): c.number_format = '0.00'
        elif col == 6: c.number_format = '0'

exceptions = [r for r in records if r['MissingReceiptOut'] == 'true']
for idx, r in enumerate(exceptions, start=5):
    copy_row_style(ws_ex, 4, idx, 4)
    vals = [r['ExpenseID'], r['EmployeeID'], r['ExpenseDateObj'], 'Missing receipt']
    for col, val in enumerate(vals, start=1):
        c = ws_ex.cell(idx, col, val)
        if col in (1,2,4): c.number_format = '@'
        elif col == 3: c.number_format = 'yyyy-mm-dd'

ws_report['B9'] = f'{len(records)} expense rows included. Missing receipt exceptions: {len(exceptions)}; all exception rows remain in Details.'

out_path = out_dir / 'expense_report_2026-09_submitted_approved.xlsx'
wb.save(out_path)
print('wrote', out_path)
print('detail_rows', len(records), 'exception_rows', len(exceptions), 'summary_rows', len(summary))
print('exception IDs:', [r['ExpenseID'] for r in exceptions])

# Reopen and verify the saved workbook.
wb2 = load_workbook(out_path, data_only=False)
d = wb2['Details']; s = wb2['Summary']; e = wb2['Exceptions']; rep = wb2['Report']
expected_headers = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
headers = [d.cell(4,c).value for c in range(1,15)]
assert headers == expected_headers, headers
out_rows = [r for r in range(5, d.max_row+1) if d.cell(r,1).value]
assert len(out_rows) == 22, len(out_rows)
assert source_counts == {'submitted_2026-09.csv': 7, 'approved_2026-09.csv': 15}, source_counts
statuses = {d.cell(r,10).value for r in out_rows}
assert statuses == {'Submitted','Approved'}, statuses
for r in out_rows:
    assert isinstance(d.cell(r,5).value, datetime), type(d.cell(r,5).value)
    assert date(2026,9,1) <= d.cell(r,5).value.date() <= date(2026,9,30), d.cell(r,5).value
    assert isinstance(d.cell(r,8).value, (int,float)), (r, d.cell(r,8).value)
    assert isinstance(d.cell(r,9).value, (int,float)), (r, d.cell(r,9).value)
    assert d.cell(r,13).value in ('true','false'), (r, d.cell(r,13).value)
    assert d.cell(r,14).value in ('true','false'), (r, d.cell(r,14).value)
expids = {d.cell(r,1).value for r in out_rows}
missing_details = [d.cell(r,1).value for r in out_rows if d.cell(r,13).value == 'true']
assert set(missing_details) == {'EXP-00015','EXP-00006'}, missing_details
# Missing-receipt rows have blank ReceiptID and are still present in Details.
for r in out_rows:
    if d.cell(r,1).value in {'EXP-00015','EXP-00006'}:
        assert d.cell(r,11).value in (None, ''), (d.cell(r,1).value, d.cell(r,11).value)
ex_rows = [r for r in range(5, e.max_row+1) if e.cell(r,1).value]
ex_ids = [e.cell(r,1).value for r in ex_rows]
assert set(ex_ids) == {'EXP-00015','EXP-00006'}, ex_ids
assert all(x in expids for x in ex_ids), ex_ids
assert isinstance(rep['B3'].value, datetime) and isinstance(rep['D3'].value, datetime)
assert rep['B3'].value.date() == date(2026,9,1) and rep['D3'].value.date() == date(2026,9,30)
assert s['B2'].value == '=SUM(Details!I5:I26)', s['B2'].value
# Verify all currencies have rate and a sample ROUND_HALF_UP calculation exactness by recomputing from saved rows.
rate_by_cur = rates
for r in out_rows:
    cur = d.cell(r,7).value
    amt = Decimal(str(d.cell(r,8).value))
    expected = (amt * rate_by_cur[cur]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    saved = Decimal(str(d.cell(r,9).value)).quantize(Decimal('0.01'))
    assert saved == expected, (r, cur, amt, saved, expected)
print('CHECK OK: reopened output; template sheet names/headers preserved; Details has 22 rows (7 Submitted + 15 Approved), Sep-2026 dates only, detail fields populated, numeric Amount/AmountTWD, ROUND_HALF_UP FX, Summary formula range, and missing-receipt ExpenseIDs listed in Exceptions while retained in Details.')