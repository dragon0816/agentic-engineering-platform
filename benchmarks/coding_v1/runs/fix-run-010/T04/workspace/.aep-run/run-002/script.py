from pathlib import Path
import shutil
import hashlib
import csv

workspace = Path.cwd()
input_root = workspace / 'input' / 'files'
output_root = workspace / 'output'
classified_root = output_root / 'classified'
manifest_path = output_root / 'manifest.csv'

if not input_root.exists() or not input_root.is_dir():
    raise FileNotFoundError(f'Missing input directory: {input_root}')

categories = {
    '.pdf': 'PDF',
    '.xls': 'Excel',
    '.xlsx': 'Excel',
    '.png': 'Image',
    '.jpg': 'Image',
    '.jpeg': 'Image',
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

# Prepare output folders. Only touch output, never input.
output_root.mkdir(parents=True, exist_ok=True)
classified_root.mkdir(parents=True, exist_ok=True)
for category in ['PDF', 'Excel', 'Image', 'Other']:
    (classified_root / category).mkdir(parents=True, exist_ok=True)

rows = []
source_files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_root).as_posix().lower())

for src in source_files:
    rel = src.relative_to(input_root)
    category = categories.get(src.suffix.lower(), 'Other')
    dst = classified_root / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    digest = sha256_file(src)
    rows.append({
        'original_path': str(Path('input') / 'files' / rel),
        'new_path': str(Path('output') / 'classified' / category / rel),
        'sha256': digest,
    })

with manifest_path.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

print('Copied files:', len(rows))
print('Manifest:', manifest_path)
for category in ['PDF', 'Excel', 'Image', 'Other']:
    count = sum(1 for p in (classified_root / category).rglob('*') if p.is_file())
    print(f'{category}: {count}')
