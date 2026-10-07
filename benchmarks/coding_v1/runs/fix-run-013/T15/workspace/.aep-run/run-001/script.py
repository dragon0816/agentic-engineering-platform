from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
input_dir = ws / 'input'
output_dir = ws / 'output'
print('input exists:', input_dir.exists())
print('output exists:', output_dir.exists())
print('input files:', [p.name for p in sorted(input_dir.iterdir())] if input_dir.exists() else [])
log = input_dir / 'test.log'
print('test.log exists:', log.exists())
if log.exists():
    lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
    print('line count:', len(lines))
    for i, line in enumerate(lines[:10], start=1):
        print(f'{i}: {line!r}')
