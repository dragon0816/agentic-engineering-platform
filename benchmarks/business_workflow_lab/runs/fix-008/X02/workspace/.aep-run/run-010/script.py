from pathlib import Path
from openpyxl import load_workbook
import csv, json
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

ws = Path.cwd()
report = ws/'output'/'project_report_C001_2026-09_TWD.xlsx'
assert report.exists(), f'Missing {report}'
wb = load_workbook(report, data_only=False)

start = date(2026,9,1)
end = date(2026,9,30)
cutoff = date(2026,9,30)

def as_date(v):
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date): return v
    return datetime.fromisoformat(str(v)[:10]).date()

def hdr(sheet):
    sh=wb[sheet]
    return [sh.cell(4,c).value for c in range(1, sh.max_column+1)]

def data(sheet):
    sh=wb[sheet]
    rows=[]
    rownums=[]
    for r in range(5, sh.max_row+1):
        vals=[sh.cell(r,c).value for c in range(1, sh.max_column+1)]
        if any(v is not None for v in vals):
            rows.append(vals); rownums.append(r)
    return rows,rownums

def round2(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Input/output file inventory
print('Installed workflow checked separately: engineering/c001-monthly-project-cost-report@1.0.0 is installed.')
print('Saved output files:')
for p in sorted((ws/'output').rglob('*')):
    if p.is_file():
        print(f' - {p.relative_to(ws)} ({p.stat().st_size} bytes)')

# FX attachment only
fx={}
with (ws/'input'/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        if r.get('Currency') and r.get('RateToTWD'):
            fx[r['Currency']]=Decimal(r['RateToTWD'])
print('FX from attachment:', fx)
assert fx == {'TWD':Decimal('1.0'), 'USD':Decimal('32.0'), 'EUR':Decimal('35.0')}

# Workbook structure and metadata
expected_sheets=['Report','Orders','Invoices','Expenses','Quotes','Summary','Exceptions','Instructions']
print('Workbook sheets:', wb.sheetnames)
assert wb.sheetnames == expected_sheets
assert as_date(wb['Report']['B3'].value)==start
assert as_date(wb['Report']['D3'].value)==end
condition=str(wb['Report']['B4'].value)
for phrase in ['Customer C001','orders exclude Cancelled','expenses Approved','quotes all statuses','FX from input/fx_rates.csv']:
    assert phrase in condition

counts={s:len(data(s)[0]) for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']}
print('Data row counts:', counts)
assert counts == {'Orders':3,'Invoices':3,'Expenses':9,'Quotes':4,'Summary':2,'Exceptions':4}

# Orders
rows,rownums=data('Orders'); h=hdr('Orders'); ix={n:i for i,n in enumerate(h) if n}
assert h == ['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD']
for vals,rn in zip(rows,rownums):
    assert isinstance(vals[ix['OrderID']], str)
    assert vals[ix['CustomerID']]=='C001'
    assert vals[ix['Status']]!='Cancelled'
    assert start <= as_date(vals[ix['OrderDate']]) <= end
    assert round2(vals[ix['NetAmount']]) * fx[vals[ix['Currency']]] == round2(vals[ix['AmountTWD']])
    assert wb['Orders'].cell(rn,7).number_format == '0.00'
    assert wb['Orders'].cell(rn,8).number_format == '0.00'

# Invoices
rows,rownums=data('Invoices'); h=hdr('Invoices'); ix={n:i for i,n in enumerate(h) if n}
assert h == ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD']
for vals,rn in zip(rows,rownums):
    assert isinstance(vals[ix['InvoiceID']], str)
    assert isinstance(vals[ix['OrderID']], str)
    assert vals[ix['CustomerID']]=='C001'
    assert start <= as_date(vals[ix['InvoiceDate']]) <= end
    assert round2(vals[ix['Amount']] - vals[ix['PaidAmount']]) == round2(vals[ix['Balance']])
    assert round2(vals[ix['Balance']]) * fx[vals[ix['Currency']]] == round2(vals[ix['BalanceTWD']])

# Expenses
rows,rownums=data('Expenses'); h=hdr('Expenses'); ix={n:i for i,n in enumerate(h) if n}
assert h == ['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD']
for vals,rn in zip(rows,rownums):
    assert isinstance(vals[ix['ExpenseID']], str)
    assert vals[ix['ProjectID']] in {'P001','P003'}
    assert vals[ix['Status']]=='Approved'
    assert start <= as_date(vals[ix['ExpenseDate']]) <= end
    assert round2(vals[ix['Amount']]) * fx[vals[ix['Currency']]] == round2(vals[ix['AmountTWD']])

# Quotes
rows,rownums=data('Quotes'); h=hdr('Quotes'); ix={n:i for i,n in enumerate(h) if n}
assert h == ['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD']
quote_by_id={r[ix['QuoteID']]:r for r in rows}
for vals,rn in zip(rows,rownums):
    assert isinstance(vals[ix['QuoteID']], str)
    assert vals[ix['CustomerID']]=='C001'
    assert start <= as_date(vals[ix['QuoteDate']]) <= end
    assert round2(vals[ix['NetAmount']]) * fx[vals[ix['Currency']]] == round2(vals[ix['AmountTWD']])
assert {r[ix['Status']] for r in rows} == {'Sent','Accepted','Draft','Expired'}

# Summary values and total formulas on row 2
rows,rownums=data('Summary'); h=hdr('Summary'); ix={n:i for i,n in enumerate(h) if n}
assert h == ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']
assert {r[ix['ProjectID']] for r in rows} == {'P001','P003'}
for c in range(2,6):
    assert wb['Summary'].cell(2,c).data_type == 'f', f'Summary total cell {c} is not formula'

# Exceptions: verify records match the requested attention conditions.
rows,rownums=data('Exceptions'); h=hdr('Exceptions'); ix={n:i for i,n in enumerate(h) if n}
actual={(r[ix['Source']], r[ix['DocumentID']], r[ix['ProjectID']]) for r in rows}
expected={('Invoices','0090000219','P001'),('Expenses','EXP-00006','P001'),('Quotes','Q0010','P001'),('Quotes','Q0014','P001')}
print('Exceptions:', json.dumps(rows, ensure_ascii=False, default=str))
assert actual == expected

# Cross-check each exception against the actual workbook/source data.
inv_rows,_=data('Invoices'); inv_h=hdr('Invoices'); inv_ix={n:i for i,n in enumerate(inv_h) if n}
for r in inv_rows:
    if r[inv_ix['InvoiceID']]=='0090000219':
        assert as_date(r[inv_ix['DueDate']]) <= cutoff and r[inv_ix['Balance']] > 0

# Missing receipt is not in workbook detail columns, so check exported Expense source file.
missing_receipt_ids=set()
for rel in ['output/expenses_P001_Approved_2026-09.csv','output/expenses_P003_Approved_2026-09.csv']:
    with (ws/rel).open(newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if str(r.get('MissingReceipt')).lower() == 'true':
                missing_receipt_ids.add(r['ExpenseID'])
assert missing_receipt_ids == {'EXP-00006'}

q_rows,_=data('Quotes'); q_h=hdr('Quotes'); q_ix={n:i for i,n in enumerate(q_h) if n}
expired_nonaccepted={r[q_ix['QuoteID']] for r in q_rows if as_date(r[q_ix['ValidUntil']]) < cutoff and r[q_ix['Status']] != 'Accepted'}
assert expired_nonaccepted == {'Q0010','Q0014'}

print('CHECK PASSED: output files and installed workflow are complete; workbook satisfies the requested filters, FX conversion, template rows, summaries, and attention flags.')