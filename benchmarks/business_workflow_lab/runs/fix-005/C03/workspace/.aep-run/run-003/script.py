from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from copy import copy
import csv, json, subprocess, sys
from openpyxl import load_workbook

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)

TEMPLATE = INPUT / 'quote_template.xlsx'
FX_FILE = INPUT / 'fx_rates.csv'
OUTFILE = OUTPUT / 'quote_report_P001-P005_2026-09_Accepted.xlsx'
CLI = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd')

PROJECTS = [f'P{i:03d}' for i in range(1, 6)]
FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
STATUS = 'Accepted'
GENERATED_AT = datetime.now().astimezone().isoformat(timespec='seconds')

TWOPLACES = Decimal('0.01')
def money(v):
    if v is None or v == '':
        return None
    return Decimal(str(v)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def twd_amount(amount, rate):
    return (Decimal(str(amount)) * Decimal(str(rate))).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def clone_row_style(ws, src_row, dst_row, max_col):
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
        dst.protection = copy(src.protection)

# Load FX rates using csv.reader because Note contains an unquoted comma in this synthetic file.
fx_rates = {}
with FX_FILE.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    try:
        currency_idx = header.index('Currency')
        rate_idx = header.index('RateToTWD')
    except ValueError as e:
        raise RuntimeError(f'fx_rates.csv missing required columns: {header}') from e
    for row in reader:
        if not row or len(row) <= max(currency_idx, rate_idx):
            continue
        cur = row[currency_idx].strip()
        rate = row[rate_idx].strip()
        if cur:
            fx_rates[cur] = Decimal(rate)
print('FX rates loaded:', fx_rates)

if not CLI.exists():
    raise FileNotFoundError(f'quote_cli not found: {CLI}')

# Fetch quote headers for each project, then fetch detail lines per quote.
headers = []
lines = []
fetched_at_parts = []
for project in PROJECTS:
    cmd = [str(CLI), 'quotes', 'list', '--project', project, '--from', FROM_DATE, '--to', TO_DATE, '--status', STATUS, '--format', 'json']
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        raise RuntimeError(f'quote_cli list failed for {project}: exit={proc.returncode}; stderr={proc.stderr}')
    data = json.loads(proc.stdout)
    if data.get('schema_version') != 1:
        raise RuntimeError(f'unexpected schema_version for {project}: {data.get("schema_version")}')
    items = data.get('items', [])
    print(project, 'accepted quote count:', len(items))
    for item in items:
        # Validate filters returned from system.
        if item.get('ProjectID') != project or item.get('Status') != STATUS or not (FROM_DATE <= item.get('QuoteDate', '') <= TO_DATE):
            raise RuntimeError(f'quote_cli returned item outside requested filters: {item}')
        cur = item.get('Currency')
        if cur not in fx_rates:
            raise RuntimeError(f'missing FX rate for currency {cur} in quote {item.get("QuoteID")}')
        item = dict(item)
        item['NetAmountTWD'] = twd_amount(item['NetAmount'], fx_rates[cur])
        headers.append(item)

        qid = item['QuoteID']
        get_cmd = [str(CLI), 'quotes', 'get', qid, '--format', 'json']
        proc2 = subprocess.run(get_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if proc2.returncode != 0:
            raise RuntimeError(f'quote_cli get failed for {qid}: exit={proc2.returncode}; stderr={proc2.stderr}')
        detail = json.loads(proc2.stdout)
        if detail.get('schema_version') != 1:
            raise RuntimeError(f'unexpected detail schema_version for {qid}: {detail.get("schema_version")}')
        detail_header = detail.get('header', {})
        if detail_header.get('QuoteID') != qid:
            raise RuntimeError(f'detail QuoteID mismatch for {qid}: {detail_header}')
        for line in detail.get('line_items', []):
            row = dict(line)
            row['QuoteID'] = qid
            lines.append(row)

fetched_at = datetime.now().astimezone().isoformat(timespec='seconds')

# Sort for deterministic workbook.
headers.sort(key=lambda x: (x['ProjectID'], x['QuoteDate'], x['QuoteID']))
lines.sort(key=lambda x: (x['QuoteID'], x['ProductID']))

# Prepare workbook.
wb = load_workbook(TEMPLATE)
ws_report = wb['Report']
ws_quotes = wb['Quotes']
ws_lines = wb['Lines']
ws_summary = wb['Summary']

# Clear existing detail rows, if any, preserving header/layout.
def clear_data_rows(ws, start_row, max_col):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)
    # Ensure a styled first data row exists for style cloning if workbook had none.
    if ws.max_row < start_row:
        ws.insert_rows(start_row)

# Report sheet
ws_report['B3'] = FROM_DATE
ws_report['D3'] = TO_DATE
ws_report['B4'] = 'ProjectID P001-P005; Status=Accepted; QuoteDate 2026-09-01..2026-09-30 inclusive'
ws_report['B5'] = GENERATED_AT
ws_report['B7'] = 'quote_cli; fx_rates.csv'
ws_report['D7'] = fetched_at
ws_report['B9'] = 'NetAmountTWD = NetAmount × RateToTWD, ROUND_HALF_UP to 2 decimals. Summary keeps zero rows for projects without Accepted quotes and does not mix original-currency amounts across currencies.'

# Clear sheets, using row 5 onward.
clear_data_rows(ws_quotes, 5, 11)
clear_data_rows(ws_lines, 5, 6)
clear_data_rows(ws_summary, 5, 6)

# Write Quotes
quote_columns = ['QuoteID', 'CustomerID', 'ProjectID', 'QuoteDate', 'ValidUntil', 'Status', 'Currency', 'Subtotal', 'DiscountPercent', 'NetAmount', 'NetAmountTWD']
for idx, item in enumerate(headers, start=5):
    if idx > 5:
        ws_quotes.insert_rows(idx)
    clone_row_style(ws_quotes, 5, idx, 11)
    for col, key in enumerate(quote_columns, start=1):
        val = item.get(key)
        cell = ws_quotes.cell(idx, col)
        if key in ('QuoteID', 'CustomerID', 'ProjectID', 'Status', 'Currency'):
            cell.value = '' if val is None else str(val)
            cell.number_format = '@'
        elif key in ('QuoteDate', 'ValidUntil'):
            cell.value = '' if val is None else str(val)
            cell.number_format = 'yyyy-mm-dd'
        elif key in ('Subtotal', 'NetAmount', 'NetAmountTWD'):
            cell.value = float(money(val)) if val is not None else None
            cell.number_format = '0.00'
        elif key == 'DiscountPercent':
            cell.value = float(Decimal(str(val))) if val is not None else None

# If no quotes, leave row 5 blank for formula range per template. In this task there may be quotes.
last_quote_row = max(5, 4 + len(headers))
if len(headers) == 0:
    # blank row 5 only
    for col in range(1, 12):
        ws_quotes.cell(5, col).value = None

# Write Lines
line_columns = ['QuoteID', 'ProductID', 'ProductName', 'Quantity', 'UnitPrice', 'LineAmount']
for idx, item in enumerate(lines, start=5):
    if idx > 5:
        ws_lines.insert_rows(idx)
    clone_row_style(ws_lines, 5, idx, 6)
    for col, key in enumerate(line_columns, start=1):
        val = item.get(key)
        cell = ws_lines.cell(idx, col)
        if key in ('QuoteID', 'ProductID', 'ProductName'):
            cell.value = '' if val is None else str(val)
            cell.number_format = '@'
        elif key == 'Quantity':
            cell.value = int(val) if val is not None else None
        elif key in ('UnitPrice', 'LineAmount'):
            cell.value = float(money(val)) if val is not None else None
            cell.number_format = '0.00'
if len(lines) == 0:
    for col in range(1, 7):
        ws_lines.cell(5, col).value = None

# Build Summary. Group by ProjectID + Currency where there are quotes to avoid mixing original currencies.
# For no Accepted quotes per project, keep one row with blank Currency, Amount=0, AmountTWD=0, Count=0.
summary_rows = []
by_project_currency = {}
for item in headers:
    key = (item['ProjectID'], item['Currency'])
    acc = by_project_currency.setdefault(key, {'Amount': Decimal('0.00'), 'AmountTWD': Decimal('0.00'), 'Count': 0})
    acc['Amount'] += money(item['NetAmount'])
    acc['AmountTWD'] += money(item['NetAmountTWD'])
    acc['Count'] += 1

for project in PROJECTS:
    rows_for_project = [(cur, vals) for (proj, cur), vals in by_project_currency.items() if proj == project]
    if rows_for_project:
        for cur, vals in sorted(rows_for_project):
            summary_rows.append({
                'Group': project,
                'SubGroup': '',
                'Currency': cur,
                'Amount': vals['Amount'].quantize(TWOPLACES),
                'AmountTWD': vals['AmountTWD'].quantize(TWOPLACES),
                'Count': vals['Count'],
            })
    else:
        summary_rows.append({'Group': project, 'SubGroup': '', 'Currency': '', 'Amount': Decimal('0.00'), 'AmountTWD': Decimal('0.00'), 'Count': 0})

for idx, row in enumerate(summary_rows, start=5):
    if idx > 5:
        ws_summary.insert_rows(idx)
    clone_row_style(ws_summary, 5, idx, 6)
    vals = [row['Group'], row['SubGroup'], row['Currency'], row['Amount'], row['AmountTWD'], row['Count']]
    for col, val in enumerate(vals, start=1):
        cell = ws_summary.cell(idx, col)
        if col in (1, 2, 3):
            cell.value = '' if val is None else str(val)
            cell.number_format = '@'
        elif col in (4, 5):
            cell.value = float(val)
            cell.number_format = '0.00'
        elif col == 6:
            cell.value = int(val)

# Update Summary B2 formula range. Keep formula, extend range to last quote data row.
ws_summary['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'

# Ensure sheet names unchanged and Instructions not changed structurally.
wb.save(OUTFILE)
print('Wrote', OUTFILE)
print('Quote rows:', len(headers), 'Line rows:', len(lines), 'Summary rows:', len(summary_rows))
print('Quote IDs:', [h['QuoteID'] for h in headers])
print('Summary:', summary_rows)

# Verification from saved output.
wb2 = load_workbook(OUTFILE, data_only=False)
errors = []
if wb2.sheetnames != ['Report', 'Quotes', 'Lines', 'Summary', 'Instructions']:
    errors.append(f'sheet names changed: {wb2.sheetnames}')
q = wb2['Quotes']
l = wb2['Lines']
s = wb2['Summary']
expected_q_headers = quote_columns
actual_q_headers = [q.cell(4, c).value for c in range(1, 12)]
if actual_q_headers != expected_q_headers:
    errors.append(f'Quotes headers mismatch: {actual_q_headers}')
expected_l_headers = line_columns
actual_l_headers = [l.cell(4, c).value for c in range(1, 7)]
if actual_l_headers != expected_l_headers:
    errors.append(f'Lines headers mismatch: {actual_l_headers}')
expected_s_headers = ['Group', 'SubGroup', 'Currency', 'Amount', 'AmountTWD', 'Count']
actual_s_headers = [s.cell(4, c).value for c in range(1, 7)]
if actual_s_headers != expected_s_headers:
    errors.append(f'Summary headers mismatch: {actual_s_headers}')

# Check quote rows count and filters.
saved_quote_rows = []
for r in range(5, 5 + len(headers)):
    row = {key: q.cell(r, i+1).value for i, key in enumerate(quote_columns)}
    saved_quote_rows.append(row)
    if row['ProjectID'] not in PROJECTS:
        errors.append(f'Quote row project outside range: {row}')
    if row['Status'] != STATUS:
        errors.append(f'Quote row status not Accepted: {row}')
    if not (FROM_DATE <= row['QuoteDate'] <= TO_DATE):
        errors.append(f'Quote row date outside period: {row}')
    expected_twd = float(twd_amount(Decimal(str(row['NetAmount'])), fx_rates[row['Currency']]))
    if round(float(row['NetAmountTWD']) - expected_twd, 2) != 0:
        errors.append(f'NetAmountTWD mismatch: {row}, expected {expected_twd}')
    for key in ('QuoteID', 'CustomerID', 'ProjectID'):
        if not isinstance(row[key], str):
            errors.append(f'{key} not text in row {r}: {row[key]!r}')

# Check line QuoteIDs all correspond.
quote_ids = {h['QuoteID'] for h in headers}
for r in range(5, 5 + len(lines)):
    qid = l.cell(r, 1).value
    if qid not in quote_ids:
        errors.append(f'Line row {r} has unmatched QuoteID {qid}')
    for c in (1, 2):
        if not isinstance(l.cell(r, c).value, str):
            errors.append(f'Line row {r} col {c} not text: {l.cell(r,c).value!r}')

# Check summary contains every P001-P005, zero rows for projects with no accepted quotes, and no mixed currency originals.
saved_summary = []
for r in range(5, 5 + len(summary_rows)):
    saved_summary.append({
        'Group': s.cell(r,1).value,
        'SubGroup': s.cell(r,2).value,
        'Currency': s.cell(r,3).value,
        'Amount': Decimal(str(s.cell(r,4).value)).quantize(TWOPLACES),
        'AmountTWD': Decimal(str(s.cell(r,5).value)).quantize(TWOPLACES),
        'Count': int(s.cell(r,6).value),
    })
summary_projects = {row['Group'] for row in saved_summary}
if summary_projects != set(PROJECTS):
    errors.append(f'Summary projects mismatch: {summary_projects}')
for project in PROJECTS:
    project_quotes = [h for h in headers if h['ProjectID'] == project]
    project_summary = [row for row in saved_summary if row['Group'] == project]
    if not project_quotes:
        if len(project_summary) != 1 or project_summary[0]['Amount'] != Decimal('0.00') or project_summary[0]['AmountTWD'] != Decimal('0.00') or project_summary[0]['Count'] != 0:
            errors.append(f'Missing/incorrect zero summary row for {project}: {project_summary}')
    else:
        # Each summary row with original amount must be one currency only.
        currencies = {h['Currency'] for h in project_quotes}
        if {row['Currency'] for row in project_summary} != currencies:
            errors.append(f'Summary currencies mismatch for {project}: {project_summary}, quotes {currencies}')
        for cur in currencies:
            qs = [h for h in project_quotes if h['Currency'] == cur]
            sr = [row for row in project_summary if row['Currency'] == cur]
            if len(sr) != 1:
                errors.append(f'Expected one summary row for {project}/{cur}, got {sr}')
            else:
                exp_amt = sum((money(h['NetAmount']) for h in qs), Decimal('0.00')).quantize(TWOPLACES)
                exp_twd = sum((money(h['NetAmountTWD']) for h in qs), Decimal('0.00')).quantize(TWOPLACES)
                if sr[0]['Amount'] != exp_amt or sr[0]['AmountTWD'] != exp_twd or sr[0]['Count'] != len(qs):
                    errors.append(f'Summary totals mismatch for {project}/{cur}: {sr[0]}, expected {exp_amt}/{exp_twd}/{len(qs)}')

if s['B2'].value != f'=SUM(Quotes!K5:K{last_quote_row})':
    errors.append(f'Summary B2 formula mismatch: {s["B2"].value}')

if errors:
    print('VERIFICATION FAILED')
    for e in errors:
        print('-', e)
    raise SystemExit(1)
else:
    print('VERIFICATION OK')
    print('Checked: saved workbook exists; sheet and column names; quote filters; ID cells as text values; NetAmountTWD from saved rows using fx rates; line QuoteID joins; Summary ProjectID coverage including zero rows; no original currency mixing; B2 formula range.')
