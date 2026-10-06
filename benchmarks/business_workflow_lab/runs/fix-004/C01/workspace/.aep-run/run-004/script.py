import csv
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from openpyxl import load_workbook

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
params = json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
customer_id = str(params['customer_id']).strip()
from_date = str(params['from_date']).strip()
to_date = str(params['to_date']).strip()
cli_path = str(params['cli_path']).strip()
if not customer_id:
    raise SystemExit('customer_id is required')
if not from_date or not to_date:
    raise SystemExit('from_date and to_date are required')
if not cli_path:
    raise SystemExit('cli_path is required')

for d in (from_date, to_date):
    datetime.strptime(d, '%Y-%m-%d')

def money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def run_cli(args):
    # Supports either a Windows .cmd/.bat/.exe or a Python .py entrypoint.
    cp_args = []
    suffix = Path(cli_path).suffix.lower()
    if suffix == '.py':
        cp_args = [sys.executable, cli_path] + args
    else:
        cp_args = [cli_path] + args
    last = None
    for attempt in range(1, 4):
        completed = subprocess.run(cp_args, capture_output=True, text=True)
        last = completed
        if completed.returncode == 0:
            return completed.stdout
        if completed.returncode == 4 and attempt < 3:
            continue
        raise RuntimeError(f"quote_cli failed rc={completed.returncode}; stderr={completed.stderr.strip()}")
    raise RuntimeError(f"quote_cli failed rc={last.returncode}; stderr={last.stderr.strip()}")

# Load FX rates; keep only first two columns because Note text can contain commas in the lab CSV.
rates = {}
with open(INPUT / 'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader, None)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
if not rates:
    raise RuntimeError('No FX rates loaded')

print('Inputs:', {'customer_id': customer_id, 'from_date': from_date, 'to_date': to_date, 'cli_path': cli_path})
print('FX rates:', {k: str(v) for k, v in rates.items()})

list_stdout = run_cli(['quotes', 'list', '--customer', customer_id, '--from', from_date, '--to', to_date, '--format', 'json'])
listed = json.loads(list_stdout)
if listed.get('schema_version') != 1:
    raise RuntimeError(f"Unexpected list schema_version: {listed.get('schema_version')}")
headers = listed.get('items', [])
print('Quote count from list:', len(headers))

quote_details = []
for h in headers:
    qid = h['QuoteID']
    detail_stdout = run_cli(['quotes', 'get', qid, '--format', 'json'])
    detail = json.loads(detail_stdout)
    if detail.get('schema_version') != 1:
        raise RuntimeError(f"Unexpected get schema_version for {qid}: {detail.get('schema_version')}")
    quote_details.append(detail)

# Sort for stable output.
quote_details.sort(key=lambda d: (d['header'].get('QuoteDate', ''), d['header'].get('QuoteID', '')))

src = INPUT / 'quote_template.xlsx'
out = OUTPUT / f"quote_report_{customer_id}_{from_date}_to_{to_date}.xlsx"
shutil.copyfile(src, out)
wb = load_workbook(out)

# Preserve existing workbook structure; clear only prior data rows from detail sheets.
def clear_data(sheet_name, min_row=5):
    ws = wb[sheet_name]
    if ws.max_row >= min_row:
        ws.delete_rows(min_row, ws.max_row - min_row + 1)

def set_text(cell, value):
    cell.value = '' if value is None else str(value)
    cell.number_format = '@'

def set_money(cell, value):
    cell.value = float(money(value)) if value is not None and value != '' else None
    cell.number_format = '0.00'

clear_data('Quotes')
clear_data('Lines')
clear_data('Summary')

report = wb['Report']
now_iso = datetime.now().astimezone().replace(microsecond=0).isoformat()
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = f"CustomerID={customer_id}; QuoteDate from {from_date} to {to_date} inclusive"
report['B5'] = now_iso
report['B7'] = 'quote_cli mock quotation system'
report['D7'] = now_iso
report['B9'] = ''

quotes_ws = wb['Quotes']
lines_ws = wb['Lines']
summary_ws = wb['Summary']

quote_row = 5
line_row = 5
summary_map = defaultdict(lambda: {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0})

for detail in quote_details:
    h = detail['header']
    currency = h.get('Currency')
    if currency not in rates:
        raise RuntimeError(f"Missing FX rate for currency {currency}")
    net = money(h.get('NetAmount'))
    net_twd = money(net * rates[currency])

    set_text(quotes_ws.cell(quote_row, 1), h.get('QuoteID'))
    set_text(quotes_ws.cell(quote_row, 2), h.get('CustomerID'))
    set_text(quotes_ws.cell(quote_row, 3), h.get('ProjectID'))
    quotes_ws.cell(quote_row, 4).value = h.get('QuoteDate')
    quotes_ws.cell(quote_row, 5).value = h.get('ValidUntil')
    set_text(quotes_ws.cell(quote_row, 6), h.get('Status'))
    set_text(quotes_ws.cell(quote_row, 7), currency)
    set_money(quotes_ws.cell(quote_row, 8), h.get('Subtotal'))
    quotes_ws.cell(quote_row, 9).value = float(Decimal(str(h.get('DiscountPercent')))) if h.get('DiscountPercent') not in (None, '') else None
    set_money(quotes_ws.cell(quote_row, 10), net)
    set_money(quotes_ws.cell(quote_row, 11), net_twd)

    key = (h.get('Status'), currency)
    summary_map[key]['amount'] += net
    summary_map[key]['twd'] += net_twd
    summary_map[key]['count'] += 1

    for li in detail.get('line_items', []):
        set_text(lines_ws.cell(line_row, 1), h.get('QuoteID'))
        set_text(lines_ws.cell(line_row, 2), li.get('ProductID'))
        lines_ws.cell(line_row, 3).value = li.get('ProductName')
        lines_ws.cell(line_row, 4).value = int(li.get('Quantity')) if li.get('Quantity') not in (None, '') else None
        set_money(lines_ws.cell(line_row, 5), li.get('UnitPrice'))
        set_money(lines_ws.cell(line_row, 6), li.get('LineAmount'))
        line_row += 1
    quote_row += 1

# Summary by status and currency.
srow = 5
for (status, currency), vals in sorted(summary_map.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
    summary_ws.cell(srow, 1).value = status
    summary_ws.cell(srow, 2).value = ''
    summary_ws.cell(srow, 3).value = currency
    set_money(summary_ws.cell(srow, 4), vals['amount'])
    set_money(summary_ws.cell(srow, 5), vals['twd'])
    summary_ws.cell(srow, 6).value = vals['count']
    srow += 1

last_quote_row = max(5, quote_row - 1)
summary_ws['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'
wb.save(out)

# Verification from saved workbook.
check = load_workbook(out, data_only=False)
errors = []
if set(check.sheetnames) != set(load_workbook(src, read_only=True).sheetnames):
    errors.append('sheet names changed')
qws = check['Quotes']
lws = check['Lines']
sws = check['Summary']
expected_quote_headers = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
expected_line_headers = ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
expected_summary_headers = ['Group','SubGroup','Currency','Amount','AmountTWD','Count']
if [qws.cell(4,c).value for c in range(1,12)] != expected_quote_headers:
    errors.append('Quotes headers mismatch')
if [lws.cell(4,c).value for c in range(1,7)] != expected_line_headers:
    errors.append('Lines headers mismatch')
if [sws.cell(4,c).value for c in range(1,7)] != expected_summary_headers:
    errors.append('Summary headers mismatch')
q_count = len(quote_details)
line_count = sum(len(d.get('line_items', [])) for d in quote_details)
s_count = len(summary_map)
if qws.max_row != (4 if q_count == 0 else 4 + q_count):
    errors.append(f'Quotes row count mismatch: {qws.max_row}')
if lws.max_row != (4 if line_count == 0 else 4 + line_count):
    errors.append(f'Lines row count mismatch: {lws.max_row}')
if sws.max_row != (4 if s_count == 0 else 4 + s_count):
    errors.append(f'Summary row count mismatch: {sws.max_row}')
for r in range(5, 5+q_count):
    if qws.cell(r,2).value != customer_id:
        errors.append(f'Unexpected CustomerID at Quotes row {r}')
    if qws.cell(r,1).number_format != '@' or qws.cell(r,2).number_format != '@':
        errors.append(f'ID text format missing at Quotes row {r}')
    for c in (8,10,11):
        if not isinstance(qws.cell(r,c).value, (int, float)):
            errors.append(f'Quotes row {r} col {c} is not numeric')
for r in range(5, 5+line_count):
    if lws.cell(r,1).number_format != '@' or lws.cell(r,2).number_format != '@':
        errors.append(f'ID text format missing at Lines row {r}')
    for c in (4,5,6):
        if not isinstance(lws.cell(r,c).value, (int, float)):
            errors.append(f'Lines row {r} col {c} is not numeric')
if sws['B2'].value != f'=SUM(Quotes!K5:K{last_quote_row})':
    errors.append('Summary B2 formula mismatch')
# Verify summary totals from saved rows.
recalc = defaultdict(lambda: {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0})
for r in range(5, 5+q_count):
    key=(qws.cell(r,6).value, qws.cell(r,7).value)
    recalc[key]['amount'] += money(qws.cell(r,10).value)
    recalc[key]['twd'] += money(qws.cell(r,11).value)
    recalc[key]['count'] += 1
for r in range(5, 5+s_count):
    key=(sws.cell(r,1).value, sws.cell(r,3).value)
    if key not in recalc:
        errors.append(f'Unexpected summary key {key}')
    else:
        if money(sws.cell(r,4).value) != recalc[key]['amount'] or money(sws.cell(r,5).value) != recalc[key]['twd'] or sws.cell(r,6).value != recalc[key]['count']:
            errors.append(f'Summary totals mismatch for {key}')
if errors:
    raise RuntimeError('; '.join(errors))
print('Wrote:', out)
print('Checked saved workbook: sheet names, headers, report fields, row counts, text ID formats, numeric amount/quantity cells, Summary B2 formula, and status+currency summary totals.')
print('Counts:', {'quotes': q_count, 'lines': line_count, 'summary_rows': s_count})
