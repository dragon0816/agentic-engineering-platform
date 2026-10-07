from pathlib import Path
import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from copy import copy
from openpyxl import load_workbook

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(parents=True, exist_ok=True)
TEMPLATE = INPUT / 'project_template.xlsx'
FX = INPUT / 'fx_rates.csv'
INVOICE_CSV = OUTPUT / 'downloads' / 'invoices_2026-09.csv'
OUTFILE = OUTPUT / 'project_invoice_report_2026-09.xlsx'

START = date(2026, 9, 1)
END = date(2026, 9, 30)
BASE = date(2026, 9, 30)
FETCHED_AT = datetime.now().astimezone().replace(microsecond=0).isoformat()

# Read fx rates (only first two columns are needed; Note includes commas in source)
rates = {}
with FX.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row or len(row) < 2:
            continue
        rates[row[0]] = Decimal(row[1])
print('FX rates:', rates)

# Read invoice export
invoices = []
with INVOICE_CSV.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print('Invoice CSV headers:', reader.fieldnames)
    for row in reader:
        inv_date = datetime.strptime(row['InvoiceDate'], '%Y-%m-%d').date()
        due_date = datetime.strptime(row['DueDate'], '%Y-%m-%d').date()
        amount = Decimal(row['Amount'])
        paid = Decimal(row['PaidAmount'])
        balance = (amount - paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # also compare exported balance
        exported_balance = Decimal(row['Balance']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if balance != exported_balance:
            print('WARN balance mismatch:', row['InvoiceID'], balance, exported_balance)
        curr = row['Currency']
        if curr not in rates:
            raise ValueError(f'Missing FX rate for {curr}')
        balance_twd = (balance * rates[curr]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        row2 = dict(row)
        row2['_InvoiceDateObj'] = inv_date
        row2['_DueDateObj'] = due_date
        row2['_AmountDec'] = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        row2['_PaidDec'] = paid.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        row2['_BalanceDec'] = balance
        row2['_BalanceTWDDec'] = balance_twd
        invoices.append(row2)

# Ensure query date range is correct
bad_dates = [r['InvoiceID'] for r in invoices if not (START <= r['_InvoiceDateObj'] <= END)]
if bad_dates:
    raise ValueError(f'Invoices outside requested date range: {bad_dates}')
print(f'Read {len(invoices)} invoices from export')
for r in invoices[:5]:
    print('sample invoice:', {k:r[k] for k in ['InvoiceID','OrderID','ProjectID','InvoiceDate','DueDate','Currency','Balance']}, 'BalanceTWD', r['_BalanceTWDDec'])

# Helpers
wb = load_workbook(TEMPLATE)

def clear_data(ws, min_row=5):
    # clear existing data rows below header, preserving styles/structure as much as possible
    if ws.max_row >= min_row:
        for row in ws.iter_rows(min_row=min_row, max_row=ws.max_row):
            for cell in row:
                cell.value = None

# Clear detail/sum/exception data areas; source sheets remain blank
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    clear_data(wb[s], 5)

# Use row 5 styles as template when adding rows if present

def copy_row_style(ws, src_row, dst_row, max_col):
    for c in range(1, max_col+1):
        src = ws.cell(src_row, c)
        dst = ws.cell(dst_row, c)
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

# Report sheet
rep = wb['Report']
rep['B3'] = START.strftime('%Y-%m-%d')
rep['D3'] = END.strftime('%Y-%m-%d')
rep['B4'] = 'Invoices InvoiceDate 2026-09-01 to 2026-09-30; Balance as of 2026-09-30; overdue when Balance > 0 and DueDate < 2026-09-30.'
rep['B5'] = FETCHED_AT
rep['B7'] = 'Lab ERP Invoices; fx_rates.csv'
rep['D7'] = FETCHED_AT
rep['B9'] = 'Only Invoices and invoice BalanceTWD summary were requested; Orders, Expenses and Quotes source sheets are left blank. Blank ProjectID values are preserved from source and included as a blank ProjectID summary row.'

# Invoices sheet
inv_ws = wb['Invoices']
headers = [inv_ws.cell(4,c).value for c in range(1, inv_ws.max_column+1)]
expected = ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD']
if headers != expected:
    raise ValueError(f'Unexpected Invoices headers: {headers}')

for idx, r in enumerate(invoices, start=5):
    copy_row_style(inv_ws, 4, idx, len(expected))
    values = [
        r['InvoiceID'], r['OrderID'], r['ProjectID'] or None, r['CustomerID'],
        r['_InvoiceDateObj'], r['_DueDateObj'], r['Currency'],
        float(r['_AmountDec']), float(r['_PaidDec']), float(r['_BalanceDec']), float(r['_BalanceTWDDec'])
    ]
    for c, v in enumerate(values, start=1):
        cell = inv_ws.cell(idx, c, v)
        if c in [1,2,3,4,7]:
            cell.number_format = '@'
        elif c in [5,6]:
            cell.number_format = 'yyyy-mm-dd'
        elif c in [8,9,10,11]:
            cell.number_format = '0.00'

# Summary by ProjectID, including blank ProjectID group to reconcile all invoices
summary = {}
for r in invoices:
    pid = r['ProjectID'] or ''
    summary[pid] = summary.get(pid, Decimal('0.00')) + r['_BalanceTWDDec']

sum_ws = wb['Summary']
summary_rows = sorted(summary.items(), key=lambda kv: (kv[0] == '', kv[0]))
for idx, (pid, total) in enumerate(summary_rows, start=5):
    copy_row_style(sum_ws, 4, idx, 5)
    sum_ws.cell(idx, 1, pid if pid else None).number_format = '@'
    # Other source columns intentionally blank per user request
    sum_ws.cell(idx, 2, None).number_format = '0.00'
    sum_ws.cell(idx, 3, float(total)).number_format = '0.00'
    sum_ws.cell(idx, 4, None).number_format = '0.00'
    sum_ws.cell(idx, 5, None).number_format = '0.00'

last_sum_row = max(5, 4 + len(summary_rows))
for col in range(2, 6):
    letter = chr(ord('A') + col - 1)
    sum_ws.cell(2, col, f'=SUM({letter}5:{letter}{last_sum_row})')

# Exceptions
exc_ws = wb['Exceptions']
exceptions = [r for r in invoices if r['_BalanceDec'] > 0 and r['_DueDateObj'] < BASE]
for idx, r in enumerate(exceptions, start=5):
    copy_row_style(exc_ws, 4, idx, 4)
    vals = ['Invoices', r['InvoiceID'], r['ProjectID'] or None, 'Overdue']
    for c, v in enumerate(vals, start=1):
        cell = exc_ws.cell(idx, c, v)
        if c in [1,2,3,4]:
            cell.number_format = '@'

# Auto filters: keep header row range updated where auto_filter already exists / useful
inv_ws.auto_filter.ref = f'A4:K{4+len(invoices)}'
sum_ws.auto_filter.ref = f'A4:E{last_sum_row}'
exc_ws.auto_filter.ref = f'A4:D{max(4,4+len(exceptions))}'

# Save
wb.save(OUTFILE)
print('Wrote', OUTFILE)
print('Exceptions:', [(r['InvoiceID'], r['DueDate'], r['Balance']) for r in exceptions])
print('Summary:', [(pid if pid else '<blank>', str(total)) for pid,total in summary_rows])

# Validation: reopen saved output and confirm requested requirements
check_wb = load_workbook(OUTFILE, data_only=False)
# Other source worksheets blank from row 5 onward
for s in ['Orders','Expenses','Quotes']:
    ws = check_wb[s]
    nonblank = []
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row, max_col=ws.max_column):
        for cell in row:
            if cell.value not in (None, ''):
                nonblank.append(cell.coordinate)
    if nonblank:
        raise AssertionError(f'{s} not blank: {nonblank[:10]}')

# Invoice row count and headers
ws = check_wb['Invoices']
headers2 = [ws.cell(4,c).value for c in range(1,12)]
assert headers2 == expected, headers2
read_rows = []
for r in range(5, 5+len(invoices)):
    if ws.cell(r,1).value:
        read_rows.append(r)
assert len(read_rows) == 13, len(read_rows)
# no extra nonblank row immediately below written block
for c in range(1,12):
    assert ws.cell(5+len(invoices), c).value in (None, ''), f'extra invoice data at row {5+len(invoices)} col {c}'
# IDs text values with leading zeros preserved
assert ws['A5'].value == '0090000207' and isinstance(ws['A5'].value, str)
assert ws['B5'].value == '0045000108' and isinstance(ws['B5'].value, str)
# dates and numbers
for r in range(5, 5+len(invoices)):
    assert isinstance(ws.cell(r,5).value, (datetime, date)), f'invoice date not date at row {r}'
    assert isinstance(ws.cell(r,6).value, (datetime, date)), f'due date not date at row {r}'
    for c in [8,9,10,11]:
        assert isinstance(ws.cell(r,c).value, (int,float)), f'amount not numeric row {r} col {c}'
# BalanceTWD calculations
for i, src in enumerate(invoices, start=5):
    assert Decimal(str(ws.cell(i,11).value)).quantize(Decimal('0.01')) == src['_BalanceTWDDec'], (i, ws.cell(i,11).value, src['_BalanceTWDDec'])

# Exceptions: expected overdue only; due date equal BASE is excluded
ws_exc = check_wb['Exceptions']
actual_exc = []
for r in range(5, 5+len(exceptions)):
    actual_exc.append((ws_exc.cell(r,1).value, ws_exc.cell(r,2).value, ws_exc.cell(r,3).value or '', ws_exc.cell(r,4).value))
expected_exc = [('Invoices', r['InvoiceID'], r['ProjectID'] or '', 'Overdue') for r in exceptions]
assert actual_exc == expected_exc, (actual_exc, expected_exc)
for c in range(1,5):
    assert ws_exc.cell(5+len(exceptions), c).value in (None, ''), 'extra exception data'
# due 2026-09-30 not exception
exception_ids = {x[1] for x in actual_exc}
assert '0090000211' not in exception_ids and '0090000213' not in exception_ids and '0090000219' not in exception_ids

# Summary rows and formulas
ws_sum = check_wb['Summary']
actual_summary = []
for r in range(5, 5+len(summary_rows)):
    actual_summary.append((ws_sum.cell(r,1).value or '', Decimal(str(ws_sum.cell(r,3).value)).quantize(Decimal('0.01'))))
assert actual_summary == [(pid, total.quantize(Decimal('0.01'))) for pid,total in summary_rows], (actual_summary, summary_rows)
for c in [2,4,5]:
    vals = [ws_sum.cell(r,c).value for r in range(5, 5+len(summary_rows))]
    assert all(v in (None, '') for v in vals), (c, vals)
assert ws_sum['B2'].value == f'=SUM(B5:B{last_sum_row})'
assert ws_sum['C2'].value == f'=SUM(C5:C{last_sum_row})'
assert ws_sum['D2'].value == f'=SUM(D5:D{last_sum_row})'
assert ws_sum['E2'].value == f'=SUM(E5:E{last_sum_row})'

print('VALIDATION OK')
print('Output file:', OUTFILE)
print('Checked: template copied; 13 invoices; IDs text; dates/date formats; numeric amounts; BalanceTWD fx conversion; Summary invoice balances; other source sheets/columns blank; overdue exceptions excluding due date 2026-09-30.')
