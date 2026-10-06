from pathlib import Path
import subprocess, json, sys, os, csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from copy import copy
from openpyxl import load_workbook

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

projects = [f'P{i:03d}' for i in range(1, 6)]
from_date = '2026-09-01'
to_date = '2026-09-30'
status = 'Accepted'
cli = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')

# Load FX rates (only first two CSV fields matter; Note contains an unquoted comma in this fixture)
fx_rates = {}
with open(input_dir / 'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row or not row[0].strip():
            continue
        fx_rates[row[0].strip()] = Decimal(row[1].strip())
print('FX rates:', {k: str(v) for k, v in fx_rates.items()})

# Helpers
def money2(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def run_cli(args):
    cmd = [sys.executable, str(cli)] + args
    cp = subprocess.run(cmd, text=True, capture_output=True, cwd=str(workspace))
    if cp.returncode != 0:
        raise RuntimeError(f'CLI failed {cp.returncode}: {cmd}\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}')
    return json.loads(cp.stdout)

# Fetch accepted quote headers and line details by project
headers = []
lines = []
fetched_at = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
for project in projects:
    data = run_cli(['quotes', 'list', '--project', project, '--from', from_date, '--to', to_date, '--status', status, '--format', 'json'])
    print(f'{project}: list count={data.get("count")}')
    for item in data.get('items', []):
        qid = item['QuoteID']
        detail = run_cli(['quotes', 'get', qid, '--format', 'json'])
        header = detail['header']
        if header.get('ProjectID') != project or header.get('Status') != status or not (from_date <= header.get('QuoteDate', '') <= to_date):
            raise AssertionError(f'Unexpected header outside filters: {header}')
        currency = header['Currency']
        if currency not in fx_rates:
            raise AssertionError(f'Missing FX rate for {currency}')
        header = dict(header)
        header['NetAmountTWD'] = money2(Decimal(header['NetAmount']) * fx_rates[currency])
        headers.append(header)
        for li in detail.get('line_items', []):
            li = dict(li)
            li['QuoteID'] = qid
            lines.append(li)

headers.sort(key=lambda h: (h['ProjectID'], h['QuoteDate'], h['QuoteID']))
lines.sort(key=lambda l: (l['QuoteID'], l['ProductID']))
print('Accepted quotes fetched:', len(headers))
print('Line items fetched:', len(lines))

# Load workbook and preserve template styling by copying row 5 style when adding rows
wb = load_workbook(input_dir / 'quote_template.xlsx')
report = wb['Report']
quotes_ws = wb['Quotes']
lines_ws = wb['Lines']
summary_ws = wb['Summary']

# Clear old data rows from row 5 downward
for ws in (quotes_ws, lines_ws, summary_ws):
    if ws.max_row >= 5:
        ws.delete_rows(5, ws.max_row - 4)

# Fill report
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = 'ProjectID P001-P005; Status Accepted; QuoteDate 2026-09-01..2026-09-30; NetAmountTWD = NetAmount × attachment FX rate'
report['B5'] = fetched_at
report['B7'] = 'quote_cli mock; input/fx_rates.csv'
report['D7'] = fetched_at

quote_columns = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
line_columns = ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
summary_columns = ['Group','SubGroup','Currency','Amount','AmountTWD','Count']

def copy_row_style(ws, src_row, dst_row, cols):
    for c in range(1, cols + 1):
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

# Insert quote headers
for r_idx, h in enumerate(headers, start=5):
    copy_row_style(quotes_ws, 5, r_idx, len(quote_columns))
    for c_idx, col in enumerate(quote_columns, start=1):
        val = h.get(col)
        if col in ('Subtotal','DiscountPercent','NetAmount','NetAmountTWD') and val is not None:
            val = float(Decimal(str(val)))
        quotes_ws.cell(r_idx, c_idx, val)

# Insert line items
for r_idx, li in enumerate(lines, start=5):
    copy_row_style(lines_ws, 5, r_idx, len(line_columns))
    for c_idx, col in enumerate(line_columns, start=1):
        val = li.get(col)
        if col in ('Quantity',):
            val = int(val)
        elif col in ('UnitPrice','LineAmount') and val is not None:
            val = float(Decimal(str(val)))
        lines_ws.cell(r_idx, c_idx, val)

# Summary: one row per ProjectID. Amount is reported only when all accepted quotes for that project use one currency;
# otherwise it is left blank and Currency='MULTI' to avoid directly adding original currency amounts.
by_project = {p: {'count': 0, 'twd': Decimal('0.00'), 'curr_amounts': {}} for p in projects}
for h in headers:
    p = h['ProjectID']
    cur = h['Currency']
    by_project[p]['count'] += 1
    by_project[p]['twd'] += Decimal(str(h['NetAmountTWD']))
    by_project[p]['curr_amounts'].setdefault(cur, Decimal('0.00'))
    by_project[p]['curr_amounts'][cur] += Decimal(str(h['NetAmount']))

for r_offset, p in enumerate(projects, start=5):
    copy_row_style(summary_ws, 5, r_offset, len(summary_columns))
    rec = by_project[p]
    curr_amounts = rec['curr_amounts']
    if rec['count'] == 0:
        currency = ''
        amount = Decimal('0.00')
    elif len(curr_amounts) == 1:
        currency, amount = next(iter(curr_amounts.items()))
    else:
        currency = 'MULTI'
        amount = None
    values = [p, 'Accepted', currency, None if amount is None else float(amount), float(rec['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), rec['count']]
    for c_idx, val in enumerate(values, start=1):
        summary_ws.cell(r_offset, c_idx, val)

# Fix summary total formula to actual quote row range
last_quote_row = max(5, 4 + len(headers))
summary_ws['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'

out_path = output_dir / 'quote_template_filled.xlsx'
wb.save(out_path)
print('Wrote', out_path)

# Verification by reopening saved output
check_wb = load_workbook(out_path, data_only=False)
qws = check_wb['Quotes']
lws = check_wb['Lines']
sws = check_wb['Summary']
rws = check_wb['Report']
assert [qws.cell(4,c).value for c in range(1,12)] == quote_columns
assert [lws.cell(4,c).value for c in range(1,7)] == line_columns
assert [sws.cell(4,c).value for c in range(1,7)] == summary_columns
assert rws['B3'].value == from_date and rws['D3'].value == to_date
quote_rows = list(qws.iter_rows(min_row=5, max_row=4+len(headers), values_only=True)) if headers else []
assert len(quote_rows) == len(headers)
for row in quote_rows:
    q = dict(zip(quote_columns, row))
    assert q['ProjectID'] in projects
    assert q['Status'] == status
    assert from_date <= q['QuoteDate'] <= to_date
    expected_twd = money2(Decimal(str(q['NetAmount'])) * fx_rates[q['Currency']])
    assert Decimal(str(q['NetAmountTWD'])).quantize(Decimal('0.01')) == expected_twd
summary_rows = list(sws.iter_rows(min_row=5, max_row=9, values_only=True))
assert len(summary_rows) == 5
assert [r[0] for r in summary_rows] == projects
for row in summary_rows:
    p, subgroup, currency, amount, amount_twd, count = row
    assert subgroup == 'Accepted'
    assert isinstance(count, int)
    assert Decimal(str(amount_twd)).quantize(Decimal('0.01')) == by_project[p]['twd'].quantize(Decimal('0.01'))
    if count == 0:
        assert Decimal(str(amount)).quantize(Decimal('0.01')) == Decimal('0.00')
        assert Decimal(str(amount_twd)).quantize(Decimal('0.01')) == Decimal('0.00')
print('Verified output: quote columns, line columns, summary columns, date/filter metadata, NetAmountTWD FX calculation, Summary P001-P005 rows including zero rows, and no mixed original-currency sum (MULTI/blank amount if needed).')