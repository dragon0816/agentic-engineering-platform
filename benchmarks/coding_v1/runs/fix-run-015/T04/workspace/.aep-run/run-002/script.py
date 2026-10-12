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
    raise FileNotFoundError(f'Missing input directory: {input_root}')

# Capture input file metadata before work to confirm we do not modify input.
before_meta = {}
for p in sorted(input_root.rglob('*')):
    if p.is_file():
        st = p.stat()
        before_meta[str(p.relative_to(input_root))] = (st.st_size, st.st_mtime_ns)

category_by_ext = {
    '.pdf': 'PDF',
    '.xls': 'Excel',
    '.xlsx': 'Excel',
    '.png': 'Image',
    '.jpg': 'Image',
    '.jpeg': 'Image',
}

def category_for(path: Path) -> str:
    return category_by_ext.get(path.suffix.lower(), 'Other')

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

output_root.mkdir(parents=True, exist_ok=True)
classified_root.mkdir(parents=True, exist_ok=True)

rows = []
files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: str(p.relative_to(input_root)).lower())
for src in files:
    rel = src.relative_to(input_root)
    category = category_for(src)
    dst = classified_root / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    digest = sha256_file(src)
    rows.append({
        'original_path': str(src.relative_to(workspace)).replace(os.sep, '/'),
        'new_path': str(dst.relative_to(workspace)).replace(os.sep, '/'),
        'sha256': digest,
    })

with manifest_path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['original_path', 'new_path', 'sha256'])
    writer.writeheader()
    writer.writerows(rows)

# Verification: reopen manifest and all copied files, confirm requirements.
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    manifest_rows = list(reader)
    manifest_fields = reader.fieldnames

assert manifest_fields == ['original_path', 'new_path', 'sha256'], f'Unexpected manifest fields: {manifest_fields}'
assert len(manifest_rows) == len(files), f'Manifest row count {len(manifest_rows)} != input file count {len(files)}'

seen_originals = set()
seen_new = set()
category_counts = {'PDF': 0, 'Excel': 0, 'Image': 0, 'Other': 0}
for row in manifest_rows:
    orig_rel_workspace = Path(row['original_path'])
    new_rel_workspace = Path(row['new_path'])
    src = workspace / orig_rel_workspace
    dst = workspace / new_rel_workspace
    assert src.is_file(), f'Manifest original missing: {src}'
    assert dst.is_file(), f'Manifest new file missing: {dst}'
    assert row['sha256'] == sha256_file(src), f'SHA mismatch for source {src}'
    assert row['sha256'] == sha256_file(dst), f'SHA mismatch for copied file {dst}'
    rel_under_input = src.relative_to(input_root)
    expected_category = category_for(src)
    expected_dst = classified_root / expected_category / rel_under_input
    assert dst == expected_dst, f'Unexpected destination for {src}: {dst} != {expected_dst}'
    assert new_rel_workspace.parts[0] == 'output' and new_rel_workspace.parts[1] == 'classified', f'New path outside output/classified: {new_rel_workspace}'
    category_counts[expected_category] += 1
    seen_originals.add(row['original_path'])
    seen_new.add(row['new_path'])

assert len(seen_originals) == len(files), 'Duplicate original_path in manifest'
assert len(seen_new) == len(files), 'Duplicate new_path in manifest'

# Verify input file set, size and mtime unchanged.
after_meta = {}
for p in sorted(input_root.rglob('*')):
    if p.is_file():
        st = p.stat()
        after_meta[str(p.relative_to(input_root))] = (st.st_size, st.st_mtime_ns)
assert before_meta == after_meta, 'Input file metadata changed'

print('Created:', classified_root.relative_to(workspace))
print('Created:', manifest_path.relative_to(workspace))
print('Input files processed:', len(files))
print('Manifest rows verified:', len(manifest_rows))
print('Category counts:', category_counts)
print('Manifest preview:')
for row in manifest_rows:
    print(row)
print('Verified: classification is case-insensitive; Excel includes xls/xlsx; Image includes png/jpg/jpeg; original relative paths are preserved under each category; SHA-256 matches source and copied files; input file metadata unchanged.')
