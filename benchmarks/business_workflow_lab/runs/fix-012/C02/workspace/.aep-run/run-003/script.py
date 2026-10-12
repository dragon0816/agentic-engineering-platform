from pathlib import Path
import subprocess, sys, json, csv, shutil, os
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime, date
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(parents=True, exist_ok=True)
TEMPLATE = INPUT / 'quote_template.xlsx'
FX = INPUT / 'fx_rates.csv'
REPORT = OUTPUT / 'quote_report_2026-09.xlsx'
FINDINGS = OUTPUT / 'findings.md'
FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
BASE_DATE = date.fromisoformat('2026-09-30')
GENERATED_AT = '2026-10-06T00:00:00+08:00'
CLI = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd')
PY_CLI = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')

TWOPLACES = Decimal('0.01')
def D(v):
    if v is None or v == '':
        return Decimal('0')
    return Decimal(str(v))

def money(v):
    return D(v).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def run_cli(args):
    if CLI.exists():
        cmd = [str(CLI)] + args
    else:
        cmd = [sys.executable, str(PY_CLI)] + args
    cp = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True)
    if cp.returncode != 0:
        raise RuntimeError(f'CLI failed code={cp.returncode}\nCMD={cmd}\nSTDERR={cp.stderr}\nSTDOUT={cp.stdout}')
    return cp.stdout

# Load FX rates. Notes may contain unquoted commas in this test file; only first two columns are relevant.
fx_rates = {}
with FX.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2 and row[0].strip():
            fx_rates[row[0].strip()] = D(row[1].strip())
print('Loaded FX rates:', fx_rates)

# Fetch all September 2026 quote headers by quote date, inclusive.
list_json = run_cli(['quotes', 'list', '--from', FROM_DATE, '--to', TO_DATE, '--format', 'json'])
listed = json.loads(list_json)
quotes_headers = listed.get('items', [])
print(f"Fetched {len(quotes_headers)} quote headers for {FROM_DATE}..{TO_DATE}")

quotes = []
all_lines = []
for h in quotes_headers:
    qid = h['QuoteID']
    detail = json.loads(run_cli(['quotes', 'get', qid, '--format', 'json']))
    header = detail['header']
    lines = detail.get('line_items', [])
    quotes.append(header)
    for line in lines:
        rec = dict(line)
        rec['QuoteID'] = qid
        all_lines.append(rec)
print(f"Fetched details for {len(quotes)} quotes and {len(all_lines)} line items")

# Validations/findings.
line_findings = []
net_findings = []
expired_unaccepted = []
quote_lines = defaultdict(list)
for line in all_lines:
    quote_lines[line['QuoteID']].append(line)
    expected_line = money(D(line.get('Quantity')) * D(line.get('UnitPrice')))
    actual_line = money(line.get('LineAmount'))
    if actual_line != expected_line:
        line_findings.append({
            'QuoteID': line['QuoteID'],
            'ProductID': line.get('ProductID', ''),
            'Quantity': str(line.get('Quantity', '')),
            'UnitPrice': str(line.get('UnitPrice', '')),
            'LineAmount': str(actual_line),
            'ExpectedLineAmount': str(expected_line),
            'Diff': str(actual_line - expected_line),
        })

for q in quotes:
    qid = q['QuoteID']
    sum_lines = money(sum((money(l.get('LineAmount')) for l in quote_lines.get(qid, [])), Decimal('0')))
    subtotal = money(q.get('Subtotal'))
    if subtotal != sum_lines:
        line_findings.append({
            'QuoteID': qid,
            'ProductID': '(subtotal)',
            'Quantity': '',
            'UnitPrice': '',
            'LineAmount': str(subtotal),
            'ExpectedLineAmount': str(sum_lines),
            'Diff': str(subtotal - sum_lines),
        })
    expected_net = money(subtotal * (Decimal('1') - (D(q.get('DiscountPercent')) / Decimal('100'))))
    actual_net = money(q.get('NetAmount'))
    if actual_net != expected_net:
        net_findings.append({
            'QuoteID': qid,
            'Subtotal': str(subtotal),
            'DiscountPercent': str(q.get('DiscountPercent', '')),
            'NetAmount': str(actual_net),
            'ExpectedNetAmount': str(expected_net),
            'Diff': str(actual_net - expected_net),
        })
    valid_until = date.fromisoformat(q['ValidUntil'])
    if valid_until < BASE_DATE and q.get('Status') != 'Accepted':
        expired_unaccepted.append({
            'QuoteID': qid,
            'CustomerID': q.get('CustomerID',''),
            'ProjectID': q.get('ProjectID',''),
            'QuoteDate': q.get('QuoteDate',''),
            'ValidUntil': q.get('ValidUntil',''),
            'Status': q.get('Status',''),
            'Currency': q.get('Currency',''),
            'NetAmount': str(money(q.get('NetAmount'))),
        })

# Fill workbook copy.
shutil.copyfile(TEMPLATE, REPORT)
wb = load_workbook(REPORT)
rep = wb['Report']
rep['B3'] = FROM_DATE
rep['D3'] = TO_DATE
rep['B4'] = '2026 年 9 月全部報價；檢查明細合計、折扣後 NetAmount；ValidUntil < 2026-09-30 且尚未 Accepted 者列入 findings；保留全部報價。'
rep['B5'] = GENERATED_AT
rep['B7'] = 'quote_cli_mock; fx_rates.csv'
rep['D7'] = GENERATED_AT
notes = []
notes.append(f'取得 {len(quotes)} 份報價、{len(all_lines)} 筆明細；未因到期刪除任何報價。')
notes.append(f'明細/小計異常 {len(line_findings)} 筆；NetAmount 異常 {len(net_findings)} 筆；基準日 {BASE_DATE.isoformat()} 已逾期且未 Accepted {len(expired_unaccepted)} 份。')
rep['B9'] = ' '.join(notes)

qsheet = wb['Quotes']
lsheet = wb['Lines']
ssheet = wb['Summary']

# Helper clear existing data rows from row 5 onward while preserving sheet and row 4 headers.
def clear_data(ws):
    if ws.max_row >= 5:
        ws.delete_rows(5, ws.max_row - 4)

clear_data(qsheet)
clear_data(lsheet)
clear_data(ssheet)

quote_cols = [qsheet.cell(row=4, column=c).value for c in range(1, qsheet.max_column+1)]
line_cols = [lsheet.cell(row=4, column=c).value for c in range(1, lsheet.max_column+1)]

# Populate Quotes
for r, q in enumerate(quotes, start=5):
    cur = q.get('Currency')
    rate = fx_rates.get(cur)
    net = money(q.get('NetAmount'))
    values = {
        'QuoteID': str(q.get('QuoteID','')),
        'CustomerID': str(q.get('CustomerID','')),
        'ProjectID': str(q.get('ProjectID','')),
        'QuoteDate': q.get('QuoteDate'),
        'ValidUntil': q.get('ValidUntil'),
        'Status': q.get('Status'),
        'Currency': cur,
        'Subtotal': float(money(q.get('Subtotal'))),
        'DiscountPercent': float(D(q.get('DiscountPercent'))),
        'NetAmount': float(net),
        'NetAmountTWD': float(money(net * rate)) if rate is not None else None,
    }
    for c, col in enumerate(quote_cols, start=1):
        qsheet.cell(row=r, column=c, value=values.get(col))
    for c in [1,2,3,6,7]:
        qsheet.cell(row=r, column=c).number_format = '@'
    for c in [4,5]:
        qsheet.cell(row=r, column=c).number_format = 'yyyy-mm-dd'
    for c in [8,10,11]:
        qsheet.cell(row=r, column=c).number_format = '0.00'
    qsheet.cell(row=r, column=9).number_format = '0.00'

# Populate Lines
for r, line in enumerate(all_lines, start=5):
    values = {
        'QuoteID': str(line.get('QuoteID','')),
        'ProductID': str(line.get('ProductID','')),
        'ProductName': line.get('ProductName'),
        'Quantity': float(D(line.get('Quantity'))),
        'UnitPrice': float(money(line.get('UnitPrice'))),
        'LineAmount': float(money(line.get('LineAmount'))),
    }
    for c, col in enumerate(line_cols, start=1):
        lsheet.cell(row=r, column=c, value=values.get(col))
    for c in [1,2,3]:
        lsheet.cell(row=r, column=c).number_format = '@'
    lsheet.cell(row=r, column=4).number_format = '0.00'
    for c in [5,6]:
        lsheet.cell(row=r, column=c).number_format = '0.00'

# Summary: group by Status then Currency; plus expired-unaccepted indicator group.
summary_rows = []
by_status_currency = defaultdict(lambda: {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
for q in quotes:
    cur = q.get('Currency')
    net = money(q.get('NetAmount'))
    rate = fx_rates.get(cur, Decimal('0'))
    key = (q.get('Status',''), cur)
    by_status_currency[key]['amount'] += net
    by_status_currency[key]['twd'] += money(net * rate)
    by_status_currency[key]['count'] += 1
for (status, cur), agg in sorted(by_status_currency.items()):
    summary_rows.append(['Status', status, cur, float(money(agg['amount'])), float(money(agg['twd'])), agg['count']])

# Add a count-only row for expired-unaccepted; Amount is sum by TWD across converted net amounts.
expired_twd = Decimal('0')
for e in expired_unaccepted:
    cur = e['Currency']
    expired_twd += money(D(e['NetAmount']) * fx_rates.get(cur, Decimal('0')))
summary_rows.append(['Finding', f'ValidUntil < {BASE_DATE.isoformat()} and Status <> Accepted', 'TWD', None, float(money(expired_twd)), len(expired_unaccepted)])

for r, row in enumerate(summary_rows, start=5):
    for c, val in enumerate(row, start=1):
        ssheet.cell(row=r, column=c, value=val)
    ssheet.cell(row=r, column=1).number_format = '@'
    ssheet.cell(row=r, column=2).number_format = '@'
    ssheet.cell(row=r, column=3).number_format = '@'
    ssheet.cell(row=r, column=4).number_format = '0.00'
    ssheet.cell(row=r, column=5).number_format = '0.00'
    ssheet.cell(row=r, column=6).number_format = '0'

last_quote_row = 4 + len(quotes) if quotes else 5
ssheet['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'

# Auto filters can extend to new data rows without changing widths/layout.
qsheet.auto_filter.ref = f'A4:K{max(4+len(quotes),4)}'
lsheet.auto_filter.ref = f'A4:F{max(4+len(all_lines),4)}'
ssheet.auto_filter.ref = f'A4:F{max(4+len(summary_rows),4)}'

wb.save(REPORT)

# findings.md
lines = []
lines.append('# Findings - 2026 年 9 月報價檢查')
lines.append('')
lines.append(f'- 查詢期間：{FROM_DATE} 至 {TO_DATE}（含起訖日）')
lines.append(f'- 逾期判定基準日：{BASE_DATE.isoformat()}')
lines.append(f'- 資料來源：quote_cli_mock；匯率：input/fx_rates.csv')
lines.append(f'- 取得報價：{len(quotes)} 份；明細：{len(all_lines)} 筆')
lines.append('- 處理原則：保留全部報價，不因到期而刪除。')
lines.append('')

def md_table(headers, rows):
    out = []
    out.append('| ' + ' | '.join(headers) + ' |')
    out.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
    for row in rows:
        out.append('| ' + ' | '.join(str(row.get(h, '')) for h in headers) + ' |')
    return out

lines.append('## 明細合計檢查')
if line_findings:
    lines.append(f'發現 {len(line_findings)} 筆明細金額或 Subtotal 不一致：')
    lines.extend(md_table(['QuoteID','ProductID','Quantity','UnitPrice','LineAmount','ExpectedLineAmount','Diff'], line_findings))
else:
    lines.append('未發現 LineAmount = Quantity × UnitPrice 或 Subtotal = 明細 LineAmount 合計的不一致。')
lines.append('')

lines.append('## 折扣後 NetAmount 檢查')
if net_findings:
    lines.append(f'發現 {len(net_findings)} 筆 NetAmount 不一致：')
    lines.extend(md_table(['QuoteID','Subtotal','DiscountPercent','NetAmount','ExpectedNetAmount','Diff'], net_findings))
else:
    lines.append('未發現 NetAmount = Subtotal × (1 − DiscountPercent / 100)（ROUND_HALF_UP 至兩位小數）的不一致。')
lines.append('')

lines.append('## ValidUntil 小於 2026-09-30 且尚未 Accepted 的報價')
if expired_unaccepted:
    lines.append(f'共 {len(expired_unaccepted)} 份：')
    lines.extend(md_table(['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','NetAmount'], expired_unaccepted))
else:
    lines.append('未發現符合條件的報價。')
lines.append('')

FINDINGS.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('Wrote:', REPORT)
print('Wrote:', FINDINGS)
print('Line/subtotal findings:', len(line_findings))
print('Net findings:', len(net_findings))
print('Expired unaccepted:', len(expired_unaccepted))

# Verification: reopen outputs and confirm requirements.
check_wb = load_workbook(REPORT, data_only=False)
assert set(['Report','Quotes','Lines','Summary','Instructions']).issubset(set(check_wb.sheetnames)), check_wb.sheetnames
cq = check_wb['Quotes']
cl = check_wb['Lines']
cs = check_wb['Summary']
actual_quote_headers = [cq.cell(row=4, column=c).value for c in range(1, 12)]
assert actual_quote_headers == ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD'], actual_quote_headers
actual_line_headers = [cl.cell(row=4, column=c).value for c in range(1, 7)]
assert actual_line_headers == ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount'], actual_line_headers
quote_rows = [r for r in range(5, cq.max_row+1) if cq.cell(row=r, column=1).value not in (None, '')]
line_rows = [r for r in range(5, cl.max_row+1) if cl.cell(row=r, column=1).value not in (None, '')]
assert len(quote_rows) == len(quotes), (len(quote_rows), len(quotes))
assert len(line_rows) == len(all_lines), (len(line_rows), len(all_lines))
assert cs['B2'].value == f'=SUM(Quotes!K5:K{last_quote_row})', cs['B2'].value
# IDs as text-ish strings; numeric money fields as numbers or blanks where appropriate.
for r in quote_rows:
    for c in [1,2,3]:
        assert isinstance(cq.cell(row=r, column=c).value, str), (r,c,cq.cell(row=r,column=c).value)
    for c in [8,9,10,11]:
        assert isinstance(cq.cell(row=r, column=c).value, (int, float)), (r,c,cq.cell(row=r,column=c).value,type(cq.cell(row=r,column=c).value))
for r in line_rows:
    for c in [1,2]:
        assert isinstance(cl.cell(row=r, column=c).value, str), (r,c,cl.cell(row=r,column=c).value)
    for c in [4,5,6]:
        assert isinstance(cl.cell(row=r, column=c).value, (int, float)), (r,c,cl.cell(row=r,column=c).value,type(cl.cell(row=r,column=c).value))
find_text = FINDINGS.read_text(encoding='utf-8')
assert 'ValidUntil 小於 2026-09-30 且尚未 Accepted' in find_text
assert '保留全部報價' in find_text
print('CHECK OK: workbook reopened; sheet names and headers retained; quote row count', len(quote_rows), 'line row count', len(line_rows), 'numeric/text types checked; Summary B2 range checked; findings.md reopened and required sections checked.')
print('Output files:', [p.name for p in sorted(OUTPUT.glob('*'))])
