from pathlib import Path
import json
ws = Path.cwd()
input_dir = ws/'input'
output_dir = ws/'output'
print('workspace=', ws)
print('input exists=', input_dir.exists())
print('output exists=', output_dir.exists())
files = sorted([p for p in input_dir.iterdir() if p.is_file()]) if input_dir.exists() else []
print('input files:', [p.name for p in files])
for p in files:
    print('\n---', p.name, 'size', p.stat().st_size, '---')
    try:
        text = p.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        text = p.read_text(encoding='utf-8-sig')
    for i, line in enumerate(text.splitlines()[:8], 1):
        print(f'{i}: {line[:300]}')
