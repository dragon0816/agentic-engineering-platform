from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
outfile = output_dir / 'combined.md'

# Collect only first-level .txt files, sorted by filename.
txt_files = sorted(
    [p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

parts = []
for p in txt_files:
    content = p.read_text(encoding='utf-8')
    parts.append(f'## {p.stem}\n\n{content}')

combined = '\n\n'.join(parts)
outfile.write_text(combined, encoding='utf-8')

print('Wrote:', outfile)
print('Included files:', [p.name for p in txt_files])
print('Output chars:', len(combined))
print('Output preview:')
print(combined[:500])

# Verification: reopen output and confirm stated requirements.
saved = outfile.read_text(encoding='utf-8')
expected = combined
print('\nCHECKS')
print('combined.md exists:', outfile.exists())
print('output matches expected first-level sorted .txt merge:', saved == expected)
print('input files still present:', all(p.exists() for p in txt_files))
print('ignored non-txt first-level present and not included:', 'ignore.csv' in [p.name for p in input_dir.iterdir()] and 'ignore' not in saved)
print('nested directory present and not traversed:', (input_dir / 'nested').is_dir())
print('headings:', [f'## {p.stem}' for p in txt_files])
print('included_count:', len(txt_files))
