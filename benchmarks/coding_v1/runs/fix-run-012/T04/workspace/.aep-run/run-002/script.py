from pathlib import Path
import csv
import hashlib
import shutil

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

def category_for(path: Path) -> str:
    return categories.get(path.suffix.lower(), 'Other')

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

output_root.mkdir(parents=True, exist_ok=True)
classified_root.mkdir(parents=True, exist_ok=True)

rows = []
for src in sorted((p for p in input_root.rglob('*') if p.is_file()), key=lambda p: str(p.relative_to(input_root)).lower()):
    rel = src.relative_to(input_root)
    cat = category_for(src)
    dst = classified_root / cat / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    rows.append({
        'original_path': str(src.relative_to(workspace)),
        'new_path': str(dst.relative_to(workspace)),
        'sha256': sha256_file(src),
    })

with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

print('copied_files:', len(rows))
print('manifest:', manifest_path)
for row in rows:
    print(row)