from pathlib import Path
import csv, openpyxl, json
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES')
for p in sorted((ws/'input').glob('*')):
    print(' -', p.relative_to(ws), p.stat().st_size)
print('OUTPUT FILES')
for p in sorted((ws/'output').rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(ws), p.stat().st_size)
for name in ['input/fx_rates.csv', 'output/downloads/sales_orders_export.csv']:
    path = ws/name
    print('\nCSV', name, 'exists', path.exists())
    if path.exists():
        with path.open(newline='', encoding='utf-8-sig') as f:
            reader=csv.DictReader(f)
            rows=list(reader)
        print('headers:', reader.fieldnames)
        print('rows:', len(rows))
        print('sample:', rows[:5])
xlsx = ws/'output'/'september_open_orders.xlsx'
print('\nXLSX exists', xlsx.exists())
if xlsx.exists():
    wb = openpyxl.load_workbook(xlsx, data_only=False)
    print('sheets:', wb.sheetnames)
    for s in wb.sheetnames:
        sh=wb[s]
        print('sheet', s, 'max', sh.max_row, sh.max_column)
        for r in range(1, min(sh.max_row,8)+1):
            print(s, r, [sh.cell(r,c).value for c in range(1, min(sh.max_column,12)+1)])