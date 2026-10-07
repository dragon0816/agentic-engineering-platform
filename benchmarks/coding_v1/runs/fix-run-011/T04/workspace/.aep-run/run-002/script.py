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

if not input_root.exists() or not input_root.is_dir():
    raise FileNotFoundError(f'Input folder not found: {input_root}')

# Snapshot input metadata before processing to confirm it is not modified.
input_before = {}
for p in sorted(input_root.rglob('*')):
    if p.is_file():
        st = p.stat()
        input_before[p.relative_to(input_root).as_posix()] = (st.st_size, st.st_mtime_ns)

# Prepare output area. Do not touch input.
output_root.mkdir(parents=True, exist_ok=True)
if classified_root.exists():
    shutil.rmtree(classified_root)
classified_root.mkdir(parents=True, exist_ok=True)
if manifest_path.exists():
    manifest_path.unlink()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def category_for(path: Path) -> str:
    ext = path.suffix.lower().lstrip('.')
    if ext == 'pdf':
        return 'PDF'
    if ext in {'xls', 'xlsx'}:
        return 'Excel'
    if ext in {'png', 'jpg', 'jpeg'}:
        return 'Image'
    return 'Other'

rows = []
for src in sorted(p for p in input_root.rglob('*') if p.is_file()):
    rel = src.relative_to(input_root)
    category = category_for(src)
    dst = classified_root / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    digest = sha256_file(src)
    rows.append({
        'original_path': src.relative_to(workspace).as_posix(),
        'new_path': dst.relative_to(workspace).as_posix(),
        'sha256': digest,
    })

with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

# Verification: reopen manifest and every copied output file.
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    read_rows = list(reader)
    if reader.fieldnames != ['original_path', 'new_path', 'sha256']:
        raise AssertionError(f'Unexpected manifest columns: {reader.fieldnames}')

if len(read_rows) != len(input_before):
    raise AssertionError(f'Manifest row count {len(read_rows)} != input file count {len(input_before)}')

seen_sources = set()
seen_dests = set()
for row in read_rows:
    src = workspace / row['original_path']
    dst = workspace / row['new_path']
    if not src.is_file():
        raise AssertionError(f'Manifest source missing: {src}')
    if not dst.is_file():
        raise AssertionError(f'Manifest destination missing: {dst}')
    if not row['new_path'].startswith('output/classified/'):
        raise AssertionError(f'Destination outside output/classified: {row["new_path"]}')
    rel = src.relative_to(input_root)
    expected_category = category_for(src)
    expected_dst = classified_root / expected_category / rel
    if dst != expected_dst:
        raise AssertionError(f'Wrong classified path for {src}: got {dst}, expected {expected_dst}')
    src_hash = sha256_file(src)
    dst_hash = sha256_file(dst)
    if row['sha256'] != src_hash:
        raise AssertionError(f'Manifest SHA mismatch for {src}')
    if dst_hash != src_hash:
        raise AssertionError(f'Copied file SHA mismatch for {dst}')
    seen_sources.add(row['original_path'])
    seen_dests.add(row['new_path'])

if len(seen_sources) != len(input_before) or len(seen_dests) != len(input_before):
    raise AssertionError('Duplicate source or destination rows found in manifest')

# Confirm input files were not modified.
input_after = {}
for p in sorted(input_root.rglob('*')):
    if p.is_file():
        st = p.stat()
        input_after[p.relative_to(input_root).as_posix()] = (st.st_size, st.st_mtime_ns)
if input_after != input_before:
    raise AssertionError('Input files changed during processing')

# Print concise summary and manifest rows.
print('Created:', manifest_path.relative_to(workspace).as_posix())
print('Copied files:', len(read_rows))
counts = {'PDF': 0, 'Excel': 0, 'Image': 0, 'Other': 0}
for row in read_rows:
    parts = Path(row['new_path']).parts
    # output/classified/<category>/...
    counts[parts[2]] += 1
print('Category counts:', counts)
print('Verified: manifest columns, row count, destination categories/relative paths, SHA-256 hashes, copied file hashes, and input file metadata unchanged.')
print('Manifest:')
for row in read_rows:
    print(f"{row['original_path']} -> {row['new_path']} {row['sha256']}")
