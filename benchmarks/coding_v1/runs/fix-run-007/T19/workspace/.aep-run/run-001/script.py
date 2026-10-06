import os, csv, json
from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input exists:', input_dir.exists())
print('output exists:', output_dir.exists())
print('input files:', [p.name for p in sorted(input_dir.iterdir())] if input_dir.exists() else [])
csv_path = input_dir / 'mixed.csv'
print('mixed.csv exists:', csv_path.exists())
if csv_path.exists():
    raw = csv_path.read_bytes()
    print('byte length:', len(raw))
    print('starts UTF-8 BOM:', raw.startswith(b'\xef\xbb\xbf'))
    text = raw.decode('utf-8-sig')
    print('char length:', len(text))
    reader = csv.reader(text.splitlines(keepends=True))
    rows = []
    for i, row in enumerate(reader):
        rows.append(row)
        if i >= 5:
            break
    print('sample rows as JSON:')
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    if rows:
        print('headers:', rows[0])
        print('column count:', len(rows[0]))