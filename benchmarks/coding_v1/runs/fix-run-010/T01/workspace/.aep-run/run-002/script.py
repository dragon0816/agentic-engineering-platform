from pathlib import Path
import hashlib

workspace = Path.cwd()
input_dir = workspace / 'input'
texts_dir = input_dir / 'texts'
output_dir = workspace / 'output'
outfile = output_dir / 'combined.md'

print(f'workspace={workspace}')
print(f'input_dir={input_dir}')
print(f'texts_dir={texts_dir}')
print(f'output_dir={output_dir}')

if not texts_dir.is_dir():
    raise FileNotFoundError(f'Input directory not found: {texts_dir}')

# Record input hashes before work to confirm they are not modified.
before_hashes = {}
for p in sorted(input_dir.rglob('*')):
    if p.is_file():
        before_hashes[str(p.relative_to(input_dir))] = hashlib.sha256(p.read_bytes()).hexdigest()

all_entries = sorted(texts_dir.iterdir(), key=lambda p: p.name)
txt_files = [p for p in all_entries if p.is_file() and p.suffix == '.txt']
print('All first-level entries under input/texts:')
for p in all_entries:
    print(f"- {'DIR' if p.is_dir() else 'FILE'} {p.name}")
print('Files selected for merge:')
for p in txt_files:
    print(f'- {p.name}')

output_dir.mkdir(parents=True, exist_ok=True)
parts = []
for idx, p in enumerate(txt_files):
    content = p.read_text(encoding='utf-8')
    section = f'## {p.stem}\n\n' + content
    parts.append(section)
combined = '\n\n'.join(parts)
outfile.write_text(combined, encoding='utf-8')
print(f'Wrote {outfile}')

# Verification: reopen output and confirm exact expected content, headings, order,
# selected file set, ignored files, and input hashes unchanged.
actual = outfile.read_text(encoding='utf-8')
expected_parts = []
for p in txt_files:
    expected_parts.append(f'## {p.stem}\n\n' + p.read_text(encoding='utf-8'))
expected = '\n\n'.join(expected_parts)

checks = []
checks.append(('output file exists', outfile.is_file()))
checks.append(('output content equals expected merged content', actual == expected))
checks.append(('selected only first-level .txt files', [p.name for p in txt_files] == ['a.txt', 'b.txt', 'empty.txt']))
checks.append(('headings/order are by filename stem', [line for line in actual.splitlines() if line.startswith('## ')] == ['## a', '## b', '## empty']))
checks.append(('ignored non-.txt and subfolder entries', 'ignore.csv' not in [p.name for p in txt_files] and 'nested' not in [p.name for p in txt_files]))

after_hashes = {}
for p in sorted(input_dir.rglob('*')):
    if p.is_file():
        after_hashes[str(p.relative_to(input_dir))] = hashlib.sha256(p.read_bytes()).hexdigest()
checks.append(('input file set and contents unchanged', before_hashes == after_hashes))

print('Verification:')
failed = []
for name, ok in checks:
    print(f"- {name}: {'OK' if ok else 'FAIL'}")
    if not ok:
        failed.append(name)
print(f'output bytes={outfile.stat().st_size}')
print('Output preview:')
print(actual[:500].replace('\r', '\\r'))
if failed:
    raise AssertionError('Failed checks: ' + ', '.join(failed))
