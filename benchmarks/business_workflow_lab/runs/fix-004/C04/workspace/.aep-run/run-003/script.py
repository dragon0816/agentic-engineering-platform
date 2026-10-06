from pathlib import Path
import subprocess, sys, json, csv, shutil, os, re
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from collections import defaultdict
from copy import copy
from openpyxl import load_workbook

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)

TEMPLATE = INPUT / 'quote_template.xlsx'
FX_CSV = INPUT / 'fx_rates.csv'
CLI = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')
OUT_XLSX = OUTPUT / 'sent_quotes_2026-09_report.xlsx'
RUN_LOG = OUTPUT / 'quote_cli_run_log.json'
CHECK_LOG = OUTPUT / 'verification_summary.txt'

FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
STATUS = 'Sent'
TODAY = '2026-10-06'

class CliError(Exception):
    def __init__(self, args, code, stderr):
        super().__init__(f'quote_cli failed code={code}: {stderr}')
        self.args_used = args
        self.code = code
        self.stderr = stderr

def run_cli(command_args, label, max_retries_on_4=2):
    """Run quote CLI. Retry only exit code 4, no retry for 2/3, parse stdout only on code 0."""
    attempts = []
    for attempt in range(1, max_retries_on_4 + 2):
        cmd = [sys.executable, str(CLI)] + command_args
        cp = subprocess.run(cmd, cwd=str(WORKSPACE), capture_output=True, text=True)
        record = {
            'label': label,
            'attempt': attempt,
            'args': command_args,
            'exit_code': cp.returncode,
            'stderr': cp.stderr.strip(),
            'stdout_length': len(cp.stdout or ''),
        }
        attempts.append(record)
        if cp.returncode == 0:
            try:
                data = json.loads(cp.stdout)
            except Exception as e:
                record['json_parse_error'] = str(e)
                raise CliError(command_args, cp.returncode, f'stdout was not parseable JSON: {e}')
            record['parsed'] = True
            cli_log.extend(attempts)
            return data
        if cp.returncode in (2, 3):
            cli_log.extend(attempts)
            raise CliError(command_args, cp.returncode, cp.stderr.strip())
        if cp.returncode == 4 and attempt <= max_retries_on_4:
            continue
        cli_log.extend(attempts)
        raise CliError(command_args, cp.returncode, cp.stderr.strip())
    raise AssertionError('unreachable')

def parse_money(x):
    if x is None or x == '':
        return None
    return Decimal(str(x))

def q2(d):
    return Decimal(d).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def dec_to_float(d):
    return float(q2(d)) if d is not None else None

def parse_date(s):
    if not s:
        return None
    return datetime.strptime(s, '%Y-%m-%d').date()

def copy_row_style(ws, src_row, dst_row, max_col):
    for col in range(1, max_col + 1):
        src = ws.cell(src_row, col)
        dst = ws.cell(dst_row, col)
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
        if src.protection:
            dst.protection = copy(src.protection)

def clear_data(ws, start_row, max_col):
    if ws.max_row >= start_row:
        for row in range(start_row, ws.max_row + 1):
            for col in range(1, max_col + 1):
                ws.cell(row, col).value = None

# Load FX rates (CSV notes contain unquoted commas; only first two columns are needed).
fx_rates = {}
with FX_CSV.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2 and row[0]:
            fx_rates[row[0]] = Decimal(row[1])

cli_log = []
error = None
try:
    listing = run_cli([
        'quotes', 'list', '--from', FROM_DATE, '--to', TO_DATE,
        '--status', STATUS, '--format', 'json'
    ], 'quotes list Sent Sep 2026')
    if listing.get('schema_version') != 1 or 'items' not in listing:
        raise ValueError(f'Unexpected list schema: {listing.keys()}')
    quote_headers = listing['items']
    full_quotes = []
    for h in quote_headers:
        qid = h.get('QuoteID')
        if not qid:
            raise ValueError(f'Missing QuoteID in header: {h}')
        detail = run_cli(['quotes', 'get', qid, '--format', 'json'], f'quotes get {qid}')
        if detail.get('schema_version') != 1 or 'header' not in detail or 'line_items' not in detail:
            raise ValueError(f'Unexpected get schema for {qid}: {detail.keys()}')
        full_quotes.append(detail)
except CliError as e:
    error = {'type': 'CliError', 'code': e.code, 'stderr': e.stderr, 'args': e.args_used}
except Exception as e:
    error = {'type': type(e).__name__, 'message': str(e)}

if error:
    RUN_LOG.write_text(json.dumps({'status': 'failed', 'error': error, 'cli_attempts': cli_log}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FAILED')
    print(json.dumps(error, ensure_ascii=False, indent=2))
    raise SystemExit(1)

# Create workbook from template.
shutil.copyfile(TEMPLATE, OUT_XLSX)
wb = load_workbook(OUT_XLSX)

# Report sheet.
report = wb['Report']
now_iso = datetime.now().astimezone().isoformat(timespec='seconds')
report['B3'] = FROM_DATE
report['D3'] = TO_DATE
report['B4'] = f'Status={STATUS}; QuoteDate {FROM_DATE} to {TO_DATE}; source date basis inclusive'
report['B5'] = now_iso
report['B7'] = 'quote_cli; fx_rates.csv'
report['D7'] = now_iso
report['B9'] = ''

# Quotes sheet.
quotes_ws = wb['Quotes']
lines_ws = wb['Lines']
summary_ws = wb['Summary']
clear_data(quotes_ws, 5, 11)
clear_data(lines_ws, 5, 6)
clear_data(summary_ws, 5, 6)

quote_rows = []
line_rows = []
for detail in full_quotes:
    h = detail['header']
    cur = h.get('Currency')
    if cur not in fx_rates:
        raise ValueError(f'Missing FX rate for currency {cur}')
    subtotal = parse_money(h.get('Subtotal'))
    disc = parse_money(h.get('DiscountPercent')) or Decimal('0')
    net = parse_money(h.get('NetAmount'))
    if net is None and subtotal is not None:
        net = q2(subtotal * (Decimal('1') - disc / Decimal('100')))
    net_twd = q2(net * fx_rates[cur]) if net is not None else None
    quote_rows.append({
        'QuoteID': h.get('QuoteID'),
        'CustomerID': h.get('CustomerID'),
        'ProjectID': h.get('ProjectID'),
        'QuoteDate': h.get('QuoteDate'),
        'ValidUntil': h.get('ValidUntil'),
        'Status': h.get('Status'),
        'Currency': cur,
        'Subtotal': subtotal,
        'DiscountPercent': disc,
        'NetAmount': net,
        'NetAmountTWD': net_twd,
    })
    for li in detail['line_items']:
        qty = parse_money(li.get('Quantity'))
        unit = parse_money(li.get('UnitPrice'))
        amt = parse_money(li.get('LineAmount'))
        if amt is None and qty is not None and unit is not None:
            amt = q2(qty * unit)
        line_rows.append({
            'QuoteID': h.get('QuoteID'),
            'ProductID': li.get('ProductID'),
            'ProductName': li.get('ProductName'),
            'Quantity': qty,
            'UnitPrice': unit,
            'LineAmount': amt,
        })

quote_rows.sort(key=lambda r: (r['QuoteDate'] or '', r['QuoteID'] or ''))
# Keep lines in quote/date sorted order.
quote_order = {r['QuoteID']: i for i, r in enumerate(quote_rows)}
line_rows.sort(key=lambda r: (quote_order.get(r['QuoteID'], 999999), r.get('ProductID') or ''))

for i, r in enumerate(quote_rows, start=5):
    copy_row_style(quotes_ws, 5 if i != 5 else 4, i, 11)
    values = [r['QuoteID'], r['CustomerID'], r['ProjectID'], parse_date(r['QuoteDate']), parse_date(r['ValidUntil']),
              r['Status'], r['Currency'], dec_to_float(r['Subtotal']), float(r['DiscountPercent']) if r['DiscountPercent'] is not None else None,
              dec_to_float(r['NetAmount']), dec_to_float(r['NetAmountTWD'])]
    for col, val in enumerate(values, start=1):
        c = quotes_ws.cell(i, col, val)
        if col in (1, 2, 3, 6, 7):
            c.number_format = '@'
        elif col in (4, 5):
            c.number_format = 'yyyy-mm-dd'
        elif col in (8, 10, 11):
            c.number_format = '0.00'
        elif col == 9:
            c.number_format = '0.##'

for i, r in enumerate(line_rows, start=5):
    copy_row_style(lines_ws, 5 if i != 5 else 4, i, 6)
    values = [r['QuoteID'], r['ProductID'], r['ProductName'], float(r['Quantity']) if r['Quantity'] is not None else None,
              dec_to_float(r['UnitPrice']), dec_to_float(r['LineAmount'])]
    for col, val in enumerate(values, start=1):
        c = lines_ws.cell(i, col, val)
        if col in (1, 2):
            c.number_format = '@'
        elif col == 4:
            c.number_format = '0.##'
        elif col in (5, 6):
            c.number_format = '0.00'

# Summary by Status and Currency.
summary = defaultdict(lambda: {'amount': Decimal('0'), 'amount_twd': Decimal('0'), 'count': 0})
for r in quote_rows:
    key = (r['Status'] or '', '', r['Currency'] or '')
    summary[key]['amount'] += r['NetAmount'] or Decimal('0')
    summary[key]['amount_twd'] += r['NetAmountTWD'] or Decimal('0')
    summary[key]['count'] += 1

for idx, ((group, subgroup, cur), vals) in enumerate(sorted(summary.items()), start=5):
    copy_row_style(summary_ws, 5 if idx != 5 else 4, idx, 6)
    row_vals = [group, subgroup, cur, dec_to_float(vals['amount']), dec_to_float(vals['amount_twd']), vals['count']]
    for col, val in enumerate(row_vals, start=1):
        c = summary_ws.cell(idx, col, val)
        if col in (4, 5):
            c.number_format = '0.00'
        if col == 6:
            c.number_format = '0'
last_quote_row = 4 + len(quote_rows) if quote_rows else 5
summary_ws['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})' if quote_rows else '=SUM(Quotes!K5:K5)'
summary_ws['B2'].number_format = '0.00'

# Freeze/filter if template lacks dynamic extension. Do not adjust widths.
if quote_rows:
    quotes_ws.auto_filter.ref = f'A4:K{4+len(quote_rows)}'
if line_rows:
    lines_ws.auto_filter.ref = f'A4:F{4+len(line_rows)}'
if summary:
    summary_ws.auto_filter.ref = f'A4:F{4+len(summary)}'

wb.save(OUT_XLSX)

RUN_LOG.write_text(json.dumps({
    'status': 'succeeded',
    'query': {'from': FROM_DATE, 'to': TO_DATE, 'status': STATUS},
    'quote_count': len(quote_rows),
    'line_count': len(line_rows),
    'fx_rates': {k: str(v) for k, v in fx_rates.items()},
    'cli_attempts': cli_log,
    'output': str(OUT_XLSX),
}, ensure_ascii=False, indent=2), encoding='utf-8')

# Verification: reopen saved output and check requirements.
wb2 = load_workbook(OUT_XLSX, data_only=False)
checks = []
failures = []
def check(name, condition, detail=''):
    checks.append((name, bool(condition), detail))
    if not condition:
        failures.append(f'{name}: {detail}')

check('Workbook exists', OUT_XLSX.exists(), str(OUT_XLSX))
check('Sheet names preserved', wb2.sheetnames == ['Report', 'Quotes', 'Lines', 'Summary', 'Instructions'], str(wb2.sheetnames))
qws = wb2['Quotes']; lws = wb2['Lines']; sws = wb2['Summary']; rws = wb2['Report']
check('Report period from', rws['B3'].value == FROM_DATE, repr(rws['B3'].value))
check('Report period to', rws['D3'].value == TO_DATE, repr(rws['D3'].value))
check('Quotes header row preserved', [qws.cell(4,c).value for c in range(1,12)] == ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD'])
check('Lines header row preserved', [lws.cell(4,c).value for c in range(1,7)] == ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount'])
check('Summary header row preserved', [sws.cell(4,c).value for c in range(1,7)] == ['Group','SubGroup','Currency','Amount','AmountTWD','Count'])
# Count nonblank data rows.
saved_quote_rows = [row for row in qws.iter_rows(min_row=5, max_col=11, values_only=True) if any(v is not None for v in row)]
saved_line_rows = [row for row in lws.iter_rows(min_row=5, max_col=6, values_only=True) if any(v is not None for v in row)]
saved_summary_rows = [row for row in sws.iter_rows(min_row=5, max_col=6, values_only=True) if any(v is not None for v in row)]
check('Quote row count', len(saved_quote_rows) == len(quote_rows), f'saved={len(saved_quote_rows)} expected={len(quote_rows)}')
check('Line row count', len(saved_line_rows) == len(line_rows), f'saved={len(saved_line_rows)} expected={len(line_rows)}')
check('Summary row count', len(saved_summary_rows) == len(summary), f'saved={len(saved_summary_rows)} expected={len(summary)}')
# Types/formats.
for row_idx in range(5, 5+len(saved_quote_rows)):
    check(f'Quote IDs text format row {row_idx}', all(qws.cell(row_idx,c).number_format == '@' for c in (1,2,3)), str([qws.cell(row_idx,c).number_format for c in (1,2,3)]))
    check(f'Quote numeric types row {row_idx}', all(isinstance(qws.cell(row_idx,c).value, (int,float)) for c in (8,9,10,11)), str([type(qws.cell(row_idx,c).value).__name__ for c in (8,9,10,11)]))
    check(f'Quote status Sent row {row_idx}', qws.cell(row_idx,6).value == STATUS, repr(qws.cell(row_idx,6).value))
    qd = qws.cell(row_idx,4).value
    check(f'Quote date in Sep 2026 row {row_idx}', isinstance(qd, (datetime, date)) and date(2026,9,1) <= (qd.date() if isinstance(qd, datetime) else qd) <= date(2026,9,30), repr(qd))
for row_idx in range(5, 5+len(saved_line_rows)):
    check(f'Line IDs text format row {row_idx}', all(lws.cell(row_idx,c).number_format == '@' for c in (1,2)), str([lws.cell(row_idx,c).number_format for c in (1,2)]))
    check(f'Line numeric types row {row_idx}', all(isinstance(lws.cell(row_idx,c).value, (int,float)) for c in (4,5,6)), str([type(lws.cell(row_idx,c).value).__name__ for c in (4,5,6)]))
# Formula and totals.
expected_formula = f'=SUM(Quotes!K5:K{4+len(quote_rows)})' if quote_rows else '=SUM(Quotes!K5:K5)'
check('Summary B2 formula extended', sws['B2'].value == expected_formula, repr(sws['B2'].value))
# Check calculated values in sheet equal our computed source values (within cents).
for saved, expected in zip(saved_quote_rows, quote_rows):
    check(f'QuoteID order {expected["QuoteID"]}', saved[0] == expected['QuoteID'], repr(saved[0]))
    check(f'NetAmountTWD {expected["QuoteID"]}', Decimal(str(saved[10])).quantize(Decimal('0.01')) == expected['NetAmountTWD'], f'saved={saved[10]} expected={expected["NetAmountTWD"]}')

summary_text = []
summary_text.append(f'Output workbook: {OUT_XLSX}')
summary_text.append(f'Quote rows: {len(quote_rows)}')
summary_text.append(f'Line rows: {len(line_rows)}')
summary_text.append(f'Summary rows: {len(summary)}')
summary_text.append('CLI attempts:')
for rec in cli_log:
    summary_text.append(f"- {rec['label']} attempt {rec['attempt']} exit {rec['exit_code']} stderr={rec['stderr']!r} stdout_length={rec['stdout_length']}")
summary_text.append('Checks:')
for name, ok, detail in checks:
    summary_text.append(f"- {'OK' if ok else 'FAIL'} {name} {detail}")
CHECK_LOG.write_text('\n'.join(summary_text), encoding='utf-8')

print('\n'.join(summary_text))
if failures:
    print('VERIFICATION FAILED')
    for f in failures:
        print(f)
    raise SystemExit(1)
print('VERIFICATION PASSED')