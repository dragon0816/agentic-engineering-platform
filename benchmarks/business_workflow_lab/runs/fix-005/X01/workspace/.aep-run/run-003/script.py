from pathlib import Path
import csv
base=Path('.')
print('input files:', sorted(str(p) for p in (base/'input').iterdir()))
for name in ['sap_manual.md','expense_manual.md','quote_cli_manual.md']:
    p=base/'input'/name
    print('\n---', name, '---')
    print(p.read_text(encoding='utf-8', errors='replace')[:2500])
for name in ['fx_rates.csv']:
    p=base/'input'/name
    print('\n---', name, '---')
    with p.open(newline='', encoding='utf-8-sig') as f:
        r=csv.reader(f)
        for i,row in zip(range(10), r): print(row)
print('\nexisting output files:', sorted(str(p) for p in (base/'output').rglob('*') if p.is_file())[:20])