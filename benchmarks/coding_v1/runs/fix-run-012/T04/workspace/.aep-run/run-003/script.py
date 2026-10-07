from pathlib import Path
import csv
import hashlib

workspace = Path.cwd()
input_root = workspace / 'input' / 'files'
output_root = workspace / 'output'
classified_root = output_root / 'classified'
manifest_path = output_root / 'manifest.csv'

categories = {
    '.pdf': 'PDF',
    '.xls': 'Excel',
    '.xlsx': 'Excel',
    '.png': 'Image',
    '.jpg': 'Image',
    '.jpeg': 'Image',
}

def category_for(path: Path) -> str:
    return categories.get(path.suffix.lower(), 'Other')

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

input_files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: str(p.relative_to(input_root)).lower())
assert manifest_path.exists(), 'manifest.csv missing'
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

assert reader.fieldnames == ['original_path', 'new_path', 'sha256'], f'bad header: {reader.fieldnames}'
assert len(rows) == len(input_files), f'row count {len(rows)} != input files {len(input_files)}'
seen_originals = set()
for row in rows:
    assert set(row) == {'original_path', 'new_path', 'sha256'}
    src = workspace / row['original_path']
    dst = workspace / row['new_path']
    assert src.exists() and src.is_file(), f'missing source listed: {src}'
    assert dst.exists() and dst.is_file(), f'missing destination listed: {dst}'
    assert src.is_relative_to(input_root), f'source outside input/files: {src}'
    assert dst.is_relative_to(classified_root), f'destination outside output/classified: {dst}'
    rel = src.relative_to(input_root)
    expected_dst = classified_root / category_for(src) / rel
    assert dst == expected_dst, f'wrong classified path for {src}: {dst} != {expected_dst}'
    src_hash = sha256_file(src)
    dst_hash = sha256_file(dst)
    assert row['sha256'] == src_hash, f'bad manifest hash for {src}'
    assert dst_hash == src_hash, f'copied content hash mismatch for {src}'
    seen_originals.add(row['original_path'])

expected_originals = {str(p.relative_to(workspace)) for p in input_files}
assert seen_originals == expected_originals, 'manifest originals do not match all input files'

print('CHECK OK')
print('input_file_count:', len(input_files))
print('manifest_rows:', len(rows))
print('manifest_columns:', reader.fieldnames)
print('classified_files:')
for p in sorted(classified_root.rglob('*')):
    if p.is_file():
        print(str(p.relative_to(workspace)), p.stat().st_size)