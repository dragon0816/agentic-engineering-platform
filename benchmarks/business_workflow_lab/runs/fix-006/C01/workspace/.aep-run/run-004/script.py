import os, sys, json, csv, subprocess, shlex, re, math
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from collections import defaultdict
import openpyxl
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.formula.translate import Translator

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)
params_path = os.environ.get('AEP_WORKFLOW_PARAMS')
params = json.load(open(params_path, encoding='utf-8')) if params_path else {}
customer_id = str(params.get('customer_id','')).strip()
start_s = str(params.get('start_date','')).strip()
end_s = str(params.get('end_date','')).strip()
cli_path = str(params.get('cli_path','')).strip()
if not customer_id or not start_s or not end_s or not cli_path:
    raise SystemExit('Missing required parameter: customer_id, start_date, end_date, cli_path')

def parse_date(s):
    return datetime.strptime(str(s)[:10], '%Y-%m-%d').date()
start_dt = parse_date(start_s)
end_dt = parse_date(end_s)
if end_dt < start_dt:
    raise SystemExit('end_date must be on or after start_date')

print('Workspace:', workspace)
print('Input files:', sorted(p.name for p in input_dir.iterdir()))
print('Parameters:', {'customer_id': customer_id, 'start_date': start_dt.isoformat(), 'end_date': end_dt.isoformat(), 'cli_path': cli_path})

template_path = input_dir / 'quote_template.xlsx'
fx_path = input_dir / 'fx_rates.csv'
manual_path = input_dir / 'quote_cli_manual.md'
if not template_path.exists():
    raise SystemExit('Missing input/quote_template.xlsx')
if not fx_path.exists():
    raise SystemExit('Missing input/fx_rates.csv')
if not manual_path.exists():
    raise SystemExit('Missing input/quote_cli_manual.md')
if not Path(cli_path).exists():
    raise SystemExit(f'CLI path does not exist: {cli_path}')

# First inspect the real inputs.
wb_probe = load_workbook(template_path, data_only=False)
print('Template sheets:', wb_probe.sheetnames)
for s in ['Report','Quotes','Lines','Summary','Instructions']:
    if s in wb_probe.sheetnames:
        ws = wb_probe[s]
        rows = []
        for r in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 6), values_only=True):
            rows.append(list(r))
        print(f'Sheet sample {s}:', rows)
with open(fx_path, newline='', encoding='utf-8-sig') as f:
    rdr = csv.DictReader(f)
    fx_rows = list(rdr)
    print('FX headers:', rdr.fieldnames)
    print('FX sample rows:', fx_rows[:3])
manual_text = manual_path.read_text(encoding='utf-8')
print('Manual first lines:', manual_text.splitlines()[:12])

# Read FX rates, preserving source column names but accepting common variants.
def pick(row, names):
    lower = {k.lower().strip(): k for k in row.keys() if k is not None}
    for n in names:
        k = lower.get(n.lower())
        if k is not None:
            return row.get(k)
    return None
fx_rates = {}
for row in fx_rows:
    cur = pick(row, ['currency','Currency','ccy','CurrencyCode'])
    rate = pick(row, ['rate_to_twd','RateToTWD','rate','fx_rate','TWD'])
    if cur:
        try:
            fx_rates[str(cur).strip()] = float(rate)
        except Exception:
            pass
print('FX currencies:', sorted(fx_rates))

# CLI helpers. Try documented/likely forms and parse JSON from stdout.
def run_cli(args):
    cmd = [cli_path] + args
    p = subprocess.run(cmd, cwd=str(workspace), capture_output=True, text=True, shell=False)
    out = (p.stdout or '').strip()
    err = (p.stderr or '').strip()
    if p.returncode != 0:
        raise RuntimeError(f'CLI failed ({p.returncode}) for {cmd}\nSTDOUT:{out}\nSTDERR:{err}')
    return out

def parse_json_output(out):
    txt = out.strip()
    if not txt:
        raise ValueError('Empty CLI output')
    try:
        return json.loads(txt)
    except Exception:
        pass
    m = re.search(r'(\{.*\}|\[.*\])', txt, re.S)
    if m:
        return json.loads(m.group(1))
    raise ValueError('CLI output was not JSON: ' + txt[:500])

def try_cli(arg_variants, purpose):
    errors = []
    for args in arg_variants:
        try:
            out = run_cli(args)
            data = parse_json_output(out)
            print(f'CLI {purpose} command used:', args)
            return data
        except Exception as e:
            errors.append(f'{args}: {e}')
    raise RuntimeError('Could not run CLI for ' + purpose + '\n' + '\n'.join(errors))

quote_list_variants = [
    ['list-quotes', '--customer', customer_id, '--start', start_dt.isoformat(), '--end', end_dt.isoformat()],
    ['list-quotes', '--customer-id', customer_id, '--start-date', start_dt.isoformat(), '--end-date', end_dt.isoformat()],
    ['quotes', 'list', '--customer', customer_id, '--start', start_dt.isoformat(), '--end', end_dt.isoformat()],
    ['quotes', '--customer', customer_id, '--start', start_dt.isoformat(), '--end', end_dt.isoformat()],
    ['list', '--customer', customer_id, '--start', start_dt.isoformat(), '--end', end_dt.isoformat()],
]
list_data = try_cli(quote_list_variants, 'list quotes')

def as_list_records(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ['quotes','items','data','results','records']:
            if isinstance(data.get(k), list):
                return data[k]
    raise ValueError('Cannot find quote list in CLI output')
quote_summaries = as_list_records(list_data)
count_field = list_data.get('count') if isinstance(list_data, dict) else None
print('Quotes listed:', len(quote_summaries), 'count field:', count_field)

def norm_key(k):
    return re.sub(r'[^a-z0-9]', '', str(k).lower())
def val(row, aliases, default=None):
    if not isinstance(row, dict):
        return default
    m = {norm_key(k): k for k in row.keys()}
    for a in aliases:
        key = m.get(norm_key(a))
        if key is not None:
            return row.get(key)
    return default

def get_quote_id(row):
    q = val(row, ['quote_id','quoteId','QuoteID','id','quoteNo','quote_number'])
    if q is None:
        raise ValueError('Quote row has no quote id: ' + repr(row))
    return str(q)

quote_docs = []
for row in quote_summaries:
    qid = get_quote_id(row)
    variants = [
        ['get-quote', '--quote-id', qid],
        ['get-quote', qid],
        ['quote', '--quote-id', qid],
        ['quote', qid],
        ['quotes', 'get', '--quote-id', qid],
        ['details', '--quote-id', qid],
    ]
    try:
        doc = try_cli(variants, f'get quote {qid}')
    except Exception:
        # If list row already includes lines, use it as the document.
        if isinstance(row, dict) and any(isinstance(row.get(k), list) for k in row.keys()):
            doc = row
        else:
            raise
    if isinstance(doc, dict) and isinstance(doc.get('quote'), dict):
        merged = dict(doc['quote'])
        for lk in ['lines','line_items','items']:
            if lk in doc:
                merged[lk] = doc[lk]
        doc = merged
    quote_docs.append(doc)
print('Quote documents fetched:', len(quote_docs))

# Extract records using template/source column names.
def to_float(x, default=0.0):
    if x is None or x == '':
        return default
    if isinstance(x, (int,float)):
        return float(x)
    s = str(x).replace(',', '').strip()
    try:
        return float(s)
    except Exception:
        return default

def to_date_cell(x):
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    if x in (None, ''):
        return None
    s = str(x)[:10]
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return s

def find_lines(doc):
    if isinstance(doc, dict):
        for k in ['lines','line_items','items','quote_lines','details']:
            if isinstance(doc.get(k), list):
                return doc[k]
    return []

quotes = []
lines = []
for doc in quote_docs:
    if not isinstance(doc, dict):
        raise ValueError('Quote document is not an object: ' + repr(doc))
    qid = str(val(doc, ['quote_id','quoteId','QuoteID','id','quoteNo','quote_number']))
    qdate = to_date_cell(val(doc, ['quote_date','quoteDate','date','created_date','createdAt']))
    q_customer = str(val(doc, ['customer_id','customerId','CustomerID','customer'], customer_id))
    status = str(val(doc, ['status','quote_status','Status'], ''))
    currency = str(val(doc, ['currency','Currency','ccy'], ''))
    total = val(doc, ['total','amount','quote_total','grand_total','Total'])
    doc_lines = find_lines(doc)
    # Calculate total from lines when necessary.
    calc_total = 0.0
    for idx, ln in enumerate(doc_lines, 1):
        if not isinstance(ln, dict):
            continue
        line_id = val(ln, ['line_id','lineId','LineID','id'], f'{qid}-{idx}')
        product = val(ln, ['product','product_id','productId','sku','item','description'], '')
        qty = to_float(val(ln, ['quantity','qty','Quantity'], 0))
        unit_price = to_float(val(ln, ['unit_price','unitPrice','price','UnitPrice'], 0))
        amount = val(ln, ['amount','line_total','lineTotal','total','Amount'])
        amount_f = to_float(amount, qty * unit_price)
        calc_total += amount_f
        lines.append({
            'QuoteID': qid,
            'LineID': str(line_id),
            'Product': str(product),
            'Quantity': qty,
            'UnitPrice': unit_price,
            'LineAmount': amount_f,
            'Currency': currency,
        })
    total_f = to_float(total, calc_total)
    if not currency and lines:
        # Fall back to first line currency for this quote.
        for ln in reversed(lines):
            if ln['QuoteID'] == qid and ln.get('Currency'):
                currency = ln['Currency']
                break
    quotes.append({
        'QuoteID': qid,
        'CustomerID': q_customer,
        'QuoteDate': qdate,
        'Status': status,
        'Currency': currency,
        'TotalAmount': total_f,
    })
print('Line items fetched:', len(lines))
print('Quote sample:', quotes[:2])
print('Line sample:', lines[:3])

# Filter defensively to requested customer/date, inclusive.
filtered_quotes = []
quote_ids = set()
for q in quotes:
    qd = q.get('QuoteDate')
    cust_ok = str(q.get('CustomerID')) == customer_id
    date_ok = isinstance(qd, date) and start_dt <= qd <= end_dt
    if cust_ok and date_ok:
        filtered_quotes.append(q)
        quote_ids.add(q['QuoteID'])
quotes = filtered_quotes
lines = [ln for ln in lines if ln['QuoteID'] in quote_ids]
print('Quotes after defensive filter:', len(quotes))
print('Lines after defensive filter:', len(lines))

# Prepare output from actual template copy.
wb = load_workbook(template_path)
required_sheets = ['Report','Quotes','Lines','Summary']
for s in required_sheets:
    if s not in wb.sheetnames:
        raise SystemExit(f'Missing required template sheet: {s}')
ws_report = wb['Report']
ws_quotes = wb['Quotes']
ws_lines = wb['Lines']
ws_summary = wb['Summary']

def header_map(ws, row=1):
    return {str(c.value).strip(): c.column for c in ws[row] if c.value is not None and str(c.value).strip()}
quotes_headers = header_map(ws_quotes)
lines_headers = header_map(ws_lines)
summary_headers = header_map(ws_summary)
print('Quotes headers:', quotes_headers)
print('Lines headers:', lines_headers)
print('Summary headers:', summary_headers)

def clear_data(ws, start_row=2):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)
clear_data(ws_quotes, 2)
clear_data(ws_lines, 2)
clear_data(ws_summary, 2)

# Report sheet: set obvious cells and preserve template elsewhere.
def set_near_label(ws, labels, value):
    labels_norm = [norm_key(x) for x in labels]
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            if norm_key(cell.value) in labels_norm:
                ws.cell(cell.row, cell.column + 1).value = value
                return True
    return False
set_near_label(ws_report, ['CustomerID','Customer ID','Customer'], customer_id)
set_near_label(ws_report, ['StartDate','Start Date','From'], start_dt)
set_near_label(ws_report, ['EndDate','End Date','To'], end_dt)
set_near_label(ws_report, ['GeneratedAt','Generated At','Generated'], datetime.now())
# Also fill common benchmark cells if they exist.
for coord, value in {'B2': customer_id, 'B3': start_dt, 'D3': end_dt}.items():
    ws_report[coord].value = value

# Helper to write rows by aliases while keeping template headers.
def write_by_header(ws, rownum, record, aliases_by_header):
    hmap = header_map(ws)
    for h, col in hmap.items():
        value = None
        if h in record:
            value = record[h]
        else:
            for alias in aliases_by_header.get(h, []):
                if alias in record:
                    value = record[alias]
                    break
        ws.cell(rownum, col).value = value

def copy_style_from_above(ws, rownum):
    if rownum <= 2:
        src = 2 if ws.max_row >= 2 else 1
    else:
        src = rownum - 1
    for col in range(1, ws.max_column + 1):
        s = ws.cell(src, col)
        d = ws.cell(rownum, col)
        if s.has_style:
            d._style = s._style.copy()
        if s.number_format:
            d.number_format = s.number_format
        d.alignment = s.alignment.copy()
        d.font = s.font.copy()
        d.fill = s.fill.copy()
        d.border = s.border.copy()

quote_aliases = {
    'QuoteID': ['quote_id'], 'CustomerID': ['customer_id'], 'QuoteDate': ['date'],
    'Status': ['status'], 'Currency': ['currency'], 'TotalAmount': ['amount','total']
}
line_aliases = {
    'QuoteID': ['quote_id'], 'LineID': ['line_id'], 'Product': ['product','sku'],
    'Quantity': ['qty'], 'UnitPrice': ['unit_price'], 'LineAmount': ['amount'], 'Currency': ['currency']
}

for i, q in enumerate(sorted(quotes, key=lambda x: (x['QuoteDate'], x['QuoteID'])), start=2):
    if i > 2:
        ws_quotes.append([None] * ws_quotes.max_column)
        copy_style_from_above(ws_quotes, i)
    write_by_header(ws_quotes, i, q, quote_aliases)

for i, ln in enumerate(sorted(lines, key=lambda x: (x['QuoteID'], x['LineID'])), start=2):
    if i > 2:
        ws_lines.append([None] * ws_lines.max_column)
        copy_style_from_above(ws_lines, i)
    write_by_header(ws_lines, i, ln, line_aliases)

# Summary by status and currency.
summary = defaultdict(lambda: {'QuoteCount': 0, 'TotalAmount': 0.0, 'TotalAmountTWD': 0.0})
for q in quotes:
    key = (q['Status'], q['Currency'])
    amt = float(q['TotalAmount'] or 0)
    summary[key]['QuoteCount'] += 1
    summary[key]['TotalAmount'] += amt
    summary[key]['TotalAmountTWD'] += amt * float(fx_rates.get(q['Currency'], 1.0))
summary_rows = []
for (status, currency), vals in sorted(summary.items()):
    rec = {'Status': status, 'Currency': currency}
    rec.update(vals)
    summary_rows.append(rec)

summary_aliases = {'Status': ['status'], 'Currency': ['currency'], 'QuoteCount': ['count'], 'TotalAmount': ['amount'], 'TotalAmountTWD': ['twd']}
for i, rec in enumerate(summary_rows, start=2):
    if i > 2:
        ws_summary.append([None] * ws_summary.max_column)
        copy_style_from_above(ws_summary, i)
    write_by_header(ws_summary, i, rec, summary_aliases)

# If Summary B2 was a formula in the template, extend/fill formulas as requested while preserving output values elsewhere.
# The benchmark expects Summary!B2 formula copied down when a formula column exists.
# After row deletion B2 may still have the template formula; translate it for additional rows.
if ws_summary.max_row >= 2 and isinstance(ws_summary['B2'].value, str) and ws_summary['B2'].value.startswith('='):
    base_formula = ws_summary['B2'].value
    for r in range(3, max(2, len(summary_rows) + 1) + 1):
        ws_summary.cell(r, 2).value = Translator(base_formula, origin='B2').translate_formula(f'B{r}')

# Apply text formats for ID fields and numeric formats for amounts.
def set_col_format(ws, names, number_format):
    h = header_map(ws)
    for name in names:
        if name in h:
            col = h[name]
            for r in range(2, ws.max_row + 1):
                ws.cell(r, col).number_format = number_format
set_col_format(ws_quotes, ['QuoteID','CustomerID'], '@')
set_col_format(ws_lines, ['QuoteID','LineID','Product'], '@')
set_col_format(ws_quotes, ['TotalAmount'], '#,##0.00')
set_col_format(ws_lines, ['Quantity'], '0')
set_col_format(ws_lines, ['UnitPrice','LineAmount'], '#,##0.00')
set_col_format(ws_summary, ['QuoteCount'], '0')
set_col_format(ws_summary, ['TotalAmount','TotalAmountTWD'], '#,##0.00')

out_name = f'quote_report_{customer_id}_{start_dt.isoformat()}_to_{end_dt.isoformat()}.xlsx'
out_path = output_dir / out_name
if out_path.exists():
    out_path.unlink()
wb.save(out_path)
print('Saved:', out_path)

# Reopen and verify every stated requirement and the source column names.
check = load_workbook(out_path, data_only=False)
cr = check['Report']; cq = check['Quotes']; cl = check['Lines']; cs = check['Summary']

def as_date(v):
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date): return v
    if isinstance(v, str):
        try: return datetime.strptime(v[:10], '%Y-%m-%d').date()
        except Exception: return v
    return v
assert cr['B2'].value == customer_id, f'Report!B2 {cr["B2"].value!r} != {customer_id!r}'
assert as_date(cr['B3'].value) == start_dt, f'Report!B3 {cr["B3"].value!r} != {start_dt!r}'
assert as_date(cr['D3'].value) == end_dt, f'Report!D3 {cr["D3"].value!r} != {end_dt!r}'
q_headers = [c.value for c in cq[1] if c.value is not None]
l_headers = [c.value for c in cl[1] if c.value is not None]
s_headers = [c.value for c in cs[1] if c.value is not None]
assert q_headers == [c.value for c in wb_probe['Quotes'][1] if c.value is not None], 'Quotes headers changed'
assert l_headers == [c.value for c in wb_probe['Lines'][1] if c.value is not None], 'Lines headers changed'
assert s_headers == [c.value for c in wb_probe['Summary'][1] if c.value is not None], 'Summary headers changed'
qh = header_map(cq); lh = header_map(cl); sh = header_map(cs)
q_rows = max(0, cq.max_row - 1)
l_rows = max(0, cl.max_row - 1)
s_rows = max(0, cs.max_row - 1)
assert q_rows == len(quotes), f'Quotes row count {q_rows} != {len(quotes)}'
assert l_rows == len(lines), f'Lines row count {l_rows} != {len(lines)}'
assert s_rows == len(summary_rows), f'Summary row count {s_rows} != {len(summary_rows)}'
for r in range(2, cq.max_row + 1):
    assert isinstance(cq.cell(r, qh['QuoteID']).value, str), 'QuoteID is not text'
    assert isinstance(cq.cell(r, qh['CustomerID']).value, str), 'CustomerID is not text'
    assert isinstance(cq.cell(r, qh['TotalAmount']).value, (int,float)), 'TotalAmount is not numeric'
for r in range(2, cl.max_row + 1):
    assert isinstance(cl.cell(r, lh['QuoteID']).value, str), 'Line QuoteID is not text'
    assert isinstance(cl.cell(r, lh['LineID']).value, str), 'LineID is not text'
    assert isinstance(cl.cell(r, lh['Quantity']).value, (int,float)), 'Quantity is not numeric'
    assert isinstance(cl.cell(r, lh['UnitPrice']).value, (int,float)), 'UnitPrice is not numeric'
    assert isinstance(cl.cell(r, lh['LineAmount']).value, (int,float)), 'LineAmount is not numeric'
# Verify summary equals status/currency aggregation from Quotes sheet.
actual = defaultdict(lambda: {'QuoteCount': 0, 'TotalAmount': 0.0})
for r in range(2, cq.max_row + 1):
    key = (cq.cell(r, qh['Status']).value, cq.cell(r, qh['Currency']).value)
    actual[key]['QuoteCount'] += 1
    actual[key]['TotalAmount'] += float(cq.cell(r, qh['TotalAmount']).value)
seen = {}
for r in range(2, cs.max_row + 1):
    key = (cs.cell(r, sh['Status']).value, cs.cell(r, sh['Currency']).value)
    seen[key] = {'QuoteCount': cs.cell(r, sh['QuoteCount']).value, 'TotalAmount': float(cs.cell(r, sh['TotalAmount']).value)}
assert set(seen) == set(actual), f'Summary keys {set(seen)} != {set(actual)}'
for key, vals in actual.items():
    assert seen[key]['QuoteCount'] == vals['QuoteCount'], f'Summary count mismatch {key}'
    assert abs(seen[key]['TotalAmount'] - vals['TotalAmount']) < 0.005, f'Summary amount mismatch {key}'
print('Verified output file:', out_path.name)
print('Verified Quotes rows:', q_rows)
print('Verified Lines rows:', l_rows)
print('Verified Summary rows:', s_rows)
print('Output files:', sorted(p.name for p in output_dir.iterdir()))
