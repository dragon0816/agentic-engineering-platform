import csv
import json
import os
import shutil
import subprocess
import sys
from copy import copy
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from openpyxl import load_workbook

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(parents=True, exist_ok=True)

params_path = os.environ.get('AEP_WORKFLOW_PARAMS')
if params_path and Path(params_path).exists():
    params = json.load(open(params_path, encoding='utf-8'))
else:
    params = {}

customer_id = str(params.get('customer_id', '')).strip()
from_date = str(params.get('from_date', '')).strip()
to_date = str(params.get('to_date', '')).strip()
cli_path = str(params.get('cli_path', '')).strip()

if not customer_id:
    raise SystemExit('customer_id is required')
if not from_date or not to_date:
    raise SystemExit('from_date and to_date are required')
if not cli_path:
    raise SystemExit('cli_path is required')

# Validate date strings and inclusive range.
from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
to_dt = datetime.strptime(to_date, '%Y-%m-%d').date()
if from_dt > to_dt:
    raise SystemExit('from_date must be on or before to_date')

cli = Path(cli_path)
if not cli.exists():
    raise SystemExit(f'CLI path does not exist: {cli_path}')

def cli_base_args():
    if cli.suffix.lower() == '.py':
        return [sys.executable, str(cli)]
    return [str(cli)]

def run_cli(args, retries=1):
    cmd = cli_base_args() + args
    last = None
    for attempt in range(retries + 1):
        cp = subprocess.run(cmd, text=True, capture_output=True)
        last = cp
        if cp.returncode == 0:
            return cp.stdout
        if cp.returncode == 4 and attempt < retries:
            continue
        raise RuntimeError('CLI failed with exit code %s for %s\nstderr:\n%s' % (cp.returncode, ' '.join(cmd), cp.stderr))
    return last.stdout

# Read FX rates; only first two columns are needed because notes may contain commas in test data.
fx_rates = {}
with (INPUT / 'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader, None)
    for row in reader:
        if len(row) >= 2 and row[0].strip():
            fx_rates[row[0].strip()] = Decimal(row[1].strip())

list_stdout = run_cli(['quotes', 'list', '--customer', customer_id, '--from', from_date, '--to', to_date, '--format', 'json'], retries=1)
list_payload = json.loads(list_stdout)
if list_payload.get('schema_version') != 1:
    raise RuntimeError('Unexpected quotes list schema_version: %r' % list_payload.get('schema_version'))
quote_ids = [item['QuoteID'] for item in list_payload.get('items', [])]

headers = []
lines = []
fetched_at = datetime.now().astimezone().isoformat(timespec='seconds')
TWOPLACES = Decimal('0.01')

def money(value):
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

for qid in quote_ids:
    detail_stdout = run_cli(['quotes', 'get', qid, '--format', 'json'], retries=1)
    detail = json.loads(detail_stdout)
    if detail.get('schema_version') != 1:
        raise RuntimeError(f'Unexpected quotes get schema_version for {qid}: {detail.get("schema_version")!r}')
    h = detail['header']
    currency = str(h['Currency'])
    if currency not in fx_rates:
        raise RuntimeError(f'Missing FX rate for currency {currency}')
    subtotal = money(h['Subtotal'])
    discount = Decimal(str(h['DiscountPercent']))
    net = money(h['NetAmount'])
    # Check the documented contract without replacing the CLI value.
    expected_net = (subtotal * (Decimal('1') - discount / Decimal('100'))).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if net != expected_net:
        raise RuntimeError(f'NetAmount mismatch for {qid}: CLI={net} expected={expected_net}')
    net_twd = (net * fx_rates[currency]).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    headers.append({
        'QuoteID': h['QuoteID'],
        'CustomerID': h['CustomerID'],
        'ProjectID': h['ProjectID'],
        'QuoteDate': h['QuoteDate'],
        'ValidUntil': h['ValidUntil'],
        'Status': h['Status'],
        'Currency': currency,
        'Subtotal': subtotal,
        'DiscountPercent': discount,
        'NetAmount': net,
        'NetAmountTWD': net_twd,
    })
    for li in detail.get('line_items', []):
        qty = Decimal(str(li['Quantity']))
        unit = money(li['UnitPrice'])
        amount = money(li['LineAmount'])
        expected_line = (qty * unit).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if amount != expected_line:
            raise RuntimeError(f'LineAmount mismatch for {qid}/{li.get("ProductID")}: CLI={amount} expected={expected_line}')
        lines.append({
            'QuoteID': h['QuoteID'],
            'ProductID': li['ProductID'],
            'ProductName': li['ProductName'],
            'Quantity': int(qty) if qty == qty.to_integral_value() else float(qty),
            'UnitPrice': unit,
            'LineAmount': amount,
        })

# Sort for deterministic workbook output.
headers.sort(key=lambda r: (r['QuoteDate'], r['QuoteID']))
line_order = {h['QuoteID']: i for i, h in enumerate(headers)}
lines.sort(key=lambda r: (line_order.get(r['QuoteID'], 999999), r['ProductID']))

safe_customer = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in customer_id)
out_name = f'quote_report_{safe_customer}_{from_date}_to_{to_date}.xlsx'
out_path = OUTPUT / out_name
shutil.copy2(INPUT / 'quote_template.xlsx', out_path)
wb = load_workbook(out_path)

# Helpers to preserve template styles from row 5 if present, otherwise row 4.
def clear_data(ws, start_row=5):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

def write_table(ws, headers_row, rows, columns):
    clear_data(ws, headers_row + 1)
    style_row = headers_row
    for ridx, row in enumerate(rows, start=headers_row + 1):
        for cidx, col in enumerate(columns, start=1):
            cell = ws.cell(ridx, cidx, row.get(col))
            tmpl = ws.cell(style_row, cidx)
            if tmpl.has_style:
                cell._style = copy(tmpl._style)
            if tmpl.number_format:
                cell.number_format = tmpl.number_format

# Report sheet.
report = wb['Report']
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = f'CustomerID={customer_id}; QuoteDate from {from_date} to {to_date} inclusive'
report['B5'] = datetime.now().astimezone().isoformat(timespec='seconds')
report['B7'] = 'quote_cli; fx_rates.csv'
report['D7'] = fetched_at

quote_cols = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
line_cols = ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
write_table(wb['Quotes'], 4, headers, quote_cols)
write_table(wb['Lines'], 4, lines, line_cols)

# Number formats and text IDs.
qws = wb['Quotes']
for row in range(5, 5 + len(headers)):
    for col in [1,2,3,4,5,6,7]:
        qws.cell(row, col).number_format = '@'
    for col in [8,10,11]:
        qws.cell(row, col).number_format = '#,##0.00'
    qws.cell(row, 9).number_format = '0.00'

lws = wb['Lines']
for row in range(5, 5 + len(lines)):
    for col in [1,2,3]:
        lws.cell(row, col).number_format = '@'
    lws.cell(row, 4).number_format = '0'
    for col in [5,6]:
        lws.cell(row, col).number_format = '#,##0.00'

# Summary grouped by status and currency.
summary = {}
for h in headers:
    key = (h['Status'], h['Currency'])
    rec = summary.setdefault(key, {'Group': 'Status', 'SubGroup': h['Status'], 'Currency': h['Currency'], 'Amount': Decimal('0.00'), 'AmountTWD': Decimal('0.00'), 'Count': 0})
    rec['Amount'] += h['NetAmount']
    rec['AmountTWD'] += h['NetAmountTWD']
    rec['Count'] += 1
summary_rows = []
for key in sorted(summary):
    rec = summary[key]
    rec['Amount'] = rec['Amount'].quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    rec['AmountTWD'] = rec['AmountTWD'].quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    summary_rows.append(rec)

sws = wb['Summary']
sws['B2'] = f'=SUM(Quotes!K5:K{max(5, 4 + len(headers))})'
write_table(sws, 4, summary_rows, ['Group','SubGroup','Currency','Amount','AmountTWD','Count'])
for row in range(5, 5 + len(summary_rows)):
    for col in [1,2,3]:
        sws.cell(row, col).number_format = '@'
    for col in [4,5]:
        sws.cell(row, col).number_format = '#,##0.00'
    sws.cell(row, 6).number_format = '0'

wb.save(out_path)

# Reopen output and verify stated requirements.
check_wb = load_workbook(out_path, data_only=False)
missing = []
for sheet in ['Quotes', 'Lines', 'Summary']:
    if sheet not in check_wb.sheetnames:
        missing.append(sheet)
if missing:
    raise RuntimeError('Missing sheets: ' + ', '.join(missing))

def row_values(ws, row, n):
    return [ws.cell(row, c).value for c in range(1, n+1)]
if row_values(check_wb['Quotes'], 4, len(quote_cols)) != quote_cols:
    raise RuntimeError('Quotes columns changed or missing')
if row_values(check_wb['Lines'], 4, len(line_cols)) != line_cols:
    raise RuntimeError('Lines columns changed or missing')
if row_values(check_wb['Summary'], 4, 6) != ['Group','SubGroup','Currency','Amount','AmountTWD','Count']:
    raise RuntimeError('Summary columns changed or missing')
if check_wb['Report']['B3'].value != from_date or check_wb['Report']['D3'].value != to_date:
    raise RuntimeError('Report dates not written')
# Verify rows and summary totals from saved workbook.
saved_quote_count = max(0, check_wb['Quotes'].max_row - 4)
saved_line_count = max(0, check_wb['Lines'].max_row - 4)
saved_summary_count = max(0, check_wb['Summary'].max_row - 4)
if saved_quote_count != len(headers):
    raise RuntimeError(f'Quote row count mismatch: saved {saved_quote_count}, expected {len(headers)}')
if saved_line_count != len(lines):
    raise RuntimeError(f'Line row count mismatch: saved {saved_line_count}, expected {len(lines)}')
if saved_summary_count != len(summary_rows):
    raise RuntimeError(f'Summary row count mismatch: saved {saved_summary_count}, expected {len(summary_rows)}')

print(json.dumps({
    'output_file': str(out_path),
    'customer_id': customer_id,
    'from_date': from_date,
    'to_date': to_date,
    'quote_count': len(headers),
    'line_count': len(lines),
    'summary_count': len(summary_rows),
    'quote_ids': quote_ids,
    'checked': ['output workbook reopened', 'Quotes/Lines/Summary columns', 'Report dates', 'row counts', 'money formulas against CLI contract']
}, ensure_ascii=False, indent=2))