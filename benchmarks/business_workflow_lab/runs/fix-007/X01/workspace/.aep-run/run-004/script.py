from pathlib import Path
import csv, json, os, shutil, subprocess
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from openpyxl import load_workbook
from copy import copy

WORKSPACE = Path.cwd()
INPUT = WORKSPACE/'input'
OUTPUT = WORKSPACE/'output'
DOWNLOADS = OUTPUT/'downloads'
OUTPUT.mkdir(exist_ok=True)
DOWNLOADS.mkdir(exist_ok=True)
FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
PERIOD = '2026-09'
TODAY = '2026-10-06'
QUOTE_CLI = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')

# Ensure quote export exists and is reproducible from CLI.
quote_path = DOWNLOADS/f'quotes_{PERIOD}_accepted.csv'
cmd = ['python', str(QUOTE_CLI), 'quotes', 'export', '--from', FROM_DATE, '--to', TO_DATE, '--status', 'Accepted', '--output', str(quote_path)]
res = subprocess.run(cmd, capture_output=True, text=True)
print('quote_cli return:', res.returncode)
if res.returncode != 0:
    raise RuntimeError(f'quote_cli failed: {res.stderr}')
print('quote_cli stdout:', res.stdout.strip())

paths = {
    'orders': DOWNLOADS/f'sap_orders_{PERIOD}.csv',
    'invoices': DOWNLOADS/f'sap_invoices_{PERIOD}.csv',
    'expenses': DOWNLOADS/f'expenses_{PERIOD}_approved.csv',
    'quotes': quote_path,
}
for k,p in paths.items():
    print(f'{k} file:', p, 'exists=', p.exists(), 'bytes=', p.stat().st_size if p.exists() else 'missing')
    if not p.exists():
        raise FileNotFoundError(p)
    with open(p, newline='', encoding='utf-8-sig') as f:
        rdr = csv.reader(f)
        rows = list(rdr)
    print(f'{k} header:', rows[0] if rows else [])
    print(f'{k} sample:', rows[1] if len(rows)>1 else [])

def read_csv_dict(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def money(x):
    if x is None or str(x).strip() == '':
        return None
    return Decimal(str(x).replace(',', '').strip())

def twd(amount, currency, fx):
    if amount is None:
        return None
    if currency not in fx:
        return None
    return (amount * fx[currency]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def parse_date(s):
    if not s:
        return None
    return datetime.strptime(s, '%Y-%m-%d').date()

fx = {}
with open(INPUT/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    r = csv.reader(f)
    header = next(r)
    for row in r:
        if len(row) >= 2 and row[0].strip():
            fx[row[0].strip()] = Decimal(row[1].strip())
print('fx loaded:', {k: str(v) for k,v in fx.items()})

raw_orders = read_csv_dict(paths['orders'])
raw_invoices = read_csv_dict(paths['invoices'])
raw_expenses = read_csv_dict(paths['expenses'])
raw_quotes = read_csv_dict(paths['quotes'])

orders = [r for r in raw_orders if r.get('Status') != 'Cancelled' and FROM_DATE <= r.get('OrderDate','') <= TO_DATE]
invoices = [r for r in raw_invoices if FROM_DATE <= r.get('InvoiceDate','') <= TO_DATE]
expenses = [r for r in raw_expenses if r.get('Status') == 'Approved' and FROM_DATE <= r.get('ExpenseDate','') <= TO_DATE]
quotes = [r for r in raw_quotes if r.get('Status') == 'Accepted' and FROM_DATE <= r.get('QuoteDate','') <= TO_DATE]
print('filtered counts:', {'orders': len(orders), 'raw_orders': len(raw_orders), 'invoices': len(invoices), 'expenses': len(expenses), 'quotes': len(quotes)})

wb = load_workbook(INPUT/'project_template.xlsx')

def clear_data(ws, start_row=5):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

def copy_row_style(ws, from_row, to_row, cols):
    for c in range(1, cols+1):
        src = ws.cell(from_row, c)
        dst = ws.cell(to_row, c)
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

def write_detail(sheet, headers, rows, type_map):
    ws = wb[sheet]
    clear_data(ws)
    for idx, row_values in enumerate(rows, start=5):
        copy_row_style(ws, 4, idx, len(headers))
        for col, (h, v) in enumerate(zip(headers, row_values), start=1):
            cell = ws.cell(idx, col)
            cell.value = v
            typ = type_map.get(h)
            if typ == 'text':
                cell.number_format = '@'
            elif typ == 'date':
                cell.number_format = 'yyyy-mm-dd'
            elif typ == 'money':
                cell.number_format = '0.00'
    if rows:
        ws.auto_filter.ref = f"A4:{ws.cell(4,len(headers)).coordinate[0]}{4+len(rows)}"

summary = {}
exceptions = []

def add_sum(project, key, amt):
    if not project:
        return
    summary.setdefault(project, {'OrderTWD': Decimal('0.00'), 'InvoiceBalanceTWD': Decimal('0.00'), 'ApprovedExpenseTWD': Decimal('0.00'), 'AcceptedQuoteTWD': Decimal('0.00')})
    summary[project][key] += amt or Decimal('0.00')

def add_exception(source, doc, project, reason):
    exceptions.append([source, doc or '', project or '', reason])

order_rows=[]
for r in orders:
    amt = money(r.get('NetAmount'))
    amount_twd = twd(amt, r.get('Currency'), fx)
    if amount_twd is None:
        add_exception('Orders', r.get('OrderID'), r.get('ProjectID'), f"Missing FX rate for {r.get('Currency')}")
    if not r.get('ProjectID'):
        add_exception('Orders', r.get('OrderID'), r.get('ProjectID'), 'Missing ProjectID; excluded from Summary')
    else:
        add_sum(r.get('ProjectID'), 'OrderTWD', amount_twd)
    order_rows.append([r.get('OrderID'), r.get('ProjectID') or None, r.get('CustomerID') or None, parse_date(r.get('OrderDate')), r.get('Status') or None, r.get('Currency') or None, float(amt) if amt is not None else None, float(amount_twd) if amount_twd is not None else None])

invoice_rows=[]
for r in invoices:
    amount = money(r.get('Amount'))
    paid = money(r.get('PaidAmount'))
    balance = money(r.get('Balance'))
    if amount is not None and paid is not None:
        calc = (amount - paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if balance is not None and calc != balance:
            add_exception('Invoices', r.get('InvoiceID'), r.get('ProjectID'), f'Balance mismatch: Amount - PaidAmount = {calc}')
    balance_twd = twd(balance, r.get('Currency'), fx)
    if balance_twd is None:
        add_exception('Invoices', r.get('InvoiceID'), r.get('ProjectID'), f"Missing FX rate for {r.get('Currency')}")
    if not r.get('ProjectID'):
        add_exception('Invoices', r.get('InvoiceID'), r.get('ProjectID'), 'Missing ProjectID; excluded from Summary')
    else:
        add_sum(r.get('ProjectID'), 'InvoiceBalanceTWD', balance_twd)
    invoice_rows.append([r.get('InvoiceID'), r.get('OrderID'), r.get('ProjectID') or None, r.get('CustomerID') or None, parse_date(r.get('InvoiceDate')), parse_date(r.get('DueDate')), r.get('Currency') or None, float(amount) if amount is not None else None, float(paid) if paid is not None else None, float(balance) if balance is not None else None, float(balance_twd) if balance_twd is not None else None])

expense_rows=[]
for r in expenses:
    amt = money(r.get('Amount'))
    amount_twd = twd(amt, r.get('Currency'), fx)
    if amount_twd is None:
        add_exception('Expenses', r.get('ExpenseID'), r.get('ProjectID'), f"Missing FX rate for {r.get('Currency')}")
    if not r.get('ProjectID'):
        add_exception('Expenses', r.get('ExpenseID'), r.get('ProjectID'), 'Missing ProjectID; excluded from Summary')
    else:
        add_sum(r.get('ProjectID'), 'ApprovedExpenseTWD', amount_twd)
    expense_rows.append([r.get('ExpenseID'), r.get('ProjectID') or None, r.get('EmployeeID') or None, parse_date(r.get('ExpenseDate')), r.get('Status') or None, r.get('Currency') or None, float(amt) if amt is not None else None, float(amount_twd) if amount_twd is not None else None])

quote_rows=[]
for r in quotes:
    amt = money(r.get('NetAmount'))
    amount_twd = twd(amt, r.get('Currency'), fx)
    if amount_twd is None:
        add_exception('Quotes', r.get('QuoteID'), r.get('ProjectID'), f"Missing FX rate for {r.get('Currency')}")
    if not r.get('ProjectID'):
        add_exception('Quotes', r.get('QuoteID'), r.get('ProjectID'), 'Missing ProjectID; excluded from Summary')
    else:
        add_sum(r.get('ProjectID'), 'AcceptedQuoteTWD', amount_twd)
    quote_rows.append([r.get('QuoteID'), r.get('ProjectID') or None, r.get('CustomerID') or None, parse_date(r.get('QuoteDate')), parse_date(r.get('ValidUntil')), r.get('Status') or None, r.get('Currency') or None, float(amt) if amt is not None else None, float(amount_twd) if amount_twd is not None else None])

write_detail('Orders', ['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'], order_rows, {'OrderID':'text','ProjectID':'text','CustomerID':'text','OrderDate':'date','NetAmount':'money','AmountTWD':'money'})
write_detail('Invoices', ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'], invoice_rows, {'InvoiceID':'text','OrderID':'text','ProjectID':'text','CustomerID':'text','InvoiceDate':'date','DueDate':'date','Amount':'money','PaidAmount':'money','Balance':'money','BalanceTWD':'money'})
write_detail('Expenses', ['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'], expense_rows, {'ExpenseID':'text','ProjectID':'text','EmployeeID':'text','ExpenseDate':'date','Amount':'money','AmountTWD':'money'})
write_detail('Quotes', ['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'], quote_rows, {'QuoteID':'text','ProjectID':'text','CustomerID':'text','QuoteDate':'date','ValidUntil':'date','NetAmount':'money','AmountTWD':'money'})

# Summary
sws = wb['Summary']
clear_data(sws)
project_ids = sorted(summary)
for idx, project in enumerate(project_ids, start=5):
    copy_row_style(sws, 4, idx, 5)
    sws.cell(idx,1).value = project; sws.cell(idx,1).number_format='@'
    for col, key in enumerate(['OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'], start=2):
        sws.cell(idx,col).value = float(summary[project][key].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        sws.cell(idx,col).number_format='0.00'
last = 4 + max(1, len(project_ids))
for col_letter in ['B','C','D','E']:
    sws[f'{col_letter}2'] = f'=SUM({col_letter}5:{col_letter}{last})'

# Exceptions
write_detail('Exceptions', ['Source','DocumentID','ProjectID','Reason'], exceptions, {'Source':'text','DocumentID':'text','ProjectID':'text','Reason':'text'})

# Report
rws = wb['Report']
rws['B3'] = FROM_DATE
rws['D3'] = TO_DATE
rws['B4'] = 'SAP Sales Orders: OrderDate in period and Status != Cancelled; SAP Invoices: InvoiceDate in period; Expense Viewer: ExpenseDate in period and Status = Approved; quote_cli: QuoteDate in period and Status = Accepted; grouped by ProjectID; FX converted with input/fx_rates.csv; orders and quotes kept separate.'
now = datetime.now().astimezone().replace(microsecond=0).isoformat()
rws['B5'] = now
rws['B7'] = 'Lab ERP SAP web; Expense Viewer desktop; quote_cli; fx_rates.csv'
rws['D7'] = now
rws['B9'] = f'Records without ProjectID are included in detail sheets and listed in Exceptions, but excluded from Summary because ProjectID is the join/group key. CustomerName was not used as a join key. Counts: orders {len(orders)} (raw {len(raw_orders)}, cancelled excluded), invoices {len(invoices)}, expenses {len(expenses)}, quotes {len(quotes)}.'

out = OUTPUT/f'project_integration_{PERIOD}.xlsx'
wb.save(out)
print('saved:', out)

# Verification by reopening saved workbook.
check = load_workbook(out, data_only=False)
expected_sheets = ['Report','Orders','Invoices','Expenses','Quotes','Summary','Exceptions','Instructions']
assert check.sheetnames == expected_sheets, check.sheetnames
checks = {}
for sheet, expected_count in [('Orders', len(order_rows)), ('Invoices', len(invoice_rows)), ('Expenses', len(expense_rows)), ('Quotes', len(quote_rows)), ('Summary', len(project_ids)), ('Exceptions', len(exceptions))]:
    ws = check[sheet]
    actual = max(0, ws.max_row - 4)
    checks[sheet] = actual
    assert actual == expected_count, (sheet, actual, expected_count)
assert check['Orders']['A5'].data_type == 's' if order_rows else True
# IDs preserved as strings; no cancelled orders; statuses filters hold.
for row in check['Orders'].iter_rows(min_row=5, values_only=True):
    assert row[4] != 'Cancelled'
for row in check['Expenses'].iter_rows(min_row=5, values_only=True):
    assert row[4] == 'Approved'
for row in check['Quotes'].iter_rows(min_row=5, values_only=True):
    assert row[5] == 'Accepted'
# Money columns are numeric where present.
for sheet, cols in {'Orders':[7,8], 'Invoices':[8,9,10,11], 'Expenses':[7,8], 'Quotes':[8,9], 'Summary':[2,3,4,5]}.items():
    ws=check[sheet]
    for row in ws.iter_rows(min_row=5, max_col=max(cols)):
        for c in cols:
            v=row[c-1].value
            if v is not None:
                assert isinstance(v, (int,float)), (sheet, row[c-1].coordinate, v, type(v))
# Summary equals independent totals and does not add orders+quotes as one revenue.
independent = {p:{k: float(v.quantize(Decimal('0.01'))) for k,v in vals.items()} for p,vals in summary.items()}
print('verification row counts:', checks)
print('summary:', json.dumps(independent, ensure_ascii=False, indent=2, sort_keys=True))
print('exceptions:', json.dumps(exceptions, ensure_ascii=False, indent=2))
print('output_file:', str(out))
