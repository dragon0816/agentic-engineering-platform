from pathlib import Path

workspace = Path.cwd()
input_texts = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_file = output_dir / 'combined.md'

output_dir.mkdir(parents=True, exist_ok=True)

# Only first-level files whose suffix is exactly .txt, sorted by file name.
txt_files = sorted(
    [p for p in input_texts.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

parts = []
for idx, path in enumerate(txt_files):
    content = path.read_text(encoding='utf-8')
    if idx > 0:
        parts.append('\n')
    parts.append(f'## {path.stem}\n\n')
    parts.append(content)
    # Put a section separator only when the original file did not already end with a newline.
    # This keeps each file's own content unchanged while preventing the next heading from
    # being appended to the same line.
    if idx < len(txt_files) - 1 and content and not content.endswith('\n'):
        parts.append('\n')

output_file.write_text(''.join(parts), encoding='utf-8', newline='')
print(f'wrote: {output_file}')
print(f'input files included: {[p.name for p in txt_files]}')

# Verification from saved output.
saved = output_file.read_text(encoding='utf-8')
expected_parts = []
for idx, path in enumerate(txt_files):
    content = path.read_text(encoding='utf-8')
    if idx > 0:
        expected_parts.append('\n')
    expected_parts.append(f'## {path.stem}\n\n')
    expected_parts.append(content)
    if idx < len(txt_files) - 1 and content and not content.endswith('\n'):
        expected_parts.append('\n')
expected = ''.join(expected_parts)

checks = []
checks.append(('output file exists', output_file.exists()))
checks.append(('saved content exactly matches expected merge', saved == expected))
checks.append(('only first-level .txt files included in sorted order', [p.name for p in txt_files] == ['a.txt', 'b.txt', 'empty.txt']))
checks.append(('headings present in order', [line for line in saved.splitlines() if line.startswith('## ')] == [f'## {p.stem}' for p in txt_files]))
checks.append(('ignored non-txt and nested content', 'ignore' not in [p.name for p in txt_files] and all(p.parent == input_texts for p in txt_files)))

for name, ok in checks:
    print(f'CHECK {name}: {ok}')

if not all(ok for _, ok in checks):
    raise SystemExit('verification failed')
print('verification succeeded')
