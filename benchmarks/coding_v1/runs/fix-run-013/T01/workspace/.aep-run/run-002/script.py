from pathlib import Path

workspace = Path.cwd()
input_texts = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_file = output_dir / 'combined.md'

output_dir.mkdir(parents=True, exist_ok=True)

# Collect only first-level .txt files, sorted by filename.
txt_files = sorted(
    [p for p in input_texts.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

parts = []
for i, path in enumerate(txt_files):
    if i > 0:
        # Separator between sections. This does not alter the copied file content;
        # it only ensures the next Markdown heading starts on a new paragraph.
        parts.append(b'\n\n')
    heading = f'## {path.stem}\n\n'.encode('utf-8')
    parts.append(heading)
    parts.append(path.read_bytes())

output_file.write_bytes(b''.join(parts))

# Verification: reopen output and verify stated requirements.
out = output_file.read_bytes()
expected = b''
for i, path in enumerate(txt_files):
    if i > 0:
        expected += b'\n\n'
    expected += f'## {path.stem}\n\n'.encode('utf-8') + path.read_bytes()

checks = []
checks.append(('output file exists', output_file.exists()))
checks.append(('output filename is combined.md', output_file.name == 'combined.md'))
checks.append(('output is under output folder', output_file.parent.resolve() == output_dir.resolve()))
checks.append(('included first-level txt files sorted by filename', [p.name for p in txt_files] == sorted([p.name for p in input_texts.iterdir() if p.is_file() and p.suffix == '.txt'])))
checks.append(('ignored non-.txt file ignore.csv', not any(b'ignore.csv' in chunk for chunk in parts)))
checks.append(('ignored nested directory contents by selecting only files in first level', all(p.parent == input_texts and p.is_file() for p in txt_files)))
checks.append(('output bytes exactly match headings plus original file bytes', out == expected))
for path in txt_files:
    checks.append((f'has level-2 heading for {path.name}', f'## {path.stem}\n\n'.encode('utf-8') in out))
    checks.append((f'preserved original bytes for {path.name}', path.read_bytes() in out))

print('Combined files:', [p.name for p in txt_files])
print('Output:', output_file)
print('Output size bytes:', output_file.stat().st_size)
print('Verification:')
failed = False
for name, ok in checks:
    print(f'- {name}: {ok}')
    if not ok:
        failed = True
if failed:
    raise SystemExit('Verification failed')
