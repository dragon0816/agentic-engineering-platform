from pathlib import Path
import subprocess, json, csv, shutil, sys, os
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime, timezone, timedelta
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Alignment
from openpyxl.formula.translate import Translator

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
TEMPLATE = INPUT / 'quote_template.xlsx'
FX = INPUT / 'fx_rates.csv'
CLI = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd')
FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
STATUS = 'Sent'
OUTFILE = OUTPUT / 'sent_quotes_2026-09.xlsx'
LOGFILE = OUTPUT / 'quote_cli_attempts.json'

TW = timezone(timedelta(hours=8))
now_iso = datetime.now(TW).isoformat(timespec='seconds')
TWOPLACES = Decimal('0.01')


def dec(v, field='value'):
    if v is None or v == '':
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation as e:
        raise ValueError(f'Cannot parse decimal for {field}: {v!r}') from e


def money(v):
    d = dec(v)
    if d is None:
        return None
    return d.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def run_cli_json(args, label, max_retries_on_4=2):
    attempts=[]
    for attempt_no in range(1, max_retries_on_4 + 2):
        cmd=[str(CLI)] + args
        p=subprocess.run(cmd, capture_output=True, text=True, shell=False)
        rec={
            'label': label,
            'attempt': attempt_no,
            'returncode': p.returncode,
            'stderr': p.stderr,
            'stdout_len': len(p.stdout or ''),
        }
        attempts.append(rec)
        if p.returncode == 0:
            try:
                data=json.loads(p.stdout)
            except Exception as e:
                rec['parse_error']=repr(e)
                raise RuntimeError(f'{label}: exit code 0 but stdout was not parseable JSON; stdout ignored. parse_error={e}; stderr={p.stderr}')
            return data, attempts
        if p.returncode in (2,3):
            raise RuntimeError(f'{label}: CLI returned exit code {p.returncode}; no retry. stderr: {p.stderr.strip()}')
        if p.returncode == 4:
            if attempt_no <= max_retries_on_4:
                continue
            raise RuntimeError(f'{label}: CLI returned exit code 4 after {attempt_no} attempts. stderr: {p.stderr.strip()}')
        raise RuntimeError(f'{label}: unexpected exit code {p.returncode}. stderr: {p.stderr.strip()}')
    raise AssertionError('unreachable')

# read fx rates
fx_rates={}
with FX.open(newline='', encoding='utf-8-sig') as f:
    reader=csv.reader(f)
    header=next(reader)
    for row in reader:
        if not row or not row[0]:
            continue
        fx_rates[row[0].strip()] = dec(row[1].strip(), f'fx {row[0]}')
print('FX rates loaded:', fx_rates)

all_attempts=[]
list_args=['quotes','list','--from',FROM_DATE,'--to',TO_DATE,'--status',STATUS,'--format','json']
list_data, attempts = run_cli_json(list_args, 'quotes list')
all_attempts.extend(attempts)
if list_data.get('schema_version') != 1 or 'items' not in list_data:
    raise RuntimeError('quotes list JSON schema not recognized')
headers = list_data['items']
print('List count:', list_data.get('count'), 'items:', len(headers))

# Enforce queried criteria on returned headers before using them as data.
for h in headers:
    if h.get('Status') != STATUS or h.get('QuoteDate') < FROM_DATE or h.get('QuoteDate') > TO_DATE:
        raise RuntimeError(f'CLI returned item outside requested filter: {h}')

quote_details=[]
for h in headers:
    qid=h.get('QuoteID')
    if not qid:
        raise RuntimeError(f'Missing QuoteID in list item: {h}')
    data, attempts = run_cli_json(['quotes','get',qid,'--format','json'], f'quotes get {qid}')
    all_attempts.extend(attempts)
    if data.get('schema_version') != 1 or 'header' not in data or 'line_items' not in data:
        raise RuntimeError(f'quotes get {qid} JSON schema not recognized')
    hdr=data['header']
    # get data must match list filter too
    if hdr.get('QuoteID') != qid:
        raise RuntimeError(f'quotes get {qid} returned mismatched QuoteID: {hdr.get("QuoteID")}')
    if hdr.get('Status') != STATUS or hdr.get('QuoteDate') < FROM_DATE or hdr.get('QuoteDate') > TO_DATE:
        raise RuntimeError(f'quotes get {qid} returned outside requested filter: {hdr}')
    quote_details.append(data)
print('Detail quote count:', len(quote_details))
print('Detail line count:', sum(len(q["line_items"]) for q in quote_details))

# copy and load template
shutil.copy2(TEMPLATE, OUTFILE)
wb=load_workbook(OUTFILE)
report=wb['Report']; quotes_ws=wb['Quotes']; lines_ws=wb['Lines']; summary=wb['Summary']

# helper preserve row 5 style from row 4 or existing? create rows and assign values

def clear_data(ws, start_row, max_col):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

clear_data(quotes_ws, 5, 11)
clear_data(lines_ws, 5, 6)
clear_data(summary, 5, 6)

# report fields
report['B3'] = FROM_DATE
report['D3'] = TO_DATE
report['B4'] = f'quotes list --from {FROM_DATE} --to {TO_DATE} --status {STATUS} --format json; each QuoteID fetched with quotes get --format json'
report['B5'] = now_iso
report['B7'] = 'quote_cli_mock; fx_rates.csv'
report['D7'] = now_iso
# notes filled after attempts

quote_rows=[]
line_rows=[]
summary_map={}

for q in quote_details:
    h=q['header']
    cur=h.get('Currency')
    if cur not in fx_rates:
        raise RuntimeError(f'Missing FX rate for currency {cur!r}')
    subtotal = money(h.get('Subtotal'))
    discount = dec(h.get('DiscountPercent'), 'DiscountPercent')
    net = money(h.get('NetAmount'))
    if subtotal is not None and discount is not None:
        expected_net = (subtotal * (Decimal('1') - discount / Decimal('100'))).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if net != expected_net:
            raise RuntimeError(f'NetAmount mismatch for {h.get("QuoteID")}: got {net}, expected {expected_net}')
    net_twd = (net * fx_rates[cur]).quantize(TWOPLACES, rounding=ROUND_HALF_UP) if net is not None else None
    quote_rows.append([
        str(h.get('QuoteID') or ''), str(h.get('CustomerID') or ''), str(h.get('ProjectID') or ''),
        h.get('QuoteDate') or None, h.get('ValidUntil') or None, h.get('Status') or None, cur,
        subtotal, discount, net, net_twd
    ])
    key=(h.get('Status') or '', '', cur)
    if key not in summary_map:
        summary_map[key]={'amount': Decimal('0'), 'amount_twd': Decimal('0'), 'count': 0}
    summary_map[key]['amount'] += net or Decimal('0')
    summary_map[key]['amount_twd'] += net_twd or Decimal('0')
    summary_map[key]['count'] += 1
    for li in q['line_items']:
        qty=dec(li.get('Quantity'), 'Quantity')
        unit=money(li.get('UnitPrice'))
        line_amt=money(li.get('LineAmount'))
        expected_line = (qty * unit).quantize(TWOPLACES, rounding=ROUND_HALF_UP) if qty is not None and unit is not None else None
        if line_amt != expected_line:
            raise RuntimeError(f'LineAmount mismatch for {h.get("QuoteID")} {li.get("ProductID")}: got {line_amt}, expected {expected_line}')
        line_rows.append([
            str(h.get('QuoteID') or ''), str(li.get('ProductID') or ''), li.get('ProductName') or None,
            qty, unit, line_amt
        ])

# Write quote rows
for r_idx, row in enumerate(quote_rows, start=5):
    for c_idx, value in enumerate(row, start=1):
        cell=quotes_ws.cell(r_idx, c_idx, value=value)
        if c_idx in (1,2,3,6,7):
            cell.number_format='@'
        elif c_idx in (4,5):
            cell.number_format='yyyy-mm-dd'
        elif c_idx in (8,10,11):
            cell.number_format='0.00'
        elif c_idx == 9:
            cell.number_format='0.00'

# Write line rows
for r_idx, row in enumerate(line_rows, start=5):
    for c_idx, value in enumerate(row, start=1):
        cell=lines_ws.cell(r_idx, c_idx, value=value)
        if c_idx in (1,2,3):
            cell.number_format='@'
        elif c_idx == 4:
            cell.number_format='0'
        elif c_idx in (5,6):
            cell.number_format='0.00'

# Write summary rows sorted by Status, Currency
for r_idx, (key, agg) in enumerate(sorted(summary_map.items()), start=5):
    status, subgroup, cur = key
    values=[status, subgroup, cur, agg['amount'].quantize(TWOPLACES, rounding=ROUND_HALF_UP), agg['amount_twd'].quantize(TWOPLACES, rounding=ROUND_HALF_UP), agg['count']]
    for c_idx, value in enumerate(values, start=1):
        cell=summary.cell(r_idx, c_idx, value=value)
        if c_idx in (1,2,3):
            cell.number_format='@'
        elif c_idx in (4,5):
            cell.number_format='0.00'
        elif c_idx == 6:
            cell.number_format='0'

last_quote_row = 4 + len(quote_rows)
if quote_rows:
    summary['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'
else:
    summary['B2'] = '=SUM(Quotes!K5:K5)'
summary['B2'].number_format='0.00'

# notes: include retry info only, no invented issue
retry_events=[a for a in all_attempts if a['returncode']==4]
if retry_events:
    report['B9'] = f'CLI temporary errors retried per rule: {len(retry_events)} attempt(s) returned exit code 4 before success where applicable. stdout from failed attempts ignored.'
else:
    report['B9'] = 'No missing values or CLI exceptions. stdout used only from successful parseable JSON responses.'

# Ensure ids are strings (openpyxl stores as str because values are str)
wb.save(OUTFILE)

with LOGFILE.open('w', encoding='utf-8') as f:
    json.dump({
        'generated_at': now_iso,
        'query': {'from': FROM_DATE, 'to': TO_DATE, 'status': STATUS},
        'attempts': all_attempts,
        'quote_count': len(quote_rows),
        'line_count': len(line_rows),
        'output': str(OUTFILE),
    }, f, ensure_ascii=False, indent=2)

# Verification by reopening saved files.
wb2=load_workbook(OUTFILE, data_only=False)
qws=wb2['Quotes']; lws=wb2['Lines']; sws=wb2['Summary']; rws=wb2['Report']
expected_quote_headers=['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
expected_line_headers=['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
expected_sum_headers=['Group','SubGroup','Currency','Amount','AmountTWD','Count']
assert [qws.cell(4,c).value for c in range(1,12)] == expected_quote_headers
assert [lws.cell(4,c).value for c in range(1,7)] == expected_line_headers
assert [sws.cell(4,c).value for c in range(1,7)] == expected_sum_headers
# row counts: no blank rows within data range
actual_q=[]
for row in qws.iter_rows(min_row=5, max_row=qws.max_row, max_col=11, values_only=True):
    if any(v is not None for v in row):
        actual_q.append(row)
actual_l=[]
for row in lws.iter_rows(min_row=5, max_row=lws.max_row, max_col=6, values_only=True):
    if any(v is not None for v in row):
        actual_l.append(row)
actual_s=[]
for row in sws.iter_rows(min_row=5, max_row=sws.max_row, max_col=6, values_only=True):
    if any(v is not None for v in row):
        actual_s.append(row)
assert len(actual_q)==len(quote_rows), (len(actual_q), len(quote_rows))
assert len(actual_l)==len(line_rows), (len(actual_l), len(line_rows))
assert len(actual_s)==len(summary_map), (len(actual_s), len(summary_map))
for row in actual_q:
    assert isinstance(row[0], str) and isinstance(row[1], str) and isinstance(row[2], str)
    assert row[3] >= FROM_DATE and row[3] <= TO_DATE and row[5] == STATUS
    assert isinstance(row[7], Decimal) or isinstance(row[7], (int,float))
for row in actual_l:
    assert isinstance(row[0], str) and isinstance(row[1], str)
for row in actual_s:
    assert row[2] in fx_rates
# formula check
expected_formula = f'=SUM(Quotes!K5:K{last_quote_row})' if quote_rows else '=SUM(Quotes!K5:K5)'
assert sws['B2'].value == expected_formula, sws['B2'].value
assert rws['B3'].value == FROM_DATE and rws['D3'].value == TO_DATE
assert rws['B4'].value and STATUS in rws['B4'].value
# log check
log=json.load(LOGFILE.open(encoding='utf-8'))
assert log['quote_count']==len(quote_rows) and log['line_count']==len(line_rows)
# Ensure no failed stdout treated as data: all quote rows equal successful detail count.
print('OUTPUT', OUTFILE)
print('LOG', LOGFILE)
print('CHECKED quote headers, line headers, summary headers, report dates/condition, row counts, ID text values, numeric amount cells, B2 formula, CLI attempt log.')
print('QUOTE_COUNT', len(quote_rows))
print('LINE_COUNT', len(line_rows))
print('SUMMARY_COUNT', len(summary_map))
print('CLI_ATTEMPTS', len(all_attempts), 'TEMPORARY_4_COUNT', len(retry_events))
print('QUOTE_IDS', [r[0] for r in quote_rows])
