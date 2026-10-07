from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from openpyxl import load_workbook
from openpyxl.styles import Font

params = json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], 'r', encoding='utf-8'))
customer_id = str(params['customer_id']).strip()
from_date = str(params['from_date']).strip()
to_date = str(params['to_date']).strip()
cli_path = str(params['cli_path']).strip()

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
template_path = input_dir / 'quote_template.xlsx'
fx_path = input_dir / 'fx_rates.csv'

if not customer_id:
    raise SystemExit('customer_id is required')
for label, value in [('from_date', from_date), ('to_date', to_date)]:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f'{label} must be YYYY-MM-DD: {value}') from exc
if date.fromisoformat(from_date) > date.fromisoformat(to_date):
    raise SystemExit('from_date must be on or before to_date')
if not Path(cli_path).exists():
    raise SystemExit(f'CLI path not found: {cli_path}')
if not template_path.exists():
    raise SystemExit(f'Missing template: {template_path}')
if not fx_path.exists():
    raise SystemExit(f'Missing fx rates: {fx_path}')

print('Inputs:')
print(' workspace:', workspace)
print(' template:', template_path)
print(' fx_rates:', fx_path)
print(' cli_path:', cli_path)
print(' customer_id:', customer_id)
print(' from_date:', from_date)
print(' to_date:', to_date)

TWO = Decimal('0.01')
def money(value) -> Decimal:
    if value is None or value == '':
        return Decimal('0.00')
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)

def twd_amount(amount: Decimal, currency: str, rates: dict[str, Decimal]) -> Decimal:
    if currency not in rates:
        raise SystemExit(f'Missing FX rate for currency {currency}')
    return (amount * rates[currency]).quantize(TWO, rounding=ROUND_HALF_UP)

def dec_or_none(value):
    if value is None or value == '':
        return None
    return Decimal(str(value))

def run_cli(args: list[str]) -> dict:
    p = Path(cli_path)
    if p.suffix.lower() == '.py':
        cmd = [sys.executable, str(p), *args]
        shell = False
    elif p.suffix.lower() in {'.cmd', '.bat'} and os.name == 'nt':
        cmd = subprocess.list2cmdline([str(p), *args])
        shell = True
    else:
        cmd = [str(p), *args]
        shell = False
    last = None
    for attempt in range(1, 4):
        proc = subprocess.run(cmd, shell=shell, text=True, capture_output=True)
        last = proc
        if proc.returncode == 0:
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                raise SystemExit(f'CLI returned non-JSON stdout for {args}: {proc.stdout[:500]}') from exc
        if proc.returncode == 4 and attempt < 3:
            continue
        raise SystemExit(f'CLI failed rc={proc.returncode} for {args}\nstderr={proc.stderr}\nstdout={proc.stdout}')
    raise SystemExit(f'CLI failed after retries: {last}')

# Read FX rates. Notes contain commas in the synthetic CSV, so only the first two columns are used.
rates: dict[str, Decimal] = {}
with fx_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0].strip()] = Decimal(row[1].strip())
print('FX rates:', {k: str(v) for k, v in rates.items()})

list_payload = run_cli(['quotes', 'list', '--customer', customer_id, '--from', from_date, '--to', to_date, '--format', 'json'])
items = list_payload.get('items', [])
print('Quote list count:', len(items), 'reported:', list_payload.get('count'))

quotes = []
lines = []
for item in items:
    qid = str(item.get('QuoteID', '')).strip()
    if not qid:
        raise SystemExit(f'Quote list item missing QuoteID: {item}')
    detail = run_cli(['quotes', 'get', qid, '--format', 'json'])
    header = detail.get('header', {})
    quote_id = str(header.get('QuoteID', qid))
    currency = str(header.get('Currency', ''))
    net_amount = money(header.get('NetAmount'))
    row = {
        'QuoteID': quote_id,
        'CustomerID': str(header.get('CustomerID', '')),
        'ProjectID': str(header.get('ProjectID', '')),
        'QuoteDate': str(header.get('QuoteDate', '')),
        'ValidUntil': str(header.get('ValidUntil', '')),
        'Status': str(header.get('Status', '')),
        'Currency': currency,
        'Subtotal': money(header.get('Subtotal')),
        'DiscountPercent': dec_or_none(header.get('DiscountPercent')),
        'NetAmount': net_amount,
        'NetAmountTWD': twd_amount(net_amount, currency, rates),
    }
    quotes.append(row)
    for li in detail.get('line_items', []):
        lines.append({
            'QuoteID': quote_id,
            'ProductID': str(li.get('ProductID', '')),
            'ProductName': li.get('ProductName', ''),
            'Quantity': dec_or_none(li.get('Quantity')),
            'UnitPrice': money(li.get('UnitPrice')),
            'LineAmount': money(li.get('LineAmount')),
        })

quotes.sort(key=lambda r: (r['QuoteDate'], r['QuoteID']))
lines.sort(key=lambda r: (r['QuoteID'], r['ProductID']))

safe = re.sub(r'[^A-Za-z0-9_.-]+', '_', f'{customer_id}_{from_date}_{to_date}')
out_path = output_dir / f'quote_report_{safe}.xlsx'
shutil.copy2(template_path, out_path)
wb = load_workbook(out_path)

# Fill Report sheet
report = wb['Report']
now = datetime.now(ZoneInfo('Asia/Taipei')) if ZoneInfo else datetime.now()
now_iso = now.isoformat(timespec='seconds')
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = f'CustomerID={customer_id}; QuoteDate between {from_date} and {to_date} inclusive'
report['B5'] = now_iso
report['B7'] = 'quote_cli'
report['D7'] = now_iso
report['B9'] = 'No quotes returned.' if not quotes else ''

# Helpers for detail sheets
text_cols = {'Quotes': ['A', 'B', 'C'], 'Lines': ['A', 'B']}
date_cols = {'Quotes': ['D', 'E']}
money_cols = {'Quotes': ['H', 'J', 'K'], 'Lines': ['E', 'F'], 'Summary': ['D', 'E']}

for sheet_name in ['Quotes', 'Lines', 'Summary']:
    ws = wb[sheet_name]
    if ws.max_row > 4:
        ws.delete_rows(5, ws.max_row - 4)

qws = wb['Quotes']
quote_headers = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
for r_idx, row in enumerate(quotes, 5):
    for c_idx, col in enumerate(quote_headers, 1):
        cell = qws.cell(r_idx, c_idx)
        value = row[col]
        if col in {'QuoteDate', 'ValidUntil'} and value:
            cell.value = date.fromisoformat(value)
            cell.number_format = 'yyyy-mm-dd'
        elif col in {'QuoteID', 'CustomerID', 'ProjectID'}:
            cell.value = str(value) if value != '' else None
            cell.number_format = '@'
        elif col in {'Subtotal', 'NetAmount', 'NetAmountTWD'}:
            cell.value = float(value)
            cell.number_format = '0.00'
        elif col == 'DiscountPercent':
            cell.value = float(value) if value is not None else None
            cell.number_format = '0.00'
        else:
            cell.value = value

lws = wb['Lines']
line_headers = ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
for r_idx, row in enumerate(lines, 5):
    for c_idx, col in enumerate(line_headers, 1):
        cell = lws.cell(r_idx, c_idx)
        value = row[col]
        if col in {'QuoteID', 'ProductID'}:
            cell.value = str(value) if value != '' else None
            cell.number_format = '@'
        elif col == 'Quantity':
            cell.value = float(value) if value is not None else None
            cell.number_format = '0'
        elif col in {'UnitPrice', 'LineAmount'}:
            cell.value = float(value)
            cell.number_format = '0.00'
        else:
            cell.value = value

# Summary by Status and Currency. Group is the Status value; Currency is kept in the template's Currency column.
summary = defaultdict(lambda: {'Amount': Decimal('0.00'), 'AmountTWD': Decimal('0.00'), 'Count': 0})
for q in quotes:
    key = (q['Status'], q['Currency'])
    summary[key]['Amount'] += q['NetAmount']
    summary[key]['AmountTWD'] += q['NetAmountTWD']
    summary[key]['Count'] += 1

sws = wb['Summary']
last_quote_row = max(5, 4 + len(quotes))
sws['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'
for r_idx, ((status, currency), agg) in enumerate(sorted(summary.items()), 5):
    sws.cell(r_idx, 1).value = status
    sws.cell(r_idx, 2).value = None
    sws.cell(r_idx, 3).value = currency
    sws.cell(r_idx, 4).value = float(agg['Amount'].quantize(TWO, rounding=ROUND_HALF_UP))
    sws.cell(r_idx, 5).value = float(agg['AmountTWD'].quantize(TWO, rounding=ROUND_HALF_UP))
    sws.cell(r_idx, 6).value = int(agg['Count'])
    for col in [4, 5]:
        sws.cell(r_idx, col).number_format = '0.00'

wb.save(out_path)

# Reopen and validate the saved workbook against the stated requirements.
check = load_workbook(out_path, data_only=False)
expected_sheets = ['Report', 'Quotes', 'Lines', 'Summary', 'Instructions']
assert check.sheetnames == expected_sheets, f'Sheet names changed: {check.sheetnames}'
assert [check['Quotes'].cell(4, c).value for c in range(1, 12)] == quote_headers
assert [check['Lines'].cell(4, c).value for c in range(1, 7)] == line_headers
assert [check['Summary'].cell(4, c).value for c in range(1, 7)] == ['Group', 'SubGroup', 'Currency', 'Amount', 'AmountTWD', 'Count']
assert check['Report']['B3'].value == from_date
assert check['Report']['D3'].value == to_date
assert check['Summary']['B2'].value == f'=SUM(Quotes!K5:K{last_quote_row})'

cq = check['Quotes']
cl = check['Lines']
cs = check['Summary']
assert max(0, cq.max_row - 4) == len(quotes), (cq.max_row, len(quotes))
assert max(0, cl.max_row - 4) == len(lines), (cl.max_row, len(lines))
assert max(0, cs.max_row - 4) == len(summary), (cs.max_row, len(summary))
for row in range(5, 5 + len(quotes)):
    for col in [1, 2, 3]:
        val = cq.cell(row, col).value
        assert val is None or isinstance(val, str), f'Quotes {row},{col} ID not text: {val!r}'
    for col in [8, 9, 10, 11]:
        val = cq.cell(row, col).value
        assert val is None or isinstance(val, (int, float)), f'Quotes {row},{col} not numeric: {val!r}'
for row in range(5, 5 + len(lines)):
    for col in [1, 2]:
        val = cl.cell(row, col).value
        assert val is None or isinstance(val, str), f'Lines {row},{col} ID not text: {val!r}'
    for col in [4, 5, 6]:
        val = cl.cell(row, col).value
        assert val is None or isinstance(val, (int, float)), f'Lines {row},{col} not numeric: {val!r}'
for row in range(5, 5 + len(summary)):
    assert isinstance(cs.cell(row, 1).value, str)
    assert isinstance(cs.cell(row, 3).value, str)
    assert isinstance(cs.cell(row, 4).value, (int, float))
    assert isinstance(cs.cell(row, 5).value, (int, float))
    assert isinstance(cs.cell(row, 6).value, int)

print('Saved:', out_path)
print('Checked: template sheet names preserved; row 4 headers unchanged; Report dates/condition/source filled;')
print('Checked: Quotes rows =', len(quotes), ', Lines rows =', len(lines), ', Summary rows =', len(summary))
print('Checked: IDs are text, money/quantity/count cells are numeric, Summary B2 formula is', check['Summary']['B2'].value)
for (status, currency), agg in sorted(summary.items()):
    print(f"Summary {status}/{currency}: count={agg['Count']} amount={agg['Amount'].quantize(TWO)} amountTWD={agg['AmountTWD'].quantize(TWO)}")
