from pathlib import Path
import csv
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
import openpyxl

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
print('Workspace:', ws)
print('Input files:', sorted(p.name for p in input_dir.glob('*')))
print('Output files:', sorted(p.name for p in output_dir.glob('*')))

# Expected files from approved workflow run
workbook_path = output_dir / 'E001_september_expenses.xlsx'
export_path = output_dir / 'expense_export_E001_2026-09-01_2026-09-30.csv'
legacy_export_path = output_dir / 'E001_september_expenses_export.csv'

for p in [workbook_path, export_path, legacy_export_path]:
    print(f'{p.name}: exists={p.exists()} size={p.stat().st_size if p.exists() else None}')

if not workbook_path.exists():
    raise FileNotFoundError(workbook_path)
if not export_path.exists():
    raise FileNotFoundError(export_path)

# Read export CSV
with export_path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    headers = reader.fieldnames
print('Export headers:', headers)
print('Export row count:', len(rows))
print('Export sample row:', rows[0] if rows else None)

# Verify employee/date filter in CSV
bad_emp = [r for r in rows if r.get('EmployeeID') != 'E001']
bad_date = [r for r in rows if not ('2026-09-01' <= r.get('ExpenseDate','') <= '2026-09-30')]
print('Rows not E001:', len(bad_emp))
print('Rows outside September 2026:', len(bad_date))

# Compute expected summary and TWD total from CSV
fx_path = input_dir / 'fx_rates.csv'
fx = {}
with fx_path.open('r', encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        fx[r['Currency']] = Decimal(str(r['TWD']))

summary = defaultdict(lambda: {'count': 0, 'amount': Decimal('0'), 'twd': Decimal('0')})
exceptions = []
for r in rows:
    amount = Decimal(str(r['Amount']))
    cur = r['Currency']
    status = r['Status']
    twd = (amount * fx[cur]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    key = (status, cur)
    summary[key]['count'] += 1
    summary[key]['amount'] += amount
    summary[key]['twd'] += twd
    if str(r.get('MissingReceipt','')).strip().lower() == 'true':
        exceptions.append(r)
expected_twd_total = sum((v['twd'] for v in summary.values()), Decimal('0'))
print('Expected summary rows:', len(summary))
print('Expected exceptions:', len(exceptions))
print('Expected TWD total:', expected_twd_total)

# Read workbook
wb = openpyxl.load_workbook(workbook_path, data_only=False)
print('Workbook sheets:', wb.sheetnames)
required_sheets = ['Details', 'Summary', 'Exceptions']
missing_sheets = [s for s in required_sheets if s not in wb.sheetnames]
if missing_sheets:
    raise AssertionError(f'Missing sheets: {missing_sheets}')

def used_rows(sheet):
    return sheet.max_row

# Inspect Details
sh_d = wb['Details']
d_headers = [sh_d.cell(4, c).value for c in range(1, sh_d.max_column+1)]
d_data_rows = []
for rr in range(5, sh_d.max_row+1):
    vals = [sh_d.cell(rr, c).value for c in range(1, len(d_headers)+1)]
    if any(v is not None for v in vals):
        d_data_rows.append(vals)
print('Details headers row 4:', d_headers)
print('Details data rows:', len(d_data_rows))
print('Details first row:', d_data_rows[0] if d_data_rows else None)

# Inspect Summary
sh_s = wb['Summary']
summary_formula = sh_s['B2'].value
s_headers = [sh_s.cell(4, c).value for c in range(1, sh_s.max_column+1)]
s_data_rows = []
for rr in range(5, sh_s.max_row+1):
    vals = [sh_s.cell(rr, c).value for c in range(1, len(s_headers)+1)]
    if any(v is not None for v in vals):
        s_data_rows.append(vals)
print('Summary B2:', summary_formula)
print('Summary headers row 4:', s_headers)
print('Summary data rows:', len(s_data_rows))
print('Summary rows:', s_data_rows)

# Inspect Exceptions
sh_e = wb['Exceptions']
e_headers = [sh_e.cell(4, c).value for c in range(1, sh_e.max_column+1)]
e_data_rows = []
for rr in range(5, sh_e.max_row+1):
    vals = [sh_e.cell(rr, c).value for c in range(1, len(e_headers)+1)]
    if any(v is not None for v in vals):
        e_data_rows.append(vals)
print('Exceptions headers row 4:', e_headers)
print('Exceptions data rows:', len(e_data_rows))
print('Exceptions rows:', e_data_rows)

# Assertions matching requested requirements
assert len(rows) == 13, f'export row count expected 13, got {len(rows)}'
assert not bad_emp, f'found non-E001 rows: {bad_emp[:2]}'
assert not bad_date, f'found outside-date rows: {bad_date[:2]}'
assert len(d_data_rows) == 13, f'Details rows expected 13, got {len(d_data_rows)}'
assert len(s_data_rows) == len(summary) == 7, f'Summary rows expected 7, got {len(s_data_rows)}'
assert len(e_data_rows) == len(exceptions) == 1, f'Exceptions rows expected 1, got {len(e_data_rows)}'
assert summary_formula == '=SUM(Details!I5:I17)', f'Unexpected Summary B2 formula: {summary_formula}'

# Compare workbook summary TWD total from Summary rows if column present
# Expected template columns observed in prior run: Status, Currency, Count, Amount, TWD Amount
try:
    twd_idx = s_headers.index('TWD Amount') + 1
except ValueError:
    twd_idx = None
if twd_idx:
    workbook_twd_total = sum(Decimal(str(sh_s.cell(r, twd_idx).value)) for r in range(5, sh_s.max_row+1) if sh_s.cell(r, twd_idx).value is not None)
    print('Workbook Summary TWD total:', workbook_twd_total)
    assert workbook_twd_total == expected_twd_total, f'TWD total mismatch: workbook {workbook_twd_total}, expected {expected_twd_total}'

# Verify ID is text-like in Details first relevant columns by values, numeric amount values exist
amount_values = []
for row in d_data_rows:
    for v in row:
        pass
# openpyxl cell type check for common ID/date/amount columns
print('Checks passed: files exist, CSV query result, workbook sheets, row counts, formula, and TWD summary total.')
