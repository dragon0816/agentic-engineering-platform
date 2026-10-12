from pathlib import Path
p = Path('output/findings.md')
print(p.read_text(encoding='utf-8'))