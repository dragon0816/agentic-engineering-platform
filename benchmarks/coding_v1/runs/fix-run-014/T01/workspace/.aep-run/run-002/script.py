from pathlib import Path
import hashlib

workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / 'combined.md'

if not input_dir.exists() or not input_dir.is_dir():
    raise SystemExit(f'Missing input directory: {input_dir}')

# Capture input file state before writing, to confirm originals are untouched.
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

input_files_all = [p for p in input_dir.iterdir() if p.is_file()]
before_hashes = {str(p.relative_to(workspace)): sha256(p) for p in input_files_all}

# Only first-level files whose extension is exactly .txt, sorted by file name.
txt_files = sorted(
    [p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

parts = []
for idx, path in enumerate(txt_files):
    content = path.read_text(encoding='utf-8')
    section = f'## {path.stem}\n\n' + content
    parts.append(section)

# Separate file sections cleanly without changing each file's internal content.
combined = ''
for idx, section in enumerate(parts):
    combined += section
    if idx != len(parts) - 1:
        if not combined.endswith('\n'):
            combined += '\n'
        combined += '\n'

output_file.write_text(combined, encoding='utf-8', newline='')

# Verification: reopen output and confirm exact generated structure and selection rules.
read_back = output_file.read_text(encoding='utf-8')
if read_back != combined:
    raise AssertionError('combined.md content changed after saving/reopening')

# Confirm no input file was modified.
after_hashes = {str(p.relative_to(workspace)): sha256(p) for p in input_files_all}
if before_hashes != after_hashes:
    raise AssertionError('An input file hash changed')

# Confirm ignored files/folders are not represented by headings.
headings = [line[3:] for line in read_back.splitlines() if line.startswith('## ')]
expected_headings = [p.stem for p in txt_files]
if headings != expected_headings:
    raise AssertionError(f'Headings/order mismatch: {headings!r} != {expected_headings!r}')
if 'ignore' in headings or 'nested' in headings:
    raise AssertionError('Ignored CSV file or nested folder appeared as a heading')

# Confirm each selected file's raw content appears immediately after its heading.
expected = ''
for idx, path in enumerate(txt_files):
    section = f'## {path.stem}\n\n' + path.read_text(encoding='utf-8')
    expected += section
    if idx != len(txt_files) - 1:
        if not expected.endswith('\n'):
            expected += '\n'
        expected += '\n'
if read_back != expected:
    raise AssertionError('Output does not match expected concatenation')

print('Wrote:', output_file)
print('Selected files:', [p.name for p in txt_files])
print('Output bytes:', output_file.stat().st_size)
print('Headings:', headings)
print('Verified: output reopened, selected first-level .txt only, sorted by filename, headings use stems, source content preserved, input file hashes unchanged.')
