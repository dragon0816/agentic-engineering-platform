from pathlib import Path
p=Path('output/expense_export_E006_2026-01-01_2026-01-31.csv')
print('exists', p.exists())
if p.exists():
    print('size', p.stat().st_size)
    print(p.read_text(encoding='utf-8-sig')[:500])
print('output files:', [x.name for x in Path('output').glob('*')])