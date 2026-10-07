from pathlib import Path
import csv
import hashlib
import os
import shutil

workspace = Path.cwd()
input_root = workspace / 'input' / 'files'
output_root = workspace / 'output'
classified_root = output_root / 'classified'
manifest_path = output_root / 'manifest.csv'

if not input_root.is_dir():
    raise FileNotFoundError(f'Missing input directory: {input_root}')

# Record input metadata before any output work, to confirm input remains unchanged.
def file_metadata(root: Path):
    records = {}
    for p in sorted(root.rglob('*')):
        if p.is_file():
            st = p.stat()
            records[str(p.relative_to(root).as_posix())] = (st.st_size, st.st_mtime_ns)
    return records

before_input_meta = file_metadata(input_root)

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

# Ensure output destinations exist. Do not remove or change input.
classified_root.mkdir(parents=True, exist_ok=True)

rows = []
files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_root).as_posix().lower())
for src in files:
    rel = src.relative_to(input_root)
    category = categories.get(src.suffix.lower(), 'Other')
    dst = classified_root / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    digest = sha256_file(src)
    rows.append({
        'original_path': (Path('input') / 'files' / rel).as_posix(),
        'new_path': (Path('output') / 'classified' / category / rel).as_posix(),
        'sha256': digest,
    })

output_root.mkdir(parents=True, exist_ok=True)
with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

# Validation: reopen manifest and all copied files; check all requirements.
errors = []
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    manifest_rows = list(csv.DictReader(f))

expected_headers = ['original_path', 'new_path', 'sha256']
if manifest_rows:
    # DictReader fieldnames from file
    pass
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    headers = next(reader, None)
if headers != expected_headers:
    errors.append(f'Manifest headers mismatch: {headers} != {expected_headers}')

if len(manifest_rows) != len(files):
    errors.append(f'Manifest row count {len(manifest_rows)} != input file count {len(files)}')

seen_new = set()
for row in manifest_rows:
    for col in expected_headers:
        if col not in row or row[col] == '':
            errors.append(f'Missing value in {col}: {row}')
    src = workspace / row['original_path']
    dst = workspace / row['new_path']
    if not src.is_file():
        errors.append(f'Original path not found: {src}')
        continue
    if not dst.is_file():
        errors.append(f'New path not found: {dst}')
        continue
    if row['sha256'] != sha256_file(src):
        errors.append(f'SHA mismatch for original {src}')
    if row['sha256'] != sha256_file(dst):
        errors.append(f'SHA mismatch for copied {dst}')
    src_rel = src.relative_to(input_root)
    suffix = src.suffix.lower()
    expected_category = categories.get(suffix, 'Other')
    expected_dst = classified_root / expected_category / src_rel
    if dst != expected_dst:
        errors.append(f'Wrong destination for {src}: {dst} != {expected_dst}')
    if row['new_path'] in seen_new:
        errors.append(f'Duplicate new_path in manifest: {row["new_path"]}')
    seen_new.add(row['new_path'])

# Check classification directories and expected copies exist preserving relative path.
for src in files:
    rel = src.relative_to(input_root)
    expected_category = categories.get(src.suffix.lower(), 'Other')
    dst = classified_root / expected_category / rel
    if not dst.is_file():
        errors.append(f'Missing classified copy: {dst}')

# Confirm input metadata unchanged.
after_input_meta = file_metadata(input_root)
if before_input_meta != after_input_meta:
    errors.append('Input files metadata changed')

print('Created:', classified_root.relative_to(workspace))
print('Created:', manifest_path.relative_to(workspace))
print('Input file count:', len(files))
print('Manifest row count:', len(manifest_rows))
print('Category counts:')
category_counts = {}
for row in manifest_rows:
    parts = Path(row['new_path']).parts
    # output/classified/<category>/...
    category = parts[2] if len(parts) >= 3 else '(invalid)'
    category_counts[category] = category_counts.get(category, 0) + 1
for k in ['PDF', 'Excel', 'Image', 'Other']:
    print(f' - {k}: {category_counts.get(k, 0)}')
print('Manifest preview:')
for row in manifest_rows[:10]:
    print(row)

if errors:
    print('VALIDATION ERRORS:')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print('Validation passed: manifest headers/rows, destination categories, preserved relative paths, SHA-256 of originals and copies, and input metadata unchanged.')
