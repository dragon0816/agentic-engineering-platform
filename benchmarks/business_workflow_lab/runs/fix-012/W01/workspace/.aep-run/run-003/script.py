from pathlib import Path
p=Path('output/downloads/orders_export.csv')
print(p.exists(), p)
if p.exists():
    print(p.read_text(encoding='utf-8-sig')[:2000])
