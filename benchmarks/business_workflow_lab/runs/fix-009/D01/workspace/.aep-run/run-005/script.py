from pathlib import Path
from openpyxl import load_workbook
from decimal import Decimal, ROUND_HALF_UP
from copy import copy
import csv

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

template_path = input_dir / 'expense_template.xlsx'
export_path = output_dir / 'E001_september_expenses_export.xlsx'
out_path = output_dir / 'E001_september_expenses.xlsx'
fx_path = input_dir / 'fx_rates.csv'

employee_id = 'E001'
from_date = '2026-09-01'
to_date = '2026-09-30'

print('Inputs:')
print(' template', template_path, template_path.exists())
print(' export', export_path, export_path.exists())
print(' fx', fx_path, fx_path.exists())

rates = {}
with fx_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        if row and row[0]:
            rates[row[0]] = Decimal(row[1])
print('rates', rates)

exp_wb = load_workbook(export_path, data_only=True)
exp_ws = exp_wb[exp_wb.sheetnames[0]]
headers = [c.value for c in exp_ws[1]]
print('export headers', headers)
rows = []
for values in exp_ws.iter_rows(min_row=2, values_only=True):
    if all(v is None for v in values):
        continue
    rows.append(dict(zip(headers, values)))
print('export row_count', len(rows))
for r in rows[:3]: print('sample', r)

bad = []
for r in rows:
    if str(r.get('EmployeeID')) != employee_id or not (from_date <= str(r.get('ExpenseDate')) <= to_date):
        bad.append(r)
if bad:
    raise AssertionError(f'Export contains rows outside requested filter: {bad[:3]}')

wb = load_workbook(template_path)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']
exceptions = wb['Exceptions']

TWO = Decimal('0.01')
def round2(x):
    return Decimal(x).quantize(TWO, rounding=ROUND_HALF_UP)

def truthy(v):
    if isinstance(v, bool): return v
    if v is None: return False
    return str(v).strip().lower() in ('true','1','yes','y')

def clear_from(ws, start_row):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

def copy_row_style(ws, src_row, dst_row, max_col):
    for col in range(1, max_col+1):
        src = ws.cell(src_row, col)
        dst = ws.cell(dst_row, col)
        if src.has_style:
            dst._style = copy(src._style)
        dst.number_format = src.number_format
        dst.font = copy(src.font)
        dst.fill = copy(src.fill)
        dst.border = copy(src.border)
        dst.alignment = copy(src.alignment)
        dst.protection = copy(src.protection)

clear_from(details, 5)
clear_from(summary, 5)
clear_from(exceptions, 5)

now = '2026-10-06T00:00:00+08:00'
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = f'EmployeeID={employee_id}; ExpenseDate {from_date} to {to_date}; Status=All'
report['B5'] = now
report['B7'] = 'Expense Viewer (synthetic lab); fx_rates.csv'
report['D7'] = now

last_row = 4
exceptions_list = []
summary_map = {}
for i, r in enumerate(rows, start=5):
    currency = str(r['Currency'])
    if currency not in rates:
        raise AssertionError(f'Missing FX rate for {currency}')
    amount = round2(Decimal(str(r['Amount'])))
    amount_twd = round2(amount * rates[currency])
    missing = truthy(r.get('MissingReceipt'))
    needs_review = missing
    receipt = '' if r.get('ReceiptID') is None else str(r.get('ReceiptID'))
    values = [
        str(r.get('ExpenseID') or ''),
        str(r.get('EmployeeID') or ''),
        str(r.get('EmployeeName') or ''),
        str(r.get('ProjectID') or ''),
        str(r.get('ExpenseDate') or ''),
        str(r.get('Category') or ''),
        currency,
        float(amount),
        float(amount_twd),
        str(r.get('Status') or ''),
        receipt,
        '' if r.get('Description') is None else str(r.get('Description')),
        'true' if missing else 'false',
        'true' if needs_review else 'false',
    ]
    copy_row_style(details, 4, i, 14)
    for col, val in enumerate(values, start=1):
        cell = details.cell(i, col, val)
        if col in (8,9):
            cell.number_format = '0.00'
        elif col == 5:
            cell.number_format = 'yyyy-mm-dd'
        else:
            cell.number_format = '@'
    key = (str(r.get('Status') or ''), currency)
    summary_map.setdefault(key, {'amount': Decimal('0'), 'amount_twd': Decimal('0'), 'count': 0})
    summary_map[key]['amount'] += amount
    summary_map[key]['amount_twd'] += amount_twd
    summary_map[key]['count'] += 1
    if missing:
        exceptions_list.append((str(r.get('ExpenseID') or ''), str(r.get('EmployeeID') or ''), str(r.get('ExpenseDate') or ''), 'Missing receipt'))
    last_row = i

summary['B2'] = f'=SUM(Details!I5:I{last_row})' if rows else '=SUM(Details!I5:I5)'
summary['B2'].number_format = '0.00'
for idx, ((status, currency), agg) in enumerate(sorted(summary_map.items()), start=5):
    copy_row_style(summary, 4, idx, 6)
    values = [status, '', currency, float(round2(agg['amount'])), float(round2(agg['amount_twd'])), agg['count']]
    for col, val in enumerate(values, start=1):
        summary.cell(idx, col, val)
    summary.cell(idx, 4).number_format = '0.00'
    summary.cell(idx, 5).number_format = '0.00'
    summary.cell(idx, 6).number_format = '0'

for idx, vals in enumerate(exceptions_list, start=5):
    copy_row_style(exceptions, 4, idx, 4)
    for col, val in enumerate(vals, start=1):
        exceptions.cell(idx, col, val)
        exceptions.cell(idx, col).number_format = '@'

report['B9'] = f'{len(exceptions_list)} expense(s) have MissingReceipt=true and are listed in Exceptions; NeedsReview=true for those rows.'
wb.save(out_path)
print('wrote', out_path)

# Verification by reopening output file
vwb = load_workbook(out_path, data_only=False)
vd = vwb['Details']; vs = vwb['Summary']; ve = vwb['Exceptions']; vr = vwb['Report']
actual_rows = [row for row in vd.iter_rows(min_row=5, max_row=vd.max_row, values_only=True) if any(v is not None for v in row)]
summary_rows = [row for row in vs.iter_rows(min_row=5, max_row=vs.max_row, values_only=True) if any(v is not None for v in row)]
exception_rows = [row for row in ve.iter_rows(min_row=5, max_row=ve.max_row, values_only=True) if any(v is not None for v in row)]
expected_total = sum((round2(Decimal(str(r['Amount'])) * rates[str(r['Currency'])]) for r in rows), Decimal('0'))
expected_formula = f'=SUM(Details!I5:I{4+len(rows)})' if rows else '=SUM(Details!I5:I5)'

assert vwb.sheetnames == ['Report', 'Details', 'Summary', 'Exceptions', 'Instructions']
assert [c.value for c in vd[4]] == ['ExpenseID', 'EmployeeID', 'EmployeeName', 'ProjectID', 'ExpenseDate', 'Category', 'Currency', 'Amount', 'AmountTWD', 'Status', 'ReceiptID', 'Description', 'MissingReceipt', 'NeedsReview']
assert [c.value for c in vs[4]] == ['Group', 'SubGroup', 'Currency', 'Amount', 'AmountTWD', 'Count']
assert [c.value for c in ve[4]] == ['ExpenseID', 'EmployeeID', 'ExpenseDate', 'Reason']
assert len(actual_rows) == len(rows) == 13
assert len(summary_rows) == len(summary_map)
assert len(exception_rows) == len(exceptions_list)
assert vr['B3'].value == from_date and vr['D3'].value == to_date and employee_id in vr['B4'].value
assert vs['B2'].value == expected_formula
for row in vd.iter_rows(min_row=5, max_row=4+len(rows)):
    for c in [1,2,4]:
        assert isinstance(row[c-1].value, str) and row[c-1].value, f'row {row[0].row} col {c} not nonblank text'
    if row[10].value is not None:
        assert isinstance(row[10].value, str), f'row {row[0].row} receipt not text/blank'
    assert isinstance(row[7].value, (int,float)), f'Amount not numeric at row {row[0].row}'
    assert isinstance(row[8].value, (int,float)), f'AmountTWD not numeric at row {row[0].row}'

# ensure summary group is status + currency and sums match independently
by_summary = {}
for status, subgroup, currency, amount, amount_twd, count in summary_rows:
    assert status and subgroup in (None, ''), 'Summary Group/SubGroup should be status with blank subgroup'
    by_summary[(status, currency)] = (Decimal(str(amount)).quantize(TWO), Decimal(str(amount_twd)).quantize(TWO), count)
expected_summary = {k:(round2(v['amount']), round2(v['amount_twd']), v['count']) for k,v in summary_map.items()}
assert by_summary == expected_summary, (by_summary, expected_summary)

print('VERIFY output sheets', vwb.sheetnames)
print('VERIFY details rows', len(actual_rows))
print('VERIFY summary rows', len(summary_rows))
print('VERIFY exceptions rows', len(exception_rows))
print('VERIFY Report B3 D3 B4 B7', vr['B3'].value, vr['D3'].value, vr['B4'].value, vr['B7'].value)
print('VERIFY Summary B2 formula', vs['B2'].value)
print('VERIFY TWD total', float(round2(expected_total)))
print('VERIFY summary rows:')
for r in summary_rows: print(r)
print('VERIFY exceptions rows:')
for r in exception_rows: print(r)
print('OK')