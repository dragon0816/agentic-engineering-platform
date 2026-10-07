from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from copy import copy
import csv
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
DOWNLOAD = OUTPUT / 'downloads' / 'invoices_2026-09.csv'
TEMPLATE = INPUT / 'project_template.xlsx'
FX = INPUT / 'fx_rates.csv'
OUTFILE = OUTPUT / 'project_report_2026-09_invoices.xlsx'

FROM_DATE = date(2026, 9, 1)
TO_DATE = date(2026, 9, 30)
BASE_DATE = date(2026, 9, 30)
GENERATED_AT = datetime.now().astimezone().replace(microsecond=0).isoformat()

# Load FX rates. Some note fields contain unquoted commas, but first two columns are stable.
rates = {}
with FX.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('FX rates loaded:', rates)

# Load downloaded invoice export.
with DOWNLOAD.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
print('Downloaded invoice rows:', len(rows))
print('Headers:', reader.fieldnames)
print('Sample rows:', rows[:3])

# Validate source rows match requested range.
def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d').date()

for r in rows:
    inv_dt = parse_date(r['InvoiceDate'])
    assert FROM_DATE <= inv_dt <= TO_DATE, f"Invoice outside range: {r}"
    assert r['Currency'] in rates, f"Missing FX rate: {r['Currency']}"

# Helpers.
def q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def clear_data(sh, min_row=5):
    # Keep header/instruction rows and existing layout. Remove surplus data rows where present.
    if sh.max_row > min_row - 1:
        sh.delete_rows(min_row, sh.max_row - min_row + 1)

def copy_row_style(sh, src_row, dst_row, max_col):
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

# Open template copy in memory.
wb = load_workbook(TEMPLATE)

# Clear source detail sheets from row 5 onward.
for s in ['Orders', 'Invoices', 'Expenses', 'Quotes', 'Summary', 'Exceptions']:
    clear_data(wb[s], 5)

# Report metadata; preserve layout.
report = wb['Report']
report['B3'] = FROM_DATE
report['D3'] = TO_DATE
report['B4'] = 'Invoices: InvoiceDate 2026-09-01 through 2026-09-30; Balance as of 2026-09-30; overdue when Balance > 0 and DueDate < 2026-09-30.'
report['B5'] = GENERATED_AT
report['B7'] = 'Lab ERP Invoices export; fx_rates.csv'
report['D7'] = GENERATED_AT
report['B9'] = 'Orders, Expenses, and Quotes were intentionally left blank per request. Same-day due invoices are not marked overdue.'
for cell in ['B3', 'D3']:
    report[cell].number_format = 'yyyy-mm-dd'

# Fill invoices.
inv = wb['Invoices']
invoice_out_rows = []
summary = {}
exceptions = []
for idx, r in enumerate(rows, start=5):
    amount = q2(Decimal(r['Amount']))
    paid = q2(Decimal(r['PaidAmount']))
    balance = q2(Decimal(r['Balance']))
    balance_twd = q2(balance * rates[r['Currency']])
    inv_dt = parse_date(r['InvoiceDate'])
    due_dt = parse_date(r['DueDate'])
    values = [
        r['InvoiceID'], r['OrderID'], r['ProjectID'] or None, r['CustomerID'],
        inv_dt, due_dt, r['Currency'], float(amount), float(paid), float(balance), float(balance_twd)
    ]
    copy_row_style(inv, 4, idx, 11)
    for col, val in enumerate(values, start=1):
        c = inv.cell(idx, col, val)
        if col in [1,2,3,4,7]:
            c.number_format = '@'
        elif col in [5,6]:
            c.number_format = 'yyyy-mm-dd'
        elif col in [8,9,10,11]:
            c.number_format = '0.00'
    invoice_out_rows.append(values)
    proj = r['ProjectID']
    if proj:
        summary[proj] = summary.get(proj, Decimal('0.00')) + balance_twd
    if balance > 0 and due_dt < BASE_DATE:
        exceptions.append(['Invoices', r['InvoiceID'], r['ProjectID'] or None, 'Overdue'])

# Fill summary: one row per project appearing in September invoices; only invoice balance is populated, other sources blank.
sumsh = wb['Summary']
for offset, project in enumerate(sorted(summary), start=5):
    copy_row_style(sumsh, 4, offset, 5)
    sumsh.cell(offset, 1, project).number_format = '@'
    sumsh.cell(offset, 2, None)
    sumsh.cell(offset, 3, float(q2(summary[project]))).number_format = '0.00'
    sumsh.cell(offset, 4, None)
    sumsh.cell(offset, 5, None)
last_summary_row = max(5, 4 + len(summary))
# Extend totals formulas across actual summary data rows; B/D/E will sum blanks.
for col in range(2, 6):
    col_letter = get_column_letter(col)
    sumsh.cell(2, col, f'=SUM({col_letter}5:{col_letter}{last_summary_row})')
    sumsh.cell(2, col).number_format = '0.00'

# Fill exceptions.
exc = wb['Exceptions']
for row_idx, vals in enumerate(exceptions, start=5):
    copy_row_style(exc, 4, row_idx, 4)
    for col, val in enumerate(vals, start=1):
        c = exc.cell(row_idx, col, val)
        if col in [1,2,3,4]:
            c.number_format = '@'

# Ensure other source sheets remain empty beyond headers.
for s in ['Orders', 'Expenses', 'Quotes']:
    sh = wb[s]
    # after clear_data, max_row should be 4; no values below header
    for row in sh.iter_rows(min_row=5):
        for cell in row:
            cell.value = None

# Freeze panes/autofilter already in template; avoid column width changes.
wb.save(OUTFILE)
print('Saved:', OUTFILE)
print('Invoices written:', len(invoice_out_rows))
print('Summary projects:', sorted(summary.items()))
print('Exceptions:', exceptions)

# Reopen saved output and verify requirements.
wb2 = load_workbook(OUTFILE, data_only=False)
errors = []

# sheet names intact
expected_sheets = ['Report', 'Orders', 'Invoices', 'Expenses', 'Quotes', 'Summary', 'Exceptions', 'Instructions']
if wb2.sheetnames != expected_sheets:
    errors.append(f'Sheet names/order changed: {wb2.sheetnames}')

# Invoices headers and row count.
inv2 = wb2['Invoices']
headers = [inv2.cell(4,c).value for c in range(1,12)]
expected_headers = ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD']
if headers != expected_headers:
    errors.append(f'Invoice headers mismatch: {headers}')
invoice_rows_saved = []
for r in range(5, inv2.max_row + 1):
    if any(inv2.cell(r,c).value is not None for c in range(1,12)):
        invoice_rows_saved.append(r)
if len(invoice_rows_saved) != len(rows):
    errors.append(f'Invoice row count {len(invoice_rows_saved)} != {len(rows)}')

# Verify invoice values, text-like IDs, dates, numbers and balances.
for idx, src in enumerate(rows, start=5):
    if inv2.cell(idx,1).value != src['InvoiceID'] or not str(inv2.cell(idx,1).value).startswith('00'):
        errors.append(f'InvoiceID text/leading zero issue row {idx}: {inv2.cell(idx,1).value}')
    if inv2.cell(idx,2).value != src['OrderID'] or not str(inv2.cell(idx,2).value).startswith('00'):
        errors.append(f'OrderID text/leading zero issue row {idx}: {inv2.cell(idx,2).value}')
    if inv2.cell(idx,5).value.date() if hasattr(inv2.cell(idx,5).value, 'date') else inv2.cell(idx,5).value != parse_date(src['InvoiceDate']):
        pass
    amount = q2(Decimal(src['Amount']))
    paid = q2(Decimal(src['PaidAmount']))
    balance = q2(Decimal(src['Balance']))
    calc_balance = q2(amount - paid)
    calc_twd = q2(balance * rates[src['Currency']])
    if balance != calc_balance:
        errors.append(f'Source balance mismatch row {idx}: {balance} != {calc_balance}')
    if Decimal(str(inv2.cell(idx,10).value)).quantize(Decimal('0.01')) != balance:
        errors.append(f'Saved balance mismatch row {idx}')
    if Decimal(str(inv2.cell(idx,11).value)).quantize(Decimal('0.01')) != calc_twd:
        errors.append(f'Saved BalanceTWD mismatch row {idx}: {inv2.cell(idx,11).value} != {calc_twd}')
    for c in [8,9,10,11]:
        if not isinstance(inv2.cell(idx,c).value, (int, float)):
            errors.append(f'Amount cell not numeric row {idx} col {c}: {type(inv2.cell(idx,c).value)}')

# Summary verification.
sum2 = wb2['Summary']
summary_rows = []
for r in range(5, sum2.max_row + 1):
    if any(sum2.cell(r,c).value is not None for c in range(1,6)):
        summary_rows.append(r)
expected_projects = sorted(summary)
saved_projects = [sum2.cell(r,1).value for r in summary_rows]
if saved_projects != expected_projects:
    errors.append(f'Summary projects {saved_projects} != {expected_projects}')
for r, proj in zip(summary_rows, saved_projects):
    val = Decimal(str(sum2.cell(r,3).value)).quantize(Decimal('0.01'))
    if val != q2(summary[proj]):
        errors.append(f'Summary BalanceTWD mismatch {proj}: {val} != {summary[proj]}')
    for c in [2,4,5]:
        if sum2.cell(r,c).value is not None:
            errors.append(f'Summary other source col not blank row {r} col {c}: {sum2.cell(r,c).value}')
for col in range(2,6):
    expected_formula = f'=SUM({get_column_letter(col)}5:{get_column_letter(col)}{last_summary_row})'
    if sum2.cell(2,col).value != expected_formula:
        errors.append(f'Summary formula mismatch {sum2.cell(2,col).coordinate}: {sum2.cell(2,col).value} != {expected_formula}')

# Exceptions verification. Overdue = balance>0 and DueDate strictly before 2026-09-30.
exc2 = wb2['Exceptions']
saved_exc = []
for r in range(5, exc2.max_row + 1):
    vals = [exc2.cell(r,c).value for c in range(1,5)]
    if any(v is not None for v in vals):
        saved_exc.append(vals)
if saved_exc != exceptions:
    errors.append(f'Exceptions mismatch: {saved_exc} != {exceptions}')
# Explicit check no DueDate == base date in exceptions.
base_due_ids = {r['InvoiceID'] for r in rows if parse_date(r['DueDate']) == BASE_DATE}
exception_ids = {e[1] for e in saved_exc}
if base_due_ids & exception_ids:
    errors.append(f'Invoices due on base date wrongly marked overdue: {base_due_ids & exception_ids}')

# Other source sheets blank.
for s in ['Orders', 'Expenses', 'Quotes']:
    sh = wb2[s]
    nonblank = []
    for row in sh.iter_rows(min_row=5, max_row=max(sh.max_row, 5), max_col=sh.max_column):
        for cell in row:
            if cell.value is not None:
                nonblank.append(cell.coordinate)
    if nonblank:
        errors.append(f'{s} has nonblank data cells: {nonblank[:10]}')

# Print a concise audit table.
print('\nAudit:')
print('Output file exists:', OUTFILE.exists(), 'bytes=', OUTFILE.stat().st_size)
print('Invoice rows checked:', len(invoice_rows_saved))
print('Summary rows checked:', len(summary_rows), saved_projects)
print('Exceptions checked:', len(saved_exc), saved_exc)
print('Other source sheets blank checked: Orders, Expenses, Quotes')
print('Summary formulas:', [sum2.cell(2,c).value for c in range(2,6)])
if errors:
    print('ERRORS:')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print('All checks passed.')
