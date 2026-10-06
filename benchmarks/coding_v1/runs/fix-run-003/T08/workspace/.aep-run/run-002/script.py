from pathlib import Path
import json
base=Path.cwd()
for p in sorted((base/'input').iterdir()):
    print('\n---', p.name, '---')
    txt=p.read_text(encoding='utf-8-sig')
    print(txt[:1000])
print('\n--- current output ---')
print((base/'output'/'reports.json').read_text(encoding='utf-8')[:2000])