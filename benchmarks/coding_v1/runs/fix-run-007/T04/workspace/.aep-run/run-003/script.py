from pathlib import Path
import csv
import hashlib
import filecmp

workspace = Path.cwd()
input_root = workspace / 'input' / 'files'
output_root = workspace / 'output'
manifest_path = output_root / 'manifest.csv'
classified_root = output_root / 'classified'

expected_categories = {
    '.pdf': 'PDF',
    '.xls': 'Excel',
    '.xlsx': 'Excel',
    '.png': 'Image',
    '.jpg': 'Image',
    '.jpeg': 'Image',
}

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

input_files = sorted([p for p in input_root.rglob('*') if p.is_file()], key=lambda p: p.relative_to(input_root).as_posix().lower())
assert manifest_path.exists(), 'manifest.csv missing'
with manifest_path.open('r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    assert reader.fieldnames == ['original_path', 'new_path', 'sha256'], f'bad headers: {reader.fieldnames}'

assert len(rows) == len(input_files), f'row count {len(rows)} != input file count {len(input_files)}'
seen_original = set()
seen_new = set()

for row in rows:
    for col in ['original_path', 'new_path', 'sha256']:
        assert row[col] != '', f'empty {col}'
    assert len(row['sha256']) == 64 and all(c in '0123456789abcdef' for c in row['sha256']), f'bad sha256: {row}'
    src = workspace / row['original_path']
    dst = workspace / row['new_path']
    assert src.exists(), f'source missing: {src}'
    assert dst.exists(), f'destination missing: {dst}'
    assert row['original_path'].startswith('input/files/'), f'original not under input/files: {row}'
    assert row['new_path'].startswith('output/classified/'), f'new not under output/classified: {row}'
    rel_under_files = src.relative_to(input_root)
    category = expected_categories.get(src.suffix.lower(), 'Other')
    expected_dst = classified_root / category / rel_under_files
    assert dst == expected_dst, f'wrong destination: got {dst}, expected {expected_dst}'
    assert row['sha256'] == sha256(src), f'sha mismatch source: {row}'
    assert row['sha256'] == sha256(dst), f'sha mismatch destination: {row}'
    assert filecmp.cmp(src, dst, shallow=False), f'copy content differs: {src} -> {dst}'
    seen_original.add(row['original_path'])
    seen_new.add(row['new_path'])

expected_originals = {p.relative_to(workspace).as_posix() for p in input_files}
assert seen_original == expected_originals, 'manifest originals do not match input files'
assert len(seen_new) == len(rows), 'duplicate new paths in manifest'

classified_files = sorted([p for p in classified_root.rglob('*') if p.is_file()])
assert len(classified_files) == len(input_files), f'classified file count {len(classified_files)} != input file count {len(input_files)}'

counts = {}
for p in classified_files:
    cat = p.relative_to(classified_root).parts[0]
    counts[cat] = counts.get(cat, 0) + 1

print('VALIDATION PASSED')
print('manifest_headers:', ['original_path', 'new_path', 'sha256'])
print('manifest_rows:', len(rows))
print('input_files:', len(input_files))
print('classified_files:', len(classified_files))
print('category_counts:', counts)
print('all_copies_match_sha256_and_content: true')
print('input_files_read_only_not_modified_by_script: true')