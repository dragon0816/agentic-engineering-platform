from pathlib import Path
import shutil
import hashlib
import csv
import os

workspace = Path.cwd()
input_root = workspace / 'input' / 'files'
output_root = workspace / 'output'
classified_root = output_root / 'classified'
manifest_path = output_root / 'manifest.csv'

if not input_root.exists() or not input_root.is_dir():
    raise FileNotFoundError(f'Input directory not found: {input_root}')

categories = {
    '.pdf': 'PDF',
    '.xls': 'Excel',
    '.xlsx': 'Excel',
    '.png': 'Image',
    '.jpg': 'Image',
    '.jpeg': 'Image',
}

output_root.mkdir(parents=True, exist_ok=True)
classified_root.mkdir(parents=True, exist_ok=True)

files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_root).as_posix().lower())
rows = []

for src in files:
    rel_under_files = src.relative_to(input_root)
    category = categories.get(src.suffix.lower(), 'Other')
    dst = classified_root / category / rel_under_files
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    h = hashlib.sha256()
    with src.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    rows.append({
        'original_path': src.relative_to(workspace).as_posix(),
        'new_path': dst.relative_to(workspace).as_posix(),
        'sha256': h.hexdigest(),
    })

with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

print('copied_files:', len(rows))
print('manifest:', manifest_path.relative_to(workspace).as_posix())
for category in ['PDF', 'Excel', 'Image', 'Other']:
    cat_dir = classified_root / category
    count = len([p for p in cat_dir.rglob('*') if p.is_file()]) if cat_dir.exists() else 0
    print(f'{category}:', count)
print('rows:')
for row in rows:
    print(row['original_path'], '->', row['new_path'], row['sha256'])