from pathlib import Path
import shutil
import hashlib
import csv
import os

workspace = Path.cwd()
input_base = workspace / 'input' / 'files'
output_base = workspace / 'output'
classified_base = output_base / 'classified'
manifest_path = output_base / 'manifest.csv'

if not input_base.exists() or not input_base.is_dir():
    raise FileNotFoundError(f'Missing input folder: {input_base}')

# Snapshot input metadata and hashes before processing to verify inputs remain unchanged.
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

input_files = sorted([p for p in input_base.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_base).as_posix())
input_snapshot = {
    p.relative_to(input_base).as_posix(): {
        'size': p.stat().st_size,
        'mtime_ns': p.stat().st_mtime_ns,
        'sha256': sha256_file(p),
    }
    for p in input_files
}

print('Discovered input files:')
for rel, meta in input_snapshot.items():
    print(f'  {rel} size={meta["size"]} sha256={meta["sha256"]}')

# Prepare output area. Only output files/folders are changed.
output_base.mkdir(parents=True, exist_ok=True)
if classified_base.exists():
    shutil.rmtree(classified_base)
classified_base.mkdir(parents=True, exist_ok=True)
if manifest_path.exists():
    manifest_path.unlink()

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
    rel_path = src.relative_to(input_base)
    ext = src.suffix.lower()
    category = category_by_ext.get(ext, 'Other')
    dst = classified_base / category / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    digest = sha256_file(src)
    rows.append({
        'original_path': (Path('input') / 'files' / rel_path).as_posix(),
        'new_path': dst.relative_to(workspace).as_posix(),
        'sha256': digest,
    })

with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

# Verification: reopen manifest and all outputs; confirm categories, paths, hashes, row count, columns, and unchanged input metadata.
errors = []
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    manifest_rows = list(reader)
    if reader.fieldnames != ['original_path', 'new_path', 'sha256']:
        errors.append(f'Unexpected manifest columns: {reader.fieldnames}')

if len(manifest_rows) != len(input_files):
    errors.append(f'Manifest row count {len(manifest_rows)} != input file count {len(input_files)}')

seen_originals = set()
for row in manifest_rows:
    original_path = row.get('original_path', '')
    new_path = row.get('new_path', '')
    digest = row.get('sha256', '')
    if not original_path.startswith('input/files/'):
        errors.append(f'Original path is not under input/files: {original_path}')
        continue
    rel = Path(original_path).relative_to(Path('input') / 'files')
    rel_posix = rel.as_posix()
    seen_originals.add(rel_posix)
    src = input_base / rel
    if not src.exists():
        errors.append(f'Missing source referenced by manifest: {original_path}')
        continue
    expected_category = category_by_ext.get(src.suffix.lower(), 'Other')
    expected_new = (Path('output') / 'classified' / expected_category / rel).as_posix()
    if new_path != expected_new:
        errors.append(f'Bad new path for {original_path}: {new_path} != {expected_new}')
    dst = workspace / new_path
    if not dst.exists() or not dst.is_file():
        errors.append(f'Copied file missing: {new_path}')
        continue
    src_hash = sha256_file(src)
    dst_hash = sha256_file(dst)
    if digest != src_hash:
        errors.append(f'Manifest SHA mismatch for {original_path}: {digest} != {src_hash}')
    if dst_hash != src_hash:
        errors.append(f'Copied file SHA mismatch for {new_path}: {dst_hash} != {src_hash}')
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        errors.append(f'SHA-256 is not lowercase 64-char hex for {original_path}: {digest}')

expected_originals = set(input_snapshot.keys())
if seen_originals != expected_originals:
    errors.append(f'Manifest originals mismatch. Missing={sorted(expected_originals-seen_originals)} Extra={sorted(seen_originals-expected_originals)}')

# Verify input files unchanged.
after_files = sorted([p for p in input_base.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_base).as_posix())
after_snapshot = {
    p.relative_to(input_base).as_posix(): {
        'size': p.stat().st_size,
        'mtime_ns': p.stat().st_mtime_ns,
        'sha256': sha256_file(p),
    }
    for p in after_files
}
if after_snapshot != input_snapshot:
    errors.append('Input file metadata/hash changed during processing')

# Check there are no missing category folders for used categories and no extra copied files under classified.
output_files = sorted([p for p in classified_base.rglob('*') if p.is_file()], key=lambda p: p.relative_to(classified_base).as_posix())
if len(output_files) != len(input_files):
    errors.append(f'Classified output file count {len(output_files)} != input file count {len(input_files)}')

print('\nCreated manifest rows:')
for row in manifest_rows:
    print(f"  {row['original_path']} -> {row['new_path']} sha256={row['sha256']}")

print('\nVerification summary:')
print('  manifest exists:', manifest_path.exists())
print('  manifest columns:', ['original_path', 'new_path', 'sha256'])
print('  input file count:', len(input_files))
print('  manifest row count:', len(manifest_rows))
print('  classified copied file count:', len(output_files))
print('  input unchanged:', after_snapshot == input_snapshot)
print('  categories used:', sorted({Path(r['new_path']).parts[2] for r in manifest_rows}))

if errors:
    print('\nERRORS:')
    for e in errors:
        print('  -', e)
    raise SystemExit(1)
print('\nAll checks passed.')