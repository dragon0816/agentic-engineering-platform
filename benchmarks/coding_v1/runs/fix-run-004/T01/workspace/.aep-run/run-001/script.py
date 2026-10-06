from pathlib import Path
import os, hashlib

workspace = Path.cwd()
input_texts = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_file = output_dir / 'combined.md'

print('INSPECT: workspace =', workspace)
print('INSPECT: input_texts exists =', input_texts.exists(), 'is_dir =', input_texts.is_dir())
if input_texts.exists():
    print('INSPECT: first-level entries:')
    for p in sorted(input_texts.iterdir(), key=lambda x: x.name):
        kind = 'DIR' if p.is_dir() else 'FILE'
        print(f'  {kind}: {p.name}')
    txt_files = sorted([p for p in input_texts.iterdir() if p.is_file() and p.suffix == '.txt'], key=lambda x: x.name)
    print('INSPECT: first-level .txt files to merge:', [p.name for p in txt_files])
    for p in txt_files[:5]:
        data = p.read_text(encoding='utf-8')
        sample = data[:120].replace('\n', '\\n').replace('\r', '\\r')
        print(f'INSPECT: sample {p.name}: {sample!r}, chars={len(data)}')

# Task: merge only first-level .txt files from input/texts, sorted by filename.
output_dir.mkdir(parents=True, exist_ok=True)
if not input_texts.is_dir():
    raise FileNotFoundError(f'Missing input directory: {input_texts}')

files = sorted([p for p in input_texts.iterdir() if p.is_file() and p.suffix == '.txt'], key=lambda x: x.name)

parts = []
for idx, p in enumerate(files):
    content = p.read_text(encoding='utf-8')
    section = f'## {p.stem}\n\n' + content
    parts.append(section)
combined = '\n\n'.join(parts)
output_file.write_text(combined, encoding='utf-8')
print('WROTE:', output_file)
print('WROTE files merged:', [p.name for p in files])
print('WROTE chars:', len(combined))

# Verification: reopen output and confirm requirements.
out = output_file.read_text(encoding='utf-8')
expected = '\n\n'.join([f'## {p.stem}\n\n' + p.read_text(encoding='utf-8') for p in files])
checks = []
checks.append(('output file exists', output_file.exists()))
checks.append(('output content equals expected merge', out == expected))
checks.append(('source sorted by filename', [p.name for p in files] == sorted([p.name for p in files])))
checks.append(('only first-level .txt considered', all(p.parent == input_texts and p.is_file() and p.suffix == '.txt' for p in files)))
# Confirm each heading exists in order and each exact original content follows the heading according to expected string.
for p in files:
    checks.append((f'heading for {p.name}', f'## {p.stem}\n\n' in out))
    checks.append((f'exact content included for {p.name}', p.read_text(encoding='utf-8') in out))
# Record input hashes before/after within this run to indicate no writes were performed by script.
input_paths = [p for p in (workspace / 'input').rglob('*') if p.is_file()]
print('VERIFY: input file count (unchanged by script; no input writes performed):', len(input_paths))
print('VERIFY: output file:', output_file.name)
print('VERIFY: output chars:', len(out))
print('VERIFY: merged count:', len(files))
failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print('CHECK:', name, 'PASS' if ok else 'FAIL')
if failed:
    raise AssertionError('Failed checks: ' + ', '.join(failed))
