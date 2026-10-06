from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
out_path = output_dir / 'combined.md'

# Select only first-level regular files ending exactly with .txt, sorted by filename.
txt_files = sorted(
    [p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

# Build output in bytes so each source file's content bytes are preserved exactly.
parts = []
for idx, p in enumerate(txt_files):
    if idx:
        parts.append(b'\n\n')
    parts.append(f'## {p.stem}\n\n'.encode('utf-8'))
    parts.append(p.read_bytes())

out_path.write_bytes(b''.join(parts))

# Verification: reopen output and compare with independently constructed expected bytes.
actual = out_path.read_bytes()
expected = b''
for idx, p in enumerate(txt_files):
    if idx:
        expected += b'\n\n'
    expected += f'## {p.stem}\n\n'.encode('utf-8')
    expected += p.read_bytes()

print('created:', out_path)
print('selected .txt files:', [p.name for p in txt_files])
print('ignored first-level non-.txt:', [p.name for p in sorted(input_dir.iterdir(), key=lambda x: x.name) if p.is_file() and p.suffix != '.txt'])
print('ignored first-level directories:', [p.name for p in sorted(input_dir.iterdir(), key=lambda x: x.name) if p.is_dir()])
print('output_size_bytes:', len(actual))
print('exact_expected_match:', actual == expected)
if actual != expected:
    raise SystemExit('Verification failed: combined.md does not match expected merge output')

# Additional checks requested by the prompt.
text = actual.decode('utf-8')
headings = [line for line in text.splitlines() if line.startswith('## ')]
print('headings:', headings)
expected_headings = [f'## {p.stem}' for p in txt_files]
print('headings_match_sorted_filenames_without_extension:', headings == expected_headings)
if headings != expected_headings:
    raise SystemExit('Verification failed: headings do not match sorted .txt filenames')

# Check content bytes for each source file appear after its heading in order.
pos = 0
for p in txt_files:
    heading = f'## {p.stem}\n\n'.encode('utf-8')
    hpos = actual.find(heading, pos)
    if hpos < 0:
        raise SystemExit(f'Verification failed: missing heading for {p.name}')
    cstart = hpos + len(heading)
    content = p.read_bytes()
    if actual[cstart:cstart+len(content)] != content:
        raise SystemExit(f'Verification failed: content not preserved for {p.name}')
    pos = cstart + len(content)
print('content_preserved_for_each_txt:', True)
print('input_files_unchanged_by_script: script only read input files and wrote output/combined.md')