from pathlib import Path
import subprocess, json, csv, shutil, os, sys
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from copy import copy
from openpyxl import load_workbook

WORKSPACE = Path('.').resolve()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
TEMPLATE = INPUT / 'quote_template.xlsx'
OUT_XLSX = OUTPUT / 'quote_template.xlsx'
OUT_MD = OUTPUT / 'findings.md'
CLI = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
FROM = '2026-09-01'
TO = '2026-09-30'
BASE_DATE = date.fromisoformat('2026-09-30')
GENERATED_AT = '2026-10-06T00:00:00+08:00'
FETCHED_AT = GENERATED_AT
TWOPLACES = Decimal('0.01')

def money(x):
    return Decimal(str(x)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def dec(x):
    return Decimal(str(x))

def run_cli(args):
    r = subprocess.run([CLI] + args, capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise RuntimeError(f'CLI failed {args}: exit {r.returncode}\nSTDERR:{r.stderr}\nSTDOUT:{r.stdout}')
    return json.loads(r.stdout)

def parse_fx(path):
    rates = {}
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row or not row[0]:
                continue
            rates[row[0]] = Decimal(row[1])
    return rates

def set_row_values(ws, row_idx, values, formats=None):
    for col_idx, value in enumerate(values, start=1):
        c = ws.cell(row_idx, col_idx)
        c.value = value
        if formats and col_idx in formats:
            c.number_format = formats[col_idx]

def clear_data(ws, start_row=5):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

def extend_sheet_columns(ws, row_idx, max_col):
    # Copy formatting from previous row when present, otherwise from row 5 template/current row.
    src_row = row_idx - 1 if row_idx > 5 else 4
    for col in range(1, max_col + 1):
        src = ws.cell(src_row, col)
        dst = ws.cell(row_idx, col)
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

# Fetch September quote headers and line details
rates = parse_fx(INPUT / 'fx_rates.csv')
list_data = run_cli(['quotes', 'list', '--from', FROM, '--to', TO, '--format', 'json'])
headers = list_data['items']
headers.sort(key=lambda h: (h['QuoteDate'], h['QuoteID']))
all_docs = []
for h in headers:
    doc = run_cli(['quotes', 'get', h['QuoteID'], '--format', 'json'])
    all_docs.append(doc)

# Validate and prepare findings
quote_findings = []
line_findings = []
overdue_unaccepted = []
for doc in all_docs:
    h = doc['header']
    qid = h['QuoteID']
    currency = h['Currency']
    line_sum = sum((money(item['LineAmount']) for item in doc['line_items']), Decimal('0.00')).quantize(TWOPLACES)
    header_subtotal = money(h['Subtotal'])
    if line_sum != header_subtotal:
        quote_findings.append({
            'QuoteID': qid,
            'Type': 'Subtotal mismatch',
            'Expected': str(line_sum),
            'Actual': str(header_subtotal),
            'Difference': str((header_subtotal - line_sum).quantize(TWOPLACES)),
        })
    expected_net = money(header_subtotal * (Decimal('1') - dec(h['DiscountPercent']) / Decimal('100')))
    actual_net = money(h['NetAmount'])
    if expected_net != actual_net:
        quote_findings.append({
            'QuoteID': qid,
            'Type': 'NetAmount mismatch',
            'Expected': str(expected_net),
            'Actual': str(actual_net),
            'Difference': str((actual_net - expected_net).quantize(TWOPLACES)),
        })
    for idx, item in enumerate(doc['line_items'], start=1):
        expected_line = money(dec(item['Quantity']) * dec(item['UnitPrice']))
        actual_line = money(item['LineAmount'])
        if expected_line != actual_line:
            line_findings.append({
                'QuoteID': qid,
                'Line': idx,
                'ProductID': item['ProductID'],
                'Expected': str(expected_line),
                'Actual': str(actual_line),
                'Difference': str((actual_line - expected_line).quantize(TWOPLACES)),
            })
    valid_until = date.fromisoformat(h['ValidUntil'])
    if valid_until < BASE_DATE and h['Status'] != 'Accepted':
        overdue_unaccepted.append(h)

# Fill workbook
shutil.copyfile(TEMPLATE, OUT_XLSX)
wb = load_workbook(OUT_XLSX)
report = wb['Report']
quotes_ws = wb['Quotes']
lines_ws = wb['Lines']
summary_ws = wb['Summary']

# Report cells
report['B3'] = FROM
report['D3'] = TO
report['B4'] = 'QuoteDate 介於 2026-09-01 至 2026-09-30（含起訖）；保留全部報價，不因 ValidUntil 到期刪除。'
report['B5'] = GENERATED_AT
report['B7'] = 'quote_cli; fx_rates.csv'
report['D7'] = FETCHED_AT
report['B9'] = f'以 {BASE_DATE.isoformat()} 為基準檢查 ValidUntil < 基準日且 Status != Accepted；詳細檢核見 findings.md。'

# Clear and write Quotes
clear_data(quotes_ws, 5)
quote_rows = []
for doc in all_docs:
    h = doc['header']
    net = money(h['NetAmount'])
    rate = rates[h['Currency']]
    quote_rows.append([
        h['QuoteID'], h['CustomerID'], h.get('ProjectID',''), h['QuoteDate'], h['ValidUntil'], h['Status'], h['Currency'],
        float(money(h['Subtotal'])), float(dec(h['DiscountPercent'])), float(net), float(money(net * rate))
    ])
for i, row in enumerate(quote_rows, start=5):
    extend_sheet_columns(quotes_ws, i, 11)
    set_row_values(quotes_ws, i, row, formats={8:'0.00', 9:'0', 10:'0.00', 11:'0.00'})
    for c in (1,2,3,4,5,6,7):
        quotes_ws.cell(i,c).number_format='@'

# Clear and write Lines
clear_data(lines_ws, 5)
line_rows = []
for doc in all_docs:
    qid = doc['header']['QuoteID']
    for item in doc['line_items']:
        line_rows.append([
            qid, item['ProductID'], item['ProductName'], int(item['Quantity']),
            float(money(item['UnitPrice'])), float(money(item['LineAmount']))
        ])
for i, row in enumerate(line_rows, start=5):
    extend_sheet_columns(lines_ws, i, 6)
    set_row_values(lines_ws, i, row, formats={4:'0', 5:'0.00', 6:'0.00'})
    for c in (1,2,3):
        lines_ws.cell(i,c).number_format='@'

# Summary by Status and Currency
clear_data(summary_ws, 5)
last_quote_row = 4 + len(quote_rows) if quote_rows else 5
summary_ws['B2'] = f'=SUM(Quotes!K5:K{last_quote_row if quote_rows else 5})'
summary = {}
for doc in all_docs:
    h = doc['header']
    key = (h['Status'], h['Currency'])
    net = money(h['NetAmount'])
    twd = money(net * rates[h['Currency']])
    if key not in summary:
        summary[key] = {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0}
    summary[key]['amount'] += net
    summary[key]['twd'] += twd
    summary[key]['count'] += 1
summary_rows = []
for (status, currency), v in sorted(summary.items()):
    summary_rows.append(['Status', status, currency, float(money(v['amount'])), float(money(v['twd'])), v['count']])
for i, row in enumerate(summary_rows, start=5):
    extend_sheet_columns(summary_ws, i, 6)
    set_row_values(summary_ws, i, row, formats={4:'0.00', 5:'0.00', 6:'0'})

# Save workbook
wb.save(OUT_XLSX)

# findings.md
lines = []
lines.append('# 2026 年 9 月報價檢核 findings')
lines.append('')
lines.append(f'- 查詢期間：{FROM} 至 {TO}（含起訖日）')
lines.append(f'- 基準日：{BASE_DATE.isoformat()}')
lines.append(f'- 報價筆數：{len(all_docs)}（已全部保留於 Excel，未因到期刪除）')
lines.append(f'- 明細列數：{len(line_rows)}')
lines.append('')
lines.append('## 明細合計與 NetAmount 檢查')
if not quote_findings and not line_findings:
    lines.append('- 所有報價的明細 LineAmount 加總皆等於 Subtotal。')
    lines.append('- 所有報價的 NetAmount 皆等於 Subtotal × (1 − DiscountPercent / 100)，並以 ROUND_HALF_UP 四捨五入至兩位小數。')
    lines.append('- 所有明細列 LineAmount 皆等於 Quantity × UnitPrice，並以 ROUND_HALF_UP 四捨五入至兩位小數。')
else:
    if quote_findings:
        lines.append('### 報價表頭差異')
        lines.append('| QuoteID | Type | Expected | Actual | Difference |')
        lines.append('|---|---|---:|---:|---:|')
        for f in quote_findings:
            lines.append(f"| {f['QuoteID']} | {f['Type']} | {f['Expected']} | {f['Actual']} | {f['Difference']} |")
    if line_findings:
        lines.append('### 明細列差異')
        lines.append('| QuoteID | Line | ProductID | Expected | Actual | Difference |')
        lines.append('|---|---:|---|---:|---:|---:|')
        for f in line_findings:
            lines.append(f"| {f['QuoteID']} | {f['Line']} | {f['ProductID']} | {f['Expected']} | {f['Actual']} | {f['Difference']} |")
lines.append('')
lines.append('## ValidUntil 小於 2026-09-30 且尚未 Accepted 的報價')
if overdue_unaccepted:
    lines.append('| QuoteID | CustomerID | ProjectID | QuoteDate | ValidUntil | Status | Currency | NetAmount | NetAmountTWD |')
    lines.append('|---|---|---|---|---|---|---|---:|---:|')
    for h in sorted(overdue_unaccepted, key=lambda x: (x['ValidUntil'], x['QuoteID'])):
        net = money(h['NetAmount'])
        twd = money(net * rates[h['Currency']])
        lines.append(f"| {h['QuoteID']} | {h['CustomerID']} | {h.get('ProjectID','')} | {h['QuoteDate']} | {h['ValidUntil']} | {h['Status']} | {h['Currency']} | {net} | {twd} |")
else:
    lines.append('- 無。')
lines.append('')
lines.append('## 匯率')
lines.append('| Currency | RateToTWD |')
lines.append('|---|---:|')
for cur in sorted(rates):
    lines.append(f'| {cur} | {rates[cur]} |')
OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')

# Reopen and verify outputs from saved files
print('Wrote:', OUT_XLSX)
print('Wrote:', OUT_MD)
wb2 = load_workbook(OUT_XLSX, data_only=False)
qws = wb2['Quotes']; lws = wb2['Lines']; sws = wb2['Summary']; rws = wb2['Report']
# headers unchanged
expected_q_headers = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
actual_q_headers = [qws.cell(4,c).value for c in range(1,12)]
expected_l_headers = ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
actual_l_headers = [lws.cell(4,c).value for c in range(1,7)]
assert actual_q_headers == expected_q_headers, actual_q_headers
assert actual_l_headers == expected_l_headers, actual_l_headers
# row counts by scanning QuoteID present
saved_quote_ids = [qws.cell(r,1).value for r in range(5, qws.max_row+1) if qws.cell(r,1).value]
saved_line_qids = [lws.cell(r,1).value for r in range(5, lws.max_row+1) if lws.cell(r,1).value]
assert len(saved_quote_ids) == len(all_docs), (len(saved_quote_ids), len(all_docs))
assert saved_quote_ids == [doc['header']['QuoteID'] for doc in all_docs]
assert len(saved_line_qids) == len(line_rows), (len(saved_line_qids), len(line_rows))
# dates and text IDs; numeric money columns
for r in range(5, 5+len(saved_quote_ids)):
    assert isinstance(qws.cell(r,1).value, str)
    assert isinstance(qws.cell(r,2).value, str)
    assert isinstance(qws.cell(r,4).value, str) and len(qws.cell(r,4).value)==10
    assert isinstance(qws.cell(r,8).value, (int,float))
    assert isinstance(qws.cell(r,10).value, (int,float))
    assert isinstance(qws.cell(r,11).value, (int,float))
for r in range(5, 5+len(saved_line_qids)):
    assert isinstance(lws.cell(r,1).value, str)
    assert isinstance(lws.cell(r,2).value, str)
    assert isinstance(lws.cell(r,4).value, int)
    assert isinstance(lws.cell(r,5).value, (int,float))
    assert isinstance(lws.cell(r,6).value, (int,float))
assert sws['B2'].value == f'=SUM(Quotes!K5:K{4+len(all_docs)})'
md = OUT_MD.read_text(encoding='utf-8')
for qid in [h['QuoteID'] for h in overdue_unaccepted]:
    assert qid in md
assert '已全部保留' in md
print('Verification passed:')
print('- Quotes headers:', actual_q_headers)
print('- Lines headers:', actual_l_headers)
print('- Quote rows:', len(saved_quote_ids), 'Line rows:', len(saved_line_qids), 'Summary rows:', len(summary_rows))
print('- Summary B2 formula:', sws['B2'].value)
print('- Findings quote mismatches:', len(quote_findings), 'line mismatches:', len(line_findings), 'overdue unaccepted:', len(overdue_unaccepted))
print('- Overdue unaccepted QuoteIDs:', ', '.join(h['QuoteID'] for h in sorted(overdue_unaccepted, key=lambda x:(x['ValidUntil'], x['QuoteID']))))
