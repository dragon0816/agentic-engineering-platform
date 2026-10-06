from pathlib import Path
import hashlib
import shutil
import csv
import os

workspace = Path.cwd()
input_root = workspace / 'input' / 'files'
output_root = workspace / 'output'
classified_root = output_root / 'classified'
manifest_path = output_root / 'manifest.csv'

# Inspect inputs first (per task discipline)
print('workspace:', workspace)
print('input_root:', input_root, 'exists=', input_root.exists())
input_files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: str(p.relative_to(input_root)).lower())
print('input file count:', len(input_files))
for p in input_files:
    print('INPUT', p.relative_to(input_root).as_posix(), 'suffix=', p.suffix, 'size=', p.stat().st_size)

if not input_root.exists():
    raise FileNotFoundError(f'Missing input folder: {input_root}')

# Prepare output. Do not touch input.
output_root.mkdir(parents=True, exist_ok=True)
if classified_root.exists():
    shutil.rmtree(classified_root)
classified_root.mkdir(parents=True, exist_ok=True)
if manifest_path.exists():
    manifest_path.unlink()

categories = {
    'pdf': 'PDF',
    'xls': 'Excel',
    'xlsx': 'Excel',
    'png': 'Image',
    'jpg': 'Image',
    'jpeg': 'Image',
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

rows = []
for src in input_files:
    rel = src.relative_to(input_root)
    ext = src.suffix[1:].lower() if src.suffix else ''
    category = categories.get(ext, 'Other')
    dst = classified_root / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    digest = sha256_file(src)
    rows.append({
        'original_path': str((Path('input') / 'files' / rel).as_posix()),
        'new_path': str((Path('output') / 'classified' / category / rel).as_posix()),
        'sha256': digest,
    })

with manifest_path.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

# Verification from saved outputs
errors = []
if not manifest_path.exists():
    errors.append('manifest.csv missing')

with manifest_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    saved_rows = list(reader)
    saved_fields = reader.fieldnames

expected_fields = ['original_path', 'new_path', 'sha256']
if saved_fields != expected_fields:
    errors.append(f'fieldnames mismatch: {saved_fields} != {expected_fields}')
if len(saved_rows) != len(input_files):
    errors.append(f'row count mismatch: {len(saved_rows)} != {len(input_files)}')

seen_originals = set()
seen_new = set()
for row in saved_rows:
    original_path = row.get('original_path', '')
    new_path = row.get('new_path', '')
    digest = row.get('sha256', '')
    seen_originals.add(original_path)
    seen_new.add(new_path)
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        errors.append(f'invalid sha256 format for {original_path}: {digest}')
    src = workspace / original_path
    dst = workspace / new_path
    if not src.exists():
        errors.append(f'source path listed does not exist: {original_path}')
        continue
    if not dst.exists():
        errors.append(f'destination path listed does not exist: {new_path}')
        continue
    rel = src.relative_to(input_root)
    ext = src.suffix[1:].lower() if src.suffix else ''
    expected_category = categories.get(ext, 'Other')
    expected_new = (Path('output') / 'classified' / expected_category / rel).as_posix()
    if new_path != expected_new:
        errors.append(f'wrong classified path for {original_path}: {new_path} != {expected_new}')
    src_hash = sha256_file(src)
    dst_hash = sha256_file(dst)
    if digest != src_hash:
        errors.append(f'manifest hash mismatch for {original_path}')
    if dst_hash != src_hash:
        errors.append(f'copied file hash mismatch for {original_path}')

expected_originals = {(Path('input') / 'files' / p.relative_to(input_root)).as_posix() for p in input_files}
if seen_originals != expected_originals:
    errors.append('manifest original_path set mismatch')

# Ensure classified file count matches input files and no extra stale files.
classified_files = sorted([p for p in classified_root.rglob('*') if p.is_file()])
if len(classified_files) != len(input_files):
    errors.append(f'classified file count mismatch: {len(classified_files)} != {len(input_files)}')

# Category summary
category_counts = {}
for p in classified_files:
    rel = p.relative_to(classified_root)
    category_counts[rel.parts[0]] = category_counts.get(rel.parts[0], 0) + 1

print('manifest:', manifest_path)
print('classified root:', classified_root)
print('manifest rows:', len(saved_rows))
print('classified files:', len(classified_files))
print('category counts:', category_counts)
print('sample manifest rows:')
for row in saved_rows:
    print(row)

if errors:
    print('CHECK FAILED')
    for e in errors:
        print('ERROR:', e)
    raise SystemExit(1)

print('CHECK PASSED: manifest columns, row count, classification paths, SHA-256 values, copied file hashes, and classified file count all verified from saved outputs.')