from pathlib import Path
ws=Path.cwd()
for p in sorted((ws/'output').glob('expenses*.csv')):
    print(p.name, p.stat().st_size)
    print(p.read_text(encoding='utf-8-sig')[:2000])