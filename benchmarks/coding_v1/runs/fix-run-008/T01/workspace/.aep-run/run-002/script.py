from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
outfile = output_dir / 'combined.md'

# Select only first-level regular files with lowercase .txt suffix, sorted by filename.
txt_files = sorted(
    [p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

parts = []
for idx, path in enumerate(txt_files):
    content = path.read_text(encoding='utf-8')
    if idx > 0:
        parts.append('\n\n')
    parts.append(f'## {path.stem}\n\n')
    parts.append(content)

outfile.write_text(''.join(parts), encoding='utf-8', newline='')

print(f'Wrote: {outfile}')
print('Merged files in order:')
for p in txt_files:
    print(f'- {p.name}')
print(f'Output size: {outfile.stat().st_size} bytes')

# Verification: reopen output and confirm requirements.
actual = outfile.read_text(encoding='utf-8')
expected_parts = []
for idx, path in enumerate(txt_files):
    content = path.read_text(encoding='utf-8')
    if idx > 0:
        expected_parts.append('\n\n')
    expected_parts.append(f'## {path.stem}\n\n')
    expected_parts.append(content)
expected = ''.join(expected_parts)

assert actual == expected, 'combined.md content does not match expected merge output'
assert outfile.name == 'combined.md', 'Output filename is not combined.md'
ignored = [p.name for p in input_dir.iterdir() if not (p.is_file() and p.suffix == '.txt')]
print('Verification passed:')
print(f'- output file name: {outfile.name}')
print(f'- first-level .txt file count: {len(txt_files)}')
print(f'- headings: {[p.stem for p in txt_files]}')
print(f'- ignored entries: {ignored}')
print('- output content exactly matches sorted first-level .txt merge with original file contents preserved')
