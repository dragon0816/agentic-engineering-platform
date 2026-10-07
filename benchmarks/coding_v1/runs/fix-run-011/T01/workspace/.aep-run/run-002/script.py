from pathlib import Path
import hashlib

workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / 'combined.md'

if not input_dir.exists() or not input_dir.is_dir():
    raise FileNotFoundError(f'Missing input directory: {input_dir}')

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

# Record input file hashes before writing, to verify inputs are not modified.
all_input_files = [p for p in (workspace / 'input').rglob('*') if p.is_file()]
before_hashes = {str(p.relative_to(workspace)): sha256(p) for p in all_input_files}

selected = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'], key=lambda p: p.name)

parts = []
for i, path in enumerate(selected):
    title = path.stem
    content = path.read_text(encoding='utf-8')
    if i:
        parts.append('\n\n')
    parts.append(f'## {title}\n\n')
    parts.append(content)

output_file.write_text(''.join(parts), encoding='utf-8')

# Verification: reopen output, check exact expected bytes/text and input hashes unchanged.
expected = ''.join(parts)
actual = output_file.read_text(encoding='utf-8')
if actual != expected:
    raise AssertionError('combined.md content does not match expected merged content')

after_hashes = {str(p.relative_to(workspace)): sha256(p) for p in all_input_files}
if before_hashes != after_hashes:
    changed = [k for k in before_hashes if before_hashes[k] != after_hashes.get(k)]
    raise AssertionError(f'Input files changed: {changed}')

# Check selected files only first-level .txt and sorted by filename.
expected_names = [p.name for p in selected]
print('created:', output_file)
print('selected file order:', expected_names)
print('output byte size:', output_file.stat().st_size)
print('input hashes unchanged:', before_hashes == after_hashes)
print('output preview:')
print(actual[:500].replace('\r', '\\r'))