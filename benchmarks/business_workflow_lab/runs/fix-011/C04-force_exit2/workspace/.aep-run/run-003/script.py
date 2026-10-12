from pathlib import Path
import subprocess, json, csv, shutil, sys
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from openpyxl import load_workbook
from openpyxl.styles import Font

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)

TEMPLATE = INPUT / 'quote_template.xlsx'
FX_FILE = INPUT / 'fx_rates.csv'
CLI = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd')
FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
STATUS = 'Sent'
GENERATED_AT = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()

OUT_XLSX = OUTPUT / 'sent_quotes_2026-09.xlsx'
RUN_LOG = OUTPUT / 'quote_cli_run_log.json'
ERROR_TXT = OUTPUT / 'quote_cli_error.txt'
CHECK_TXT = OUTPUT / 'check_report.txt'

print('Inputs confirmed:')
print(' workspace =', WORKSPACE)
print(' template =', TEMPLATE, TEMPLATE.exists())
print(' fx_rates =', FX_FILE, FX_FILE.exists())
print(' cli =', CLI, CLI.exists())
print(' query =', FROM_DATE, 'to', TO_DATE, 'status', STATUS)

# Robust CSV reader for known small fx file; Note column contains unquoted comma in fixture, so use first two cols.
fx_rates = {}
with FX_FILE.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row or not row[0].strip():
            continue
        fx_rates[row[0].strip()] = Decimal(row[1].strip())
print('fx rates:', {k: str(v) for k, v in fx_rates.items()})

run_log = []

def run_cli(args, max_temp_retries=2):
    """Run quote CLI. Retry exit code 4 up to max_temp_retries. Never retry code 2/3. Return dict."""
    attempts = 0
    while True:
        attempts += 1
        cmd = [str(CLI)] + args
        cp = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True, shell=False)
        rec = {
            'args': args,
            'attempt': attempts,
            'exit_code': cp.returncode,
            'stdout': cp.stdout,
            'stderr': cp.stderr,
        }
        run_log.append(rec)
        print('CLI attempt', attempts, 'exit', cp.returncode, 'args:', ' '.join(args))
        if cp.returncode == 4 and attempts <= max_temp_retries + 1:
            if attempts <= max_temp_retries:
                print(' temporary service error; retrying')
                continue
        # exit 2/3 and all non-4 return immediately; exit 4 returns after retries exhausted
        return rec

def parse_json_stdout(rec, what):
    if rec['exit_code'] != 0:
        raise RuntimeError(f"{what} failed exit {rec['exit_code']}: {rec['stderr'].strip()}")
    try:
        return json.loads(rec['stdout'])
    except Exception as e:
        raise RuntimeError(f"{what} stdout was not parseable JSON: {e}") from e

fatal_error = None
quotes = []
details = []
try:
    list_args = ['quotes', 'list', '--from', FROM_DATE, '--to', TO_DATE, '--status', STATUS, '--format', 'json']
    list_rec = run_cli(list_args)
    if list_rec['exit_code'] in (2, 3):
        fatal_error = f"quotes list failed with exit code {list_rec['exit_code']}; no retry per instruction. stderr: {list_rec['stderr'].strip()}"
    elif list_rec['exit_code'] == 4:
        fatal_error = f"quotes list failed with exit code 4 after retries. stderr: {list_rec['stderr'].strip()}"
    elif list_rec['exit_code'] != 0:
        fatal_error = f"quotes list failed with exit code {list_rec['exit_code']}. stderr: {list_rec['stderr'].strip()}"
    else:
        data = parse_json_stdout(list_rec, 'quotes list')
        if data.get('schema_version') != 1 or not isinstance(data.get('items'), list):
            fatal_error = 'quotes list stdout JSON did not match schema_version 1 with items list.'
        else:
            quotes = data['items']
            for q in quotes:
                qid = str(q.get('QuoteID', ''))
                get_rec = run_cli(['quotes', 'get', qid, '--format', 'json'])
                if get_rec['exit_code'] in (2, 3):
                    fatal_error = f"quotes get {qid} failed with exit code {get_rec['exit_code']}; no retry per instruction. stderr: {get_rec['stderr'].strip()}"
                    break
                elif get_rec['exit_code'] == 4:
                    fatal_error = f"quotes get {qid} failed with exit code 4 after retries. stderr: {get_rec['stderr'].strip()}"
                    break
                elif get_rec['exit_code'] != 0:
                    fatal_error = f"quotes get {qid} failed with exit code {get_rec['exit_code']}. stderr: {get_rec['stderr'].strip()}"
                    break
                detail = parse_json_stdout(get_rec, f'quotes get {qid}')
                if detail.get('schema_version') != 1 or 'header' not in detail or 'line_items' not in detail:
                    fatal_error = f'quotes get {qid} stdout JSON did not match schema_version 1 detail shape.'
                    break
                details.append(detail)
except Exception as e:
    fatal_error = str(e)

# Always write log; stdout is stored only as execution log and only parsed if success above.
RUN_LOG.write_text(json.dumps(run_log, ensure_ascii=False, indent=2), encoding='utf-8')

# Fill a copy of the template. If CLI failed, leave detail sheets empty and record reason in Report!B9.
shutil.copy2(TEMPLATE, OUT_XLSX)
wb = load_workbook(OUT_XLSX)
report = wb['Report']
quotes_ws = wb['Quotes']
lines_ws = wb['Lines']
summary_ws = wb['Summary']

# Clear possible existing data rows while preserving headers/template structure.
for ws_name in ['Quotes', 'Lines', 'Summary']:
    wsht = wb[ws_name]
    if wsht.max_row >= 5:
        wsht.delete_rows(5, wsht.max_row - 4)

report['B3'] = FROM_DATE
report['D3'] = TO_DATE
report['B4'] = f'Status={STATUS}; QuoteDate {FROM_DATE}..{TO_DATE}'
report['B5'] = GENERATED_AT
report['B7'] = 'quote_cli; fx_rates.csv'
report['D7'] = GENERATED_AT

if fatal_error:
    report['B9'] = fatal_error
    ERROR_TXT.write_text(fatal_error + '\n', encoding='utf-8')
    print('FATAL:', fatal_error)
else:
    ERROR_TXT.write_text('', encoding='utf-8')
    report['B9'] = ''

    # Use detail header as authoritative; list and get headers should match, but detail has line items.
    quote_headers = []
    line_rows = []
    for d in details:
        h = d['header']
        quote_headers.append(h)
        qid = str(h.get('QuoteID', ''))
        for li in d.get('line_items', []):
            row = dict(li)
            row['QuoteID'] = qid
            line_rows.append(row)

    # Sort stable by QuoteID then ProductID for deterministic reruns.
    quote_headers.sort(key=lambda x: str(x.get('QuoteID', '')))
    line_rows.sort(key=lambda x: (str(x.get('QuoteID', '')), str(x.get('ProductID', ''))))

    # Fill Quotes
    q_cols = ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
    for r, h in enumerate(quote_headers, start=5):
        currency = str(h.get('Currency', '') or '')
        rate = fx_rates.get(currency)
        if rate is None:
            net_twd = None
            report['B9'] = (report['B9'] or '') + f'Missing FX rate for {currency}; '
        else:
            net_twd = (Decimal(str(h.get('NetAmount', '0'))) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        vals = [
            str(h.get('QuoteID', '') or ''),
            str(h.get('CustomerID', '') or ''),
            str(h.get('ProjectID', '') or ''),
            h.get('QuoteDate', None),
            h.get('ValidUntil', None),
            h.get('Status', None),
            currency,
            Decimal(str(h['Subtotal'])) if h.get('Subtotal') not in (None, '') else None,
            Decimal(str(h['DiscountPercent'])) if h.get('DiscountPercent') not in (None, '') else None,
            Decimal(str(h['NetAmount'])) if h.get('NetAmount') not in (None, '') else None,
            net_twd,
        ]
        for c, val in enumerate(vals, start=1):
            cell = quotes_ws.cell(r, c, val)
            if c in (1,2,3):
                cell.number_format = '@'
            elif c in (8,10,11):
                cell.number_format = '0.00'
            elif c == 9:
                cell.number_format = '0.00'

    # Fill Lines
    l_cols = ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
    for r, li in enumerate(line_rows, start=5):
        vals = [
            str(li.get('QuoteID', '') or ''),
            str(li.get('ProductID', '') or ''),
            li.get('ProductName', None),
            Decimal(str(li['Quantity'])) if li.get('Quantity') not in (None, '') else None,
            Decimal(str(li['UnitPrice'])) if li.get('UnitPrice') not in (None, '') else None,
            Decimal(str(li['LineAmount'])) if li.get('LineAmount') not in (None, '') else None,
        ]
        for c, val in enumerate(vals, start=1):
            cell = lines_ws.cell(r, c, val)
            if c in (1,2):
                cell.number_format = '@'
            elif c in (5,6):
                cell.number_format = '0.00'

    # Summary by Status and Currency (plain reading for quote summary: group by status/currency)
    groups = {}
    for h in quote_headers:
        key = (str(h.get('Status', '') or ''), str(h.get('Currency', '') or ''))
        amt = Decimal(str(h.get('NetAmount', '0')))
        rate = fx_rates.get(key[1])
        twd = (amt * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if rate is not None else None
        if key not in groups:
            groups[key] = {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0, 'missing_twd': False}
        groups[key]['amount'] += amt
        if twd is None:
            groups[key]['missing_twd'] = True
        else:
            groups[key]['twd'] += twd
        groups[key]['count'] += 1

    for idx, ((status, currency), agg) in enumerate(sorted(groups.items()), start=5):
        summary_ws.cell(idx, 1, 'Status')
        summary_ws.cell(idx, 2, status)
        summary_ws.cell(idx, 3, currency)
        summary_ws.cell(idx, 4, agg['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        summary_ws.cell(idx, 5, None if agg['missing_twd'] else agg['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        summary_ws.cell(idx, 6, agg['count'])
        summary_ws.cell(idx, 4).number_format = '0.00'
        summary_ws.cell(idx, 5).number_format = '0.00'

# Update total formula range; zero rows preserve K5:K5 per instructions.
last_quote_row = max(5, 4 + (0 if fatal_error else len(details)))
summary_ws['B2'] = f'=SUM(Quotes!K5:K{last_quote_row})'

# Ensure footer not changed if exists.
wb.save(OUT_XLSX)

# Reopen and verify stated requirements.
check_lines = []
wb2 = load_workbook(OUT_XLSX, data_only=False)
check_lines.append(f'Workbook exists: {OUT_XLSX.exists()}')
check_lines.append(f'Sheets: {wb2.sheetnames}')
check_lines.append(f'Report B3={wb2["Report"]["B3"].value} D3={wb2["Report"]["D3"].value} B4={wb2["Report"]["B4"].value}')
check_lines.append(f'Report B9={wb2["Report"]["B9"].value}')
check_lines.append(f'Quotes header row: {[wb2["Quotes"].cell(4,c).value for c in range(1,12)]}')
check_lines.append(f'Lines header row: {[wb2["Lines"].cell(4,c).value for c in range(1,7)]}')
check_lines.append(f'Summary header row: {[wb2["Summary"].cell(4,c).value for c in range(1,7)]}')
q_data_rows = 0 if fatal_error else len(details)
l_data_rows = 0 if fatal_error else sum(len(d.get('line_items', [])) for d in details)
# inspect actual nonempty data rows
actual_q = []
for r in range(5, wb2['Quotes'].max_row+1):
    if any(wb2['Quotes'].cell(r,c).value is not None for c in range(1,12)):
        actual_q.append(r)
actual_l = []
for r in range(5, wb2['Lines'].max_row+1):
    if any(wb2['Lines'].cell(r,c).value is not None for c in range(1,7)):
        actual_l.append(r)
check_lines.append(f'Expected quote rows: {q_data_rows}; actual nonempty quote rows: {len(actual_q)}')
check_lines.append(f'Expected line rows: {l_data_rows}; actual nonempty line rows: {len(actual_l)}')
check_lines.append(f'Summary B2 formula: {wb2["Summary"]["B2"].value}')
check_lines.append(f'CLI calls: {len(run_log)}; exit codes: {[r["exit_code"] for r in run_log]}')
if run_log:
    check_lines.append(f'First stderr: {run_log[0]["stderr"].strip()}')

# Assertions for critical requirements
assert wb2['Report']['B3'].value == FROM_DATE
assert wb2['Report']['D3'].value == TO_DATE
assert wb2['Report']['B4'].value == f'Status={STATUS}; QuoteDate {FROM_DATE}..{TO_DATE}'
assert [wb2['Quotes'].cell(4,c).value for c in range(1,12)] == ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount','NetAmountTWD']
assert [wb2['Lines'].cell(4,c).value for c in range(1,7)] == ['QuoteID','ProductID','ProductName','Quantity','UnitPrice','LineAmount']
assert [wb2['Summary'].cell(4,c).value for c in range(1,7)] == ['Group','SubGroup','Currency','Amount','AmountTWD','Count']
assert len(actual_q) == q_data_rows
assert len(actual_l) == l_data_rows
if fatal_error:
    assert 'exit code' in wb2['Report']['B9'].value
else:
    # Check ID text format and amount numeric-like values
    for r in actual_q:
        assert wb2['Quotes'].cell(r,1).number_format == '@'
        assert wb2['Quotes'].cell(r,2).number_format == '@'
        assert wb2['Quotes'].cell(r,3).number_format == '@'
        assert isinstance(wb2['Quotes'].cell(r,8).value, (int, float, Decimal))
        assert wb2['Quotes'].cell(r,8).number_format == '0.00'
        assert wb2['Quotes'].cell(r,10).number_format == '0.00'
        assert wb2['Quotes'].cell(r,11).number_format == '0.00'
    for r in actual_l:
        assert wb2['Lines'].cell(r,1).number_format == '@'
        assert wb2['Lines'].cell(r,2).number_format == '@'
        assert wb2['Lines'].cell(r,5).number_format == '0.00'
        assert wb2['Lines'].cell(r,6).number_format == '0.00'

CHECK_TXT.write_text('\n'.join(check_lines) + '\n', encoding='utf-8')
print('\nCHECK REPORT:')
print('\n'.join(check_lines))
print('\nOUTPUT FILES:')
for p in sorted(OUTPUT.iterdir()):
    print('-', p.name, p.stat().st_size, 'bytes')