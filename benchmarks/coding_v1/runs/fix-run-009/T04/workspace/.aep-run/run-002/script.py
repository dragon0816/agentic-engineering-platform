from pathlib import Path
import shutil
import hashlib
import csv
import os
import json

workspace = Path.cwd()
input_root = workspace / 'input' / 'files'
output_root = workspace / 'output'
classified_root = output_root / 'classified'
manifest_path = output_root / 'manifest.csv'

if not input_root.exists() or not input_root.is_dir():
    raise FileNotFoundError(f'Missing input directory: {input_root}')

# Snapshot input before any output work, to verify it is not modified.
def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

input_snapshot_before = {}
for p in sorted(input_root.rglob('*'), key=lambda x: str(x.relative_to(input_root)).lower()):
    if p.is_file():
        rel = p.relative_to(input_root).as_posix()
        st = p.stat()
        input_snapshot_before[rel] = {
            'size': st.st_size,
            'sha256': file_digest(p),
        }

category_by_ext = {
    '.pdf': 'PDF',
    '.xls': 'Excel',
    '.xlsx': 'Excel',
    '.png': 'Image',
    '.jpg': 'Image',
    '.jpeg': 'Image',
}

# Prepare output directory. This modifies output only.
classified_root.mkdir(parents=True, exist_ok=True)

rows = []
for src in sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: str(p.relative_to(input_root)).lower()):
    rel_path = src.relative_to(input_root)
    rel_posix = rel_path.as_posix()
    category = category_by_ext.get(src.suffix.lower(), 'Other')
    dst = classified_root / category / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    sha = file_digest(src)
    rows.append({
        'original_path': rel_posix,
        'new_path': dst.relative_to(output_root).as_posix(),
        'sha256': sha,
    })

output_root.mkdir(parents=True, exist_ok=True)
with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

# Verification: reopen manifest and every output file; confirm requirements.
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    read_rows = list(csv.DictReader(f))

errors = []
expected_headers = ['original_path', 'new_path', 'sha256']
if read_rows:
    # DictReader fieldnames checked separately; empty manifests still have headers.
    pass
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    actual_headers = next(reader, None)
if actual_headers != expected_headers:
    errors.append(f'manifest headers mismatch: {actual_headers}')
if len(read_rows) != len(rows):
    errors.append(f'manifest row count {len(read_rows)} != expected {len(rows)}')

expected_by_original = {r['original_path']: r for r in rows}
seen = set()
for r in read_rows:
    orig = r.get('original_path', '')
    new = r.get('new_path', '')
    sha = r.get('sha256', '')
    seen.add(orig)
    if orig not in input_snapshot_before:
        errors.append(f'unknown original_path in manifest: {orig}')
        continue
    suffix = Path(orig).suffix.lower()
    expected_category = category_by_ext.get(suffix, 'Other')
    expected_new = (Path('classified') / expected_category / Path(orig)).as_posix()
    if new != expected_new:
        errors.append(f'new_path mismatch for {orig}: {new} != {expected_new}')
    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        errors.append(f'invalid sha256 format for {orig}: {sha}')
    if sha != input_snapshot_before[orig]['sha256']:
        errors.append(f'sha256 mismatch against source for {orig}')
    out_file = output_root / Path(new)
    if not out_file.exists() or not out_file.is_file():
        errors.append(f'output file missing: {new}')
    else:
        out_sha = file_digest(out_file)
        if out_sha != sha:
            errors.append(f'output sha mismatch for {new}: {out_sha} != {sha}')

missing = set(input_snapshot_before) - seen
if missing:
    errors.append('missing manifest originals: ' + ', '.join(sorted(missing)))

# Confirm input unchanged by file list, sizes, and hashes.
input_snapshot_after = {}
for p in sorted(input_root.rglob('*'), key=lambda x: str(x.relative_to(input_root)).lower()):
    if p.is_file():
        rel = p.relative_to(input_root).as_posix()
        st = p.stat()
        input_snapshot_after[rel] = {
            'size': st.st_size,
            'sha256': file_digest(p),
        }
if input_snapshot_after != input_snapshot_before:
    errors.append('input snapshot changed')

# Count output files by category.
category_counts = {}
for category in ['PDF', 'Excel', 'Image', 'Other']:
    category_dir = classified_root / category
    category_counts[category] = len([p for p in category_dir.rglob('*') if p.is_file()]) if category_dir.exists() else 0

print('processed_files:', len(rows))
print('manifest:', manifest_path.relative_to(workspace).as_posix())
print('classified_root:', classified_root.relative_to(workspace).as_posix())
print('category_counts:', json.dumps(category_counts, ensure_ascii=False, sort_keys=True))
print('manifest_rows:')
for r in read_rows:
    print(f"{r['original_path']} -> {r['new_path']} sha256={r['sha256']}")

if errors:
    print('VERIFICATION_ERRORS:')
    for e in errors:
        print('-', e)
    raise SystemExit(1)
print('verification: OK - manifest headers/rows, category paths, copied file SHA-256, and input unchanged were checked')