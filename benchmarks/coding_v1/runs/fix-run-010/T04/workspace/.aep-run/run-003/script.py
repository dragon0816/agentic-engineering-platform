from pathlib import Path
import csv
import hashlib
import os

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
expected_headers = ['original_path', 'new_path', 'sha256']

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def relstr(path: Path) -> str:
    return str(path)

source_files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_root).as_posix().lower())
assert manifest_path.exists(), 'manifest.csv missing'

with manifest_path.open('r', newline='', encoding='utf-utf-8-sig'.replace('utf-utf','utf')) as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames
    rows = list(reader)

assert headers == expected_headers, f'headers mismatch: {headers}'
assert len(rows) == len(source_files), f'row count mismatch: manifest {len(rows)} vs input {len(source_files)}'

seen_originals = set()
seen_new = set()
for row in rows:
    assert set(row.keys()) == set(expected_headers), f'row keys mismatch: {row.keys()}'
    original_rel = Path(row['original_path'])
    new_rel = Path(row['new_path'])
    assert str(original_rel).startswith(str(Path('input') / 'files')), f'bad original path: {original_rel}'
    assert str(new_rel).startswith(str(Path('output') / 'classified')), f'bad new path: {new_rel}'
    src = workspace / original_rel
    dst = workspace / new_rel
    assert src.exists() and src.is_file(), f'original missing: {src}'
    assert dst.exists() and dst.is_file(), f'copy missing: {dst}'
    rel = src.relative_to(input_root)
    expected_category = categories.get(src.suffix.lower(), 'Other')
    expected_new_rel = Path('output') / 'classified' / expected_category / rel
    assert new_rel == expected_new_rel, f'new path mismatch for {src}: {new_rel} != {expected_new_rel}'
    digest = sha256_file(src)
    assert row['sha256'] == digest, f'sha256 mismatch for {src}'
    assert len(row['sha256']) == 64 and all(c in '0123456789abcdef' for c in row['sha256']), f'bad sha256 format: {row["sha256"]}'
    assert sha256_file(dst) == digest, f'copied file content differs: {dst}'
    seen_originals.add(str(original_rel))
    seen_new.add(str(new_rel))

expected_originals = {str(Path('input') / 'files' / p.relative_to(input_root)) for p in source_files}
assert seen_originals == expected_originals, 'manifest originals do not match all input files'

output_files = sorted([p for p in classified_root.rglob('*') if p.is_file()])
assert len(output_files) == len(source_files), f'classified file count mismatch: {len(output_files)} vs {len(source_files)}'
assert {str(p.relative_to(workspace)) for p in output_files} == seen_new, 'classified files do not match manifest new paths'

category_counts = {}
for category in ['PDF', 'Excel', 'Image', 'Other']:
    cat_dir = classified_root / category
    assert cat_dir.exists() and cat_dir.is_dir(), f'category folder missing: {category}'
    category_counts[category] = sum(1 for p in cat_dir.rglob('*') if p.is_file())

# Confirm no unexpected files were created under input by checking source count and paths against initial expectation from disk.
current_input_files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_root).as_posix().lower())
assert [p.relative_to(input_root) for p in current_input_files] == [p.relative_to(input_root) for p in source_files], 'input file list changed during verification'

print('CHECK PASSED')
print('manifest headers:', headers)
print('manifest rows:', len(rows))
print('classified files:', len(output_files))
print('category counts:', category_counts)
print('verified paths:')
for row in rows:
    print(' -', row['original_path'], '=>', row['new_path'], row['sha256'])
