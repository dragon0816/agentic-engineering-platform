from pathlib import Path
import csv, shutil, json
from decimal import Decimal
from datetime import datetime, date
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
download_dir = output_dir / 'downloads'
output_dir.mkdir(exist_ok=True)

src_template = input_dir / 'project_template.xlsx'
fx_path = input_dir / 'fx_rates.csv'
invoice_csv = download_dir / 'invoices_2026-09.csv'
out_path = output_dir / 'project_report_2026-09_invoices.xlsx'

print('Inputs resolved:')
for p in [src_template, fx_path, invoice_csv]:
    print(f'- {p}: exists={p.exists()} size={p.stat().st_size if p.exists() else "NA"}')

# Load FX rates. Note text may contain unquoted commas; only the first two columns are needed.
rates = {}
with open(fx_path, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('FX header:', header)
    for row in reader:
        if len(row) >= 2 and row[0].strip():
            rates[row[0].strip()] = Decimal(row[1].strip())
print('FX rates:', {k: str(v) for k,v in rates.items()})

# Read invoices exported from ERP.
with open(invoice_csv, newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    invoices = list(reader)
print('Invoice CSV headers:', reader.fieldnames)
print('Invoice row count:', len(invoices))
print('First rows:', invoices[:3])

required_headers = ['InvoiceID','OrderID','CustomerID','ProjectID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance']
if reader.fieldnames != required_headers:
    raise RuntimeError(f'Unexpected invoice CSV headers: {reader.fieldnames}')

# Validate all rows are September 2026 invoices and currencies are supported.
for row in invoices:
    inv_date = datetime.strptime(row['InvoiceDate'], '%Y-%m-%d').date()
    if not (date(2026,9,1) <= inv_date <= date(2026,9,30)):
        raise RuntimeError(f"Invoice outside 2026-09: {row['InvoiceID']} {row['InvoiceDate']}")
    if row['Currency'] not in rates:
        raise RuntimeError(f"Missing FX rate for {row['Currency']}")

# Sort deterministically by InvoiceID as exported.
invoices.sort(key=lambda r: r['InvoiceID'])

wb = load_workbook(src_template)

# Helper: clear all data rows from row 5 downward but leave headings/instructions intact.
def clear_data(sheet_name):
    ws = wb[sheet_name]
    if ws.max_row >= 5:
        ws.delete_rows(5, ws.max_row - 4)
    return ws

# Other source sheets requested blank.
for s in ['Orders','Expenses','Quotes']:
    clear_data(s)

# Fill Report metadata, preserving template text.
ws_report = wb['Report']
ws_report['B3'] = '2026-09-01'
ws_report['D3'] = '2026-09-30'
ws_report['B4'] = 'Invoices only; outstanding balance as of 2026-09-30; source worksheets Orders/Expenses/Quotes left blank'
ws_report['B5'] = '2026-10-06 Asia/Taipei'

# Fill Invoices.
ws_inv = clear_data('Invoices')
invoice_headers = [ws_inv.cell(row=4, column=c).value for c in range(1, ws_inv.max_column + 1)]
expected_invoice_headers = ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD']
if invoice_headers != expected_invoice_headers:
    raise RuntimeError(f'Unexpected Invoices sheet headers: {invoice_headers}')

summary = {}
exceptions = []
base_date = date(2026, 9, 30)
for idx, row in enumerate(invoices, start=5):
    amount = float(Decimal(row['Amount']))
    paid = float(Decimal(row['PaidAmount']))
    balance_dec = Decimal(row['Balance'])
    balance = float(balance_dec)
    balance_twd_dec = balance_dec * rates[row['Currency']]
    balance_twd = float(balance_twd_dec)
    inv_values = [
        row['InvoiceID'],
        row['OrderID'],
        row['ProjectID'],
        row['CustomerID'],
        row['InvoiceDate'],
        row['DueDate'],
        row['Currency'],
        amount,
        paid,
        balance,
        balance_twd,
    ]
    for col, val in enumerate(inv_values, start=1):
        cell = ws_inv.cell(row=idx, column=col, value=val)
        if col in [1,2,3,4,5,6,7]:
            cell.number_format = '@'
        elif col in [8,9,10,11]:
            cell.number_format = '#,##0.00'
    # Summary is by non-empty project ID only.
    if row['ProjectID']:
        summary[row['ProjectID']] = summary.get(row['ProjectID'], Decimal('0')) + balance_twd_dec
    due = datetime.strptime(row['DueDate'], '%Y-%m-%d').date()
    if balance_dec > 0 and due < base_date:
        exceptions.append({'Source':'Invoices','DocumentID':row['InvoiceID'],'ProjectID':row['ProjectID'],'Reason':'Overdue'})

# Fill Summary: only invoice balances; other source totals zero.
ws_sum = clear_data('Summary')
summary_headers = [ws_sum.cell(row=4, column=c).value for c in range(1, ws_sum.max_column + 1)]
expected_summary_headers = ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']
if summary_headers != expected_summary_headers:
    raise RuntimeError(f'Unexpected Summary sheet headers: {summary_headers}')
for r_idx, project_id in enumerate(sorted(summary), start=5):
    values = [project_id, 0.0, float(summary[project_id]), 0.0, 0.0]
    for c_idx, val in enumerate(values, start=1):
        cell = ws_sum.cell(row=r_idx, column=c_idx, value=val)
        if c_idx == 1:
            cell.number_format = '@'
        else:
            cell.number_format = '#,##0.00'
last_sum_row = max(5, 4 + len(summary))
ws_sum['B2'] = f'=SUM(B5:B{last_sum_row})'
ws_sum['C2'] = f'=SUM(C5:C{last_sum_row})'
ws_sum['D2'] = f'=SUM(D5:D{last_sum_row})'
ws_sum['E2'] = f'=SUM(E5:E{last_sum_row})'

# Fill Exceptions.
ws_exc = clear_data('Exceptions')
exception_headers = [ws_exc.cell(row=4, column=c).value for c in range(1, ws_exc.max_column + 1)]
expected_exception_headers = ['Source','DocumentID','ProjectID','Reason']
if exception_headers != expected_exception_headers:
    raise RuntimeError(f'Unexpected Exceptions sheet headers: {exception_headers}')
for r_idx, exc in enumerate(exceptions, start=5):
    values = [exc['Source'], exc['DocumentID'], exc['ProjectID'], exc['Reason']]
    for c_idx, val in enumerate(values, start=1):
        cell = ws_exc.cell(row=r_idx, column=c_idx, value=val)
        cell.number_format = '@'

# Autofit-ish widths for populated sheets (safe cosmetic only).
for s in ['Invoices','Summary','Exceptions']:
    ws = wb[s]
    for col in range(1, ws.max_column + 1):
        max_len = 0
        for row in range(1, ws.max_row + 1):
            v = ws.cell(row=row, column=col).value
            if v is not None:
                max_len = max(max_len, len(str(v)))
        ws.column_dimensions[get_column_letter(col)].width = min(max(max_len + 2, 10), 45)

wb.save(out_path)
print('Saved workbook:', out_path)
print('Summary totals:', {k: str(v) for k,v in sorted(summary.items())})
print('Exceptions:', exceptions)

# Verification by reopening output.
wb2 = load_workbook(out_path, data_only=False)
checks = []
# Data row counts.
checks.append(('Invoices data rows', wb2['Invoices'].max_row - 4, len(invoices)))
checks.append(('Summary data rows', wb2['Summary'].max_row - 4, len(summary)))
checks.append(('Exceptions data rows', wb2['Exceptions'].max_row - 4, len(exceptions)))
for s in ['Orders','Expenses','Quotes']:
    checks.append((f'{s} data rows blank', wb2[s].max_row - 4, 0))
# Header preservation.
checks.append(('Invoices headers', [wb2['Invoices'].cell(4,c).value for c in range(1,12)], expected_invoice_headers))
checks.append(('Summary headers', [wb2['Summary'].cell(4,c).value for c in range(1,6)], expected_summary_headers))
checks.append(('Exceptions headers', [wb2['Exceptions'].cell(4,c).value for c in range(1,5)], expected_exception_headers))
# Dates and overdue logic.
out_invoice_rows = []
for r in range(5, wb2['Invoices'].max_row + 1):
    vals = [wb2['Invoices'].cell(r,c).value for c in range(1,12)]
    out_invoice_rows.append(vals)
checks.append(('All invoice dates Sep 2026', all('2026-09-01' <= vals[4] <= '2026-09-30' for vals in out_invoice_rows), True))
checks.append(('InvoiceID/OrderID text-like', all(isinstance(vals[0], str) and isinstance(vals[1], str) for vals in out_invoice_rows), True))
checks.append(('Numeric amounts', all(isinstance(vals[c], (int,float)) for vals in out_invoice_rows for c in [7,8,9,10]), True))
# Recompute expected balance TWD and exceptions from saved output.
saved_exception_ids = [wb2['Exceptions'].cell(r,2).value for r in range(5, wb2['Exceptions'].max_row+1)]
expected_exception_ids = [e['DocumentID'] for e in exceptions]
checks.append(('Overdue exceptions IDs', saved_exception_ids, expected_exception_ids))
# Ensure due date equal 2026-09-30 was not marked overdue.
due_0930_ids = [vals[0] for vals in out_invoice_rows if vals[5] == '2026-09-30' and vals[9] > 0]
checks.append(('Due 2026-09-30 not overdue', all(x not in saved_exception_ids for x in due_0930_ids), True))
# Check source sheets blank.
# Check summary amounts exactly within cents.
saved_summary = {wb2['Summary'].cell(r,1).value: Decimal(str(wb2['Summary'].cell(r,3).value)) for r in range(5, wb2['Summary'].max_row+1)}
expected_summary = {k: v for k,v in summary.items()}
checks.append(('Summary project IDs', sorted(saved_summary.keys()), sorted(expected_summary.keys())))
checks.append(('Summary InvoiceBalanceTWD', {k: str(saved_summary[k]) for k in saved_summary}, {k: str(expected_summary[k]) for k in expected_summary}))

print('\nVerification checks:')
ok = True
for name, actual, expected in checks:
    passed = actual == expected
    ok = ok and passed
    print(f'- {name}: {"PASS" if passed else "FAIL"} actual={actual!r} expected={expected!r}')
if not ok:
    raise RuntimeError('One or more verification checks failed')
print('All checks passed.')