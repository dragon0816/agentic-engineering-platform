from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
outfile = output_dir / 'combined.md'

# First-level .txt files only, sorted by file name.
txt_files = sorted(
    [p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

parts = []
for p in txt_files:
    title = p.stem
    content = p.read_text(encoding='utf-8')
    # Keep file content byte-for-text as read; only add markdown title/separators.
    section = f'## {title}\n\n' + content
    parts.append(section)

combined = '\n\n'.join(parts)
outfile.write_text(combined, encoding='utf-8')

# Verification: reopen output and confirm exact expected construction.
actual = outfile.read_text(encoding='utf-8')
expected = '\n\n'.join([f'## {p.stem}\n\n' + p.read_text(encoding='utf-8') for p in txt_files])
print('Input txt files used:', [p.name for p in txt_files])
print('Ignored first-level non-txt/dirs:', [p.name for p in sorted(input_dir.iterdir(), key=lambda x: x.name) if not (p.is_file() and p.suffix == '.txt')])
print('Output file:', outfile)
print('Output chars:', len(actual))
print('Matches expected:', actual == expected)
print('Head preview:', actual[:200].replace('\n', '\\n'))
if actual != expected:
    raise SystemExit('Verification failed: combined.md does not match expected content')
for p in txt_files:
    marker = f'## {p.stem}\n\n'
    if marker not in actual:
        raise SystemExit(f'Missing heading for {p.name}')
print('Verified headings and original content construction for all included .txt files.')
