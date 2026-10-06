from pathlib import Path
from openpyxl import load_workbook
from copy import copy
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
import csv, json
from collections import defaultdict

BASE = Path.cwd()
IN = BASE/'input'
OUT = BASE/'output'
DL = OUT/'downloads'
OUT.mkdir(exist_ok=True)

TEMPLATE = IN/'project_template.xlsx'
FX = IN/'fx_rates.csv'
INV_CSV = DL/'invoices_2026-09.csv'
OUT_XLSX = OUT/'project_report_2026-09_invoices.xlsx'

START = date(2026,9,1)
END = date(2026,9,30)
ASOF = date(2026,9,30)
GENERATED_AT = '2026-10-06T00:00:00+08:00'
TWOPLACES = Decimal('0.01')

def money(x):
    return Decimal(str(x)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
def to_float(d):
    return float(money(d))
def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d').date() if s else None

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

# Read fx rates; only first two columns are needed because Note contains an unquoted comma in this lab file.
rates = {}
with open(FX, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        if row and row[0].strip():
            rates[row[0].strip()] = Decimal(row[1].strip())
print('FX rates:', rates)

# Read invoices exported from the ERP browser query.
with open(INV_CSV, newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    invoice_headers = reader.fieldnames
    invoices = list(reader)
print('Invoice CSV headers:', invoice_headers)
print('Invoice rows downloaded:', len(invoices))

for r in invoices:
    inv_date = parse_date(r['InvoiceDate'])
    assert START <= inv_date <= END, f"Invoice outside requested month: {r}"
    assert r['Currency'] in rates, f"Missing FX rate for {r['Currency']}"

wb = load_workbook(TEMPLATE)

def clear_data(wsname):
    ws = wb[wsname]
    if ws.max_row >= 5:
        ws.delete_rows(5, ws.max_row - 4)
for wsname in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    clear_data(wsname)

# Report metadata.
report = wb['Report']
report['B3'] = START
report['B3'].number_format = 'yyyy-mm-dd'
report['D3'] = END
report['D3'].number_format = 'yyyy-mm-dd'
report['B4'] = 'Invoices InvoiceDate 2026-09-01 to 2026-09-30; balance as of 2026-09-30; overdue if Balance > 0 and DueDate < 2026-09-30.'
report['B5'] = GENERATED_AT
report['B7'] = 'Lab ERP Invoices; fx_rates.csv'
report['D7'] = GENERATED_AT
report['B9'] = 'Only Invoices and Summary were populated. Orders, Expenses, and Quotes source worksheets remain blank. Invoices without ProjectID are listed in Invoices/Exceptions but are not included in project Summary.'

# Invoices and calculations.
inv_ws = wb['Invoices']
summary_totals = defaultdict(Decimal)
project_ids_seen = set()
exceptions = []
invoice_rows_out = []

for r in invoices:
    inv_id = r['InvoiceID']
    order_id = r['OrderID']
    project = r.get('ProjectID','') or ''
    customer = r['CustomerID']
    inv_date = parse_date(r['InvoiceDate'])
    due = parse_date(r['DueDate'])
    cur = r['Currency']
    amount = money(r['Amount'])
    paid = money(r['PaidAmount'])
    balance = money(r['Balance'])
    calc_balance = money(amount - paid)
    assert calc_balance == balance, f"Balance mismatch {inv_id}: source {balance} calc {calc_balance}"
    balance_twd = money(balance * rates[cur])
    invoice_rows_out.append([inv_id, order_id, project if project else None, customer, inv_date, due, cur, to_float(amount), to_float(paid), to_float(balance), to_float(balance_twd)])
    if project:
        project_ids_seen.add(project)
        summary_totals[project] += balance_twd
    if balance > 0 and due < ASOF:
        exceptions.append(['Invoices', inv_id, project if project else None, 'Overdue'])

for idx, row in enumerate(invoice_rows_out, start=5):
    copy_row_style(inv_ws, 4, idx, 11)
    for col, val in enumerate(row, start=1):
        cell = inv_ws.cell(idx, col, val)
        if col in (1,2,3,4,7):
            cell.number_format = '@'
        elif col in (5,6):
            cell.number_format = 'yyyy-mm-dd'
        elif col in (8,9,10,11):
            cell.number_format = '0.00'

# Summary: one row per nonblank project in September invoices.
sum_ws = wb['Summary']
projects = sorted(project_ids_seen)
for idx, project in enumerate(projects, start=5):
    copy_row_style(sum_ws, 4, idx, 5)
    values = [project, 0.0, to_float(summary_totals[project]), 0.0, 0.0]
    for col, val in enumerate(values, start=1):
        cell = sum_ws.cell(idx, col, val)
        cell.number_format = '@' if col == 1 else '0.00'
last_summary = max(5, 4 + len(projects))
for col_letter in ['B','C','D','E']:
    sum_ws[f'{col_letter}2'] = f'=SUM({col_letter}5:{col_letter}{last_summary})'
    sum_ws[f'{col_letter}2'].number_format = '0.00'

# Exceptions.
exc_ws = wb['Exceptions']
for idx, row in enumerate(exceptions, start=5):
    copy_row_style(exc_ws, 4, idx, 4)
    for col, val in enumerate(row, start=1):
        cell = exc_ws.cell(idx, col, val)
        cell.number_format = '@'

# Other source sheets stay blank below headers.
for wsname in ['Orders','Expenses','Quotes']:
    ws = wb[wsname]
    assert ws.max_row == 4, f"{wsname} should remain blank below header, max_row={ws.max_row}"

wb.save(OUT_XLSX)
print('Wrote:', OUT_XLSX)
print('Summary totals:', {p: str(money(v)) for p,v in sorted(summary_totals.items())})
print('Exceptions:', exceptions)

# Reopen output and verify saved requirements.
check = load_workbook(OUT_XLSX, data_only=False)
errors = []

ws = check['Invoices']
expected_headers = ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD']
headers = [ws.cell(4,c).value for c in range(1,12)]
if headers != expected_headers:
    errors.append(f'Invoices headers mismatch: {headers}')
if ws.max_row != 4 + len(invoices):
    errors.append(f'Invoices row count {ws.max_row-4} != {len(invoices)}')
for row in range(5, ws.max_row+1):
    if not isinstance(ws.cell(row,1).value, str) or not ws.cell(row,1).value.startswith('009'):
        errors.append(f'InvoiceID not text/preserved at row {row}: {ws.cell(row,1).value!r}')
    if not isinstance(ws.cell(row,2).value, str) or not ws.cell(row,2).value.startswith('004'):
        errors.append(f'OrderID not text/preserved at row {row}: {ws.cell(row,2).value!r}')
    if ws.cell(row,5).value < START or ws.cell(row,5).value > END:
        errors.append(f'InvoiceDate outside range row {row}: {ws.cell(row,5).value}')
    for col in [8,9,10,11]:
        if not isinstance(ws.cell(row,col).value, (int,float)):
            errors.append(f'Numeric col {col} not numeric row {row}: {ws.cell(row,col).value!r}')
    cur = ws.cell(row,7).value
    bal = Decimal(str(ws.cell(row,10).value))
    exp_twd = money(bal * rates[cur])
    got_twd = money(ws.cell(row,11).value)
    if got_twd != exp_twd:
        errors.append(f'BalanceTWD mismatch row {row}: got {got_twd} expected {exp_twd}')

ws = check['Summary']
if [ws.cell(4,c).value for c in range(1,6)] != ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']:
    errors.append('Summary headers mismatch')
if ws.max_row != 4 + len(projects):
    errors.append(f'Summary row count {ws.max_row-4} != {len(projects)}')
summary_read = {}
for row in range(5, ws.max_row+1):
    p = ws.cell(row,1).value
    summary_read[p] = money(ws.cell(row,3).value)
    if money(ws.cell(row,2).value) != Decimal('0.00') or money(ws.cell(row,4).value) != Decimal('0.00') or money(ws.cell(row,5).value) != Decimal('0.00'):
        errors.append(f'Other source summary columns not zero at row {row}')
expected_summary = {p: money(v) for p,v in summary_totals.items()}
if summary_read != expected_summary:
    errors.append(f'Summary totals mismatch: got {summary_read} expected {expected_summary}')
for col_letter in ['B','C','D','E']:
    exp_formula = f'=SUM({col_letter}5:{col_letter}{last_summary})'
    if ws[f'{col_letter}2'].value != exp_formula:
        errors.append(f'{col_letter}2 formula {ws[f"{col_letter}2"].value!r} != {exp_formula!r}')

ws = check['Exceptions']
expected_exc = exceptions
if ws.max_row != 4 + len(expected_exc):
    errors.append(f'Exceptions row count {ws.max_row-4} != {len(expected_exc)}')
read_exc = [[ws.cell(row,c).value for c in range(1,5)] for row in range(5, ws.max_row+1)]
if read_exc != expected_exc:
    errors.append(f'Exceptions mismatch: got {read_exc} expected {expected_exc}')
due_on_asof = {r['InvoiceID'] for r in invoices if parse_date(r['DueDate']) == ASOF and Decimal(r['Balance']) > 0}
marked = {row[1] for row in read_exc}
wrong_marked = due_on_asof & marked
if wrong_marked:
    errors.append(f'Due-on-asof invoices incorrectly marked overdue: {wrong_marked}')

for wsname in ['Orders','Expenses','Quotes']:
    ws = check[wsname]
    if ws.max_row != 4:
        errors.append(f'{wsname} has data rows; max_row={ws.max_row}')

if errors:
    print('CHECK FAILED')
    for e in errors:
        print('ERROR:', e)
    raise SystemExit(1)

print('CHECK PASSED')
print(json.dumps({
    'output': str(OUT_XLSX),
    'invoice_rows': len(invoices),
    'summary_projects': projects,
    'summary_totals_twd': {p: str(expected_summary[p]) for p in projects},
    'exceptions_count': len(exceptions),
    'exceptions': exceptions,
    'due_on_asof_not_overdue': sorted(due_on_asof),
    'other_source_sheets_blank': ['Orders','Expenses','Quotes'],
}, ensure_ascii=False, indent=2))
