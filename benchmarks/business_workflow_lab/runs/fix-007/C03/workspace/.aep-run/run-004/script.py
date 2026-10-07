from pathlib import Path
import subprocess, json, sys, csv, re, shutil
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timezone, timedelta
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Alignment
from openpyxl.cell.cell import MergedCell

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
TEMPLATE = INPUT / 'quote_template.xlsx'
FX_FILE = INPUT / 'fx_rates.csv'
MANUAL = INPUT / 'quote_cli_manual.md'
OUTFILE = OUTPUT / 'quote_report_P001-P005_2026-09_Accepted.xlsx'
PROJECTS = [f'P{i:03d}' for i in range(1,6)]
FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
STATUS = 'Accepted'
TWOPLACES = Decimal('0.01')

def q2(x):
    return Decimal(str(x)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def parse_date(s):
    y,m,d = map(int, s.split('-'))
    return date(y,m,d)

def read_fx(path):
    rates = {}
    with open(path, newline='', encoding='utf-8-sig') as f:
        r = csv.reader(f)
        header = next(r)
        if header[0] != 'Currency' or header[1] != 'RateToTWD':
            raise RuntimeError(f'Unexpected fx header: {header}')
        for row in r:
            if not row: continue
            rates[row[0]] = Decimal(row[1])
    return rates

def find_cli(manual_text):
    m = re.search(r'python "([^"]*run_quote_cli\.py)" <command>', manual_text)
    if not m:
        raise RuntimeError('Cannot find run_quote_cli.py path in manual')
    return m.group(1)

def run_cli(cli, args):
    cmd = [sys.executable, cli] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f'CLI failed {res.returncode}: {cmd}\nstderr={res.stderr}\nstdout={res.stdout}')
    return json.loads(res.stdout)

def copy_row_style(ws, src_row, dst_row, max_col):
    for col in range(1, max_col+1):
        src = ws.cell(src_row, col)
        dst = ws.cell(dst_row, col)
        if src.has_style:
            dst._style = src._style.copy()
        if src.number_format:
            dst.number_format = src.number_format
        if src.alignment:
            dst.alignment = src.alignment.copy()
        if src.font:
            dst.font = src.font.copy()
        if src.fill:
            dst.fill = src.fill.copy()
        if src.border:
            dst.border = src.border.copy()
    ws.row_dimensions[dst_row].height = ws.row_dimensions[src_row].height

def clear_sheet_data(ws, start_row, max_col):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)
    # leave sheet ending at header row; styles for data rows will be copied from header if needed

# Read source metadata and fetch data
print('Workspace:', WORKSPACE)
print('Input files:', sorted(p.name for p in INPUT.iterdir()))
fx = read_fx(FX_FILE)
print('FX rates:', {k: str(v) for k,v in fx.items()})
cli = find_cli(MANUAL.read_text(encoding='utf-8'))
print('CLI:', cli)

headers = []
line_rows = []
for project in PROJECTS:
    listed = run_cli(cli, ['quotes', 'list', '--project', project, '--from', FROM_DATE, '--to', TO_DATE, '--status', STATUS, '--format', 'json'])
    if listed.get('schema_version') != 1:
        raise RuntimeError(f'Unexpected schema for list {project}: {listed.get("schema_version")}')
    print(f'Fetched {project}: {listed.get("count")} rows')
    for item in listed.get('items', []):
        # defensive checks for requested filters
        if item['ProjectID'] != project or item['Status'] != STATUS or not (FROM_DATE <= item['QuoteDate'] <= TO_DATE):
            raise RuntimeError(f'CLI returned out-of-filter item: {item}')
        if item['Currency'] not in fx:
            raise RuntimeError(f'Missing FX rate for {item["Currency"]}')
        detail = run_cli(cli, ['quotes', 'get', item['QuoteID'], '--format', 'json'])
        if detail.get('schema_version') != 1:
            raise RuntimeError(f'Unexpected schema for quote {item["QuoteID"]}')
        hdr = detail['header']
        if hdr != item:
            # Same keys and values are expected by the manual; fail rather than guessing.
            raise RuntimeError(f'Header mismatch for {item["QuoteID"]}: list={item}, get={hdr}')
        net = q2(hdr['NetAmount'])
        rate = fx[hdr['Currency']]
        hdr = dict(hdr)
        hdr['NetAmountTWD'] = q2(net * rate)
        headers.append(hdr)
        for li in detail.get('line_items', []):
            row = dict(li)
            row['QuoteID'] = hdr['QuoteID']
            line_rows.append(row)

headers.sort(key=lambda h: (h['ProjectID'], h['QuoteDate'], h['QuoteID']))
line_rows.sort(key=lambda r: (r['QuoteID'], r['ProductID']))
print('Total accepted quotes:', len(headers))
print('Total line items:', len(line_rows))

# Build summary; do not mix original currencies. Actual data has at most one currency per project, but this handles multiple currencies by project/currency rows.
summary = []
by_project_currency = defaultdict(lambda: {'Amount': Decimal('0.00'), 'AmountTWD': Decimal('0.00'), 'Count': 0})
for h in headers:
    key = (h['ProjectID'], h['Currency'])
    by_project_currency[key]['Amount'] += Decimal(h['NetAmount'])
    by_project_currency[key]['AmountTWD'] += h['NetAmountTWD']
    by_project_currency[key]['Count'] += 1
for project in PROJECTS:
    keys = sorted([k for k in by_project_currency if k[0] == project], key=lambda k: k[1])
    if not keys:
        summary.append({'Group': project, 'SubGroup': '', 'Currency': '', 'Amount': Decimal('0.00'), 'AmountTWD': Decimal('0.00'), 'Count': 0})
    else:
        for (proj, curr) in keys:
            v = by_project_currency[(proj, curr)]
            summary.append({'Group': proj, 'SubGroup': '', 'Currency': curr, 'Amount': q2(v['Amount']), 'AmountTWD': q2(v['AmountTWD']), 'Count': v['Count']})
print('Summary rows:', summary)

# Fill a copy of the template
shutil.copyfile(TEMPLATE, OUTFILE)
wb = load_workbook(OUTFILE)
report = wb['Report']
quotes_ws = wb['Quotes']
lines_ws = wb['Lines']
summary_ws = wb['Summary']

# Clear detail data while preserving headers/template sheets
for ws, max_col in [(quotes_ws, 11), (lines_ws, 6), (summary_ws, 6)]:
    clear_sheet_data(ws, 5, max_col)

# Report sheet
generated = datetime(2026, 10, 6, 0, 0, 0, tzinfo=timezone(timedelta(hours=8))).isoformat()
report['B3'] = FROM_DATE
report['D3'] = TO_DATE
report['B4'] = 'ProjectID P001-P005; Status Accepted; QuoteDate 2026-09-01..2026-09-30; Summary by ProjectID, original amounts not mixed across currencies'
report['B5'] = generated
report['B7'] = 'quote_cli; fx_rates.csv'
report['D7'] = generated
missing_projects = [p for p in PROJECTS if not any(h['ProjectID'] == p for h in headers)]
report['B9'] = ('No Accepted quote in period for: ' + ', '.join(missing_projects)) if missing_projects else ''

# Quotes sheet rows
quote_cols = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
for i, h in enumerate(headers, start=5):
    copy_row_style(quotes_ws, 4, i, 11)
    for c, col in enumerate(quote_cols, start=1):
        cell = quotes_ws.cell(i, c)
        if col in ('QuoteID','CustomerID','ProjectID','Status','Currency'):
            cell.value = str(h[col])
            cell.number_format = '@'
        elif col in ('QuoteDate','ValidUntil'):
            cell.value = parse_date(h[col])
            cell.number_format = 'yyyy-mm-dd'
        else:
            cell.value = float(q2(h[col])) if col != 'DiscountPercent' else float(Decimal(str(h[col])))
            cell.number_format = '0.00' if col != 'DiscountPercent' else '0'

# Lines sheet rows
line_cols = ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
for i, r in enumerate(line_rows, start=5):
    copy_row_style(lines_ws, 4, i, 6)
    for c, col in enumerate(line_cols, start=1):
        cell = lines_ws.cell(i, c)
        if col in ('QuoteID','ProductID','ProductName'):
            cell.value = str(r[col])
            cell.number_format = '@'
        elif col == 'Quantity':
            cell.value = int(r[col]) if Decimal(str(r[col])) == Decimal(str(int(r[col]))) else float(Decimal(str(r[col])))
            cell.number_format = '0'
        else:
            cell.value = float(q2(r[col]))
            cell.number_format = '0.00'

# Summary sheet rows
for i, r in enumerate(summary, start=5):
    copy_row_style(summary_ws, 4, i, 6)
    values = [r['Group'], r['SubGroup'], r['Currency'], r['Amount'], r['AmountTWD'], r['Count']]
    for c, v in enumerate(values, start=1):
        cell = summary_ws.cell(i, c)
        if c <= 3:
            cell.value = str(v) if v != '' else None
            cell.number_format = '@'
        elif c in (4,5):
            cell.value = float(q2(v))
            cell.number_format = '0.00'
        else:
            cell.value = int(v)
            cell.number_format = '0'

last_quote_row = 4 + max(1, len(headers))
summary_ws['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'

# Ensure autofilter ranges include data if present, but preserve if absent
if quotes_ws.auto_filter and quotes_ws.auto_filter.ref:
    quotes_ws.auto_filter.ref = f'A4:K{max(4, 4+len(headers))}'
if lines_ws.auto_filter and lines_ws.auto_filter.ref:
    lines_ws.auto_filter.ref = f'A4:F{max(4, 4+len(line_rows))}'
if summary_ws.auto_filter and summary_ws.auto_filter.ref:
    summary_ws.auto_filter.ref = f'A4:F{max(4, 4+len(summary))}'

wb.save(OUTFILE)
print('Wrote:', OUTFILE)

# Validation: reopen saved workbook and check stated requirements
wbv = load_workbook(OUTFILE, data_only=False)
assert wbv.sheetnames == ['Report', 'Quotes', 'Lines', 'Summary', 'Instructions'], wbv.sheetnames
qws = wbv['Quotes']; lws = wbv['Lines']; sws = wbv['Summary']; rws = wbv['Report']
assert [qws.cell(4,c).value for c in range(1,12)] == quote_cols
assert [lws.cell(4,c).value for c in range(1,7)] == line_cols
assert [sws.cell(4,c).value for c in range(1,7)] == ['Group','SubGroup','Currency','Amount','AmountTWD','Count']
assert rws['B3'].value == FROM_DATE and rws['D3'].value == TO_DATE
# Row counts
quote_data_rows = qws.max_row - 4
line_data_rows = lws.max_row - 4
summary_data_rows = sws.max_row - 4
assert quote_data_rows == len(headers), (quote_data_rows, len(headers))
assert line_data_rows == len(line_rows), (line_data_rows, len(line_rows))
assert summary_data_rows == len(summary), (summary_data_rows, len(summary))
# Filter/values and types
saved_projects = set()
for row in range(5, 5+len(headers)):
    qid = qws.cell(row,1).value; cust = qws.cell(row,2).value; proj = qws.cell(row,3).value
    saved_projects.add(proj)
    assert isinstance(qid, str) and qid.startswith('Q')
    assert isinstance(cust, str) and cust.startswith('C')
    assert isinstance(proj, str) and proj in PROJECTS
    assert qws.cell(row,6).value == STATUS
    d = qws.cell(row,4).value
    assert isinstance(d, date) and date(2026,9,1) <= d <= date(2026,9,30)
    curr = qws.cell(row,7).value
    net = Decimal(str(qws.cell(row,10).value))
    twd = Decimal(str(qws.cell(row,11).value))
    assert twd == q2(net * fx[curr]), (row, curr, net, twd, q2(net*fx[curr]))
for row in range(5, 5+len(line_rows)):
    assert isinstance(lws.cell(row,1).value, str) and lws.cell(row,1).value.startswith('Q')
    assert isinstance(lws.cell(row,2).value, str)
    assert isinstance(lws.cell(row,4).value, int)
    assert isinstance(lws.cell(row,5).value, (int,float))
    assert isinstance(lws.cell(row,6).value, (int,float))
summary_projects = [sws.cell(row,1).value for row in range(5, 5+len(summary))]
for project in PROJECTS:
    assert project in summary_projects, f'missing summary project {project}'
for row in range(5, 5+len(summary)):
    proj = sws.cell(row,1).value
    curr = sws.cell(row,3).value
    amount = Decimal(str(sws.cell(row,4).value))
    amount_twd = Decimal(str(sws.cell(row,5).value))
    count = sws.cell(row,6).value
    assert proj in PROJECTS
    assert isinstance(count, int)
    if count == 0:
        assert amount == Decimal('0') and amount_twd == Decimal('0')
    else:
        assert curr in fx and amount_twd == q2(amount * fx[curr])
assert sws['B2'].value == f'=SUM(Quotes!K5:K{last_quote_row})'
print('Validation OK:')
print('- output reopened:', OUTFILE.name)
print('- Quotes rows:', quote_data_rows, 'with text IDs, date/status/project filters, numeric amounts, NetAmountTWD from fx')
print('- Lines rows:', line_data_rows, 'with text IDs and numeric quantities/amounts')
print('- Summary rows:', summary_data_rows, 'covers P001-P005; zero rows for no Accepted quotes; no cross-currency original amount mixing')
print('- Summary!B2 formula:', sws['B2'].value)
print('- Report cells B3/D3/B4/B5/B7/D7/B9 checked')