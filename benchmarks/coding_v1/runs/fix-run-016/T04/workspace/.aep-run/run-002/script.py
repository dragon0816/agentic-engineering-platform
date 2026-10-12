from pathlib import Path
import csv
import hashlib
import shutil
import os

ws = Path.cwd()
input_root = ws / 'input' / 'files'
output_root = ws / 'output'
classified_root = output_root / 'classified'
manifest_path = output_root / 'manifest.csv'

if not input_root.is_dir():
    raise FileNotFoundError(f'Missing input directory: {input_root}')

# Classification rules, case-insensitive and based on suffix without dot.
def category_for(path: Path) -> str:
    ext = path.suffix.lower().lstrip('.')
    if ext == 'pdf':
        return 'PDF'
    if ext in {'xls', 'xlsx'}:
        return 'Excel'
    if ext in {'png', 'jpg', 'jpeg'}:
        return 'Image'
    return 'Other'

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

output_root.mkdir(parents=True, exist_ok=True)
classified_root.mkdir(parents=True, exist_ok=True)

records = []
source_files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_root).as_posix().lower())

for src in source_files:
    rel = src.relative_to(input_root)
    category = category_for(src)
    dst = classified_root / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    records.append({
        'original_path': src.relative_to(ws).as_posix(),
        'new_path': dst.relative_to(ws).as_posix(),
        'sha256': sha256_file(src),
    })

with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(records)

# Verification: reopen outputs and confirm requirements.
print('WROTE_MANIFEST:', manifest_path.relative_to(ws).as_posix())
print('SOURCE_FILE_COUNT:', len(source_files))
print('MANIFEST_RECORD_COUNT:', len(records))

# Read manifest back.
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    print('MANIFEST_COLUMNS:', reader.fieldnames)

assert reader.fieldnames == ['original_path', 'new_path', 'sha256'], 'Manifest columns mismatch'
assert len(rows) == len(source_files), 'Manifest row count mismatch'

category_counts = {'PDF': 0, 'Excel': 0, 'Image': 0, 'Other': 0}
for row in rows:
    original = ws / row['original_path']
    new = ws / row['new_path']
    assert original.is_file(), f'Original path missing: {original}'
    assert new.is_file(), f'New copied file missing: {new}'
    assert str(original).startswith(str(input_root)), f'Original outside input/files: {original}'
    assert str(new).startswith(str(classified_root)), f'New path outside output/classified: {new}'
    rel = original.relative_to(input_root)
    expected_category = category_for(original)
    expected_new = classified_root / expected_category / rel
    assert new == expected_new, f'Wrong classified path for {original}: {new} != {expected_new}'
    src_hash = sha256_file(original)
    dst_hash = sha256_file(new)
    assert row['sha256'] == src_hash, f'SHA mismatch in manifest for {original}'
    assert dst_hash == src_hash, f'Copied file hash differs for {original}'
    assert len(row['sha256']) == 64 and all(c in '0123456789abcdef' for c in row['sha256']), 'SHA-256 format invalid'
    category_counts[expected_category] += 1

# Ensure no outputs were written under input by this script: only inspect names/mtimes impossible to prove generally,
# but all generated paths are under output and copied paths verified.
print('CATEGORY_COUNTS:', category_counts)
print('OUTPUT_FILES:')
for p in sorted(output_root.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(ws).as_posix(), 'size=', p.stat().st_size)
print('CHECKS_PASSED: manifest columns, row count, classified category paths, preserved relative paths, SHA-256 source/copy equality, output under output/classified')
