import os, json, csv
from pathlib import Path
from openpyxl import load_workbook

ws = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-011\X01\workspace')
out = ws/'output'
print('Workspace:', ws)
print('Output exists:', out.exists())
print('Output files:')
for p in sorted(out.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(ws), p.stat().st_size)

# Find likely deliverables
xlsx_files = sorted(out.glob('*.xlsx'))
json_files = sorted(out.glob('*.json'))
csv_files = sorted(out.glob('*.csv'))
print('Top-level xlsx:', [p.name for p in xlsx_files])
print('Top-level json:', [p.name for p in json_files])
print('Top-level csv:', [p.name for p in csv_files])

# Inspect all xlsx outputs
for xlsx in xlsx_files:
    print('\nWorkbook:', xlsx.name)
    wb = load_workbook(xlsx, data_only=False)
    print('Sheets:', wb.sheetnames)
    for sname in wb.sheetnames:
        sh = wb[sname]
        max_r = sh.max_row
        max_c = sh.max_column
        headers = [sh.cell(1,c).value for c in range(1, max_c+1)]
        print(' Sheet', sname, 'rows', max_r, 'cols', max_c, 'headers', headers)
        for r in range(2, min(max_r, 6)+1):
            print('  row', r, [sh.cell(r,c).value for c in range(1, max_c+1)])

# Inspect JSON validations/summaries
for jf in json_files:
    print('\nJSON:', jf.name)
    try:
        data=json.load(open(jf, encoding='utf-8'))
    except Exception as e:
        print(' Could not load JSON:', e)
        continue
    print(json.dumps(data, ensure_ascii=False, indent=2)[:6000])

# Inspect CSV headers/counts
for cf in csv_files:
    print('\nCSV:', cf.name)
    with open(cf, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows=list(reader)
    print(' headers:', reader.fieldnames)
    print(' rows:', len(rows))
    print(' sample:', rows[:3])

# Validate stated requirements on main workbook, if present
candidate_names = ['project_financials_2026-09.xlsx', 'project_report_2026-09.xlsx', 'project_template_filled_2026-09.xlsx']
main = None
for name in candidate_names:
    p=out/name
    if p.exists():
        main=p; break
if main is None and xlsx_files:
    main = xlsx_files[0]
print('\nMain workbook selected:', main.name if main else None)
checks = []
if main:
    wb = load_workbook(main, data_only=True)
    # locate summary sheet and header row
    sheet = 'Summary' if 'Summary' in wb.sheetnames else wb.sheetnames[0]
    sh = wb[sheet]
    headers = [sh.cell(1,c).value for c in range(1, sh.max_column+1)]
    required_cols = ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']
    for col in required_cols:
        checks.append((f'{col} column exists in {sheet}', col in headers))
    if all(col in headers for col in required_cols):
        idx={h:i+1 for i,h in enumerate(headers)}
        project_ids=[]
        numeric_ok=True
        for r in range(2, sh.max_row+1):
            pid=sh.cell(r,idx['ProjectID']).value
            if pid is not None and str(pid).strip()!='':
                project_ids.append(str(pid))
            for col in required_cols[1:]:
                v=sh.cell(r,idx[col]).value
                if v is not None and not isinstance(v,(int,float)):
                    numeric_ok=False
        checks.append(('ProjectID values present in summary rows', len(project_ids)>0))
        checks.append(('Financial summary columns are numeric or blank', numeric_ok))
        # Check there is no obvious combined revenue column summing order+quote
        forbidden=[h for h in headers if h and str(h).lower().replace(' ','') in ('revenue','totrevenue','totalrevenue','營收')]
        checks.append(('No obvious revenue column that could combine orders and quotes', len(forbidden)==0))
    # Exceptions sheet exists and has expected marker info if any exceptions
    checks.append(('Exceptions sheet exists', 'Exceptions' in wb.sheetnames))

print('\nRequirement checks:')
for name, ok in checks:
    print(('PASS' if ok else 'FAIL'), '-', name)
if checks and not all(ok for _,ok in checks):
    raise SystemExit('Some checks failed')
print('CHECK_COMPLETE')