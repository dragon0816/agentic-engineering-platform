from pathlib import Path
import subprocess, sys, json, csv, shutil, os, re
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from openpyxl import load_workbook
from openpyxl.styles import Alignment

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(parents=True, exist_ok=True)
TEMPLATE = INPUT / 'quote_template.xlsx'
FX = INPUT / 'fx_rates.csv'
CLI = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')

FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
STATUS = 'Sent'
TODAY_TAIPEI = '2026-10-06'
GENERATED_AT = '2026-10-06T09:00:00+08:00'
FETCHED_AT = GENERATED_AT

log = []

class CliError(Exception):
    def __init__(self, command, code, stderr, stdout, attempts):
        super().__init__(stderr)
        self.command = command
        self.code = code
        self.stderr = stderr
        self.stdout = stdout
        self.attempts = attempts

def run_cli(args, parse_json=True):
    """Run quote CLI. Retry exit code 4 up to two times. Do not retry 2/3. Return parsed JSON only on rc=0 and parse success."""
    cmd = [sys.executable, str(CLI)] + args
    attempts = 0
    last = None
    while True:
        attempts += 1
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE))
        last = proc
        entry = {
            'command': ' '.join(args),
            'attempt': attempts,
            'exit_code': proc.returncode,
            'stderr': proc.stderr.strip(),
            'stdout_length': len(proc.stdout or ''),
        }
        log.append(entry)
        if proc.returncode == 4 and attempts < 3:
            continue
        if proc.returncode != 0:
            raise CliError(args, proc.returncode, proc.stderr.strip(), proc.stdout, attempts)
        if not parse_json:
            return proc.stdout
        try:
            return json.loads(proc.stdout)
        except Exception as e:
            # stdout is not to be treated as data if not parseable.
            raise CliError(args, 0, f'stdout JSON parse failed: {e}', proc.stdout, attempts)

def decimal2(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def read_fx_rates():
    rates = {}
    with FX.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) >= 2 and row[0]:
                rates[row[0]] = Decimal(row[1])
    return rates

def clear_data_rows(ws, start_row=5):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

def set_text(cell, value):
    cell.value = '' if value is None else str(value)
    cell.number_format = '@'

def set_money(cell, value):
    cell.value = float(decimal2(value))
    cell.number_format = '0.00'

def fill_error_workbook(error):
    out = OUTPUT / 'quote_report_2026-09_Sent.xlsx'
    shutil.copy2(TEMPLATE, out)
    wb = load_workbook(out)
    rpt = wb['Report']
    rpt['B3'] = FROM_DATE
    rpt['D3'] = TO_DATE
    rpt['B4'] = f'Status={STATUS}; QuoteDate {FROM_DATE}..{TO_DATE}'
    rpt['B5'] = GENERATED_AT
    rpt['B7'] = 'quote_cli'
    rpt['D7'] = FETCHED_AT
    rpt['B9'] = f'CLI 查詢失敗，未填入報價資料。exit code {error.code}; stderr: {error.stderr}'
    # Ensure detail sheets have no stale rows beyond headers.
    for name in ('Quotes', 'Lines', 'Summary'):
        clear_data_rows(wb[name], 5)
    wb.save(out)
    return out

def fill_success_workbook(headers, details):
    rates = read_fx_rates()
    out = OUTPUT / 'quote_report_2026-09_Sent.xlsx'
    shutil.copy2(TEMPLATE, out)
    wb = load_workbook(out)
    rpt = wb['Report']
    quotes_ws = wb['Quotes']
    lines_ws = wb['Lines']
    summary_ws = wb['Summary']
    for name in ('Quotes', 'Lines', 'Summary'):
        clear_data_rows(wb[name], 5)

    rpt['B3'] = FROM_DATE
    rpt['D3'] = TO_DATE
    rpt['B4'] = f'Status={STATUS}; QuoteDate {FROM_DATE}..{TO_DATE}'
    rpt['B5'] = GENERATED_AT
    rpt['B7'] = 'quote_cli; fx_rates.csv'
    rpt['D7'] = FETCHED_AT

    missing = []
    # Quotes columns: QuoteID, CustomerID, ProjectID, QuoteDate, ValidUntil, Status, Currency, Subtotal, DiscountPercent, NetAmount, NetAmountTWD
    qrow = 5
    summary_acc = {}
    for h in headers:
        cur = h.get('Currency')
        net = decimal2(h.get('NetAmount'))
        rate = rates.get(cur)
        if rate is None:
            missing.append(f'missing FX rate for {cur}')
            amount_twd = None
        else:
            amount_twd = decimal2(net * rate)
        values_text = [h.get('QuoteID'), h.get('CustomerID'), h.get('ProjectID'), h.get('QuoteDate'), h.get('ValidUntil'), h.get('Status'), cur]
        for col, val in enumerate(values_text, 1):
            set_text(quotes_ws.cell(qrow, col), val)
        set_money(quotes_ws.cell(qrow, 8), h.get('Subtotal'))
        quotes_ws.cell(qrow, 9).value = float(Decimal(str(h.get('DiscountPercent'))))
        quotes_ws.cell(qrow, 9).number_format = '0.00'
        set_money(quotes_ws.cell(qrow, 10), net)
        if amount_twd is not None:
            set_money(quotes_ws.cell(qrow, 11), amount_twd)
        else:
            quotes_ws.cell(qrow, 11).value = None
        key = ('Status', h.get('Status'), cur)
        if key not in summary_acc:
            summary_acc[key] = {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0}
        summary_acc[key]['amount'] += net
        if amount_twd is not None:
            summary_acc[key]['twd'] += amount_twd
        summary_acc[key]['count'] += 1
        qrow += 1

    # Lines columns: QuoteID, ProductID, ProductName, Quantity, UnitPrice, LineAmount
    lrow = 5
    for detail in details:
        qid = detail['header']['QuoteID']
        for line in detail.get('line_items', []):
            set_text(lines_ws.cell(lrow, 1), qid)
            set_text(lines_ws.cell(lrow, 2), line.get('ProductID'))
            lines_ws.cell(lrow, 3).value = line.get('ProductName')
            lines_ws.cell(lrow, 4).value = int(line.get('Quantity'))
            lines_ws.cell(lrow, 4).number_format = '0'
            set_money(lines_ws.cell(lrow, 5), line.get('UnitPrice'))
            set_money(lines_ws.cell(lrow, 6), line.get('LineAmount'))
            lrow += 1

    srow = 5
    for (group, subgroup, cur), vals in sorted(summary_acc.items()):
        set_text(summary_ws.cell(srow, 1), group)
        set_text(summary_ws.cell(srow, 2), subgroup)
        set_text(summary_ws.cell(srow, 3), cur)
        set_money(summary_ws.cell(srow, 4), vals['amount'])
        set_money(summary_ws.cell(srow, 5), vals['twd'])
        summary_ws.cell(srow, 6).value = vals['count']
        summary_ws.cell(srow, 6).number_format = '0'
        srow += 1
    # Also total by currency if useful
    if missing:
        rpt['B9'] = '; '.join(sorted(set(missing)))
    else:
        rpt['B9'] = f'完成。Sent 報價 {len(headers)} 筆；明細 {sum(len(d.get("line_items", [])) for d in details)} 筆。'
    wb.save(out)
    return out

result = {'status': None, 'output_workbook': None, 'error': None, 'log': log}
try:
    listing = run_cli(['quotes', 'list', '--from', FROM_DATE, '--to', TO_DATE, '--status', STATUS, '--format', 'json'])
    if listing.get('schema_version') != 1 or 'items' not in listing:
        raise CliError(['quotes','list'], 0, 'Unexpected list JSON schema', json.dumps(listing), 1)
    headers = listing['items']
    details = []
    for h in headers:
        qid = h.get('QuoteID')
        detail = run_cli(['quotes', 'get', str(qid), '--format', 'json'])
        if detail.get('schema_version') != 1 or 'header' not in detail or 'line_items' not in detail:
            raise CliError(['quotes','get',str(qid)], 0, f'Unexpected get JSON schema for {qid}', json.dumps(detail), 1)
        details.append(detail)
    out = fill_success_workbook(headers, details)
    result.update({'status': 'success', 'output_workbook': str(out), 'quote_count': len(headers), 'line_count': sum(len(d.get('line_items', [])) for d in details)})
except CliError as e:
    out = fill_error_workbook(e)
    result.update({'status': 'cli_error', 'output_workbook': str(out), 'error': {'command': ' '.join(e.command), 'exit_code': e.code, 'stderr': e.stderr, 'attempts': e.attempts}})

# Save run log/result.
(OUTPUT / 'quote_cli_run_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

# Verification: reopen every output, confirm requirements.
print('RUN RESULT')
print(json.dumps(result, ensure_ascii=False, indent=2))
print('\nVERIFY OUTPUTS')
# Verify JSON exists and contains no stdout-as-data on error.
loaded_result = json.loads((OUTPUT / 'quote_cli_run_result.json').read_text(encoding='utf-8'))
print('json status:', loaded_result['status'])
print('cli attempts:', [(x['command'], x['attempt'], x['exit_code']) for x in loaded_result['log']])
wb_path = Path(loaded_result['output_workbook'])
wb = load_workbook(wb_path, data_only=False)
print('workbook exists:', wb_path.exists(), wb_path.name)
print('Report B3/D3/B4/B5/B7/D7/B9:', wb['Report']['B3'].value, wb['Report']['D3'].value, wb['Report']['B4'].value, wb['Report']['B5'].value, wb['Report']['B7'].value, wb['Report']['D7'].value, wb['Report']['B9'].value)
# Headers preserved.
for sheet in ('Quotes','Lines','Summary'):
    hdr = [wb[sheet].cell(4,c).value for c in range(1, wb[sheet].max_column+1)]
    print(sheet, 'row4 headers:', hdr)
# Row counts and cell type samples.
for sheet in ('Quotes','Lines','Summary'):
    data_rows = max(0, wb[sheet].max_row - 4)
    nonempty = 0
    for r in range(5, wb[sheet].max_row+1):
        if any(wb[sheet].cell(r,c).value is not None for c in range(1, wb[sheet].max_column+1)):
            nonempty += 1
    print(sheet, 'max_row:', wb[sheet].max_row, 'nonempty_data_rows:', nonempty)
if loaded_result['status'] == 'success':
    qws = wb['Quotes']; lws = wb['Lines']
    print('QuoteID format/value sample:', qws['A5'].number_format, qws['A5'].value, type(qws['A5'].value).__name__)
    print('NetAmountTWD format/value sample:', qws['K5'].number_format, qws['K5'].value, type(qws['K5'].value).__name__)
    print('LineAmount format/value sample:', lws['F5'].number_format, lws['F5'].value, type(lws['F5'].value).__name__)
else:
    # Check no retries for code 2 or 3, retry max for code 4.
    err = loaded_result['error']
    print('error command:', err['command'])
    print('error exit code:', err['exit_code'])
    print('error stderr:', err['stderr'])
    print('error attempts:', err['attempts'])
    if err['exit_code'] in (2,3):
        assert err['attempts'] == 1, 'exit code 2/3 must not be retried'
    if err['exit_code'] == 4:
        assert err['attempts'] <= 3, 'exit code 4 may be tried at most 3 total times'
print('checked: CLI retry policy, stderr capture, workbook reopened, metadata, preserved headers, data row counts, output JSON reopened.')
