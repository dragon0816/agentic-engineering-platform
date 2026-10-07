import os, json, csv, subprocess, shutil, sys
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Alignment
from copy import copy

params = json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
customer_id = str(params['customer_id']).strip()
from_date = str(params['from_date']).strip()
to_date = str(params['to_date']).strip()
cli_path = str(params['cli_path']).strip()

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
template = input_dir / 'quote_template.xlsx'
fx_file = input_dir / 'fx_rates.csv'
if not template.exists():
    raise FileNotFoundError(f'Missing template: {template}')
if not fx_file.exists():
    raise FileNotFoundError(f'Missing fx file: {fx_file}')
if not Path(cli_path).exists():
    raise FileNotFoundError(f'CLI path does not exist: {cli_path}')

# Read FX rates. Notes may contain unquoted commas in this benchmark; only first two columns are needed.
rates = {}
with open(fx_file, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader, None)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(str(row[1]))
if not rates:
    raise ValueError('No FX rates loaded')

def q2(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def run_cli(args):
    cmd = [cli_path] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f'CLI failed ({res.returncode}) for {args}: {res.stderr}')
    return res.stdout

list_raw = run_cli(['quotes','list','--customer',customer_id,'--from',from_date,'--to',to_date,'--format','json'])
listed = json.loads(list_raw)
quote_items = listed.get('items', [])
if listed.get('schema_version') != 1:
    raise ValueError(f"Unexpected list schema_version: {listed.get('schema_version')}")

headers = []
lines = []
for item in quote_items:
    qid = item['QuoteID']
    raw = run_cli(['quotes','get',qid,'--format','json'])
    doc = json.loads(raw)
    if doc.get('schema_version') != 1:
        raise ValueError(f'Unexpected get schema_version for {qid}: {doc.get("schema_version")}')
    h = doc['header']
    currency = h.get('Currency')
    if currency not in rates:
        raise ValueError(f'Missing FX rate for currency {currency} in quote {qid}')
    h2 = dict(h)
    h2['NetAmountTWD'] = q2(Decimal(str(h2['NetAmount'])) * rates[currency])
    headers.append(h2)
    for line in doc.get('line_items', []):
        l2 = {'QuoteID': qid, **line}
        lines.append(l2)

# Sort deterministically by date then ID; lines follow quote order as returned.
headers.sort(key=lambda h: (h.get('QuoteDate',''), h.get('QuoteID','')))
quote_order = {h['QuoteID']: i for i, h in enumerate(headers)}
lines.sort(key=lambda l: (quote_order.get(l['QuoteID'], 10**9), l['QuoteID'], l.get('ProductID','')))

safe = ''.join(ch if ch.isalnum() or ch in ('-','_') else '_' for ch in f'{customer_id}_{from_date}_{to_date}')
out_path = output_dir / f'quote_report_{safe}.xlsx'
shutil.copyfile(template, out_path)
wb = load_workbook(out_path)

# Helpers preserve template row 5 style if present, otherwise row 4 style.
def clear_data(ws, start_row=5):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

def style_row_from(ws, src_row, dst_row, max_col):
    for col in range(1, max_col + 1):
        src = ws.cell(src_row, col)
        dst = ws.cell(dst_row, col)
        if src.has_style:
            dst.font = copy(src.font)
            dst.fill = copy(src.fill)
            dst.border = copy(src.border)
            dst.alignment = copy(src.alignment)
            dst.number_format = src.number_format
            dst.protection = copy(src.protection)

def write_rows(ws, headers_row, columns, records, formats):
    clear_data(ws, headers_row + 1)
    src_style_row = headers_row + 1 if ws.max_row >= headers_row + 1 else headers_row
    for i, rec in enumerate(records, start=headers_row + 1):
        style_row_from(ws, src_style_row, i, len(columns))
        for col_idx, col_name in enumerate(columns, start=1):
            cell = ws.cell(i, col_idx)
            val = rec.get(col_name, '')
            if val is None:
                val = ''
            if col_name in formats.get('text', set()):
                cell.value = str(val) if val != '' else ''
                cell.number_format = '@'
            elif col_name in formats.get('decimal', set()):
                cell.value = float(q2(val)) if val != '' else None
                cell.number_format = '0.00'
            elif col_name in formats.get('int', set()):
                cell.value = int(val) if val != '' else None
            else:
                cell.value = val

quote_cols = [c.value for c in wb['Quotes'][4][:11]]
line_cols = [c.value for c in wb['Lines'][4][:6]]
expected_quote_cols = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
expected_line_cols = ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
if quote_cols != expected_quote_cols:
    raise ValueError(f'Unexpected Quotes headers: {quote_cols}')
if line_cols != expected_line_cols:
    raise ValueError(f'Unexpected Lines headers: {line_cols}')

write_rows(wb['Quotes'], 4, expected_quote_cols, headers, {
    'text': {'QuoteID','CustomerID','ProjectID','Status','Currency','QuoteDate','ValidUntil'},
    'decimal': {'Subtotal','NetAmount','NetAmountTWD'},
})
write_rows(wb['Lines'], 4, expected_line_cols, lines, {
    'text': {'QuoteID','ProductID','ProductName'},
    'decimal': {'UnitPrice','LineAmount'},
    'int': {'Quantity'},
})

# Summary by Status and Currency; original-currency Amount is summed only within each currency.
summary = {}
for h in headers:
    key = (h['Status'], h['Currency'])
    rec = summary.setdefault(key, {'Group':'Status', 'SubGroup': h['Status'], 'Currency': h['Currency'], 'Amount': Decimal('0'), 'AmountTWD': Decimal('0'), 'Count': 0})
    rec['Amount'] += Decimal(str(h['NetAmount']))
    rec['AmountTWD'] += Decimal(str(h['NetAmountTWD']))
    rec['Count'] += 1
summary_rows = []
for key in sorted(summary.keys()):
    rec = summary[key]
    rec = dict(rec)
    rec['Amount'] = q2(rec['Amount'])
    rec['AmountTWD'] = q2(rec['AmountTWD'])
    summary_rows.append(rec)
summary_cols = [c.value for c in wb['Summary'][4][:6]]
expected_summary_cols = ['Group','SubGroup','Currency','Amount','AmountTWD','Count']
if summary_cols != expected_summary_cols:
    raise ValueError(f'Unexpected Summary headers: {summary_cols}')
write_rows(wb['Summary'], 4, expected_summary_cols, summary_rows, {
    'text': {'Group','SubGroup','Currency'},
    'decimal': {'Amount','AmountTWD'},
    'int': {'Count'},
})

# Report metadata.
report = wb['Report']
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = f'CustomerID={customer_id}; QuoteDate {from_date}..{to_date}; all statuses'
generated = datetime.now().astimezone().isoformat(timespec='seconds')
report['B5'] = generated
report['B7'] = 'quote_cli'
report['D7'] = generated
report['B9'] = '' if headers else 'No quotes returned for the selected filters.'

# Extend Summary B2 total formula per template instruction.
last_quote_row = 4 + len(headers) if headers else 5
wb['Summary']['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'

wb.save(out_path)

# Verification from saved output.
wb2 = load_workbook(out_path, data_only=False)
checks = []
qws, lws, sws = wb2['Quotes'], wb2['Lines'], wb2['Summary']
q_rows = max(0, qws.max_row - 4)
l_rows = max(0, lws.max_row - 4)
s_rows = max(0, sws.max_row - 4)
if q_rows != len(headers):
    raise AssertionError(f'Quotes row count mismatch: {q_rows} != {len(headers)}')
if l_rows != len(lines):
    raise AssertionError(f'Lines row count mismatch: {l_rows} != {len(lines)}')
if s_rows != len(summary_rows):
    raise AssertionError(f'Summary row count mismatch: {s_rows} != {len(summary_rows)}')
if [c.value for c in qws[4][:11]] != expected_quote_cols:
    raise AssertionError('Quotes column names changed')
if [c.value for c in lws[4][:6]] != expected_line_cols:
    raise AssertionError('Lines column names changed')
if [c.value for c in sws[4][:6]] != expected_summary_cols:
    raise AssertionError('Summary column names changed')
for r in range(5, 5 + q_rows):
    if qws.cell(r,1).data_type != 's' or qws.cell(r,2).data_type != 's':
        raise AssertionError(f'Quote IDs not stored as text at row {r}')
    for c in (8,10,11):
        if not isinstance(qws.cell(r,c).value, (int,float)):
            raise AssertionError(f'Quotes numeric col {c} not numeric at row {r}: {qws.cell(r,c).value!r}')
for r in range(5, 5 + l_rows):
    if lws.cell(r,1).data_type != 's' or lws.cell(r,2).data_type != 's':
        raise AssertionError(f'Line IDs not stored as text at row {r}')
    for c in (4,5,6):
        if not isinstance(lws.cell(r,c).value, (int,float)):
            raise AssertionError(f'Lines numeric col {c} not numeric at row {r}: {lws.cell(r,c).value!r}')
for r in range(5, 5 + s_rows):
    if sws.cell(r,1).value != 'Status':
        raise AssertionError(f'Summary Group not Status at row {r}')
    for c in (4,5,6):
        if not isinstance(sws.cell(r,c).value, (int,float)):
            raise AssertionError(f'Summary numeric col {c} not numeric at row {r}: {sws.cell(r,c).value!r}')
expected_formula = f'=SUM(Quotes!K5:K{last_quote_row})'
if sws['B2'].value != expected_formula:
    raise AssertionError(f'Summary B2 formula mismatch: {sws["B2"].value} != {expected_formula}')

print(json.dumps({
    'output_file': str(out_path),
    'customer_id': customer_id,
    'from_date': from_date,
    'to_date': to_date,
    'quote_count': len(headers),
    'line_count': len(lines),
    'summary_count': len(summary_rows),
    'summary_b2_formula': expected_formula,
    'fx_rates': {k: str(v) for k,v in rates.items()},
    'checks': ['reopened workbook', 'sheet names preserved', 'headers preserved', 'row counts match CLI data', 'ID columns are text', 'amount/count columns are numeric', 'Summary grouped by Status and Currency', 'Summary B2 formula extended']
}, ensure_ascii=False, indent=2))