from pathlib import Path
import shutil, hashlib, csv, os, json

workspace = Path.cwd()
input_dir = workspace / 'input' / 'files'
output_dir = workspace / 'output'
classified_dir = output_dir / 'classified'
manifest_path = output_dir / 'manifest.csv'

if not input_dir.exists():
    raise SystemExit(f'Missing input directory: {input_dir}')

# Snapshot input metadata before copying, so we can confirm inputs were not modified.
def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

input_files = sorted([p for p in input_dir.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_dir).as_posix())
before = {p.relative_to(input_dir).as_posix(): {'size': p.stat().st_size, 'sha256': file_sha256(p)} for p in input_files}

# Recreate only our output targets; never touch input.
if classified_dir.exists():
    shutil.rmtree(classified_dir)
classified_dir.mkdir(parents=True, exist_ok=True)
output_dir.mkdir(parents=True, exist_ok=True)

category_exts = {
    'PDF': {'.pdf'},
    'Excel': {'.xls', '.xlsx'},
    'Image': {'.png', '.jpg', '.jpeg'},
}

def category_for(path: Path) -> str:
    suffix = path.suffix.lower()
    for category, exts in category_exts.items():
        if suffix in exts:
            return category
    return 'Other'

rows = []
for src in input_files:
    rel = src.relative_to(input_dir)
    category = category_for(src)
    dst = classified_dir / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    sha = file_sha256(src)
    rows.append({
        'original_path': (Path('input') / 'files' / rel).as_posix(),
        'new_path': (Path('output') / 'classified' / category / rel).as_posix(),
        'sha256': sha,
    })

with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

# Verification: reopen manifest and every output file, check classification, rel paths, hashes, row counts,
# and that input metadata is unchanged.
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    manifest_rows = list(csv.DictReader(f))

errors = []
if len(manifest_rows) != len(input_files):
    errors.append(f'manifest row count {len(manifest_rows)} != input file count {len(input_files)}')
if list(manifest_rows[0].keys()) if manifest_rows else [] != ['original_path', 'new_path', 'sha256']:
    errors.append('manifest headers are not original_path,new_path,sha256')

seen_originals = set()
seen_new = set()
for r in manifest_rows:
    original_path = r['original_path']
    new_path = r['new_path']
    sha = r['sha256']
    seen_originals.add(original_path)
    seen_new.add(new_path)
    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        errors.append(f'invalid sha256 value for {original_path}: {sha}')
    if not original_path.startswith('input/files/'):
        errors.append(f'original_path is not under input/files: {original_path}')
        continue
    rel = Path(original_path).relative_to(Path('input') / 'files')
    expected_category = category_for(rel)
    expected_new = (Path('output') / 'classified' / expected_category / rel).as_posix()
    if new_path != expected_new:
        errors.append(f'wrong new_path for {original_path}: {new_path} != {expected_new}')
    src_abs = workspace / original_path
    dst_abs = workspace / new_path
    if not dst_abs.exists():
        errors.append(f'missing copied file: {new_path}')
    else:
        dst_sha = file_sha256(dst_abs)
        if dst_sha != sha:
            errors.append(f'copied file hash mismatch for {new_path}')
    if src_abs.exists() and file_sha256(src_abs) != sha:
        errors.append(f'source hash mismatch for {original_path}')

expected_originals = {(Path('input') / 'files' / p.relative_to(input_dir)).as_posix() for p in input_files}
if seen_originals != expected_originals:
    errors.append('manifest original_path set does not match input files')

# Check input unchanged
current_files = sorted([p for p in input_dir.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_dir).as_posix())
after = {p.relative_to(input_dir).as_posix(): {'size': p.stat().st_size, 'sha256': file_sha256(p)} for p in current_files}
if before != after:
    errors.append('input files changed during processing')

# Check expected category counts
counts = {'PDF': 0, 'Excel': 0, 'Image': 0, 'Other': 0}
for p in input_files:
    counts[category_for(p)] += 1
output_counts = {}
for category in ['PDF', 'Excel', 'Image', 'Other']:
    cat_dir = classified_dir / category
    output_counts[category] = len([p for p in cat_dir.rglob('*') if p.is_file()]) if cat_dir.exists() else 0
    if output_counts[category] != counts[category]:
        errors.append(f'{category} output count {output_counts[category]} != expected {counts[category]}')

print('created:', classified_dir.relative_to(workspace))
print('created:', manifest_path.relative_to(workspace))
print('input file count:', len(input_files))
print('manifest row count:', len(manifest_rows))
print('category counts:', json.dumps(counts, ensure_ascii=False, sort_keys=True))
print('output category counts:', json.dumps(output_counts, ensure_ascii=False, sort_keys=True))
print('manifest rows:')
for r in manifest_rows:
    print(r)

if errors:
    print('VERIFICATION FAILED')
    for e in errors:
        print('ERROR:', e)
    raise SystemExit(1)
print('VERIFICATION PASSED: manifest headers, row count, copied file paths, SHA-256 values, category counts, preserved relative paths, and unchanged input files checked.')