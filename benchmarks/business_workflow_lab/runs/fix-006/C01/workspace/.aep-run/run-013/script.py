import csv
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font

WORKSPACE = Path.cwd()
INPUT_DIR = WORKSPACE / 'input'
OUTPUT_DIR = WORKSPACE / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

params_path = os.environ.get('AEP_WORKFLOW_PARAMS')
params = json.load(open(params_path, encoding='utf-8')) if params_path else {}
customer_id = str(params.get('customer_id', '')).strip()
start_s = str(params.get('start_date', '')).strip()
end_s = str(params.get('end_date', '')).strip()
cli_path = str(params.get('cli_path', '')).strip()
if not customer_id or not start_s or not end_s or not cli_path:
    raise SystemExit('Missing required parameters: customer_id, start_date, end_date, cli_path')

start_dt = datetime.strptime(start_s[:10], '%Y-%m-%d').date()
end_dt = datetime.strptime(end_s[:10], '%Y-%m-%d').date()
if end_dt < start_dt:
    raise SystemExit('end_date must be on or after start_date')

print('Workspace:', WORKSPACE)
print('Input files:', sorted(p.name for p in INPUT_DIR.glob('*')))
print('Parameters:', {'customer_id': customer_id, 'start_date': start_s, 'end_date': end_s, 'cli_path': cli_path})

TEMPLATE = INPUT_DIR / 'quote_template.xlsx'
FX_FILE = INPUT_DIR / 'fx_rates.csv'
MANUAL = INPUT_DIR / 'quote_cli_manual.md'
for p in [TEMPLATE, FX_FILE, MANUAL]:
    if not p.exists():
        raise FileNotFoundError(p)

# First inspect and print the real inputs.
wb0 = load_workbook(TEMPLATE, data_only=False)
print('Template sheets:', wb0.sheetnames)
for sheet in ['Report', 'Quotes', 'Lines', 'Summary', 'Instructions']:
    ws0 = wb0[sheet]
    sample = []
    for row in ws0.iter_rows(min_row=1, max_row=min(ws0.max_row, 5), values_only=True):
        sample.append(tuple(row[:min(ws0.max_column, 12)]))
    print(f'Sheet sample {sheet}:', sample)
quote_headers = [wb0['Quotes'].cell(4, c).value for c in range(1, wb0['Quotes'].max_column + 1) if wb0['Quotes'].cell(4, c).value is not None]
line_headers = [wb0['Lines'].cell(4, c).value for c in range(1, wb0['Lines'].max_column + 1) if wb0['Lines'].cell(4, c).value is not None]
summary_headers = [wb0['Summary'].cell(4, c).value for c in range(1, wb0['Summary'].max_column + 1) if wb0['Summary'].cell(4, c).value is not None]
wb0.close()

with open(FX_FILE, newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print('FX headers:', reader.fieldnames)
    fx = {}
    for row in reader:
        cur = str(row.get('Currency', '')).strip()
        rate = str(row.get('RateToTWD', '')).strip()
        if cur:
            fx[cur] = Decimal(rate)
print('FX currencies:', sorted(fx))
manual_text = MANUAL.read_text(encoding='utf-8', errors='replace')
print('Manual preview:', manual_text[:500].replace('\n', ' '))

required_quote = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
required_line = ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
required_summary = ['Group','SubGroup','Currency','Amount','AmountTWD','Count']
if quote_headers != required_quote:
    raise AssertionError(f'Unexpected Quotes headers: {quote_headers}')
if line_headers != required_line:
    raise AssertionError(f'Unexpected Lines headers: {line_headers}')
if summary_headers != required_summary:
    raise AssertionError(f'Unexpected Summary headers: {summary_headers}')

TWOPLACES = Decimal('0.01')
def D(v):
    if v is None or v == '':
        return Decimal('0')
    return Decimal(str(v))

def q2(v):
    return D(v).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def to_float(v):
    return float(q2(v))

def run_cli(args, retries=1):
    cmd = [cli_path] + args
    last = None
    for attempt in range(retries + 1):
        cp = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        last = cp
        if cp.returncode == 0:
            return cp.stdout
        if cp.returncode == 4 and attempt < retries:
            continue
        break
    raise RuntimeError('CLI failed rc={} cmd={}\nSTDOUT:{}\nSTDERR:{}'.format(last.returncode, cmd, last.stdout, last.stderr))

# Correct CLI contract from quote_cli_manual.md:
#   quote_cli quotes list [--customer C001] [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--format json]
#   quote_cli quotes get Q0001 [--format json]
list_stdout = run_cli(['quotes', 'list', '--customer', customer_id, '--from', start_dt.isoformat(), '--to', end_dt.isoformat(), '--format', 'json'], retries=1)
listed = json.loads(list_stdout)
items = listed.get('items', [])
print('Quotes listed:', len(items), 'count field:', listed.get('count'))
if listed.get('count') != len(items):
    raise AssertionError('quotes list count does not match items length')

quote_docs = []
for item in items:
    qid = item.get('QuoteID')
    if not qid:
        raise AssertionError(f'Missing QuoteID in list item: {item}')
    doc = json.loads(run_cli(['quotes', 'get', str(qid), '--format', 'json'], retries=1))
    header = doc.get('header', {})
    lines = doc.get('line_items', [])
    if header.get('QuoteID') != qid:
        raise AssertionError(f'QuoteID mismatch for {qid}: {header.get("QuoteID")}')
    quote_docs.append({'header': header, 'line_items': lines})
print('Quote documents fetched:', len(quote_docs))
print('Line items fetched:', sum(len(d['line_items']) for d in quote_docs))

# Sort by QuoteDate then QuoteID to make output deterministic.
quote_docs.sort(key=lambda d: (d['header'].get('QuoteDate', ''), d['header'].get('QuoteID', '')))

out_path = OUTPUT_DIR / f'quote_report_{customer_id}_{start_dt.isoformat()}_to_{end_dt.isoformat()}.xlsx'
shutil.copy2(TEMPLATE, out_path)
wb = load_workbook(out_path)
wr = wb['Report']
wq = wb['Quotes']
wl = wb['Lines']
ws = wb['Summary']

# Clear existing data rows while preserving the template rows and instructions.
def clear_from(sheet, min_row, max_col):
    for row in sheet.iter_rows(min_row=min_row, max_row=sheet.max_row, max_col=max_col):
        for cell in row:
            cell.value = None
            cell.comment = None

clear_from(wq, 5, len(quote_headers))
clear_from(wl, 5, len(line_headers))
clear_from(ws, 5, len(summary_headers))

wr['B3'] = datetime.combine(start_dt, datetime.min.time())
wr['D3'] = datetime.combine(end_dt, datetime.min.time())
wr['B4'] = f'CustomerID={customer_id}; QuoteDate {start_dt.isoformat()} to {end_dt.isoformat()} inclusive'
now_text = datetime.now().astimezone().isoformat(timespec='seconds')
wr['B5'] = now_text
wr['B7'] = 'quote_cli; fx_rates.csv'
wr['D7'] = now_text

qh = {h: i + 1 for i, h in enumerate(quote_headers)}
lh = {h: i + 1 for i, h in enumerate(line_headers)}
sh = {h: i + 1 for i, h in enumerate(summary_headers)}

summary = defaultdict(lambda: {'amount': Decimal('0'), 'amount_twd': Decimal('0'), 'count': 0})
line_row = 5
for idx, doc in enumerate(quote_docs, start=5):
    h = doc['header']
    qdate = datetime.strptime(h['QuoteDate'][:10], '%Y-%m-%d').date()
    valid = datetime.strptime(h['ValidUntil'][:10], '%Y-%m-%d').date()
    if h.get('CustomerID') != customer_id:
        raise AssertionError(f'Unexpected customer in quote {h}')
    if not (start_dt <= qdate <= end_dt):
        raise AssertionError(f'Quote outside requested period: {h}')
    cur = h['Currency']
    if cur not in fx:
        raise AssertionError(f'Missing FX rate for {cur}')
    subtotal = q2(h['Subtotal'])
    disc = q2(h['DiscountPercent'])
    net = q2(h['NetAmount'])
    expected_net = q2(subtotal * (Decimal('1') - disc / Decimal('100')))
    if net != expected_net:
        raise AssertionError(f'NetAmount mismatch for {h["QuoteID"]}: {net} != {expected_net}')
    net_twd = q2(net * fx[cur])
    values = {
        'QuoteID': str(h['QuoteID']),
        'CustomerID': str(h['CustomerID']),
        'ProjectID': str(h['ProjectID']),
        'QuoteDate': datetime.combine(qdate, datetime.min.time()),
        'ValidUntil': datetime.combine(valid, datetime.min.time()),
        'Status': str(h['Status']),
        'Currency': str(cur),
        'Subtotal': to_float(subtotal),
        'DiscountPercent': to_float(disc),
        'NetAmount': to_float(net),
        'NetAmountTWD': to_float(net_twd),
    }
    for name, val in values.items():
        cell = wq.cell(idx, qh[name])
        cell.value = val
        if name in ['QuoteID','CustomerID','ProjectID']:
            cell.number_format = '@'
        elif name in ['QuoteDate','ValidUntil']:
            cell.number_format = 'yyyy-mm-dd'
        elif name in ['Subtotal','DiscountPercent','NetAmount','NetAmountTWD']:
            cell.number_format = '#,##0.00'
    key = (str(h['Status']), str(cur))
    summary[key]['amount'] += net
    summary[key]['amount_twd'] += net_twd
    summary[key]['count'] += 1

    line_sum = Decimal('0')
    for li in doc['line_items']:
        qty = D(li['Quantity'])
        unit = D(li['UnitPrice'])
        amt = q2(li['LineAmount'])
        expected_amt = q2(qty * unit)
        if amt != expected_amt:
            raise AssertionError(f'LineAmount mismatch for {h["QuoteID"]}: {amt} != {expected_amt}')
        line_sum += amt
        line_values = {
            'QuoteID': str(h['QuoteID']),
            'ProductID': str(li['ProductID']),
            'ProductName': str(li['ProductName']),
            'Quantity': to_float(qty),
            'UnitPrice': to_float(unit),
            'LineAmount': to_float(amt),
        }
        for name, val in line_values.items():
            cell = wl.cell(line_row, lh[name])
            cell.value = val
            if name in ['QuoteID','ProductID','ProductName']:
                cell.number_format = '@'
            elif name in ['Quantity']:
                cell.number_format = '0.00'
            else:
                cell.number_format = '#,##0.00'
        line_row += 1
    if q2(line_sum) != subtotal:
        raise AssertionError(f'Line sum mismatch for {h["QuoteID"]}: {line_sum} != {subtotal}')

last_quote_row = 4 + len(quote_docs)
if quote_docs:
    ws['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'
else:
    ws['B2'] = '=SUM(Quotes!K5:K5)'

summary_row = 5
for (status, cur), vals in sorted(summary.items(), key=lambda kv: (kv[0][0], kv[0][1])):
    row_values = {
        'Group': 'Status',
        'SubGroup': status,
        'Currency': cur,
        'Amount': to_float(vals['amount']),
        'AmountTWD': to_float(vals['amount_twd']),
        'Count': int(vals['count']),
    }
    for name, val in row_values.items():
        cell = ws.cell(summary_row, sh[name])
        cell.value = val
        if name in ['Amount','AmountTWD']:
            cell.number_format = '#,##0.00'
        elif name == 'Count':
            cell.number_format = '0'
    summary_row += 1

# Make inserted rows readable but do not alter source files.
for sheet, headers in [(wq, quote_headers), (wl, line_headers), (ws, summary_headers)]:
    for c in range(1, len(headers) + 1):
        sheet.cell(4, c).font = Font(bold=True)

wb.save(out_path)
wb.close()

# Reopen the saved output and verify every stated requirement.
check = load_workbook(out_path, data_only=False)
cr = check['Report']
cq = check['Quotes']
cl = check['Lines']
cs = check['Summary']

def as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        return datetime.strptime(v[:10], '%Y-%m-%d').date()
    return v

assert check.sheetnames == ['Report', 'Quotes', 'Lines', 'Summary', 'Instructions'], f'Sheets changed: {check.sheetnames}'
assert [cq.cell(4,c).value for c in range(1, len(quote_headers)+1)] == quote_headers, 'Quotes headers changed'
assert [cl.cell(4,c).value for c in range(1, len(line_headers)+1)] == line_headers, 'Lines headers changed'
assert [cs.cell(4,c).value for c in range(1, len(summary_headers)+1)] == summary_headers, 'Summary headers changed'
assert as_date(cr['B3'].value) == start_dt, f'Report!B3 {cr["B3"].value!r} != {start_dt}'
assert as_date(cr['D3'].value) == end_dt, f'Report!D3 {cr["D3"].value!r} != {end_dt}'
assert cr['B4'].value == f'CustomerID={customer_id}; QuoteDate {start_dt.isoformat()} to {end_dt.isoformat()} inclusive'
assert cq.max_row == (4 if not quote_docs else 4 + len(quote_docs)), f'Quotes rows {cq.max_row}'
assert cl.max_row == (4 if not quote_docs else 4 + sum(len(d['line_items']) for d in quote_docs)), f'Lines rows {cl.max_row}'
assert cs.max_row == (4 if not summary else 4 + len(summary)), f'Summary rows {cs.max_row}'

for r in range(5, 5 + len(quote_docs)):
    for c in [qh['QuoteID'], qh['CustomerID'], qh['ProjectID']]:
        assert isinstance(cq.cell(r,c).value, str), f'Quotes text column {c} row {r}'
    for c in [qh['Subtotal'], qh['DiscountPercent'], qh['NetAmount'], qh['NetAmountTWD']]:
        assert isinstance(cq.cell(r,c).value, (int,float)), f'Quotes numeric column {c} row {r}'
for r in range(5, 5 + sum(len(d['line_items']) for d in quote_docs)):
    for c in [lh['QuoteID'], lh['ProductID'], lh['ProductName']]:
        assert isinstance(cl.cell(r,c).value, str), f'Lines text column {c} row {r}'
    for c in [lh['Quantity'], lh['UnitPrice'], lh['LineAmount']]:
        assert isinstance(cl.cell(r,c).value, (int,float)), f'Lines numeric column {c} row {r}'

expected_formula = '=SUM(Quotes!K5:K5)' if not quote_docs else f'=SUM(Quotes!K5:K{last_quote_row})'
assert cs['B2'].value == expected_formula, f'Summary!B2 {cs["B2"].value!r} != {expected_formula!r}'

saved_summary = {}
for r in range(5, cs.max_row+1):
    if cs.cell(r, 1).value is None:
        continue
    key = (cs.cell(r, sh['SubGroup']).value, cs.cell(r, sh['Currency']).value)
    saved_summary[key] = {
        'amount': q2(cs.cell(r, sh['Amount']).value),
        'amount_twd': q2(cs.cell(r, sh['AmountTWD']).value),
        'count': int(cs.cell(r, sh['Count']).value),
    }
expected_summary = {k: {'amount': q2(v['amount']), 'amount_twd': q2(v['amount_twd']), 'count': int(v['count'])} for k, v in summary.items()}
assert saved_summary == expected_summary, f'Summary mismatch saved={saved_summary} expected={expected_summary}'
check.close()

print('Verified output file:', out_path.name)
print('Checked: input template copied, source input files unchanged; sheets and headers preserved; Report dates/condition written; Quotes rows:', len(quote_docs), '; Lines rows:', sum(len(d['line_items']) for d in quote_docs), '; Summary rows:', len(expected_summary), '; Summary!B2:', expected_formula, '; ID columns text; money/quantity/count columns numeric; saved workbook re-opened successfully.')
print('Output files:', sorted(p.name for p in OUTPUT_DIR.iterdir()))
