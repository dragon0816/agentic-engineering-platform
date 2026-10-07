from pathlib import Path
import json
ws = Path.cwd()
inp = ws / 'input'
out = ws / 'output'
print('workspace:', ws)
print('input exists:', inp.exists())
print('output exists:', out.exists())
for p in sorted(inp.iterdir() if inp.exists() else []):
    print('\nFILE:', p.name, 'size:', p.stat().st_size)
    try:
        text = p.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        text = p.read_text(encoding='utf-8-sig')
    lines = text.splitlines()
    print('line_count:', len(lines))
    for i, line in enumerate(lines[:5], 1):
        print(f'  sample {i}:', line[:300])