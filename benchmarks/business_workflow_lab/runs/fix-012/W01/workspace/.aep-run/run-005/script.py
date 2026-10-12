from pathlib import Path
p=Path('output/downloads/all_orders_export.csv')
print(p.exists(), p.stat().st_size if p.exists() else None)
print(p.read_text(encoding='utf-8-sig')[:1000])
