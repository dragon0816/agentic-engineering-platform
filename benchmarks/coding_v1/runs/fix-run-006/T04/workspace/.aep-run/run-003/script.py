from pathlib import Path
import shutil, hashlib, csv, json

workspace = Path.cwd()
input_dir = workspace / 'input' / 'files'
output_dir = workspace / 'output'
classified_dir = output_dir / 'classified'
manifest_path = output_dir / 'manifest.csv'

if not input_dir.exists():
    raise SystemExit(f'Missing input directory: {input_dir}')

def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

input_files = sorted([p for p in input_dir.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_dir).as_posix())
before = {p.relative_to(input_dir).as_posix(): {'size': p.stat().st_size, 'sha256': file_sha256(p)} for p in input_files}

# Clean and recreate the requested output tree only. Input is never modified.
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
    ext = path.suffix.lower()
    for category, exts in category_exts.items():
        if ext in exts:
            return category
    return 'Other'

rows = []
for src in input_files:
    rel = src.relative_to(input_dir)
    category = category_for(src)
    dst = classified_dir / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    rows.append({
        'original_path': (Path('input') / 'files' / rel).as_posix(),
        'new_path': (Path('output') / 'classified' / category / rel).as_posix(),
        'sha256': file_sha256(src),
    })

with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

# Reopen all outputs and verify requirements.
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames or []
    manifest_rows = list(reader)

errors = []
if headers != ['original_path', 'new_path', 'sha256']:
    errors.append(f'manifest headers {headers} != [original_path, new_path, sha256]')
if len(manifest_rows) != len(input_files):
    errors.append(f'manifest row count {len(manifest_rows)} != input file count {len(input_files)}')

expected_originals = {(Path('input') / 'files' / p.relative_to(input_dir)).as_posix() for p in input_files}
seen_originals = set()

for r in manifest_rows:
    original_path = r.get('original_path', '')
    new_path = r.get('new_path', '')
    sha = r.get('sha256', '')
    seen_originals.add(original_path)
    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        errors.append(f'invalid sha256 for {original_path}: {sha}')
    if not original_path.startswith('input/files/'):
        errors.append(f'bad original_path prefix: {original_path}')
        continue
    rel = Path(original_path).relative_to(Path('input') / 'files')
    expected_category = category_for(rel)
    expected_new = (Path('output') / 'classified' / expected_category / rel).as_posix()
    if new_path != expected_new:
        errors.append(f'wrong new_path for {original_path}: {new_path} != {expected_new}')
    src_abs = workspace / original_path
    dst_abs = workspace / new_path
    if not src_abs.exists():
        errors.append(f'missing source unexpectedly: {original_path}')
    if not dst_abs.exists():
        errors.append(f'missing copied file: {new_path}')
    else:
        if file_sha256(dst_abs) != sha:
            errors.append(f'copied SHA-256 mismatch: {new_path}')
    if src_abs.exists() and file_sha256(src_abs) != sha:
        errors.append(f'source SHA-256 mismatch: {original_path}')

if seen_originals != expected_originals:
    errors.append(f'manifest original paths do not match input files: missing={sorted(expected_originals-seen_originals)}, extra={sorted(seen_originals-expected_originals)}')

current_files = sorted([p for p in input_dir.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_dir).as_posix())
after = {p.relative_to(input_dir).as_posix(): {'size': p.stat().st_size, 'sha256': file_sha256(p)} for p in current_files}
if before != after:
    errors.append('input files changed')

expected_counts = {'PDF': 0, 'Excel': 0, 'Image': 0, 'Other': 0}
for p in input_files:
    expected_counts[category_for(p)] += 1
actual_counts = {}
for category in ['PDF', 'Excel', 'Image', 'Other']:
    d = classified_dir / category
    actual_counts[category] = len([p for p in d.rglob('*') if p.is_file()]) if d.exists() else 0
    if actual_counts[category] != expected_counts[category]:
        errors.append(f'{category} count {actual_counts[category]} != expected {expected_counts[category]}')

print('created:', classified_dir.relative_to(workspace))
print('created:', manifest_path.relative_to(workspace))
print('input file count:', len(input_files))
print('manifest row count:', len(manifest_rows))
print('category counts:', json.dumps(actual_counts, sort_keys=True))
print('manifest rows:')
for r in manifest_rows:
    print(r)

if errors:
    print('VERIFICATION FAILED')
    for e in errors:
        print('ERROR:', e)
    raise SystemExit(1)
print('VERIFICATION PASSED: reopened manifest.csv and copied files; checked headers, row count, source/new paths, case-insensitive classification, preserved relative paths, SHA-256 values, category counts, and unchanged input files.')