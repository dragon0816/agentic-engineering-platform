from pathlib import Path
repo=Path('../../../../..').resolve().parent
p=repo/'tests/test_product_e2e_02.py'
txt=p.read_text(encoding='utf-8', errors='replace')
print(txt[:5000])