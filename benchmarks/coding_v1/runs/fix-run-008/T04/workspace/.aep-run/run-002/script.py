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

if not input_root.exists():
    raise FileNotFoundError(f'Input folder not found: {input_root}')

# Snapshot input before work to prove we do not modify it.
def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

input_files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: str(p.relative_to(input_root)).lower())
before = {str(p.relative_to(input_root)): (p.stat().st_size, file_digest(p)) for p in input_files}

# Start from a clean destination for deterministic results.
if classified_root.exists():
    shutil.rmtree(classified_root)
classified_root.mkdir(parents=True, exist_ok=True)
output_root.mkdir(parents=True, exist_ok=True)

category_by_ext = {
    '.pdf': 'PDF',
    '.xls': 'Excel',
    '.xlsx': 'Excel',
    '.png': 'Image',
    '.jpg': 'Image',
    '.jpeg': 'Image',
}

rows = []
for src in input_files:
    rel = src.relative_to(input_root)
    category = category_by_ext.get(src.suffix.lower(), 'Other')
    dst = classified_root / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    rows.append({
        'original_path': str(Path('input') / 'files' / rel).replace(os.sep, '/'),
        'new_path': str(Path('output') / 'classified' / category / rel).replace(os.sep, '/'),
        'sha256': file_digest(src),
    })

with manifest_path.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

# Verification: reopen outputs and check all requirements.
errors = []
# 1. Manifest exists and has required columns/row count.
with manifest_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    manifest_rows = list(reader)
    if reader.fieldnames != ['original_path', 'new_path', 'sha256']:
        errors.append(f'Bad manifest columns: {reader.fieldnames}')
if len(manifest_rows) != len(input_files):
    errors.append(f'Manifest row count {len(manifest_rows)} != input file count {len(input_files)}')

# 2. Each row's source/destination/SHA/category is correct, and copied bytes match.
seen_new = set()
for row in manifest_rows:
    for col in ['original_path', 'new_path', 'sha256']:
        if col not in row or row[col] == '':
            errors.append(f'Missing value in {col}: {row}')
    orig = workspace / Path(row['original_path'])
    new = workspace / Path(row['new_path'])
    if not orig.exists():
        errors.append(f'Original path missing from manifest: {row["original_path"]}')
        continue
    if not new.exists():
        errors.append(f'Copied file missing: {row["new_path"]}')
        continue
    expected_sha = file_digest(orig)
    copied_sha = file_digest(new)
    if row['sha256'] != expected_sha:
        errors.append(f'Manifest SHA mismatch for {row["original_path"]}: {row["sha256"]} != {expected_sha}')
    if copied_sha != expected_sha:
        errors.append(f'Copied file SHA mismatch for {row["new_path"]}')
    rel = orig.relative_to(input_root)
    expected_category = category_by_ext.get(orig.suffix.lower(), 'Other')
    expected_new = Path('output') / 'classified' / expected_category / rel
    if Path(row['new_path']) != expected_new:
        errors.append(f'Wrong new path for {row["original_path"]}: {row["new_path"]} != {expected_new}')
    seen_new.add(str(new))

# 3. Ensure all copied files under classified are represented in manifest.
classified_files = sorted([p for p in classified_root.rglob('*') if p.is_file()], key=lambda p: str(p).lower())
if len(classified_files) != len(input_files):
    errors.append(f'Classified file count {len(classified_files)} != input file count {len(input_files)}')
for p in classified_files:
    if str(p) not in seen_new:
        errors.append(f'Classified file not listed in manifest: {p.relative_to(workspace)}')

# 4. Confirm input unchanged by size and SHA.
after_files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: str(p.relative_to(input_root)).lower())
after = {str(p.relative_to(input_root)): (p.stat().st_size, file_digest(p)) for p in after_files}
if before != after:
    errors.append('Input files changed during processing')

# 5. Summary counts by category.
counts = {}
for p in classified_files:
    rel_parts = p.relative_to(classified_root).parts
    counts[rel_parts[0]] = counts.get(rel_parts[0], 0) + 1

print('created:', manifest_path.relative_to(workspace))
print('created_classified_root:', classified_root.relative_to(workspace))
print('input_file_count:', len(input_files))
print('manifest_row_count:', len(manifest_rows))
print('classified_file_count:', len(classified_files))
print('category_counts:', counts)
print('manifest_rows:')
for row in manifest_rows:
    print(row)

if errors:
    print('VERIFICATION FAILED')
    for e in errors:
        print('ERROR:', e)
    raise SystemExit(1)
print('VERIFICATION PASSED: manifest columns, row count, category paths, copied SHA-256 values, and unchanged input files confirmed.')
