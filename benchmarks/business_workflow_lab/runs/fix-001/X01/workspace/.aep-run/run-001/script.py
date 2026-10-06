from pathlib import Path
import csv, zipfile
ws=Path.cwd()
print('cwd', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, p.stat().st_size)
print('\nfx_rates.csv sample:')
with open(ws/'input'/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    r=csv.reader(f)
    for i,row in zip(range(10), r): print(row)
print('\nmanual headers/snippets:')
for name in ['sap_manual.md','expense_manual.md','quote_cli_manual.md']:
    p=ws/'input'/name
    print('\n##', name)
    txt=p.read_text(encoding='utf-8')
    print(txt[:2000])
print('\nproject_template.xlsx workbook structure:')
p=ws/'input'/'project_template.xlsx'
with zipfile.ZipFile(p) as z:
    print('xlsx entries count', len(z.namelist()))
    print([n for n in z.namelist() if n.startswith('xl/worksheets/')][:10])
