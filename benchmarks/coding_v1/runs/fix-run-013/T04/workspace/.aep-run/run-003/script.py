from pathlib import Path
import csv
import hashlib

workspace = Path.cwd()
input_dir = workspace / 'input' / 'files'
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

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

source_files = sorted((p for p in input_dir.rglob('*') if p.is_file()), key=lambda p: p.relative_to(input_dir).as_posix().lower())
assert manifest_path.exists(), 'manifest.csv missing'
with manifest_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

assert reader.fieldnames == ['原路徑', '新路徑', 'SHA-256'], f'bad headers: {reader.fieldnames}'
assert len(rows) == len(source_files), f'row count mismatch: manifest {len(rows)} vs source {len(source_files)}'

by_src = {row['原路徑']: row for row in rows}
for src in source_files:
    rel_src_workspace = src.relative_to(workspace).as_posix()
    rel_under_files = src.relative_to(input_dir)
    category = categories.get(src.suffix.lower(), 'Other')
    expected_dst = classified_root / category / rel_under_files
    rel_dst_workspace = expected_dst.relative_to(workspace).as_posix()
    assert rel_src_workspace in by_src, f'missing manifest row for {rel_src_workspace}'
    row = by_src[rel_src_workspace]
    assert row['新路徑'] == rel_dst_workspace, f'wrong destination for {rel_src_workspace}: {row["新路徑"]} != {rel_dst_workspace}'
    assert expected_dst.exists(), f'copied file missing: {expected_dst}'
    assert expected_dst.read_bytes() == src.read_bytes(), f'content mismatch: {expected_dst}'
    expected_hash = sha256_file(src)
    assert row['SHA-256'] == expected_hash, f'hash mismatch for {rel_src_workspace}'
    assert len(row['SHA-256']) == 64 and all(c in '0123456789abcdef' for c in row['SHA-256']), f'bad sha256 format: {row["SHA-256"]}'

# Check no extra files under classified beyond the expected copied files.
expected_outputs = {classified_root / categories.get(src.suffix.lower(), 'Other') / src.relative_to(input_dir) for src in source_files}
actual_outputs = {p for p in classified_root.rglob('*') if p.is_file()}
assert actual_outputs == expected_outputs, f'extra/missing classified outputs: extra={actual_outputs-expected_outputs}, missing={expected_outputs-actual_outputs}'

print('verification_ok')
print('source_file_count:', len(source_files))
print('manifest_row_count:', len(rows))
print('manifest_headers:', reader.fieldnames)
print('classified_files:')
for p in sorted(actual_outputs, key=lambda x: x.relative_to(workspace).as_posix().lower()):
    print(' -', p.relative_to(workspace).as_posix(), 'bytes=', p.stat().st_size)
