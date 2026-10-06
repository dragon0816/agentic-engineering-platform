from pathlib import Path
p=Path('input/specs.md')
print(p.read_text(encoding='utf-8'))
