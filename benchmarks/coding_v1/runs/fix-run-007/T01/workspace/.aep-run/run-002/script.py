from pathlib import Path

workspace = Path.cwd()
input_texts = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / 'combined.md'

if not input_texts.exists() or not input_texts.is_dir():
    raise FileNotFoundError(f'Missing directory: {input_texts}')

# Only first-level files with exact .txt suffix, sorted by filename.
txt_files = sorted(
    [p for p in input_texts.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

parts = []
for p in txt_files:
    content = p.read_text(encoding='utf-8')
    parts.append(f'## {p.stem}\n\n{content}')

combined = '\n\n'.join(parts)
output_file.write_text(combined, encoding='utf-8')

print('Wrote:', output_file)
print('Included files:', [p.name for p in txt_files])
print('Ignored first-level entries:', [p.name for p in sorted(input_texts.iterdir(), key=lambda x: x.name) if p not in txt_files])
print('Output bytes:', output_file.stat().st_size)

# Verification: reopen output and rebuild expected from source files.
actual = output_file.read_text(encoding='utf-8')
expected_parts = []
for p in txt_files:
    expected_parts.append(f'## {p.stem}\n\n{p.read_text(encoding="utf-8")}')
expected = '\n\n'.join(expected_parts)

checks = []
checks.append(('output file exists with requested name', output_file.exists() and output_file.name == 'combined.md'))
checks.append(('output is in output folder', output_file.parent.resolve() == output_dir.resolve()))
checks.append(('only first-level .txt files included in filename order', [p.name for p in txt_files] == ['a.txt', 'b.txt', 'empty.txt']))
checks.append(('combined.md content exactly matches required headings and original content', actual == expected))
checks.append(('non-.txt and nested entries excluded', 'ignore.csv' not in actual and 'nested' not in actual))

for name, ok in checks:
    print(('PASS' if ok else 'FAIL') + ': ' + name)

if not all(ok for _, ok in checks):
    raise AssertionError('One or more checks failed')
