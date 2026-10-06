from pathlib import Path
import csv, json, subprocess, sys, shutil
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
TEMPLATE = INPUT / 'quote_template.xlsx'
FX_FILE = INPUT / 'fx_rates.csv'
OUTFILE = OUTPUT / 'quote_report_P001_P005_2026-09_Accepted.xlsx'
CLI = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')

PROJECTS = [f'P{i:03d}' for i in range(1, 6)]
FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
STATUS = 'Accepted'
GENERATED_AT = '2026-10-06T00:00:00+08:00'
Q = Decimal('0.01')

def money(x):
    return Decimal(str(x)).quantize(Q, rounding=ROUND_HALF_UP)

# Read FX rates; csv note field has commas, so keep first two columns.
fx = {}
with open(FX_FILE, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row or not row[0].strip():
            continue
        fx[row[0].strip()] = Decimal(row[1].strip())
print('FX rates loaded:', fx)

# Fetch accepted September quotes for P001-P005 and detail lines.
headers = []
lines = []
fetch_log = []
for project in PROJECTS:
    cmd = [sys.executable, str(CLI), 'quotes', 'list', '--project', project, '--from', FROM_DATE, '--to', TO_DATE, '--status', STATUS, '--format', 'json']
    res = subprocess.run(cmd, text=True, capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f'quote_cli list failed for {project}: rc={res.returncode} stderr={res.stderr}')
    data = json.loads(res.stdout)
    fetch_log.append((project, data.get('count', len(data.get('items', [])))))
    for item in data.get('items', []):
        qid = item['QuoteID']
        gres = subprocess.run([sys.executable, str(CLI), 'quotes', 'get', qid, '--format', 'json'], text=True, capture_output=True)
        if gres.returncode != 0:
            raise RuntimeError(f'quote_cli get failed for {qid}: rc={gres.returncode} stderr={gres.stderr}')
        detail = json.loads(gres.stdout)
        h = detail['header']
        cur = h['Currency']
        if cur not in fx:
            raise RuntimeError(f'Missing FX rate for currency {cur}')
        net = money(h['NetAmount'])
        h['_NetAmountTWD'] = money(net * fx[cur])
        headers.append(h)
        for li in detail.get('line_items', []):
            row = {'QuoteID': qid, **li}
            lines.append(row)

headers.sort(key=lambda h: (h['ProjectID'], h['QuoteID']))
lines.sort(key=lambda r: (r['QuoteID'], r['ProductID']))
print('Fetched counts by project:', fetch_log)
print('Fetched quote IDs:', [h['QuoteID'] for h in headers])

# Helper to clear sheet data rows while preserving row 4 headers and sheet structure.
def clear_data(ws, min_row=5):
    if ws.max_row >= min_row:
        ws.delete_rows(min_row, ws.max_row - min_row + 1)

def copy_row_style(ws, source_row, target_row, max_col):
    for c in range(1, max_col + 1):
        s = ws.cell(source_row, c)
        t = ws.cell(target_row, c)
        if s.has_style:
            t._style = s._style.copy()
        if s.number_format:
            t.number_format = s.number_format
        if s.alignment:
            t.alignment = s.alignment.copy()

wb = load_workbook(TEMPLATE)
report = wb['Report']
quotes_ws = wb['Quotes']
lines_ws = wb['Lines']
summary_ws = wb['Summary']

# Clear existing data rows
for sheet in (quotes_ws, lines_ws, summary_ws):
    clear_data(sheet, 5)

# Fill report metadata
report['B3'] = FROM_DATE
report['D3'] = TO_DATE
report['B4'] = 'ProjectID P001-P005; Status Accepted; QuoteDate 2026-09-01 through 2026-09-30; FX from input/fx_rates.csv'
report['B5'] = GENERATED_AT
report['B7'] = 'quote_cli_mock; input/fx_rates.csv'
report['D7'] = GENERATED_AT
zero_projects = [p for p, c in fetch_log if c == 0]
report['B9'] = 'Projects with no Accepted quote kept as zero rows in Summary: ' + ', '.join(zero_projects) if zero_projects else 'None'

# Fill Quotes
quote_cols = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
for idx, h in enumerate(headers, start=5):
    row_values = [
        h['QuoteID'], h['CustomerID'], h['ProjectID'], h['QuoteDate'], h['ValidUntil'], h['Status'], h['Currency'],
        float(money(h['Subtotal'])), float(Decimal(str(h['DiscountPercent']))), float(money(h['NetAmount'])), float(h['_NetAmountTWD'])
    ]
    for col, value in enumerate(row_values, start=1):
        cell = quotes_ws.cell(idx, col, value)
        if col in (1,2,3,4,5,6,7):
            cell.number_format = '@'
        elif col in (8,10,11):
            cell.number_format = '0.00'
        elif col == 9:
            cell.number_format = '0'

# Fill Lines
for idx, li in enumerate(lines, start=5):
    row_values = [li['QuoteID'], li['ProductID'], li['ProductName'], int(li['Quantity']), float(money(li['UnitPrice'])), float(money(li['LineAmount']))]
    for col, value in enumerate(row_values, start=1):
        cell = lines_ws.cell(idx, col, value)
        if col in (1,2,3):
            cell.number_format = '@'
        elif col in (5,6):
            cell.number_format = '0.00'
        elif col == 4:
            cell.number_format = '0'

# Build Summary by ProjectID. Do not mix original currencies: if multiple currencies occur in a project,
# make separate project/currency rows. Projects with no quotes get one zero row.
summary_rows = []
for project in PROJECTS:
    hs = [h for h in headers if h['ProjectID'] == project]
    if not hs:
        summary_rows.append((project, '', '', Decimal('0.00'), Decimal('0.00'), 0))
    else:
        bycur = {}
        for h in hs:
            cur = h['Currency']
            bycur.setdefault(cur, {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0})
            bycur[cur]['amount'] += money(h['NetAmount'])
            bycur[cur]['twd'] += money(h['_NetAmountTWD'])
            bycur[cur]['count'] += 1
        for cur in sorted(bycur):
            d = bycur[cur]
            summary_rows.append((project, '', cur, money(d['amount']), money(d['twd']), d['count']))

for idx, row in enumerate(summary_rows, start=5):
    for col, value in enumerate(row, start=1):
        cell = summary_ws.cell(idx, col, value if not isinstance(value, Decimal) else float(value))
        if col in (1,2,3):
            cell.number_format = '@'
        elif col in (4,5):
            cell.number_format = '0.00'
        elif col == 6:
            cell.number_format = '0'

last_quote_row = max(5, 4 + len(headers))
summary_ws['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'
summary_ws['B2'].number_format = '0.00'

# Save workbook
wb.save(OUTFILE)
print('Saved:', OUTFILE)

# Reopen and verify all stated requirements from saved output.
wb2 = load_workbook(OUTFILE, data_only=False)
qws = wb2['Quotes']; lws = wb2['Lines']; sws = wb2['Summary']; rws = wb2['Report']
# Headers unchanged
assert [qws.cell(4,c).value for c in range(1,12)] == quote_cols
assert [lws.cell(4,c).value for c in range(1,7)] == ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
assert [sws.cell(4,c).value for c in range(1,7)] == ['Group','SubGroup','Currency','Amount','AmountTWD','Count']
# Quote row checks
quote_rows = list(qws.iter_rows(min_row=5, max_row=qws.max_row, values_only=True)) if qws.max_row >= 5 else []
line_rows = list(lws.iter_rows(min_row=5, max_row=lws.max_row, values_only=True)) if lws.max_row >= 5 else []
summary_saved = list(sws.iter_rows(min_row=5, max_row=sws.max_row, values_only=True)) if sws.max_row >= 5 else []
assert len(quote_rows) == 3, len(quote_rows)
assert len(line_rows) == 5, len(line_rows)
assert len(summary_saved) == 5, len(summary_saved)
expected_qids = {'Q0011','Q0013','Q0015'}
assert {r[0] for r in quote_rows} == expected_qids
for r in quote_rows:
    assert r[2] in PROJECTS
    assert FROM_DATE <= r[3] <= TO_DATE
    assert r[5] == STATUS
    cur = r[6]
    expected_twd = money(Decimal(str(r[9])) * fx[cur])
    assert money(r[10]) == expected_twd, (r[0], r[10], expected_twd)
    assert isinstance(r[0], str) and isinstance(r[1], str) and isinstance(r[2], str)
    assert isinstance(r[7], (int, float)) and isinstance(r[9], (int, float)) and isinstance(r[10], (int, float))
# Summary checks: all P001-P005 present, P003/P005 zero, total equals quote K.
summary_by_project = {r[0]: r for r in summary_saved}
assert list(summary_by_project) == PROJECTS, list(summary_by_project)
assert summary_by_project['P003'][3] == 0 and summary_by_project['P003'][4] == 0 and summary_by_project['P003'][5] == 0
assert summary_by_project['P005'][3] == 0 and summary_by_project['P005'][4] == 0 and summary_by_project['P005'][5] == 0
assert sws['B2'].value == '=SUM(Quotes!K5:K7)', sws['B2'].value
quote_twd_total = sum(money(r[10]) for r in quote_rows)
summary_twd_total = sum(money(r[4]) for r in summary_saved)
assert quote_twd_total == summary_twd_total == Decimal('670759.85'), (quote_twd_total, summary_twd_total)
# Check original amounts by project not direct mixed-currency total: row currency matches quote currency when nonzero.
assert summary_by_project['P001'][2] == 'USD' and money(summary_by_project['P001'][3]) == Decimal('10350.00') and money(summary_by_project['P001'][4]) == Decimal('331200.00')
assert summary_by_project['P002'][2] == 'EUR' and money(summary_by_project['P002'][3]) == Decimal('2784.31') and money(summary_by_project['P002'][4]) == Decimal('97450.85')
assert summary_by_project['P004'][2] == 'TWD' and money(summary_by_project['P004'][3]) == Decimal('282150.00') and money(summary_by_project['P004'][4]) == Decimal('282150.00')
assert rws['B3'].value == FROM_DATE and rws['D3'].value == TO_DATE
print('Verification passed:')
print('- output workbook exists and was reopened')
print('- Quotes headers preserved; 3 Accepted quote rows (Q0011/Q0013/Q0015), text IDs, numeric money, NetAmountTWD by fx_rates')
print('- Lines headers preserved; 5 line item rows')
print('- Summary headers preserved; P001-P005 rows present; P003/P005 zero rows; no original-currency mixed total')
print('- Summary B2 formula extended to =SUM(Quotes!K5:K7); TWD total 670759.85')
print('- Report metadata filled')