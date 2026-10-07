from pathlib import Path
import subprocess, json, csv, shutil, os, sys
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from copy import copy
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Alignment, Protection
from openpyxl.utils import get_column_letter

WORK = Path('.').resolve()
INPUT = WORK / 'input'
OUTPUT = WORK / 'output'
OUTPUT.mkdir(exist_ok=True)

# Print full instructions so the run log captures the template contract.
print('=== Template Instructions ===')
wb_check = load_workbook(INPUT / 'quote_template.xlsx', data_only=False)
ws_i = wb_check['Instructions']
for row in ws_i.iter_rows(values_only=True):
    if any(v is not None for v in row):
        print(row)

# Load FX rates. The Note field contains commas in this synthetic CSV, so only first two columns are relevant.
fx_rates = {}
with (INPUT / 'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('FX header:', header)
    for row in reader:
        if not row or not row[0].strip():
            continue
        fx_rates[row[0].strip()] = Decimal(row[1].strip())
print('FX rates used:', {k: str(v) for k, v in fx_rates.items()})

manual = (INPUT / 'quote_cli_manual.md').read_text(encoding='utf-8')
cli_cmd = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
if not Path(cli_cmd).exists():
    raise FileNotFoundError(cli_cmd)
print('CLI:', cli_cmd)

FROM = '2026-09-01'
TO = '2026-09-30'
STATUS = 'Accepted'
PROJECTS = [f'P{i:03d}' for i in range(1, 6)]

# Helper to run CLI safely; stdout is data only on exit 0 per manual.
def run_cli(args):
    cmd = [cli_cmd] + args
    print('RUN:', ' '.join(cmd))
    cp = subprocess.run(cmd, text=True, capture_output=True, shell=False)
    print('  exit:', cp.returncode)
    if cp.stderr.strip():
        print('  stderr:', cp.stderr.strip())
    if cp.returncode != 0:
        raise RuntimeError(f'CLI failed: {cmd}\n{cp.stderr}')
    return cp.stdout

# Obtain quote headers for each project with explicit filters; then get line items for each quote.
headers = []
seen = set()
for project in PROJECTS:
    out = run_cli(['quotes', 'list', '--project', project, '--from', FROM, '--to', TO, '--status', STATUS, '--format', 'json'])
    data = json.loads(out)
    print(f'{project} list count:', data.get('count'), 'items:', data.get('items'))
    if data.get('schema_version') != 1:
        raise ValueError(f'Unexpected schema_version for {project}: {data.get("schema_version")}')
    for h in data.get('items', []):
        qid = h['QuoteID']
        if qid not in seen:
            seen.add(qid)
            headers.append(h)

headers.sort(key=lambda h: (h['ProjectID'], h['QuoteDate'], h['QuoteID']))
print('Total unique accepted quote headers:', len(headers))

quote_details = {}
all_lines = []
for h in headers:
    qid = h['QuoteID']
    detail = json.loads(run_cli(['quotes', 'get', qid, '--format', 'json']))
    if detail.get('schema_version') != 1:
        raise ValueError(f'Unexpected detail schema_version for {qid}')
    quote_details[qid] = detail
    for line in detail.get('line_items', []):
        row = {'QuoteID': qid, **line}
        all_lines.append(row)
print('Total line items:', len(all_lines))

# Prepare workbook copy from template; never alter input.
template = INPUT / 'quote_template.xlsx'
out_path = OUTPUT / 'quote_report_P001-P005_2026-09_Accepted.xlsx'
shutil.copyfile(template, out_path)
wb = load_workbook(out_path)

# Utility: clear data rows from row 5 downward only, preserving row 4 headers and top instruction rows.
def clear_data(ws, start_row=5):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

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

money_fmt = '0.00'
date_fmt = 'yyyy-mm-dd'
text_fmt = '@'

# Report sheet.
ws = wb['Report']
ws['B3'] = FROM
ws['D3'] = TO
ws['B4'] = 'ProjectID P001-P005; Status Accepted; QuoteDate 2026-09-01 through 2026-09-30 inclusive'
now = datetime.now().astimezone().replace(microsecond=0).isoformat()
ws['B5'] = now
ws['B7'] = 'quote_cli synthetic quote system; fx_rates.csv'
ws['D7'] = now
ws['B9'] = 'NetAmountTWD calculated from NetAmount × RateToTWD using attached fixed rates; Summary groups by ProjectID and Currency to avoid mixing original-currency amounts. Projects without Accepted quotes retained with zero row.'

# Quotes sheet.
wsq = wb['Quotes']
clear_data(wsq)
quote_cols = [wsq.cell(4, c).value for c in range(1, wsq.max_column + 1)]
print('Quote columns:', quote_cols)
for idx, h in enumerate(headers, start=5):
    copy_row_style(wsq, 4, idx, len(quote_cols))
    currency = h['Currency']
    if currency not in fx_rates:
        raise KeyError(f'Missing FX rate for {currency}')
    net = Decimal(str(h['NetAmount']))
    twd = (net * fx_rates[currency]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    values = {
        'QuoteID': str(h['QuoteID']),
        'CustomerID': str(h['CustomerID']),
        'ProjectID': str(h['ProjectID']),
        'QuoteDate': str(h['QuoteDate']),
        'ValidUntil': str(h['ValidUntil']),
        'Status': str(h['Status']),
        'Currency': str(currency),
        'Subtotal': float(Decimal(str(h['Subtotal']))),
        'DiscountPercent': float(Decimal(str(h['DiscountPercent']))),
        'NetAmount': float(net),
        'NetAmountTWD': float(twd),
    }
    for c, col in enumerate(quote_cols, start=1):
        wsq.cell(idx, c).value = values[col]
    for c in [1,2,3,6,7]:
        wsq.cell(idx, c).number_format = text_fmt
    for c in [4,5]:
        wsq.cell(idx, c).number_format = 'yyyy-mm-dd'
    for c in [8,9,10,11]:
        wsq.cell(idx, c).number_format = money_fmt

# Lines sheet.
wsl = wb['Lines']
clear_data(wsl)
line_cols = [wsl.cell(4, c).value for c in range(1, wsl.max_column + 1)]
print('Line columns:', line_cols)
all_lines.sort(key=lambda r: (r['QuoteID'], r['ProductID']))
for idx, line in enumerate(all_lines, start=5):
    copy_row_style(wsl, 4, idx, len(line_cols))
    values = {
        'QuoteID': str(line['QuoteID']),
        'ProductID': str(line['ProductID']),
        'ProductName': str(line['ProductName']),
        'Quantity': int(line['Quantity']),
        'UnitPrice': float(Decimal(str(line['UnitPrice']))),
        'LineAmount': float(Decimal(str(line['LineAmount']))),
    }
    for c, col in enumerate(line_cols, start=1):
        wsl.cell(idx, c).value = values[col]
    for c in [1,2,3]:
        wsl.cell(idx, c).number_format = text_fmt
    wsl.cell(idx, 4).number_format = '0'
    for c in [5,6]:
        wsl.cell(idx, c).number_format = money_fmt

# Summary sheet. Group by ProjectID and Currency, retaining zero row for projects with no accepted quotes.
wss = wb['Summary']
clear_data(wss)
summary_cols = [wss.cell(4, c).value for c in range(1, wss.max_column + 1)]
print('Summary columns:', summary_cols)
summary = {}
for h in headers:
    key = (h['ProjectID'], h['Currency'])
    net = Decimal(str(h['NetAmount']))
    twd = (net * fx_rates[h['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    cur = summary.setdefault(key, {'Amount': Decimal('0.00'), 'AmountTWD': Decimal('0.00'), 'Count': 0})
    cur['Amount'] += net
    cur['AmountTWD'] += twd
    cur['Count'] += 1

summary_rows = []
for project in PROJECTS:
    keys = sorted([k for k in summary if k[0] == project], key=lambda k: k[1])
    if keys:
        for project_id, currency in keys:
            s = summary[(project_id, currency)]
            summary_rows.append({
                'Group': project_id,
                'SubGroup': 'ProjectID',
                'Currency': currency,
                'Amount': s['Amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'AmountTWD': s['AmountTWD'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'Count': s['Count'],
            })
    else:
        summary_rows.append({
            'Group': project,
            'SubGroup': 'ProjectID',
            'Currency': '',
            'Amount': Decimal('0.00'),
            'AmountTWD': Decimal('0.00'),
            'Count': 0,
        })

for idx, row in enumerate(summary_rows, start=5):
    copy_row_style(wss, 4, idx, len(summary_cols))
    values = {**row, 'Amount': float(row['Amount']), 'AmountTWD': float(row['AmountTWD'])}
    for c, col in enumerate(summary_cols, start=1):
        wss.cell(idx, c).value = values[col]
    for c in [1,2,3]:
        wss.cell(idx, c).number_format = text_fmt
    for c in [4,5]:
        wss.cell(idx, c).number_format = money_fmt
    wss.cell(idx, 6).number_format = '0'

# Update total formula to cover actual quote rows; no data => zero.
last_quote_row = 4 + len(headers)
if len(headers) > 0:
    wss['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'
else:
    wss['B2'] = '=0'
wss['B2'].number_format = money_fmt

# Freeze panes helpful but not required; avoid touching Instructions.
for sname in ['Quotes','Lines','Summary']:
    wb[sname].freeze_panes = 'A5'

wb.save(out_path)
print('Saved:', out_path)

# Verification: reopen output and confirm requirements.
wb2 = load_workbook(out_path, data_only=False)
wsq2 = wb2['Quotes']; wsl2 = wb2['Lines']; wss2 = wb2['Summary']; wr2 = wb2['Report']
errors = []
# Column names unchanged.
if [wsq2.cell(4,c).value for c in range(1,12)] != quote_cols:
    errors.append('Quotes columns changed')
if [wsl2.cell(4,c).value for c in range(1,7)] != line_cols:
    errors.append('Lines columns changed')
if [wss2.cell(4,c).value for c in range(1,7)] != summary_cols:
    errors.append('Summary columns changed')
# Quote rows match filters and NetAmountTWD.
q_rows = list(wsq2.iter_rows(min_row=5, max_row=4+len(headers), values_only=True)) if headers else []
if len(q_rows) != len(headers):
    errors.append(f'Quote row count {len(q_rows)} != {len(headers)}')
for r in q_rows:
    qid, customer, project, qdate, valid, status, curr, subtotal, disc, net, twd = r
    if project not in PROJECTS or status != STATUS or not (FROM <= str(qdate) <= TO):
        errors.append(f'Quote row violates filters: {r}')
    expected = (Decimal(str(net)) * fx_rates[curr]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if Decimal(str(twd)).quantize(Decimal('0.01')) != expected:
        errors.append(f'Bad NetAmountTWD for {qid}: {twd} != {expected}')
    if not isinstance(qid, str) or not isinstance(project, str):
        errors.append(f'ID not text in quote row: {r}')
# Lines count.
l_rows = list(wsl2.iter_rows(min_row=5, max_row=4+len(all_lines), values_only=True)) if all_lines else []
if len(l_rows) != len(all_lines):
    errors.append(f'Line row count {len(l_rows)} != {len(all_lines)}')
for r in l_rows:
    if not isinstance(r[0], str) or not isinstance(r[1], str):
        errors.append(f'Line ID not text: {r}')
    if not isinstance(r[3], int):
        errors.append(f'Quantity not int: {r}')
# Summary contains every P001-P005 at least once, zero row where no quote.
s_rows = list(wss2.iter_rows(min_row=5, max_row=4+len(summary_rows), values_only=True))
projects_in_summary = {r[0] for r in s_rows}
if projects_in_summary != set(PROJECTS):
    errors.append(f'Summary projects {projects_in_summary} != {set(PROJECTS)}')
for project in PROJECTS:
    has_quote = any(h['ProjectID'] == project for h in headers)
    rows = [r for r in s_rows if r[0] == project]
    if not has_quote:
        if len(rows) != 1 or rows[0][3] != 0 or rows[0][4] != 0 or rows[0][5] != 0:
            errors.append(f'Missing/invalid zero summary row for {project}: {rows}')
for r in s_rows:
    if not isinstance(r[0], str):
        errors.append(f'Summary project ID not text: {r}')
    if not isinstance(r[3], (int, float)) or not isinstance(r[4], (int, float)) or not isinstance(r[5], int):
        errors.append(f'Summary value types invalid: {r}')
# Report fields.
if wr2['B3'].value != FROM or wr2['D3'].value != TO:
    errors.append('Report dates not set')

print('\n=== Result summary ===')
print('Quote rows:', len(headers))
print('Line rows:', len(all_lines))
print('Summary rows:', len(summary_rows))
print('Summary data:')
for r in s_rows:
    print(r)
print('Total formula B2:', wss2['B2'].value)

if errors:
    print('\nVERIFICATION FAILED')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print('\nVERIFICATION PASSED')
print('Checked: output file opens; template sheet/headers preserved; Report period/source filled; Quotes filtered to P001-P005, 2026-09, Accepted; NetAmountTWD uses fx_rates.csv; Lines populated from quote details; Summary has every project P001-P005, grouped by ProjectID+Currency and zero row for projects without Accepted quotes; ID cells are text and monetary cells are numeric.')
